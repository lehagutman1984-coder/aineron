"""
Общая логика начисления реферального бонуса за покупку/продление тарифа.

Раньше бонус начислялся только внутри вебхука Робокассы
(`users/views.py::payment_success`, ветка `payment_type == 'subscription'`) —
из-за этого рефереры не получали ничего за приглашённых, которые оформили
тариф через Telegram Stars или через автопродление (оба пути создают
подписку в обход этого вебхука). Вынесено сюда и вызывается из всех точек,
где реально активируется платный тариф.

Намеренно НЕ вызывается для обычных пополнений баланса без тарифа
(`payment_type == 'pages'`, в т.ч. крипто-пополнения) — по дизайну
реферальный бонус привязан к покупке тарифа, а не к любому платежу
(см. TARIFFS.md §6: бонус — это часть экономики тарифа, k уже учитывает
именно его).
"""
import logging
from decimal import Decimal

from django.db.models import F

from users.models import ReferralEarning

logger = logging.getLogger(__name__)


def grant_referral_bonus(user, tariff, reference, context=''):
    """Начисляет бонус рефереру `user`, если он есть, за оплату `tariff`.

    `reference` должен быть уникален для конкретного факта оплаты (invoice_id,
    charge_id и т.п.) — идемпотентность рублёвого пути обеспечивает
    add_kopecks(reference=...); путь через rub_balance идемпотентности не
    имеет (унаследовано из исходной логики в payment_success) — вызывающая
    сторона обязана гарантировать однократный вызов на факт оплаты.
    """
    referrer = getattr(user, 'referrer', None)
    if not referrer:
        return

    if referrer.can_convert_to_rub and tariff.referral_bonus > 0:
        type(referrer).objects.filter(pk=referrer.pk).update(
            rub_balance=F('rub_balance') + Decimal(str(tariff.referral_bonus))
        )
        referrer.refresh_from_db(fields=['rub_balance'])
        amount_rub = tariff.referral_bonus
        amount_stars = 0
        logger.info(
            f"[REFERRAL] {referrer.email}: +{tariff.referral_bonus} руб за "
            f"{tariff.display_name} ({user.email}, {context})"
        )
    else:
        referrer.add_kopecks(
            tariff.referral_bonus_kopecks, type='referral', reference=reference,
        )
        amount_rub = 0
        amount_stars = tariff.referral_bonus_stars
        logger.info(
            f"[REFERRAL] {referrer.email}: +{tariff.referral_bonus_stars} на баланс за "
            f"{tariff.display_name} ({user.email}, {context})"
        )

    if amount_rub > 0 or amount_stars > 0:
        ReferralEarning.objects.create(
            user=referrer,
            amount_rub=amount_rub,
            amount_stars=amount_stars,
            tariff=tariff,
            description=f'Бонус за приглашение {user.email} (тариф {tariff.display_name})',
        )
