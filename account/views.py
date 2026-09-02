from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Exists, OuterRef, Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CustomUserSerializer, UserInteractionSerializer, OrderSerializer, CustomUserDetailSerializer, VoucherSerializer,PointsHistorySerializer, OrderMobileSerializer, BlogSerializer, UserPoints, AdminOrderSerializer
from .models import UserInteraction, AddressBook, Voucher, PointsHistory, Blog
from django.utils.translation import gettext as _
from .models import CustomUser 

from rest_framework import permissions, viewsets, generics
from .models import AddressBook, Order, OrderItem, OrderStatus
from product.models import ProductImage
from .serializers import AddressBookSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from scripts.currency_converter import DEFAULT_CURRENCY
from google.oauth2 import id_token
from google.auth.transport import requests
import logging
from django.utils.dateparse import parse_datetime
from rest_framework import views

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
import datetime
from .tasks import send_verification_code, send_order_confirmation_email, send_reset_password_email
from .order_email_data import build_order_confirmation_email_data
#EMAIL
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from sendgrid.helpers.mail import Mail
from sendgrid import SendGridAPIClient
from backend.settings import DEFAULT_DOMAIN



logger = logging.getLogger(__name__)


def build_password_reset_frontend_url(language, uid, token):
    """SPA reset: https://{DEFAULT_DOMAIN}/{lang}/reset-password/{uid}/{token}/"""
    lang = (language or "en").split("-")[0].lower()
    if lang not in ("en", "de"):
        lang = "en"
    path_segment = f"{lang}/reset-password/{uid}/{token}/"
    host = str(DEFAULT_DOMAIN).strip().rstrip("/")
    scheme = "http" if host.startswith("localhost") or host.startswith("127.") else "https"
    return f"{scheme}://{host}/{path_segment}"


#Premesti ispod negde kada se uveris da radi
class VerifyCodeAPIView(APIView):
    def post(self, request, *args, **kwargs):
        # Pokušaj autentifikacije korisnika pomoću JWT-a
        try:
            jwt_authenticator = JWTAuthentication()
            user, token = jwt_authenticator.authenticate(request)
        except Exception as e:
            raise AuthenticationFailed('Token is invalid or expired')

        # Izvucite verifikacioni kod iz zahteva
        code = request.data.get('code')

        if not code:
            return Response({'error': 'Verification code is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Proverite kod i vreme isteka
        if user.verification_code == code and user.verification_code_expires_at > timezone.now():
            user.is_email_verified = True
            user.is_active = True
            user.verification_code = None  # Resetujte kod nakon uspešne verifikacije
            user.verification_code_expires_at = None
            user.save()
            token_serializer = CustomTokenObtainPairSerializer()
            token_data = token_serializer.get_token(user)

            return Response({
                'refresh': str(token_data),
                'access': str(token_data.access_token),
                'message': 'Email successfully verified!'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': 'Invalid or expired code'}, status=status.HTTP_400_BAD_REQUEST)
        
class ResendVerificationCodeAPIView(APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response({'error': 'Invalid email'}, status=status.HTTP_400_BAD_REQUEST)

        user.verification_code = CustomUser.objects.generate_verification_code()
        user.verification_code_expires_at = timezone.now() + datetime.timedelta(minutes=30)  # Novi kod važi 3 minuta
        user.save()

        language = request.headers.get('Accept-Language', 'en')
        try:
            send_verification_code.delay(user.email, user.verification_code, language)
            pass
        except Exception as e:
            logger.info(f"Error sending email: {e}")

        
        return Response({'message': 'A new verification code has been sent to your email'}, status=status.HTTP_200_OK)

# Create your views here.
class GoogleLogin(APIView):
    def post(self, request):
        token = request.data.get('token')
        CLIENT_ID = settings.GOOGLE_CLIENT_ID

        try:
            idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
            email = idinfo.get('email')
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')

            user, created = CustomUser.objects.get_or_create(email=email, defaults={
                'first_name': first_name,
                'last_name': last_name,
                'domain': DEFAULT_DOMAIN,
            })

            if created:
                user.set_unusable_password()
                user.is_email_verified = True
                user.save()

            #refresh = RefreshToken.for_user(user)
            token_serializer = CustomTokenObtainPairSerializer()
            token_data = token_serializer.get_token(user)

            return Response({
                'refresh': str(token_data),
                'access': str(token_data.access_token),
            }, status=status.HTTP_201_CREATED)

        except ValueError as e:
            logger.info(f"Error verifying token: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
def send_subscribe_confirmation_email(subscriber_email):
    try:
        customer_html_content = render_to_string("success_register.html")
        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=subscriber_email,
            subject='Subscription Confirmation',
            html_content=customer_html_content
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        
        return {"status_code": response.status_code, "body": response.body.decode('utf-8')}
    except Exception as e:
        raise e   
#TODO    napraviti odmah VERIFICATION code i poslati email po registraciji
class RegisterUserAPIView(APIView):
    def post(self, request):
        serializer = CustomUserSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            if user:
                # Kreiranje tokena za novoregistrovanog korisnika
                #refresh = RefreshToken.for_user(user)
                token_serializer = CustomTokenObtainPairSerializer()
                token_data = token_serializer.get_token(user)
                data = {
                    'refresh': str(token_data),
                    'access': str(token_data.access_token),
                }

                # Opcionalno: možete dodati dodatne podatke u odgovor, kao što su korisnički podaci
                data.update(serializer.data)
                try:
                    send_subscribe_confirmation_email(user.email)
                except Exception as e:
                    print(f"Error sending email: {e}")
                return Response(data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            jwt_authenticator = JWTAuthentication()
            user, token = jwt_authenticator.authenticate(request)
        except TokenError:
            raise AuthenticationFailed('Token has expired')

        user = CustomUser.objects.filter(id=request.user.id).prefetch_related(
            Prefetch('addresses'),
            Prefetch('referrals_made'),
            Prefetch('vouchers'),
            Prefetch('user_points'),
        ).get()
        serializer = CustomUserDetailSerializer(user, context={'currency': request.headers.get('Currency', DEFAULT_CURRENCY)})
        return Response(serializer.data)

class UpdateUserInfoAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        phone_number = request.data.get('phone_number')

        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if phone_number:
            user.phone_number = phone_number

        user.save()
        return Response({'message': 'User information updated successfully.'}, status=200)
class CreateAddressAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logger.info("Received data for address creation: %s", request.data)
        # Proverite koliko adresa trenutno ima korisnik
        user_addresses_count = AddressBook.objects.filter(user=request.user).count()

        # Ako korisnik već ima 5 adresa, vratite odgovor koji to navodi
        if user_addresses_count >= 5:
            return Response({'error': 'You cannot have more than 5 addresses.'}, status=status.HTTP_400_BAD_REQUEST)

        address_data = request.data.copy()

        if user_addresses_count == 0:
            address_data['is_primary'] = True
        
        # Proverite i ažurirajte korisnikov `phone_number` ako je prazan
        phone_number = address_data.get('phone_number')
        if phone_number and not request.user.phone_number:
            request.user.phone_number = phone_number
            request.user.save()  # Sačuvajte ažurirani broj telefona za korisnika

        serializer = AddressBookSerializer(data=address_data, context={'request': request})
        if serializer.is_valid():
            serializer.save()  # request.user će biti automatski obrađen unutar serializer-a
            return Response(serializer.data, status=status.HTTP_201_CREATED)  # Vraća kreiranu adresu
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        
class UpdateAddressAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, address_id):
        try:
            # Pronađite adresu po ID-u unutar korisnikovih adresa
            address = AddressBook.objects.get(id=address_id, user=request.user)
        except AddressBook.DoesNotExist:
            return Response({'error': 'Address not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ažuriranje adrese sa novim podacima bez polja phone_number
        address_data = request.data.copy()
        logger.info("Received address data: %s", address_data)

        serializer = AddressBookSerializer(address, data=address_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)  # Vraća ažuriranu adresu
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def delete(self, request, address_id):
        try:
            # Pronađite adresu po ID-u unutar korisnikovih adresa
            address = AddressBook.objects.get(id=address_id, user=request.user)
        except AddressBook.DoesNotExist:
            return Response({'error': 'Address not found.'}, status=status.HTTP_404_NOT_FOUND)

        if address.is_primary:
            return Response({'error': 'Cannot delete primary address.'}, status=status.HTTP_400_BAD_REQUEST)

        address.delete()
        return Response({'message': 'Address deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)
#AUTENTIFIKACIJA
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes

#Password Reset
class ChangePasswordAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        # Verify the old password
        if not user.check_password(old_password):
            return Response({'error': 'Incorrect old password.'}, status=400)

        # Validate new password here if needed

        # Set the new password
        user.set_password(new_password)
        user.save()

        return Response({'message': 'Password has been successfully changed.'}, status=200)
    
class ForgotPasswordAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=400)

        try:
            user = CustomUser.objects.get(email=email)

            # Generisanje tokena za resetovanje lozinke
            token = PasswordResetTokenGenerator().make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            language = request.headers.get('Accept-Language', 'en')

            reset_link = build_password_reset_frontend_url(language, uid, token)

            email_context = {
                'user_id': user.id,
                'user_email': email
            }

           
            try:
                send_reset_password_email.delay(email, reset_link, language, user.first_name)
            except Exception as e:
                logger.exception("An error occurred while sending email")

            return Response({'message': 'Password reset email sent.', 'reset_link': reset_link}, status=200)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found.'}, status=404)

from uuid import UUID

class ResetPasswordAPIView(APIView):
    def post(self, request, uidb64, token):
        try:
            uid = urlsafe_base64_decode(uidb64).decode('utf-8')

            try:
                UUID(uid, version=4)
            except ValueError:
                return Response({'error': 'Invalid user.'}, status=400)

            user = CustomUser.objects.get(pk=uid)
        except CustomUser.DoesNotExist:
            return Response({'error': 'Invalid user.'}, status=400)

        if user is not None and PasswordResetTokenGenerator().check_token(user, token):
            new_password = request.data.get('password')
            if new_password:
                user.set_password(new_password)
                user.save()
                return Response({'message': 'Password has been reset.'}, status=200)
            else:
                return Response({'error': 'No new password provided.'}, status=400)
        else:
            return Response({'error': 'Invalid token or user.'}, status=400)



#ORDER





class OrderCreateView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        logger.info(f"Raw order request data: {request.data}")

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            logger.error(f"Order validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = serializer.save()

        data = build_order_confirmation_email_data(order)

        logger.info("Trying to send email...")
        language = self.request.headers.get('Accept-Language', 'en')

        try:
            response = send_order_confirmation_email.delay(order.user.email, data, language)
            if response.ready():
                result = response.get()
                if result and result.get("sent"):
                    logger.info("Email sent successfully!")
                else:
                    logger.error("Failed to send email: %s", result)
            else:
                logger.info("Email sending task is in progress.")
        except Exception:
            logger.exception("Error occurred while sending email")

        return Response(data, status=status.HTTP_201_CREATED)
        


############# APLIKACIJE TRECA STRANA
#STRIPE
import stripe
from .models import PaymentDetails

stripe.api_key = settings.STRIPE_SECRET_KEY

import stripe
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import PaymentDetails
from django.conf import settings
import logging

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

class CreatePaymentIntentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            amount = request.data.get('amount')
            email = request.data.get('email', request.user.email)
            billing_details = request.data.get('billing_details')
            description = request.data.get('description', 'Purchase from Snusco-AT')

            if not amount:
                return Response({'error': 'Amount is required'}, status=status.HTTP_400_BAD_REQUEST)

            currency = request.headers.get('Currency', 'eur')

            # Proveri ili kreiraj Stripe Customer-a
            customer_details, created = PaymentDetails.objects.get_or_create(
                user=request.user,
                defaults={'email': email}
            )

            if not customer_details.stripe_customer_id:
                stripe_customer = stripe.Customer.create(
                    email=email,
                    metadata={"user_id": request.user.id}
                )
                customer_details.stripe_customer_id = stripe_customer['id']
                customer_details.save()

            # Kreiraj PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_details.stripe_customer_id,
                automatic_payment_methods={'enabled': True},
                receipt_email=email,
                description=description,
                setup_future_usage='off_session',
                metadata={
                    'user_id': request.user.id,
                },
            )

            return Response({'clientSecret': intent['client_secret']}, status=status.HTTP_201_CREATED)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.critical(f"Unexpected error: {str(e)}")
            return Response({'error': 'Something went wrong', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SavePaymentDetailsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        payment_method_id = request.data.get('payment_method_id')

        if not payment_method_id:
            return Response({'error': 'Payment Method ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Pronađi ili kreiraj PaymentDetails za korisnika
        customer_details, _ = PaymentDetails.objects.get_or_create(user=request.user)

        # Ažuriraj Payment Method ID
        customer_details.payment_method_id = payment_method_id
        customer_details.save()

        return Response({'message': 'Payment method saved successfully.'}, status=status.HTTP_200_OK)



class GetPaymentMethodsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Dohvatanje detalja korisnika
            customer = PaymentDetails.objects.get(user=request.user)
            
            # Dohvatanje sačuvanih metoda plaćanja sa Stripe-a
            payment_methods = stripe.PaymentMethod.list(
                customer=customer.stripe_customer_id,
                type="card"
            )

            response_data = [
                {
                    "id": pm.id,
                    "brand": pm.card.brand,
                    "last4": pm.card.last4,
                    "exp_month": pm.card.exp_month,
                    "exp_year": pm.card.exp_year,
                }
                for pm in payment_methods.data
            ]

            logger.info(f"Fetched {len(payment_methods.data)} payment methods for user {request.user.id}")
            return Response(response_data, status=status.HTTP_200_OK)

        except PaymentDetails.DoesNotExist:
            logger.warning(f"No payment details found for user {request.user.id}")
            return Response({'message': 'No payment details found for user.'}, status=status.HTTP_404_NOT_FOUND)
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error for user {request.user.id}: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.critical(f"Unexpected error for user {request.user.id}: {str(e)}")
            return Response({'error': 'Something went wrong', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RemovePaymentMethodView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, payment_method_id, *args, **kwargs):
        try:
            stripe.PaymentMethod.detach(payment_method_id)
            return Response({'message': 'Payment method removed successfully.'}, status=status.HTTP_200_OK)
        except stripe.error.InvalidRequestError as e:
            return Response({'error': f'Invalid request: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.StripeError as e:
            return Response({'error': f'Stripe error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({'error': f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


##
class OrderDateRangeView(views.APIView):
    def post(self, request):
        # Extracting dates from JSON body
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if start_date and end_date:
            start_date = parse_datetime(start_date)
            end_date = parse_datetime(end_date)
            if start_date and end_date:
                orders = Order.objects.filter(purchase_date__range=[start_date, end_date])
            else:
                return Response({"error": "Invalid date format"}, status=400)
        else:
            return Response({"error": "Missing start_date or end_date in request"}, status=400)

        serializer = OrderMobileSerializer(orders, many=True)
        return Response(serializer.data)


class UpdateOrderView(views.APIView):
    def post(self, request):

        api_key = request.headers.get('X-API-KEY')
        if api_key != settings.GOOGLE_SHEET_API_KEY:
            return Response({"error": "Unauthorized"}, status=401)

        # Get order ID and new status from the request
        order_id = request.data.get('order_id')
        new_status = request.data.get('status')

        if not order_id:
            return Response({"error": "Order ID is required"}, status=400)

        try:
            # Update the order status in the database
            order = Order.objects.get(id=order_id)
            order.order_status  = new_status
            order.save()

            # Optionally, update Google Sheet here
            # self.update_google_sheet(order)

            return Response({"message": "Order updated successfully"})
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            logger.exception("An error occurred while updating order")
            return Response({"error": "An error occurred"}, status=500)


class IsStaffUser(permissions.BasePermission):
    """API pristup samo za naloge sa is_staff=True."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, 'is_staff', False))


def _admin_order_queryset():
    return Order.objects.select_related('user', 'address').prefetch_related(
        'order_items__product__category',
        Prefetch(
            'order_items__product__images',
            queryset=ProductImage.objects.order_by('-is_primary', 'id'),
        ),
    ).order_by('-created_at')


def _sync_order_status_if_all_items_shipped(order):
    if order.order_status == OrderStatus.CANCELED:
        return
    items = list(order.order_items.all())
    if not items:
        return
    if all(i.is_shipped for i in items):
        if order.order_status in (OrderStatus.PENDING, OrderStatus.PAID):
            order.order_status = OrderStatus.SHIPPED
            order.save(update_fields=['order_status', 'updated_at'])


def _sync_order_items_with_shipment_status(order):
    """
    Jedan status pošiljke određuje da li su stavke 'poslate' u adminu:
    Shipped/Delivered → sve stavke poslate; Pending/Paid → sve neposlate.
    Otkazane porudžbine ne diramo po stavkama ovde.
    """
    if order.order_status == OrderStatus.CANCELED:
        return
    if order.order_status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
        now = timezone.now()
        OrderItem.objects.filter(order=order).update(is_shipped=True, shipped_at=now)
    elif order.order_status in (OrderStatus.PENDING, OrderStatus.PAID):
        OrderItem.objects.filter(order=order).update(is_shipped=False, shipped_at=None)


class AdminOrderListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get(self, request):
        qs = _admin_order_queryset()
        q = request.query_params.get('q', '').strip()
        status_param = request.query_params.get('status', '').strip()
        queue = request.query_params.get('queue', 'all').strip()

        if q:
            filters = Q(customer_order_id__icontains=q) | Q(user__email__icontains=q)
            if q.isdigit():
                filters |= Q(id=int(q))
            qs = qs.filter(filters)

        if status_param:
            qs = qs.filter(order_status=status_param)

        unshipped_exists = OrderItem.objects.filter(
            order_id=OuterRef('pk'), is_shipped=False
        )
        if queue == 'to_send':
            qs = qs.filter(~Q(order_status=OrderStatus.CANCELED)).filter(Exists(unshipped_exists))
        elif queue == 'sent':
            qs = qs.filter(~Q(order_status=OrderStatus.CANCELED)).exclude(Exists(unshipped_exists))

        return Response(AdminOrderSerializer(qs, many=True).data)


class AdminOrderBulkStatusView(APIView):
    """Masovna promena `order_status` za izabrane porudžbine (staff)."""

    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def post(self, request):
        raw_ids = request.data.get('order_ids')
        new_status = request.data.get('order_status')
        if not isinstance(raw_ids, list) or len(raw_ids) == 0:
            return Response({'error': 'order_ids must be a non-empty list'}, status=400)
        if new_status is None:
            return Response({'error': 'order_status is required'}, status=400)
        valid = {c[0] for c in OrderStatus.choices}
        if new_status not in valid:
            return Response({'error': 'Invalid order_status'}, status=400)

        clean_ids = []
        for x in raw_ids:
            try:
                clean_ids.append(int(x))
            except (TypeError, ValueError):
                continue
        clean_ids = list(dict.fromkeys(clean_ids))
        if not clean_ids:
            return Response({'error': 'No valid order ids'}, status=400)

        updated = 0
        with transaction.atomic():
            qs = Order.objects.filter(id__in=clean_ids).select_for_update()
            for order in qs:
                order.order_status = new_status
                order.save()
                _sync_order_items_with_shipment_status(order)
                updated += 1

        return Response({
            'updated': updated,
            'order_ids': clean_ids,
            'order_status': new_status,
        })


class AdminOrderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get(self, request, pk):
        order = get_object_or_404(_admin_order_queryset(), pk=pk)
        return Response(AdminOrderSerializer(order).data)

    def patch(self, request, pk):
        order = get_object_or_404(Order.objects.select_related('user', 'address'), pk=pk)
        new_status = request.data.get('order_status')
        if new_status is None:
            return Response({'error': 'order_status is required'}, status=400)
        valid = {c[0] for c in OrderStatus.choices}
        if new_status not in valid:
            return Response({'error': 'Invalid order_status'}, status=400)
        order.order_status = new_status
        order.save()
        _sync_order_items_with_shipment_status(order)
        order = get_object_or_404(_admin_order_queryset(), pk=order.pk)
        return Response(AdminOrderSerializer(order).data)


class AdminOrderItemShippedPatchView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def patch(self, request, order_id, item_id):
        order = get_object_or_404(Order, pk=order_id)
        item = get_object_or_404(OrderItem, pk=item_id, order=order)
        val = request.data.get('is_shipped')
        if val is None:
            return Response({'error': 'is_shipped is required'}, status=400)
        item.is_shipped = bool(val)
        item.shipped_at = timezone.now() if item.is_shipped else None
        item.save()
        _sync_order_status_if_all_items_shipped(order)
        order = get_object_or_404(_admin_order_queryset(), pk=order.pk)
        return Response(AdminOrderSerializer(order).data)


class AdminOrderMarkAllShippedView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if order.order_status == OrderStatus.CANCELED:
            return Response({'error': 'Canceled order'}, status=400)
        now = timezone.now()
        OrderItem.objects.filter(order=order).update(is_shipped=True, shipped_at=now)
        if order.order_status != OrderStatus.DELIVERED:
            order.order_status = OrderStatus.SHIPPED
        order.save()
        order = get_object_or_404(_admin_order_queryset(), pk=order.pk)
        return Response(AdminOrderSerializer(order).data)


class RedeemPointsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        points_to_redeem = int(request.data.get('points', 0))
        user = request.user

        if points_to_redeem > user.points or points_to_redeem < 150:
            return Response({'error': 'Invalid points amount.'}, status=400)

        # Koristimo Django tranzakciju kako bismo osigurali konzistentnost podataka
        with transaction.atomic():
            # Konverzija poena u novac u DEFAULT_CURRENCY
            amount_in_usd = points_to_redeem * 0.01
            # Kreiranje vauchera u DEFAULT_CURRENCY
            voucher = Voucher.objects.create(user=user, amount=amount_in_usd, points=points_to_redeem)

            # Kreiramo negativan zapis u PointsHistory da označimo oduzimanje poena
            PointsHistory.objects.create(
                user=user,
                points=-points_to_redeem,  # Negativna vrednost da označimo oduzimanje
                point_type=PointsHistory.PointType.REDEEM,  # Koristimo novi tip poena "REDEEM"
                reason="Redeeming points for voucher",
                status=PointsHistory.Status.APPROVED  # Pretpostavljamo da ova akcija odmah odobrava poene
            )


            # Signal receiver `update_user_points` će automatski ažurirati `user.points`

            serializer = VoucherSerializer(voucher, context={'request': request, 'currency': request.headers.get('Currency', DEFAULT_CURRENCY)})

            return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class UserPointsHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # Osigurava da je korisnik autentifikovan

    def get(self, request):
        user = request.user
        points_history = PointsHistory.objects.filter(user=user)  # Dobavlja istoriju poena za trenutnog korisnika
        serializer = PointsHistorySerializer(points_history, many=True)
        return Response(serializer.data)

#USER ACITIVIY
class UserInteractionViewSet(viewsets.ModelViewSet):
    queryset = UserInteraction.objects.all()
    serializer_class = UserInteractionSerializer
    permission_classes = [permissions.IsAuthenticated]  # Obezbeđuje da je korisnik autentifikovan

class BlogListView(APIView):
    def get(self, request, format=None):
        blogs = Blog.objects.all()
        serializer = BlogSerializer(blogs, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

class BlogDetailView(generics.RetrieveAPIView):
    queryset = Blog.objects.all()
    serializer_class = BlogSerializer
    lookup_field = 'slug'

    def get_object(self):
        queryset = self.get_queryset()
        slug = self.kwargs.get("slug")
        try:
            blog = queryset.get(slug=slug)
        except Blog.DoesNotExist:
            return Response({'error': 'Blog not found.'}, status=status.HTTP_404_NOT_FOUND)
        return blog


    

