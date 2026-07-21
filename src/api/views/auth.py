from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from api.authentication import CsrfExemptSessionAuthentication
from rest_framework.response import Response
from rest_framework import status

from api.serializers.auth import UserSerializer
from users.email_service import send_verification_email

User = get_user_model()


def apply_referral(user, request):
    """
    Привязка реферера при регистрации: ref_code берётся из тела запроса
    или из cookie `ref_code` (её ставит Next.js middleware при заходе по ?ref=CODE).
    """
    ref_code = (request.data.get('ref_code') or request.COOKIES.get('ref_code') or '').strip()
    if not ref_code:
        return False
    referrer = User.objects.filter(referral_code__iexact=ref_code).exclude(pk=user.pk).first()
    if referrer is None:
        return False
    from django.db.models import F
    user.referrer = referrer
    user.save(update_fields=['referrer'])
    User.objects.filter(pk=referrer.pk).update(referral_clicks=F('referral_clicks') + 1)
    return True


class MeView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication]
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
        lang = (request.data.get('lang') or '').strip().lower()
        if lang in dict(User.LANGUAGE_CHOICES):
            user.language = lang
            user.save(update_fields=['language'])
        apply_referral(user, request)
        if settings.INTL_MODE:
            # Международный инстанс: SMTP недоступен (порты хостера закрыты) —
            # верифицируем email сразу, чтобы не заводить пользователя в тупик.
            user.email_verified = True
            user.save(update_fields=['email_verified'])
        else:
            try:
                send_verification_email(user, request)
            except Exception:
                pass
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        response = Response(UserSerializer(user).data, status=201)
        if request.COOKIES.get('ref_code'):
            response.delete_cookie('ref_code')
        return response


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [CsrfExemptSessionAuthentication]

    def post(self, request):
        code = (request.data.get('code') or '').strip()
        if not code or len(code) != 6:
            return Response({'error': {'message': 'Введите 6-значный код', 'code': 'invalid_code'}}, status=400)

        try:
            user = User.objects.get(email_verification_code=code)
        except User.DoesNotExist:
            return Response({'error': {'message': 'Неверный или устаревший код', 'code': 'invalid_code'}}, status=400)

        user.verify_email()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response({'ok': True})


class ResendVerificationView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.email_verified:
            return Response({'error': {'message': 'Email уже подтверждён', 'code': 'already_verified'}}, status=400)
        try:
            send_verification_email(request.user, request)
        except Exception:
            return Response({'error': {'message': 'Ошибка отправки письма', 'code': 'send_error'}}, status=500)
        return Response({'ok': True})
