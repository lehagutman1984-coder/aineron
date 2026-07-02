from pathlib import Path
import os
import sys
import warnings
warnings.filterwarnings("ignore", message="allauth.exceptions is deprecated", category=UserWarning)


BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', '')


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = int(os.environ.get('DEBUG', 0))


# ========== НАСТРОЙКИ ДОМЕНОВ ==========
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split() or ['*']
if '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('*')


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django_celery_beat',
    'django.contrib.sites',
    'django.contrib.sitemaps',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.yandex',
    'allauth.socialaccount.providers.vk',
    'allauth.socialaccount.providers.mailru',
    'allauth.socialaccount.providers.github',

    'channels',

    'users.apps.UsersConfig',
    'landing.apps.LandingConfig',
    'aitext',
    'blog',

    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'oauth2_provider',
    'api',
    'teams',
    'studio',
    'telegram_bot',
]

OAUTH2_PROVIDER = {
    'PKCE_REQUIRED': True,
    'SCOPES': {
        'read': 'Чтение профиля',
        'profile': 'Данные пользователя',
        'api': 'Доступ к API',
    },
    'ACCESS_TOKEN_EXPIRE_SECONDS': 3600,
    'REFRESH_TOKEN_EXPIRE_SECONDS': 86400 * 30,
    'ROTATE_REFRESH_TOKEN': True,
    'AUTHENTICATION_BACKENDS': [
        'telegram_bot.oauth.TelegramOAuthBackend',
        'django.contrib.auth.backends.ModelBackend',
    ],
}


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',

    'users.middleware.ShadowBanMiddleware',
    'users.middleware.EmailVerificationMiddleware',
    'users.middleware.UserActivityMiddleware',
    'teams.middleware.OrganizationBrandingMiddleware',
]


ROOT_URLCONF = 'config.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.site_counter',
                'blog.context_processors.notification_posts',
                'users.context_processors.user_balance',
                'users.context_processors.site_settings',
                'users.context_processors.current_site',
                'aitext.context_processors.footer_networks',
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# ========== НАСТРОЙКИ БАЗЫ ДАННЫХ ==========
if 'test' in sys.argv or 'test_coverage' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'neiro_db'),
            'USER': os.environ.get('DB_USER', 'neiro_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'db'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }


# ========== ВАЛИДАТОРЫ ПАРОЛЕЙ ==========
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ========== INTERNATIONALIZATION ==========
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = False
USE_L10N = True
USE_TZ = True


# ========== СТАТИЧЕСКИЕ ФАЙЛЫ ==========
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'


# ========== МЕДИА ФАЙЛЫ ==========
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# ========== ПОЛЬЗОВАТЕЛИ ==========
AUTH_USER_MODEL = 'users.CustomUser'


AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]


# ========== DJANGO-ALLAUTH ==========
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_ADAPTER = 'users.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_REQUIRED = False
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_LOGIN_ON_GET = False

LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/users/pages/auth/'
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'


# ========== СОЦИАЛЬНЫЕ ПРОВАЙДЕРЫ ==========
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'yandex': {
        'SCOPE': ['login:email', 'login:info'],
        'AUTH_PARAMS': {'lang': 'ru'},
    },
    'vk': {
        'SCOPE': ['email'],
        'AUTH_PARAMS': {'v': '5.131'},
        'METHOD': 'oauth2',
        'OAUTH_PKCE_ENABLED': True,
    },
    'mailru': {
        'APP': {
            'client_id': '000000000000000000000000',
            'secret': '00000000000000000000000000',
            'key': ''
        }
    }
}


# ========== CSRF И TRUSTED ORIGINS ==========
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8000',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:8000',
    'https://aineron.ru',
    'https://www.aineron.ru',
]


# ========== ДОМЕН И URL ==========
SITE_URL = os.environ.get('SITE_URL', 'https://aineron.ru')
SITE_NAME = os.environ.get('SITE_NAME', 'aineron.ru')
DOMAIN = 'aineron.ru'


# ========== EMAIL ==========
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True' and not EMAIL_USE_SSL

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
SERVER_EMAIL = DEFAULT_FROM_EMAIL


# ========== CELERY ==========
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = os.environ.get('REDIS_PORT', '6379')
REDIS_DB = os.environ.get('REDIS_DB', '0')
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
TELEGRAM_FSM_REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/2"

# ========== КЭШИ (Redis DB 3) ==========
# django-redis для кросс-воркерного кэша и rate limiting
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{REDIS_HOST}:{REDIS_PORT}/3",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'aineron',
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [f"redis://{REDIS_HOST}:{REDIS_PORT}/4"]},
    }
}

MODERATION_ENABLED = os.environ.get('MODERATION_ENABLED', '0') == '1'

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Moscow'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_ROUTES = {'studio.tasks.*': {'queue': 'studio_queue'}}

from celery.schedules import crontab  # noqa: E402
CELERY_BEAT_SCHEDULE = {
    **(globals().get('CELERY_BEAT_SCHEDULE') or {}),
    'studio-reap-stale-sandboxes': {
        'task': 'studio.tasks.reap_stale_sandboxes',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'studio_queue'},
    },
    'poll-project-connectors': {
        'task': 'aitext.tasks.poll_connectors',
        'schedule': crontab(minute='*/10'),
    },
    # Sprint 8: settle billing for expired/abandoned E2B preview sessions
    'reconcile-preview-billing': {
        'task': 'studio.tasks.reconcile_preview_billing',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'studio_queue'},
    },
}

# Sprint 8: E2B preview billing rate (stars per minute of sandbox time)
# $0.0022/min × markup. Adjust via E2B_PREVIEW_STARS_PER_MIN env var once you know the star-per-ruble rate.
E2B_PREVIEW_STARS_PER_MIN = int(os.environ.get('E2B_PREVIEW_STARS_PER_MIN', '1'))
PREVIEW_SERVICE_URL = os.environ.get('PREVIEW_SERVICE_URL', 'http://preview_service:8001')
PREVIEW_INTERNAL_TOKEN = os.environ.get('PREVIEW_INTERNAL_TOKEN', '')


# ========== API КЛЮЧИ ==========
LAOZHANG_API_KEY = os.environ.get('LAOZHANG_API_KEY', '')
LAOZHANG_API_URL = "https://api.laozhang.ai/v1"
SITEMAP_CACHE_TIMEOUT = 3600

# Веб-поиск (используется в call_web_search)
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY', '')  # tavily.com — 1000 req/month free

# Seedance (ByteDance video) — отдельный токен группы SeeDance2 на laozhang.ai
SEEDANCE_API_KEY = os.environ.get('SEEDANCE_API_KEY', '')

# APIMart — видео генерация (Sora, Veo, Kling и другие)
APIMART_API_KEY = os.environ.get('APIMART_API_KEY', '')
APIMART_API_URL = "https://api.apimart.ai/v1"


# ========== VIBE-CODING STUDIO ==========
STUDIO_SANDBOX_IMAGE = os.getenv('STUDIO_SANDBOX_IMAGE', 'aineron-sandbox:latest')
STUDIO_SANDBOX_NET = os.getenv('STUDIO_SANDBOX_NET', 'aineron_sandbox_net')
STUDIO_SANDBOX_MEM = os.getenv('STUDIO_SANDBOX_MEM', '512m')
STUDIO_SANDBOX_CPUS = float(os.getenv('STUDIO_SANDBOX_CPUS', '1'))
# Project Connector: Fernet key for encrypting PAT tokens (generate with Fernet.generate_key())
PROJECT_CONNECTOR_FERNET_KEY = os.getenv('PROJECT_CONNECTOR_FERNET_KEY', '')
PROJECT_AI_COMMITS = os.getenv('PROJECT_AI_COMMITS', '0') == '1'
# Sprint 4.1 — Vector RAG (pgvector) — по умолчанию выключен, лексика остаётся
PROJECT_VECTOR_RAG   = os.getenv('PROJECT_VECTOR_RAG',   '0') == '1'
PROJECT_EMBED_MODEL  = os.getenv('PROJECT_EMBED_MODEL',  'text-embedding-3-small')
PROJECT_EMBED_DIMS   = int(os.getenv('PROJECT_EMBED_DIMS', '1536'))
# Sprint 5.7 — RAG Quality (env-driven, rollback без деплоя)
PROJECT_SYNC_MAX_FILES = int(os.getenv('PROJECT_SYNC_MAX_FILES', '50'))
PROJECT_INJECT_LIMIT   = int(os.getenv('PROJECT_INJECT_LIMIT',   '200000'))
PROJECT_TOP_K          = int(os.getenv('PROJECT_TOP_K',          '6'))
PROJECT_CHUNK_SIZE     = int(os.getenv('PROJECT_CHUNK_SIZE',     '500'))
PROJECT_SMART_CHUNK    = os.getenv('PROJECT_SMART_CHUNK', '0') == '1'
# Sprint 5.3 — Knowledge intelligence
PROJECT_FILE_SEARCH  = os.getenv('PROJECT_FILE_SEARCH',  '0') == '1'
PROJECT_EMBED_CACHE  = os.getenv('PROJECT_EMBED_CACHE',  '0') == '1'
PROJECT_KB_METRICS   = os.getenv('PROJECT_KB_METRICS',   '0') == '1'
# Sprint 5.4 — Sync hardening
PROJECT_FILE_VERSIONS  = os.getenv('PROJECT_FILE_VERSIONS',  '0') == '1'
PROJECT_SYNC_POLLING   = os.getenv('PROJECT_SYNC_POLLING',   '0') == '1'
# Sprint 5.2 — Codebase intelligence
PROJECT_CODEBASE       = os.getenv('PROJECT_CODEBASE',       '0') == '1'
PROJECT_PR_PROPOSALS   = os.getenv('PROJECT_PR_PROPOSALS',   '0') == '1'
# Sprint 5.5 — Observability + public Spaces hardening
PROJECT_AUDIT_LOG        = os.getenv('PROJECT_AUDIT_LOG',        '0') == '1'
PROJECT_PUBLIC_HARDENING = os.getenv('PROJECT_PUBLIC_HARDENING', '1') == '1'  # on by default (security)
# Sprint 5.6 — Telegram upload to project knowledge base
PROJECT_TG_UPLOAD        = os.getenv('PROJECT_TG_UPLOAD',        '0') == '1'
# Sprint 6.1 — Hybrid Search (RRF) + Adaptive top_k + Conversation-aware
PROJECT_HYBRID_SEARCH    = os.getenv('PROJECT_HYBRID_SEARCH',    '0') == '1'
PROJECT_RRF_K            = int(os.getenv('PROJECT_RRF_K',        '60'))
PROJECT_ADAPTIVE_TOPK    = os.getenv('PROJECT_ADAPTIVE_TOPK',    '0') == '1'
PROJECT_CONV_SEARCH      = os.getenv('PROJECT_CONV_SEARCH',      '0') == '1'
PROJECT_CONV_WINDOW      = int(os.getenv('PROJECT_CONV_WINDOW',  '4'))
# Sprint 6.2 — Query Expansion
PROJECT_QUERY_EXPANSION  = os.getenv('PROJECT_QUERY_EXPANSION',  '0') == '1'
PROJECT_EXPAND_MODEL     = os.getenv('PROJECT_EXPAND_MODEL',     'gpt-4o-mini')
PROJECT_EXPAND_N         = int(os.getenv('PROJECT_EXPAND_N',     '3'))
# Sprint 6.3 — Reranking (Cross-Encoder, CPU)
PROJECT_RERANK           = os.getenv('PROJECT_RERANK',           '0') == '1'
PROJECT_RERANK_MODEL     = os.getenv('PROJECT_RERANK_MODEL',     'cross-encoder/ms-marco-MiniLM-L-6-v2')
PROJECT_RERANK_CANDIDATES= int(os.getenv('PROJECT_RERANK_CANDIDATES', '50'))
PROJECT_RERANK_TOPK      = int(os.getenv('PROJECT_RERANK_TOPK',  '15'))
# Sprint 6.4 — @file + @web явный контекст
PROJECT_FILE_PIN         = os.getenv('PROJECT_FILE_PIN',         '0') == '1'
PROJECT_WEB_SEARCH       = os.getenv('PROJECT_WEB_SEARCH',       '0') == '1'
# Sprint 6.5 — Two-Level Retrieval (File → Chunk)
PROJECT_TWO_LEVEL        = os.getenv('PROJECT_TWO_LEVEL',        '0') == '1'
PROJECT_TWO_LEVEL_FILES  = int(os.getenv('PROJECT_TWO_LEVEL_FILES', '5'))
# Sprint 7.1 — Встроенный редактор кода (Monaco/CodeMirror)
PROJECT_CODE_EDITOR      = os.getenv('PROJECT_CODE_EDITOR',      '0') == '1'
# Sprint 7.2 — Deploy-хук
PROJECT_DEPLOY_HOOK      = os.getenv('PROJECT_DEPLOY_HOOK',      '0') == '1'
INTERNAL_DEPLOY_ENABLED  = os.getenv('INTERNAL_DEPLOY_ENABLED',  '0') == '1'
INTERNAL_DEPLOY_SCRIPT   = os.getenv('INTERNAL_DEPLOY_SCRIPT',   '/app/deploy.sh')

STUDIO_GITEA_URL = os.getenv('STUDIO_GITEA_URL', 'http://gitea:3000')
STUDIO_GITEA_ADMIN_USER = os.getenv('STUDIO_GITEA_ADMIN_USER', 'studio_admin')
STUDIO_GITEA_ADMIN_TOKEN = os.getenv('STUDIO_GITEA_ADMIN_TOKEN', '')
STUDIO_MAX_ITERATIONS = int(os.getenv('STUDIO_MAX_ITERATIONS', '3'))
STUDIO_MAX_SANDBOXES_PER_USER = int(os.getenv('STUDIO_MAX_SANDBOXES_PER_USER', '5'))
STUDIO_VERCEL_TOKEN = os.getenv('STUDIO_VERCEL_TOKEN', '')
STUDIO_PROMPT_LANG = os.getenv('STUDIO_PROMPT_LANG', 'en')
STUDIO_STEP_STALL_SEC = int(os.getenv('STUDIO_STEP_STALL_SEC', '240'))
STUDIO_PIPELINE_MAX_SEC = int(os.getenv('STUDIO_PIPELINE_MAX_SEC', '2700'))
STUDIO_V3 = os.getenv('STUDIO_V3', '0') == '1'  # Studio V3 pipeline (FILE_BLOCKS, validators, EDIT blocks)

# ========== STUDIO V4 FLAGS (все по умолчанию выключены) ==========
STUDIO_V4_TOKEN_BILLING     = os.getenv('STUDIO_V4_TOKEN_BILLING',     '0') == '1'
STUDIO_V4_COMMITS_CACHE     = os.getenv('STUDIO_V4_COMMITS_CACHE',     '0') == '1'
STUDIO_V4_PROVIDER_FALLBACK = os.getenv('STUDIO_V4_PROVIDER_FALLBACK', '0') == '1'
STUDIO_V4_AUTOFIX           = os.getenv('STUDIO_V4_AUTOFIX',           '0') == '1'
STUDIO_V4_STREAMING         = os.getenv('STUDIO_V4_STREAMING',         '0') == '1'
STUDIO_V4_GUARDIAN_CONTEXT  = os.getenv('STUDIO_V4_GUARDIAN_CONTEXT',  '0') == '1'
STUDIO_V4_RU_STACK          = os.getenv('STUDIO_V4_RU_STACK',          '0') == '1'
STUDIO_V4_TMA               = os.getenv('STUDIO_V4_TMA',               '0') == '1'
STUDIO_MAX_AUTOFIX          = int(os.getenv('STUDIO_MAX_AUTOFIX',       '3'))
# Sprint 6: deprecate legacy Docker sandbox for frontend stacks (Sandpack handles react/vue/html/tma)
STUDIO_DEPRECATE_DOCKER_FRONTEND = os.getenv('STUDIO_DEPRECATE_DOCKER_FRONTEND', '1') == '1'
LAOZHANG_API_URL_FALLBACK   = os.getenv('LAOZHANG_API_URL_FALLBACK',   '')
GIGACHAT_API_URL            = os.getenv('GIGACHAT_API_URL',            '')
GIGACHAT_API_KEY            = os.getenv('GIGACHAT_API_KEY',            '')
TIMEWEB_API_TOKEN           = os.getenv('TIMEWEB_API_TOKEN',           '')
SELECTEL_ACCOUNT_ID         = os.getenv('SELECTEL_ACCOUNT_ID',         '')
SELECTEL_API_KEY            = os.getenv('SELECTEL_API_KEY',            '')
STUDIO_TMA_BOT_TOKEN        = os.getenv('STUDIO_TMA_BOT_TOKEN',        '')

# ========== TELEGRAM BOT ==========
TELEGRAM_BOT_ENABLED    = os.getenv('TELEGRAM_BOT_ENABLED',    '0') == '1'
TELEGRAM_BOT_TOKEN      = os.getenv('TELEGRAM_BOT_TOKEN',      '')
TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
TELEGRAM_BOT_USERNAME   = os.getenv('TELEGRAM_BOT_USERNAME',   'aineron_bot')
TELEGRAM_ADMIN_IDS      = [int(x) for x in os.getenv('TELEGRAM_ADMIN_IDS', '').split(',') if x.strip().isdigit()]

# Фиче-флаги Bot API 9.3+/10.1 (TELEGRAM_SUPREMACY_PLAN, S0).
# Каждая супер-фича включается отдельно и откатывается без деплоя кода.
TG_NATIVE_STREAMING    = os.getenv('TG_NATIVE_STREAMING',    '0') == '1'  # sendMessageDraft (S1)
TG_RICH_MESSAGES       = os.getenv('TG_RICH_MESSAGES',       '0') == '1'  # sendRichMessage (S1)
TG_STARS_SUBSCRIPTIONS = os.getenv('TG_STARS_SUBSCRIPTIONS', '0') == '1'  # подписки в Stars (S4)
TG_BUSINESS            = os.getenv('TG_BUSINESS',            '0') == '1'  # AI-секретарь (S5)
TG_AFFILIATE           = os.getenv('TG_AFFILIATE',           '0') == '1'  # партнёрская программа (S4)
TG_GIFTS               = os.getenv('TG_GIFTS',               '0') == '1'  # подарки за активность (S4)
TG_TOPICS              = os.getenv('TG_TOPICS',              '0') == '1'  # топики-проекты в личке (S7)
TG_MANAGED_BOTS        = os.getenv('TG_MANAGED_BOTS',        '0') == '1'  # персональные боты (S8)
TG_STYLED_BUTTONS      = os.getenv('TG_STYLED_BUTTONS',      '0') == '1'  # icon_custom_emoji_id (S1, нужен Premium)
# Бюджет подарков: максимум Stars в месяц с баланса бота (S4)
TG_GIFTS_MONTHLY_BUDGET_STARS = int(os.getenv('TG_GIFTS_MONTHLY_BUDGET_STARS', '500'))
# Курс XTR→копейки: сколько копеек начисляется за 1 звезду Telegram Stars.
# Единая точка пересмотра при изменении цен Telegram (S4). 1 XTR = 2 ₽ = 200 коп.
TG_XTR_RATE_KOPECKS = int(os.getenv('TG_XTR_RATE_KOPECKS', '200'))
# AI-задачи (S2): дневной cap исполнений на пользователя — защита юнит-экономики
AITASK_DAILY_CAP = int(os.getenv('AITASK_DAILY_CAP', '30'))
# Deep Research (S3): фиксированная цена запуска в боте, копейки (10 ₽)
RESEARCH_PRICE_KOPECKS = int(os.getenv('RESEARCH_PRICE_KOPECKS', '1000'))
# AI-секретарь (S5): цена ответа сверх лимита тарифа «Бизнес», копейки (1 ₽)
BUSINESS_REPLY_PRICE_KOPECKS = int(os.getenv('BUSINESS_REPLY_PRICE_KOPECKS', '100'))
# Сколько авто-ответов в месяц включено в тариф «Бизнес»
BUSINESS_TARIFF_ALLOWANCE = int(os.getenv('BUSINESS_TARIFF_ALLOWANCE', '300'))


# ========== БИЛЛИНГ (единый рублёвый баланс, копейки) ==========
# Инвариант: 1 звезда (legacy) = 1 рубль = 100 копеек. См. src/core/money.py и BILLING_MIGRATION_PLAN.md
MIN_CHARGE_KOPECKS = int(os.environ.get('MIN_CHARGE_KOPECKS', '10'))  # 0,10 ₽ минимальное списание
ORG_KOPECKS_PER_STAR = int(os.environ.get('ORG_KOPECKS_PER_STAR', '100'))  # унифицировано с MIN_CHARGE: 1 звезда = 100 коп


# ========== ROBOKASSA ==========
ROBOKASSA_LOGIN = os.environ.get('ROBOKASSA_LOGIN', 'aineron.ru')
ROBOKASSA_PASS1 = os.environ.get('ROBOKASSA_PASS1', '')
ROBOKASSA_PASS2 = os.environ.get('ROBOKASSA_PASS2', '')
ROBOKASSA_TEST_MODE = int(os.environ.get('ROBOKASSA_TEST_MODE', 0))


# ========== ОБРАБОТЧИК 404 ==========
handler404 = 'landing.views.custom_404_view'


# ========== ДРУГИЕ НАСТРОЙКИ ==========
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUDIO_DIR = os.path.join(MEDIA_ROOT, 'audio')
SESSION_ENGINE = 'django.contrib.sessions.backends.db'


# ========== DJANGO REST FRAMEWORK ==========
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.authentication.APIKeyAuthentication',
        # S6: JWT из Mini App (telegram_webapp_auth выдаёт simplejwt-токены)
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'api.authentication.CsrfExemptSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
    'DEFAULT_THROTTLE_CLASSES': [
        'api.throttling.APIKeyRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'api_key': '120/min',
        'public_space': '60/min',
    },
    'EXCEPTION_HANDLER': 'api.exceptions.openai_exception_handler',
}


# ========== CORS ==========
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://frontend:3000',
    'https://aineron.ru',
    'https://www.aineron.ru',
]
CORS_ALLOW_CREDENTIALS = True
# Allow CORS on /api/ (for external devs) and /users/api/ (for Next.js web-auth calls)
CORS_URLS_REGEX = r'^/(api|users/api)/.*$'


# ========== DRF SPECTACULAR ==========
SPECTACULAR_SETTINGS = {
    'TITLE': 'aineron.ru API',
    'DESCRIPTION': 'OpenAI-совместимый API для доступа к нейросетям без VPN',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
        'displayRequestDuration': True,
    },
}


# ========== LOGGING ==========
LOGGING = {
    'version': 1,
    'disable_existing_handlers': False,
    'formatters': {
        'studio': {
            'format': '[%(asctime)s] %(levelname)s %(name)s: %(message)s',
            'datefmt': '%H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'studio',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'studio.agents': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'studio.tasks': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}