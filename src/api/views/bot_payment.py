"""
GET /v1/billing/bot-pay-url/?stars=100&pack=stars_100

Creates a PaymentHistory for the authenticated user and returns a
Robokassa redirect URL that can be sent as an inline button in the Telegram bot.
Robokassa supports both POST (form) and GET (redirect URL).
"""
import hashlib
import json
import random
import time
import logging
import urllib.parse

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import PaymentHistory

logger = logging.getLogger(__name__)

BOT_STAR_PACKS = {
    'stars_100':  {'stars': 100,  'price': '99.00',  'label': '100 звёзд aineron'},
    'stars_220':  {'stars': 220,  'price': '199.00', 'label': '220 звёзд aineron (+10%)'},
    'stars_600':  {'stars': 600,  'price': '499.00', 'label': '600 звёзд aineron (+20%)'},
    'stars_1500': {'stars': 1500, 'price': '999.00', 'label': '1500 звёзд aineron (+25%)'},
}


def _robokassa_get_url(merchant_login, out_sum, inv_id, description, password1,
                        receipt_json, test_mode, success_url, fail_url) -> str:
    sig_str = f"{merchant_login}:{out_sum}:{inv_id}:{receipt_json}:{password1}"
    signature = hashlib.md5(sig_str.encode('cp1251')).hexdigest()

    params = {
        'MerchantLogin': merchant_login,
        'OutSum': out_sum,
        'InvId': str(inv_id),
        'Description': description,
        'SignatureValue': signature,
        'IsTest': str(test_mode),
        'Culture': 'ru',
        'Encoding': 'utf-8',
        'SuccessURL': success_url,
        'FailURL': fail_url,
        'Receipt': receipt_json,
    }
    return "https://auth.robokassa.ru/Merchant/Index.aspx?" + urllib.parse.urlencode(params)


class BotPayUrlView(APIView):
    """
    GET /v1/billing/bot-pay-url/?pack=stars_100
    Returns a Robokassa payment URL for the bot inline button.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pack_key = request.query_params.get('pack', 'stars_100')
        pack = BOT_STAR_PACKS.get(pack_key)
        if not pack:
            return Response({'error': 'Unknown pack'}, status=400)

        merchant_login = getattr(settings, 'ROBOKASSA_LOGIN', '')
        password1 = getattr(settings, 'ROBOKASSA_PASS1', '')
        if not merchant_login or not password1:
            return Response({'error': 'Robokassa not configured'}, status=503)

        inv_id = int(time.time() * 1000) % 10_000_000 + random.randint(1, 999)
        out_sum = pack['price']
        description = pack['label']
        stars = pack['stars']

        receipt_data = {
            "items": [{
                "name": description[:128],
                "quantity": 1,
                "sum": float(out_sum),
                "tax": "none",
            }]
        }
        receipt_json = json.dumps(receipt_data, separators=(',', ':'), ensure_ascii=False)

        payment = PaymentHistory.objects.create(
            user=request.user,
            payment_type='pages',
            invoice_id=str(inv_id),
            amount=float(out_sum),
            pages_count=stars,
            status='pending',
            description=description,
        )

        site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
        pay_url = _robokassa_get_url(
            merchant_login=merchant_login,
            out_sum=out_sum,
            inv_id=inv_id,
            description=description,
            password1=password1,
            receipt_json=receipt_json,
            test_mode=getattr(settings, 'ROBOKASSA_TEST_MODE', 0),
            success_url=f"{site_url}/payment-success/",
            fail_url=f"{site_url}/users/pages/payment-fail/",
        )

        logger.info(
            f"BotPayUrl: user={request.user.email} pack={pack_key} "
            f"stars={stars} inv_id={inv_id}"
        )
        return Response({
            'pay_url': pay_url,
            'payment_id': payment.id,
            'stars': stars,
            'price': out_sum,
            'label': description,
        })
