from django.urls import path
from . import views

app_name = 'users_pages'

urlpatterns = [
    # ========== СТРАНИЦА БЛОКИРОВКИ ==========
    path('blocked/', views.blocked_page, name='blocked_page'),

    # ========== СТРАНИЦА ТАРИФОВ ==========
    path('payment-success/', views.payment_success_page, name='payment_success_page'),
    path('payment-fail/', views.payment_fail_page, name='payment_fail_page'),

    # ========== СТРАНИЦЫ Документов ==========
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    # ========== Профиль пользователя ==========
    path('profile/', views.profile_page, name='profile_page'),

    # ========== Партнерская программа ==========
    path('referral/', views.referral_page, name='referral_page'),
]