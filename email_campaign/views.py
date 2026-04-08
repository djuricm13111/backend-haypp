from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Subscriber
from .serializers import SubscriberSerializer
from .tasks import send_subscribe_confirmation_email

class SubscribeView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = SubscriberSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            if Subscriber.objects.filter(email=email).exists():
                return Response({'message': 'This email is already subscribed.'}, status=status.HTTP_409_CONFLICT)
            
            subscriber = serializer.save()
            language = request.headers.get('Accept-Language', 'en')
            try:
                send_subscribe_confirmation_email.delay(subscriber.email, language)
            except Exception as e:
                print(f"Error sending email: {e}")
            return Response({'message': 'Subscription successful!'}, status=status.HTTP_201_CREATED)
        else:
            print("Serializer Errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    



