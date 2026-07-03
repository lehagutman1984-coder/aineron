from rest_framework import serializers
from users.models import Tariff, PaymentHistory, PageSaleSettings, UserSubscription


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = [
            'id', 'display_name', 'pages_count', 'balance_grant_kopecks', 'price',
            'is_free', 'is_trial', 'duration_days',
        ]


class UserSubscriptionSerializer(serializers.ModelSerializer):
    tariff = TariffSerializer(read_only=True)
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'tariff', 'started_at', 'expires_at', 'is_active',
            'auto_renew', 'status', 'next_payment_date', 'days_left',
        ]

    def get_days_left(self, obj):
        return obj.days_until_expiration()


class PaymentHistorySerializer(serializers.ModelSerializer):
    tariff_name = serializers.SerializerMethodField()

    class Meta:
        model = PaymentHistory
        fields = [
            'id', 'payment_type', 'invoice_id', 'amount', 'amount_kopecks',
            'pages_count', 'status', 'description',
            'tariff_name', 'paid_at', 'created_at',
        ]

    def get_tariff_name(self, obj):
        return obj.tariff.display_name if obj.tariff else None


class PageSaleSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageSaleSettings
        fields = ['price_per_page', 'min_pages_for_purchase', 'max_pages_for_purchase', 'is_active']
