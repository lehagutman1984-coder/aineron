from .models import SiteCounter
from .models import CustomUser
from .models import SiteSettings
from django.contrib.sites.models import Site

def current_site(request):
    return {'site': Site.objects.get_current()}

def site_counter(request):
    """Добавляет счетчик сайта во все шаблоны"""
    try:
        counter = SiteCounter.objects.first()
    except:
        counter = None

    return {
        'site_counter': counter
    }

def user_balance(request):
    """Добавляет баланс пользователя во все шаблоны"""
    balance = 0
    if request.user.is_authenticated:
        balance = request.user.pages_count
    return {'user_balance': balance}

def site_settings(request):
    settings = SiteSettings.get_settings()
    return {
        'inn': settings.inn,
        'vk_url': settings.vk_url,
        'telegram_url': settings.telegram_url,
        'blog_title': settings.blog_title,
        'blog_description': settings.blog_description,
        'blog_keywords': settings.blog_keywords,
        'catalog_title': settings.catalog_title,
        'catalog_description': settings.catalog_description,
        'catalog_keywords': settings.catalog_keywords,
    }