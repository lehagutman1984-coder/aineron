from rest_framework import serializers
from teams.models import Organization, OrganizationMember, OrganizationInvite, Invoice


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'inn', 'kpp', 'legal_address',
            'balance_rub', 'member_count', 'user_role', 'created_at',
        ]
        read_only_fields = ['id', 'balance_rub', 'member_count', 'user_role', 'created_at']

    def get_member_count(self, obj):
        return obj.members.count()

    def get_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            return obj.members.get(user=request.user).role
        except OrganizationMember.DoesNotExist:
            return None


class OrganizationMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = OrganizationMember
        fields = ['id', 'user_id', 'email', 'username', 'role', 'created_at']
        read_only_fields = ['id', 'user_id', 'email', 'username', 'created_at']


class OrganizationInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationInvite
        fields = ['id', 'email', 'token', 'expires_at', 'is_accepted', 'created_at']
        read_only_fields = ['id', 'token', 'expires_at', 'is_accepted', 'created_at']


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ['id', 'number', 'amount_rub', 'status', 'description', 'created_at', 'paid_at']
        read_only_fields = ['id', 'number', 'status', 'created_at', 'paid_at']
