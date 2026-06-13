from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from aitext.models import Chat
from users.models import Tariff, SiteSettings
from aitext.views import get_faqs_for_page
from blog.models import Post

def custom_404_view(request, exception):
    """Кастомная страница 404"""
    return render(request, 'neuro/404.html', status=404)


def api_docs(request):
    """Документация API для разработчиков"""
    return render(request, 'neuro/api_docs.html')


def ide_integrations(request):
    """Гайды по интеграции с IDE (Cursor, Cline, Continue)"""
    return render(request, 'neuro/ide_integrations.html')


def index(request):
    """Главная страница"""
    # Обработка реферального параметра
    ref = request.GET.get('ref')
    if ref:
        request.session['ref_code'] = ref

    user_chats = []
    current_chat_id = None
    trial_tariff = None
    if request.user.is_authenticated:
        user_chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related('messages').order_by('-updated_at')[:15]
        if not request.user.active_subscription or request.user.tariff.is_free:
            trial_tariff = Tariff.objects.filter(is_trial=True, is_active=True).first()
    faqs = get_faqs_for_page()
    news_posts = Post.objects.filter(is_published=True, show_on_main=True).order_by('-published_at')[:3]
    site_settings = SiteSettings.get_settings()
    return render(request, 'neuro/index.html', {
        'user_chats': user_chats,
        'current_chat_id': current_chat_id,
        'trial_tariff': trial_tariff,
        'faqs': faqs,
        'news_posts': news_posts,
        'site_settings': site_settings,
    })