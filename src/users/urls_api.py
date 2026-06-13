from django.urls import path, include
from . import views

app_name = 'users_api'

urlpatterns = [
    # ========== AJAX API АУТЕНТИФИКАЦИИ ==========
    path('ajax/login/', views.ajax_login, name='ajax_login'),
    path('ajax/register/', views.ajax_register, name='ajax_register'),
    path('ajax/logout/', views.ajax_logout, name='ajax_logout'),
    path('ajax/password-reset/', views.ajax_password_reset, name='ajax_password_reset'),

    # ========== ВЕРИФИКАЦИЯ EMAIL ==========
    path('ajax/verify-email/', views.ajax_verify_email_code, name='ajax_verify_email_code'),
    path('ajax/resend-verification/', views.resend_verification_email, name='resend_verification_email'),
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('verify-email/', views.verify_email_page, name='verify_email_page'),

    # ========== ТАРИФЫ И ПОДПИСКИ ==========
    path('tariffs/', views.get_tariffs, name='get_tariffs'),
    path('create-payment/', views.create_robokassa_payment, name='create_payment'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-fail/', views.payment_fail, name='payment_fail'),

    # ========== ПОКУПКА ЗВЕЗД ==========
    path('page-settings/', views.get_page_sale_settings, name='page_sale_settings'),
    path('buy-pages/', views.buy_pages, name='buy_pages'),  # Добавляем эту строку

    # ========== ПРОВЕРКА СТАТУСА ==========
    path('auth-status/', views.check_auth_status, name='check_auth_status'),
    path('check-email/', views.check_email_exists, name='check_email_exists'),
    path('subscription-status/', views.get_subscription_status, name='subscription_status'),

    # ========== УПРАВЛЕНИЕ ПОДПИСКОЙ ==========
    path('update-auto-renewal/', views.update_auto_renewal, name='update_auto_renewal'),
    path('send-renewal-code/', views.send_renewal_confirmation_code, name='send_renewal_code'),
    path('verify-renewal-code/', views.verify_renewal_code, name='verify_renewal_code'),
    path('resend-renewal-code/', views.resend_renewal_code, name='resend_renewal_code'),

    # ========== ALLAUTH (СОЦИАЛЬНЫЕ СЕТИ) ==========
    path('auth/', include('allauth.urls')),

    # ========== Активация промокодов ==========
    path('apply-promo/', views.apply_promo_code, name='apply_promo'),

    # ========== Получаем данные из профиля ==========
    path('profile-data/', views.profile_data, name='profile_data'),

    # ========== Вывод средств из партнерской программы ==========
    path('request-withdrawal/', views.request_withdrawal, name='request_withdrawal'),
]