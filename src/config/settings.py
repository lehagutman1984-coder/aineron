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
ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS',
    'aineron.ru www.aineron.ru localhost 127.0.0.1'
).split()


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
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

    'users.apps.UsersConfig',
    'landing.apps.LandingConfig',
    'aitext',
    'blog',

    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'api',
    'teams',
    'studio',
]


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
}


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
STUDIO_GITEA_URL = os.getenv('STUDIO_GITEA_URL', 'http://gitea:3000')
STUDIO_GITEA_ADMIN_USER = os.getenv('STUDIO_GITEA_ADMIN_USER', 'studio_admin')
STUDIO_GITEA_ADMIN_TOKEN = os.getenv('STUDIO_GITEA_ADMIN_TOKEN', '')
STUDIO_MAX_ITERATIONS = int(os.getenv('STUDIO_MAX_ITERATIONS', '3'))
STUDIO_MAX_SANDBOXES_PER_USER = int(os.getenv('STUDIO_MAX_SANDBOXES_PER_USER', '5'))
STUDIO_VERCEL_TOKEN = os.getenv('STUDIO_VERCEL_TOKEN', '')
STUDIO_PROMPT_LANG = os.getenv('STUDIO_PROMPT_LANG', 'en')
STUDIO_STEP_STALL_SEC = int(os.getenv('STUDIO_STEP_STALL_SEC', '240'))
STUDIO_PIPELINE_MAX_SEC = int(os.getenv('STUDIO_PIPELINE_MAX_SEC', '2700'))


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