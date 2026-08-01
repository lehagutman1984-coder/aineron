"""
Сохранение UTM-меток первого захода в профиль пользователя при регистрации.

Cookie `utm_source`/`utm_medium`/`utm_campaign` ставит `frontend/middleware.ts`
при заходе с соответствующими параметрами в URL (см. GROWTH_PLAN_RU.md §2.5) —
тем же способом, что уже работает для `ref_code`. Без этого нельзя было понять,
какой канал (vc.ru, каталоги, TG-посевы, Директ) реально приводит
регистрирующихся пользователей, а не просто визиты (Метрика UTM видит сама,
но не связывает их с конкретным платящим пользователем в нашей БД).

Вызывается один раз при создании аккаунта, из всех точек регистрации:
`api/views/auth.py` (DRF), `users/views.py` (legacy), `users/adapters.py`
(allauth — email и соцсети).
"""

_UTM_COOKIE_TO_FIELD = {
    'utm_source': 'acquisition_utm_source',
    'utm_medium': 'acquisition_utm_medium',
    'utm_campaign': 'acquisition_utm_campaign',
}


def apply_utm_attribution(user, request, save=True):
    """Копирует UTM-cookie в атрибуты пользователя. Возвращает True, если что-то нашли.

    `save=False` — для мест, где объект ещё не имеет pk (allauth `save_user`
    с `commit=False`) и будет сохранён вызывающей стороной чуть позже вместе
    с остальными полями, как это уже делается для `referrer`.
    """
    updates = {}
    for cookie_name, field_name in _UTM_COOKIE_TO_FIELD.items():
        value = (request.COOKIES.get(cookie_name) or '').strip()
        if value:
            updates[field_name] = value[:100]
    if not updates:
        return False
    for field_name, value in updates.items():
        setattr(user, field_name, value)
    if save:
        user.save(update_fields=list(updates.keys()))
    return True
