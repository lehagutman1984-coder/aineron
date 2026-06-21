from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status


class TelegramLinkTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Статус привязки: привязан ли Telegram к аккаунту."""
        try:
            tg = request.user.telegram
            return Response({
                'linked': True,
                'telegram_id': tg.telegram_id,
                'telegram_username': tg.telegram_username,
                'telegram_first_name': tg.telegram_first_name,
                'linked_at': tg.linked_at.isoformat(),
            })
        except Exception:
            return Response({'linked': False})

    def post(self, request):
        """Создать одноразовый токен для привязки бота."""
        from telegram_bot.models import TelegramLinkToken
        token_obj = TelegramLinkToken.create_for_user(request.user, ttl_minutes=15)
        bot_username = settings.TELEGRAM_BOT_USERNAME
        link = f'https://t.me/{bot_username}?start={token_obj.token}'
        return Response({'link': link, 'expires_in': 900, 'token': token_obj.token})

    def delete(self, request):
        """Отвязать Telegram от аккаунта."""
        try:
            request.user.telegram.delete()
            return Response({'unlinked': True})
        except Exception:
            return Response({'error': 'not linked'}, status=status.HTTP_400_BAD_REQUEST)
