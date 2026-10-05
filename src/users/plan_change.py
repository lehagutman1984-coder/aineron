# users/plan_change.py
"""
Правила покупки тарифа, когда у пользователя УЖЕ действует платный тариф.

2026-10-05: перенесено с yurist-center (backend/services/plan_change.py) — там
обкатано и задеплоено первым. Логика та же, адаптирована под модели aineron.ru
(Tariff/UserSubscription, рубли в копейках, balance_grant_kopecks вместо
лимитов-счётчиков).

Тариф считается действующим, если у пользователя есть active_subscription,
она is_active, тариф платный (price > 0) и expires_at в будущем. Тогда новая
покупка — это:

  extend   — тот же тариф: срок +duration_days к ТЕКУЩЕМУ сроку (не сброс),
             баланс начисляется полный бонус нового периода (как и раньше —
             баланс не сгорает и не "обнуляется", это просто добавка);
  upgrade  — тариф дороже: платится полная цена нового тарифа, остаток дней
             старого пересчитывается в бонусные дни нового по соотношению цен
             (остаток × цена_старого / цена_нового) и добавляется к сроку
             нового тарифа — вместо того чтобы просто сгорать;
  blocked  — тариф дешевле или равный по цене, но другой: сменить можно
             после окончания текущего срока;
  new      — иначе (бесплатный/пробный тариф, срока нет, истёк): как раньше,
             срок duration_days дней с даты оплаты.

Выбор пользователя «автопродление выключено» при extend/upgrade сохраняется
(не включаем молча) — это уже обеспечено тем, что мы не трогаем auto_renew
в UserSubscription при extend/upgrade в вызывающем коде.
"""
from datetime import timedelta
from typing import Optional

from django.utils import timezone


def classify(user, new_tariff) -> dict:
    """
    Что произойдёт при покупке new_tariff. Возвращает:
      kind: new | extend | upgrade | blocked
      new_expires: datetime окончания после покупки (для blocked — None)
      bonus_days: сколько дней добавлено к новому периоду за остаток старого
                  (для upgrade; для extend — остаток в днях, информативно)
      current_tariff / current_expires, message (для blocked)
    """
    now = timezone.now()
    subscription = getattr(user, 'active_subscription', None)
    current_tariff = subscription.tariff if subscription else None
    expires = subscription.expires_at if subscription else None
    active = bool(
        subscription and subscription.is_active and current_tariff
        and not current_tariff.is_free and current_tariff.price > 0
        and expires and expires > now
    )

    base = {
        'kind': 'new',
        'current_tariff_id': current_tariff.id if active else None,
        'current_tariff_name': current_tariff.display_name if active else None,
        'current_expires': expires if active else None,
        'new_tariff_id': new_tariff.id,
        'new_tariff_name': new_tariff.display_name,
        'bonus_days': 0.0,
        'new_expires': now + timedelta(days=new_tariff.duration_days),
        'message': None,
    }
    if not active:
        return base

    remaining = expires - now
    if current_tariff.id == new_tariff.id:
        base.update(
            kind='extend',
            bonus_days=remaining.total_seconds() / 86400,
            new_expires=expires + timedelta(days=new_tariff.duration_days),
        )
    elif new_tariff.price > current_tariff.price:
        bonus = remaining * (float(current_tariff.price) / float(new_tariff.price))
        base.update(
            kind='upgrade',
            bonus_days=bonus.total_seconds() / 86400,
            new_expires=now + timedelta(days=new_tariff.duration_days) + bonus,
        )
    else:
        base.update(
            kind='blocked',
            new_expires=None,
            message=(
                f"У вас действует тариф «{current_tariff.display_name}» до "
                f"{expires.strftime('%d.%m.%Y')}. Перейти на тариф «{new_tariff.display_name}» "
                f"(ниже или равный по цене) можно после окончания срока текущего тарифа."
            ),
        )
    return base
