from django.urls import path
from . import views

app_name = 'users_pages'

urlpatterns = [
    # Обрабатывает сторону неудачного платежа (ставит payment.status='failed', редиректит на /payment-fail/)
    path('payment-fail/', views.payment_fail_page, name='payment_fail_page'),
]
