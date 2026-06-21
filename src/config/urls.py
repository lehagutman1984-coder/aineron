from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.contrib.sitemaps.views import sitemap
from aitext.sitemaps import NeuralNetworkSitemap
from blog.sitemaps import PostSitemap
from landing.sitemaps import StaticViewSitemap

urlpatterns = [
    # ========== СТАТИЧЕСКИЕ ФАЙЛЫ ==========
    path("robots.txt", serve, {
        "path": "robots.txt",
        "document_root": settings.BASE_DIR / "static"
    }),
    # Sitemap
    path('sitemap.xml', sitemap, {'sitemaps': {
        'neural-networks': NeuralNetworkSitemap,
        'posts': PostSitemap,
        'static': StaticViewSitemap,
    }}, name='django.contrib.sitemaps.views.sitemap'),

    # ========== АДМИНКА ==========
    path('admin/', admin.site.urls),

    # ========== API ЭНДПОИНТЫ (БЕЗ ПРЕФИКСА) ==========
    path('users/api/', include('users.urls_api')),

    # ========== ALLAUTH ==========
    path('accounts/', include('allauth.urls')),
    path('aitext/', include('aitext.urls')),

    # ========== DEV API ==========
    path('api/', include('api.urls', namespace='api')),

    # ========== СТРАНИЦЫ ПОЛЬЗОВАТЕЛЕЙ ==========
    # ОДИН РАЗ! Включаем сюда и страницу auth, и blocked
    path('users/pages/', include('users.urls_pages')),

    # ========== ЛЕНДИНГ И ГЛАВНАЯ ==========
    #path('generate/', include('generate.urls')),
    path('', include('landing.urls')),

]

# ========== ОБСЛУЖИВАНИЕ МЕДИА И СТАТИКИ ==========
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
        re_path(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
    ]

# ========== TELEGRAM BOT WEBHOOK ==========
if settings.TELEGRAM_BOT_ENABLED:
    from telegram_bot import views as tg_views
    urlpatterns += [path('telegram/webhook/', tg_views.telegram_webhook, name='telegram_webhook')]

# ========== ОБРАБОТЧИК 404 ==========
handler404 = 'landing.views.custom_404_view'
