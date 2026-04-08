from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import  RegisterUserAPIView, CustomTokenObtainPairView, UserInteractionViewSet, OrderCreateView,UpdateOrderView, UserProfileView,UpdateUserInfoAPIView, ChangePasswordAPIView, UpdateAddressAPIView, ForgotPasswordAPIView, ResetPasswordAPIView, CreateAddressAPIView, RedeemPointsView,UserPointsHistoryView, GoogleLogin, OrderDateRangeView, AdminOrderListView, AdminOrderBulkStatusView, AdminOrderDetailView, AdminOrderItemShippedPatchView, AdminOrderMarkAllShippedView
from .subscription_views import SubscriptionListCreateView, SubscriptionCancelView, SubscriptionAddItemView, SubscriptionItemDeleteView
from .views import BlogDetailView, BlogListView, ResendVerificationCodeAPIView, VerifyCodeAPIView, CreatePaymentIntentView, SavePaymentDetailsView, GetPaymentMethodsView,RemovePaymentMethodView
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'user-interactions', UserInteractionViewSet)
urlpatterns = [
   path('verify-code/', VerifyCodeAPIView.as_view(), name='verify_code'),
   path('resend-verification-code/', ResendVerificationCodeAPIView.as_view(), name='resend_verification_code'),
   path('google-login/', GoogleLogin.as_view(), name='google-login'),
   path('register/', RegisterUserAPIView.as_view(), name='register'),
   path('change-password/', ChangePasswordAPIView.as_view(), name='change-password'),
   path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
   path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
 
   path('orders/create/', OrderCreateView.as_view(), name='create-order'),

   path('subscriptions/', SubscriptionListCreateView.as_view(), name='subscriptions-list-create'),
   path('subscriptions/<int:pk>/cancel/', SubscriptionCancelView.as_view(), name='subscriptions-cancel'),
   path('subscriptions/<int:pk>/items/', SubscriptionAddItemView.as_view(), name='subscriptions-add-item'),
   path('subscriptions/<int:pk>/items/<int:item_id>/', SubscriptionItemDeleteView.as_view(), name='subscriptions-delete-item'),
   path('user/profile/', UserProfileView.as_view(), name='user-profile'),
   path('user/profile/update/', UpdateUserInfoAPIView.as_view(), name='user-profile'),
   path('address-book/<int:address_id>/update/', UpdateAddressAPIView.as_view(), name='update-address-book'),
   path('address-book/create/', CreateAddressAPIView.as_view(), name='create-address-book'),
   

   path('', include(router.urls)),

   #vauceri
   path('voucher/redeem/', RedeemPointsView.as_view(), name='reedem-voucher'),
   path('points-history/', UserPointsHistoryView.as_view(), name='points-history'),

   # Putanja za slanje zahteva za resetovanje lozinke
   path('password-reset-request/', ForgotPasswordAPIView.as_view(), name='password-reset-request'),
   # Putanja za promenu lozinke (sa uid i token parametrima)
   path('password-reset-confirm/<uidb64>/<token>/', ResetPasswordAPIView.as_view(), name='password-reset-confirm'),
   #path('orders/by_date/', OrderDateRangeView.as_view(), name='order-by-date'),
   path('update-order/', UpdateOrderView.as_view(), name='update_order'),

   path('admin/orders/', AdminOrderListView.as_view(), name='admin-order-list'),
   path('admin/orders/bulk-status/', AdminOrderBulkStatusView.as_view(), name='admin-order-bulk-status'),
   path('admin/orders/<int:pk>/', AdminOrderDetailView.as_view(), name='admin-order-detail'),
   path('admin/orders/<int:pk>/mark-all-shipped/', AdminOrderMarkAllShippedView.as_view(), name='admin-order-mark-all-shipped'),
   path('admin/orders/<int:order_id>/items/<int:item_id>/', AdminOrderItemShippedPatchView.as_view(), name='admin-order-item-shipped'),
   
   #Blogs
   path('blogs/', BlogListView.as_view(), name='blog-list'),
   path('blogs/<slug:slug>/', BlogDetailView.as_view(), name='blog-detail'),

   #STRIPE
   path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create_payment_intent'),
   path('save-payment-details/', SavePaymentDetailsView.as_view(), name='save_payment_details'),
   path('get-payment-methods/', GetPaymentMethodsView.as_view(), name='get_payment_methods'),
   path('remove-payment-method/<str:payment_method_id>/', RemovePaymentMethodView.as_view(), name='remove-payment-method'),
]

