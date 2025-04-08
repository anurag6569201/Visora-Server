# wallet/serializers.py
import decimal
import re
from rest_framework import serializers
from django.db import transaction
# from django.utils import timezone # Not needed for ID simulation anymore
from django.contrib.auth import get_user_model
from .models import UserWallet, WithdrawalRequest

User = get_user_model()

# --- UserWalletSerializer unchanged ---
class UserWalletSerializer(serializers.ModelSerializer):
    withdrawable_balance = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    locked_balance = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    class Meta:
        model = UserWallet
        fields = ['withdrawable_balance', 'locked_balance']
        read_only_fields = fields

# --- WithdrawalHistorySerializer unchanged ---
class WithdrawalHistorySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, coerce_to_string=True)
    class Meta:
        model = WithdrawalRequest
        fields = [
            'request_id', 'amount', 'status', 'status_display', 'method',
            'method_display', 'requested_at', 'processed_at', 'rejection_reason',
            'razorpay_payout_id', 'razorpay_payout_status',
        ]
        read_only_fields = fields

# --- Detail Serializers (UPI/Bank) unchanged ---
class यूपीIDetailSerializer(serializers.Serializer):
    upi_id = serializers.CharField(max_length=100, required=True)
    def validate_upi_id(self, value):
        if not value or '@' not in value or len(value.split('@')[0]) == 0 or len(value.split('@')[1]) < 2 :
             raise serializers.ValidationError("Invalid UPI ID format. Expected format: username@bank")
        return value.strip()

class BankDetailSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=True)
    account_number = serializers.CharField(max_length=50, required=True)
    ifsc = serializers.CharField(max_length=11, min_length=11, required=True)
    def validate_ifsc(self, value):
        if not value: raise serializers.ValidationError("IFSC code is required.")
        value = value.strip().upper()
        if len(value) != 11: raise serializers.ValidationError("IFSC code must be 11 characters long.")
        if not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", value):
             raise serializers.ValidationError("Invalid IFSC code format. Expected format: ABCD0123456")
        return value
    def validate_name(self, value):
        if not value or not value.strip(): raise serializers.ValidationError("Beneficiary name cannot be empty.")
        return value.strip()
    def validate_account_number(self, value):
        if not value or not value.strip() or not value.strip().isdigit():
            raise serializers.ValidationError("Account number must contain only digits and cannot be empty.")
        return value.strip()

# --- WithdrawalCreateSerializer (MODIFIED) ---
class WithdrawalCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=decimal.Decimal('1.00'))
    method = serializers.ChoiceField(choices=WithdrawalRequest.MethodChoices.choices)
    details = serializers.JSONField()

    def validate(self, attrs):
        method = attrs.get('method')
        details_data = attrs.get('details')
        if not isinstance(details_data, dict):
            raise serializers.ValidationError({"details": "Payout details must be an object."})

        if method == WithdrawalRequest.MethodChoices.UPI:
            detail_serializer = यूपीIDetailSerializer(data=details_data)
        elif method == WithdrawalRequest.MethodChoices.BANK:
            detail_serializer = BankDetailSerializer(data=details_data)
        else:
            raise serializers.ValidationError({"method": "Invalid payout method selected."})

        if not detail_serializer.is_valid():
            raise serializers.ValidationError({"details": detail_serializer.errors})

        # No longer need 'validated_details' explicitly stored if not used elsewhere
        # attrs['validated_details'] = detail_serializer.validated_data
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        amount = validated_data['amount']
        method = validated_data['method']
        # 'details' were validated but we don't need to pass them to the model now

        # 1. Get Wallet & Check Balance
        wallet, created = UserWallet.objects.select_for_update().get_or_create(user=user)
        if wallet.withdrawable_balance < amount:
            raise serializers.ValidationError(
                f"Withdrawal amount (₹{amount:.2f}) exceeds available balance (₹{wallet.withdrawable_balance:.2f})."
            )

        # 2. **REMOVED**: Simulation/Placeholder for Razorpay Contact/Fund Account Creation

        # 3. Update Wallet Balance (Lock Funds)
        wallet.withdrawable_balance -= amount
        wallet.locked_balance += amount
        wallet.save()

        # 4. Create Withdrawal Request (without simulated Razorpay IDs)
        withdrawal_request = WithdrawalRequest.objects.create(
            user=user,
            amount=amount,
            method=method,
            status=WithdrawalRequest.StatusChoices.PENDING,
            # razorpay_contact_id=None, # Fields will be null by default
            # razorpay_fund_account_id=None,
        )
        return withdrawal_request