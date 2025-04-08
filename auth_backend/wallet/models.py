# wallet/models.py
import uuid
import decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

class UserWallet(models.Model):
    """
    Stores user balance information.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='userwallet'
    )
    # Balance available for withdrawal
    withdrawable_balance = models.DecimalField(
        _("Withdrawable Balance"),
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    # Balance locked pending withdrawal approval
    locked_balance = models.DecimalField(
        _("Locked Balance"),
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Wallet")
        verbose_name_plural = _("User Wallets")

    def __str__(self):
        return f"{self.user.username}'s Wallet"

    @property
    def total_balance(self):
        return self.withdrawable_balance + self.locked_balance

class WithdrawalRequest(models.Model):
    """
    Tracks user withdrawal requests, admin approval, and Razorpay payout status.
    """
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', _('Pending Approval')
        APPROVED = 'approved', _('Approved (Processing Payout)') # Admin approved, Payout initiated
        REJECTED = 'rejected', _('Rejected') # Admin rejected
        PROCESSING = 'processing', _('Processing (Razorpay)') # Razorpay status
        COMPLETED = 'completed', _('Completed') # Razorpay status: processed
        FAILED = 'failed', _('Failed') # Payout failed (Admin or Razorpay)
        CANCELLED = 'cancelled', _('Cancelled') # Optional: If user can cancel

    class MethodChoices(models.TextChoices):
        UPI = 'upi', _('UPI')
        BANK = 'bank', _('Bank Account')

    # Core Info
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT, # Don't delete request if user is deleted? Or SET_NULL?
        related_name='withdrawal_requests'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(decimal.Decimal('1.00'))] # Example minimum
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
        db_index=True
    )
    request_id = models.UUIDField( # Public facing ID
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        help_text=_("Unique identifier for this request")
    )
    method = models.CharField(
        max_length=10,
        choices=MethodChoices.choices
    )

    # Razorpay Pre-registration Info (Filled during request submission)
    razorpay_contact_id = models.CharField(max_length=50, blank=True, null=True)
    razorpay_fund_account_id = models.CharField(max_length=50, blank=True, null=True)

    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Timestamp when approved/rejected/processed")
    )

    # Admin Action Info
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_withdrawals',
        help_text=_("Admin user who approved/rejected")
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text=_("Reason if the request was rejected by admin")
    )

    # Razorpay Payout Info (Filled after approval & payout attempt)
    razorpay_payout_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True, # Can be null, but if set, must be unique
        db_index=True
    )
    razorpay_payout_status = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text=_("Status received from Razorpay (e.g., processing, reversed)")
    )

    class Meta:
        ordering = ['-requested_at']
        verbose_name = _("Withdrawal Request")
        verbose_name_plural = _("Withdrawal Requests")

    def __str__(self):
        return f"Withdrawal {self.request_id} by {self.user.username} for {self.amount} ({self.get_status_display()})"

    def get_display_details(self):
        # Method to get a user-friendly representation of payout method/destination
        # Requires fetching the actual Fund Account details from Razorpay if needed,
        # or store minimal masked details during request if absolutely necessary.
        # For now, just return the method.
        return self.get_method_display()