# wallet/serializers.py
from rest_framework import serializers
from .models import UserWallet, WithdrawalRequest

class UserWalletSerializer(serializers.ModelSerializer):
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = UserWallet
        fields = ['withdrawable_balance', 'locked_balance', 'total_balance', 'last_updated']
        read_only_fields = ['locked_balance', 'total_balance', 'last_updated']

class WithdrawalRequestSerializer(serializers.ModelSerializer):
    # Use SlugRelatedField for readable user representation, or just return ID
    username = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = [
            'request_id',
            'username', # Added for context
            'amount',
            'status',
            'status_display', # Human-readable status
            'method',
            'method_display', # Human-readable method
            'requested_at',
            'processed_at',
            'rejection_reason', # Show if rejected
            'razorpay_payout_id', # Show for tracking
            'razorpay_payout_status',
        ]
        read_only_fields = fields # History is read-only