# aineron.ru — Реализация §7 (Stage 2): ASGI, Moderation, White-label, Bot OAuth, Yjs, Voice

> Составлен: 2026-06-24 | Модель: Claude Opus 4.8 + Advisor

---

## Порядок реализации

```
0. ASGI-миграция (БЛОКЕР для §7.1 и §7.10) ──┐
                                              ├─→ 4. Yjs (§7.10)
1. Moderation (§7.9)  ─┐ независимы,          └─→ 5. Voice (§7.1)
2. White-label (§7.6) ─┤ делать параллельно
3. Bot OAuth (§7.12)  ─┘
```

---

## 0. ASGI-миграция — M, 2-3 дня (БЛОКЕР для Voice и Yjs)

**Принцип:** gunicorn WSGI остаётся обслуживать все HTTP-запросы.
Добавляем только отдельный `daphne`-контейнер для WebSocket.
nginx роутит `/ws/` на daphne, остальное — на gunicorn.

### Шаги

1. `src/config/asgi.py` →
```python
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from config.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
```

2. `src/config/settings.py`:
- `INSTALLED_APPS` → добавить `'channels'` после `django.contrib.staticfiles`
- `ASGI_APPLICATION = 'config.asgi.application'`
- `CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [env("REDIS_URL")]}}}`

3. Новый файл `src/config/routing.py`:
```python
websocket_urlpatterns = []  # заполнится §7.10 и §7.1
```

4. `docker-compose.yml` — новый сервис:
```yaml
daphne:
  build: .
  command: daphne -b 0.0.0.0 -p 9000 config.asgi:application
  env_file: [.env]
  volumes: [./src:/app]
  depends_on:
    db: {condition: service_healthy}
    redis: {condition: service_healthy}
```

5. `nginx.conf`:
```nginx
upstream daphne { server daphne:9000; }

# Добавить в server HTTPS-блок (копия блока studio preview nginx.conf:151-162):
location /ws/ {
    proxy_pass http://daphne;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 3600s;
}
```

6. Auth middleware для WS: `TokenAuthMiddleware` в `src/config/channel_auth.py` —
   извлекает пользователя из session cookie/JWT, не полагается на sync middleware.

### Риски
- Синхронный middleware (ShadowBan, EmailVerification, UserActivity, allauth) — НЕ тащить в ASGI-путь
- Долгие WS → `proxy_read_timeout 3600s`
- daphne как SPOF → MVP: один инстанс; масштабирование через несколько daphne позже

### Деплой
- Это структурное изменение сервера — нельзя катить пофичево
- Деплоить одним коммитом с полным набором изменений: settings + asgi + routing + docker-compose + nginx
- Тестировать WS-эхо до включения Yjs/Voice

---

## 1. §7.9 AI-модерация контента — S-M, 2-3 дня (ПЛАТНО: копейки)

### Шаг 0 — SPIKE (до написания кода)
Проверить, что `api.laozhang.ai` отдаёт `/moderations`:
```bash
curl -X POST "https://api.laozhang.ai/v1/moderations" \
  -H "Authorization: Bearer $LAOZHANG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"omni-moderation-latest","input":"test"}'
```
- Если есть → использовать через `get_laozhang_client()` (`client.moderations.create(...)`)
- Если нет → отдельный OpenAI-клиент (другой ключ) ИЛИ feature отложить

### Шаги (после spike)

1. `src/config/settings.py`: `MODERATION_ENABLED = env.bool('MODERATION_ENABLED', False)`

2. Модель `ModerationLog` в `src/aitext/models.py`:
```python
class ModerationLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    message = models.ForeignKey('Message', null=True, on_delete=models.SET_NULL)
    input_excerpt = models.CharField(max_length=200)
    flagged = models.BooleanField()
    categories = models.JSONField(default=dict)
    scores = models.JSONField(default=dict)
    action = models.CharField(max_length=10, choices=[('allowed','Разрешено'),('blocked','Заблокировано')])
    source = models.CharField(max_length=20, default='web_chat')
    created_at = models.DateTimeField(auto_now_add=True)
```
Миграция `aitext/0032`.

3. Хелпер `src/aitext/moderation.py`:
```python
def check_moderation(text: str) -> dict:
    """Returns {'flagged': bool, 'categories': {...}, 'scores': {...}}"""
```

4. Точка вставки в **web-чат** (`src/aitext/tasks.py`, `generate_ai_response`):
   - После строки 868 (финализация `messages_for_api`)
   - До строки 893 (вызов LLM)
   - Если `flagged` → `message.status = FAILED`, `error_message = 'Контент нарушает политику'`, `return`

5. Точка вставки в **developer API** (`src/api/views/chat.py`, `ChatCompletionsView.post`):
   - Pre-check перед `client.chat.completions.create`
   - Возврат `400` с OpenAI-форматом: `{'error': {'type': 'invalid_request_error', 'code': 'content_policy_violation'}}`

---

## 2. §7.6 White-label B2B — L, 1-1.5 недели

### Этап A — MVP: субдомены `orgname.aineron.ru` (один wildcard-сертификат)

**DevOps-задачи (отдельно, до кода):**
1. Выпустить wildcard `*.aineron.ru` (Let's Encrypt DNS-01)
2. Добавить в `nginx.conf` блок `server_name *.aineron.ru;` (копия HTTPS-блока, те же upstream)
3. DNS wildcard A-запись `*.aineron.ru → IP сервера`

**Код:**

1. Модель `OrganizationBranding` в `src/teams/models.py`:
```python
class OrganizationBranding(models.Model):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='branding')
    subdomain = models.SlugField(max_length=63, unique=True)
    custom_domain = models.CharField(max_length=253, blank=True)
    logo_url = models.URLField(blank=True)
    primary_color = models.CharField(max_length=7, default='#0a7cff')
    company_name = models.CharField(max_length=100, blank=True)
    support_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
```
Миграция `teams/0004`.

2. Middleware `OrganizationBrandingMiddleware` в `src/teams/middleware.py`:
   - Парсит `request.get_host()` → извлекает subdomain/custom_domain
   - Резолвит `OrganizationBranding` с Redis-кэшом (TTL 300с)
   - Кладёт в `request.org_branding`
   - Добавить в `MIDDLEWARE` после `CommonMiddleware`

3. API endpoint `GET /v1/branding/?host=...` (новый view `api/views/branding.py`):
   - Используется Next.js middleware для получения данных брендинга

4. Next.js middleware `frontend/middleware.ts`:
   - Читает `Host`, дёргает `/v1/branding/?host=...`
   - Прокидывает брендинг в layout через cookies/headers
   - Применяет CSS-переменные (logo, primary_color)

5. UI в `/dashboard/organization/` — настройки subdomain, logo, цвета

### Этап B — кастомные домены `chat.client.com` (планируется, не MVP)
- Требует on-demand TLS: либо Caddy-контейнер перед nginx с `ask`-эндпоинтом (Django /v1/verify-domain/)
- Реализовать отдельно после консультации с DevOps

---

## 3. §7.12 Bot as OAuth provider — M-L, 1 неделя (security-critical)

### Принцип
Используем `django-oauth-toolkit` (DOT) — не переизобретаем OAuth2/PKCE.
Кастомный кусок только: Telegram initData → Django user.

### Шаги

1. `src/requirements.txt`: `django-oauth-toolkit>=2.4.0`
2. `settings.py`: добавить `'oauth2_provider'` в INSTALLED_APPS
3. `OAUTH2_PROVIDER = {'PKCE_REQUIRED': True, 'SCOPES': {'read': 'Чтение профиля', 'profile': 'Данные пользователя'}, 'ACCESS_TOKEN_EXPIRE_SECONDS': 3600}`
4. Миграции DOT (`python manage.py migrate oauth2_provider`)
5. URLs DOT в `config/urls.py` под `/oauth/`

6. **Telegram auth backend** `src/telegram_bot/oauth.py`:
```python
class TelegramOAuthBackend:
    def authenticate(self, request, init_data=None):
        # validate_init_data (scaffold.py:230)
        # проверить auth_date freshness (< 300 сек)
        # TelegramUser.objects.get(telegram_id=...) → user
```

7. Authorize-view: пользователь → Telegram Login Widget → DOT выдаёт code → token exchange

8. Frontend `/dashboard/oauth-apps/` (Next.js):
   - Список OAuth-приложений (DOT Application модель)
   - Создание/удаление client_id + redirect URIs

### Ключевые security-требования (обязательно)
- `auth_date` freshness проверка (не старше 300 сек) — защита от replay
- PKCE обязателен (`PKCE_REQUIRED = True`)
- Whitelist redirect_uri (DOT валидирует сам)
- Привязка только через существующий TelegramUser → user

---

## 4. §7.10 Real-time collaboration (Yjs) — L, 1-1.5 недели (зависит от §0)

### Предусловие: §0 ASGI-миграция выполнена

### Шаги

1. Зависимости: `ypy-websocket` или `channels-yjs` (Python Yjs server)
   Проверить совместимость с channels 4.x

2. `YjsConsumer` в `src/aitext/consumers.py`:
```python
class YjsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        # Проверить ProjectCollaborator access
        await self.channel_layer.group_add(f'project_{self.project_id}', self.channel_name)
        await self.accept()
    
    async def receive(self, bytes_data):
        # y-websocket protocol: sync step 1/2, update broadcast
        await self.channel_layer.group_send(...)
```

3. Роут в `config/routing.py`:
```python
websocket_urlpatterns = [
    re_path(r'ws/yjs/(?P<project_id>\d+)/$', YjsConsumer.as_asgi()),
]
```

4. Авторизация в `connect()`: `ProjectCollaborator.objects.filter(project_id=..., user=user).exists()`

5. Персистентность: поле `yjs_state = models.BinaryField(null=True)` в `Project`, сохранять snapshot по таймеру

6. Frontend: `yjs` + `y-websocket` в редакторе Projects, `wss://aineron.ru/ws/yjs/<id>/`

---

## 5. §7.1 Voice mode — L, 1.5-2 недели (ПЛАТНО, зависит от §0)

### Предусловие: §0 ASGI + spike laozhang streaming STT/TTS

### Spike (до кода):
Проверить, есть ли у laozhang стриминговые STT и TTS.
Если нет → MVP остаётся half-duplex (push-to-talk).

### MVP (half-duplex, push-to-talk)

1. `VoiceConsumer` в `src/aitext/voice_consumers.py`:
   - клиент шлёт аудио-blob → consumer вызывает Whisper (логика AudioTranscriptionsView) → текст → LLM → TTS → аудио обратно по WS

2. Роут: `ws/voice/<chat_id>/` в `config/routing.py`

3. Биллинг: `user.spend_pages(cost)` (ASR + LLM + TTS), `pages_count > 0` проверка до начала

4. Frontend: компонент Voice в веб-чате, MediaRecorder → WS → AudioContext воспроизведение

### Полное (full-duplex, после MVP)
- Серверный VAD (webrtcvad), barge-in, потоковая транскрипция
- Зависит от наличия стриминговых эндпоинтов у laozhang

---

## Сводная таблица

| # | Фича | Сложн. | Время | Зависит от | Платно |
|---|------|--------|-------|------------|--------|
| 0 | ASGI-миграция | M | 2-3 дня | — | нет |
| 1 | §7.9 Moderation | S-M | 2-3 дня | spike `/moderations` | да (копейки) |
| 2 | §7.6 White-label MVP | L | 1-1.5 нед | DevOps wildcard cert | нет |
| 3 | §7.12 Bot OAuth | M-L | 1 нед | — | нет |
| 4 | §7.10 Yjs collab | L | 1-1.5 нед | §0 ASGI | нет |
| 5 | §7.1 Voice mode | L | 1.5-2 нед | §0 ASGI + spike | да |

## Незакрытые вопросы (спайки до кода)

1. **§7.9**: `curl -X POST https://api.laozhang.ai/v1/moderations -H "Authorization: Bearer $LAOZHANG_API_KEY" ...` — есть ли эндпоинт?
2. **§7.1**: есть ли у laozhang стриминговые STT/TTS (для full-duplex) или только request/response (push-to-talk MVP)?
3. **§7.6**: DevOps может выпустить wildcard `*.aineron.ru` и настроить nginx?

## Важно для деплоя

Этот этап принципиально отличается от Sprint 7 (additive Python/TSX).
Здесь меняются:
- `settings.py` (INSTALLED_APPS, MIDDLEWARE, ASGI_APPLICATION, CHANNEL_LAYERS)
- `docker-compose.yml` (новый сервис daphne)
- `nginx.conf` (новый upstream, /ws/ location)
- Миграции DOT

Неправильный nginx-блок = nginx не перезагрузится.
Неправильный INSTALLED_APPS = gunicorn не стартанёт.
Это потенциальный простой прода.

**Рекомендация:** ASGI-миграцию + nginx-изменения катить как один полный коммит,
тестировать на стейдже если есть, или в нерабочее время с быстрым rollback-планом.
