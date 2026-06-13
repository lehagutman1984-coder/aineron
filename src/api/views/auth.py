from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from api.serializers.auth import UserSerializer
from users.email_service import send_verification_email

User = get_user_model()


class MeView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        password = request.data.get('password') or ''

        if not email or not password:
            return Response({
                'error': {'message': 'Email и пароль обязательны', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        user = authenticate(request, username=email, password=password)
        if user is None:
            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None or not user.is_active:
            return Response({
                'error': {'message': 'Неверный email или пароль', 'type': 'authentication_error', 'code': 'invalid_credentials'}
            }, status=401)

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({'ok': True})


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        password = request.data.get('password') or ''

        if not email or not password:
            return Response({
                'error': {'message': 'Email и пароль обязательны', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        if len(password) < 8:
            return Response({
                'error': {'message': 'Пароль должен содержать минимум 8 символов', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        if User.objects.filter(email=email).exists():
            return Response({
                'error': {'message': 'Пользователь с таким email уже существует', 'type': 'invalid_request_error', 'code': 'email_taken'}
            }, status=400)

        username = email.split('@')[0]
        base = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username, email=email, password=password
        )
        try:
            send_verification_email(user, request)
        except Exception:
            pass
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response(UserSerializer(user).data, status=201)
