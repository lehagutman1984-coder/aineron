from rest_framework import serializers


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField()
    pages_count = serializers.IntegerField()
    active_subscription = serializers.BooleanField()
    referral_code = serializers.CharField()
    tariff_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_tariff_name(self, user):
        try:
            return user.tariff.name if user.tariff else ''
        except Exception:
            return ''

    def get_avatar(self, user):
        return f"https://ui-avatars.com/api/?name={user.email[0].upper()}&background=0a7cff&color=fff&size=64"
