# wallet/admin.py
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import WithdrawalRequest, UserWallet
from .services import initiate_razorpay_payout, PayoutServiceError # Import service

@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'withdrawable_balance', 'locked_balance', 'total_balance', 'last_updated')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'last_updated', 'total_balance') # User should not be changed here
    list_select_related = ('user',) # Optimize query

    def user_link(self, obj):
        link = reverse("admin:custom_user_customuser_change", args=[obj.user.id]) # Adjust if user model path is different
        return format_html('<a href="{}">{}</a>', link, obj.user.username)
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__username'

    # Optional: Action to recalculate balances if needed (use with caution)
    # def recalculate_balances(self, request, queryset): ...

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = (
        'request_id',
        'user_link',
        'amount',
        'method_display', # Use display name
        'status_display', # Use display name
        'requested_at',
        'processed_at',
        'processed_by_link', # Link to admin user
        'razorpay_payout_id_link',
    )
    list_filter = ('status', 'method', 'requested_at')
    search_fields = ('user__username', 'user__email', 'request_id__iexact', 'razorpay_payout_id__iexact')
    date_hierarchy = 'requested_at'
    list_select_related = ('user', 'processed_by') # Optimize query

    # Make most fields readonly in detail view, focus on actions
    readonly_fields = (
        'request_id', 'user_link', 'amount', 'method', 'requested_at',
        'status_display_colored', # Show colored status
        'razorpay_contact_id', 'razorpay_fund_account_id',
        'processed_at', 'processed_by_link',
        'razorpay_payout_id_link', 'razorpay_payout_status'
    )
    # Fields to display in detail view, allowing rejection_reason editing if status is REJECTED/FAILED
    fields = (
        'request_id', 'user_link', 'amount', 'method', 'requested_at',
        'status_display_colored', # Use custom method below
        'razorpay_contact_id', 'razorpay_fund_account_id',
        'processed_at', 'processed_by_link',
        'razorpay_payout_id_link', 'razorpay_payout_status',
        'rejection_reason', # Allow editing reason
    )

    actions = ['approve_selected_requests', 'reject_selected_requests']

    # Custom display methods
    def user_link(self, obj):
        link = reverse("admin:custom_user_customuser_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', link, obj.user.username)
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__username'

    def processed_by_link(self, obj):
        if not obj.processed_by: return "-"
        link = reverse("admin:custom_user_customuser_change", args=[obj.processed_by.id])
        return format_html('<a href="{}">{}</a>', link, obj.processed_by.username)
    processed_by_link.short_description = _('Processed By')
    processed_by_link.admin_order_field = 'processed_by__username'

    def razorpay_payout_id_link(self, obj):
        if obj.razorpay_payout_id:
             # Replace with your actual Razorpay dashboard URL structure if known
             # url = f"https://dashboard.razorpay.com/app/payouts/{obj.razorpay_payout_id}"
             # return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, obj.razorpay_payout_id)
             return obj.razorpay_payout_id
        return "-"
    razorpay_payout_id_link.short_description = _('Rzp Payout ID')
    razorpay_payout_id_link.admin_order_field = 'razorpay_payout_id'

    def status_display(self, obj):
         return obj.get_status_display()
    status_display.short_description = _('Status')
    status_display.admin_order_field = 'status'

    def method_display(self, obj):
         return obj.get_method_display()
    method_display.short_description = _('Method')
    method_display.admin_order_field = 'method'

    def status_display_colored(self, obj):
         # Show colored status in detail view
         status_val = obj.status
         display_text = obj.get_status_display()
         color = 'black'
         if status_val == WithdrawalRequest.StatusChoices.PENDING: color = 'orange'
         elif status_val == WithdrawalRequest.StatusChoices.APPROVED: color = 'blue'
         elif status_val == WithdrawalRequest.StatusChoices.PROCESSING: color = 'purple'
         elif status_val == WithdrawalRequest.StatusChoices.COMPLETED: color = 'green'
         elif status_val in [WithdrawalRequest.StatusChoices.REJECTED, WithdrawalRequest.StatusChoices.FAILED]: color = 'red'
         elif status_val == WithdrawalRequest.StatusChoices.CANCELLED: color = 'grey'
         return format_html('<b style="color: {};">{}</b>', color, display_text)
    status_display_colored.short_description = _('Current Status')


    # Allow editing rejection_reason only if status allows it
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        # Allow editing rejection_reason unless status is Pending/Approved/Processing/Completed
        if obj and obj.status in [
            WithdrawalRequest.StatusChoices.PENDING,
            WithdrawalRequest.StatusChoices.APPROVED,
            WithdrawalRequest.StatusChoices.PROCESSING,
            WithdrawalRequest.StatusChoices.COMPLETED,
        ]:
            if 'rejection_reason' not in readonly:
                readonly.append('rejection_reason')
        elif 'rejection_reason' in readonly:
             # Allow editing if status is Rejected/Failed/Cancelled etc.
             try:
                  readonly.remove('rejection_reason')
             except ValueError: pass # Already removed
        return readonly


    # --- Admin Actions ---
    @admin.action(description=_('Approve selected pending requests'))
    def approve_selected_requests(self, request, queryset):
        approved_count = 0
        failed_count = 0
        already_processed = 0
        admin_user = request.user

        # Process only PENDING requests from the selection
        pending_requests = queryset.filter(status=WithdrawalRequest.StatusChoices.PENDING)

        if not pending_requests.exists():
            self.message_user(request, _("No pending requests selected."), messages.WARNING)
            return

        for req in pending_requests:
            try:
                with transaction.atomic():
                    # Lock request and wallet
                    req_locked = WithdrawalRequest.objects.select_for_update().get(pk=req.pk)
                    wallet_locked = UserWallet.objects.select_for_update().get(user=req_locked.user)
                    amount_decimal = req_locked.amount

                    # Final status check inside transaction
                    if req_locked.status != WithdrawalRequest.StatusChoices.PENDING:
                        already_processed += 1
                        continue

                    # Mark as approved first
                    req_locked.status = WithdrawalRequest.StatusChoices.APPROVED
                    req_locked.processed_by = admin_user
                    req_locked.processed_at = timezone.now()
                    req_locked.rejection_reason = None
                    req_locked.save() # Save approval state

                    # --- Initiate Payout ---
                    try:
                         payout_initiated = initiate_razorpay_payout(req_locked)

                         if payout_initiated:
                             # Service updated status, confirm wallet deduction
                             wallet_locked.locked_balance = F('locked_balance') - amount_decimal
                             wallet_locked.save()
                             approved_count += 1
                         else:
                              # Service failed, set status to FAILED, rollback wallet
                             wallet_locked.locked_balance = F('locked_balance') - amount_decimal
                             wallet_locked.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                             wallet_locked.save()
                             failed_count += 1
                             # Reason should be set by the service
                    except PayoutServiceError as service_err:
                         # Critical error in service during payout initiation
                         messages.error(request, f"Service Error for Req {req_locked.request_id}: {service_err}")
                         # Rollback wallet and mark as failed
                         req_locked.status = WithdrawalRequest.StatusChoices.FAILED
                         req_locked.rejection_reason = f"Admin Approval Error: {service_err}"
                         req_locked.save() # Save failure status
                         wallet_locked.locked_balance = F('locked_balance') - amount_decimal
                         wallet_locked.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                         wallet_locked.save()
                         failed_count += 1
                    except Exception as payout_err:
                         # Unexpected error during payout call
                         messages.error(request, f"Unexpected Payout Error for Req {req_locked.request_id}: {payout_err}")
                         req_locked.status = WithdrawalRequest.StatusChoices.FAILED
                         req_locked.rejection_reason = f"Unexpected Admin Error: {payout_err}"
                         req_locked.save()
                         wallet_locked.locked_balance = F('locked_balance') - amount_decimal
                         wallet_locked.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                         wallet_locked.save()
                         failed_count += 1

            except (UserWallet.DoesNotExist, WithdrawalRequest.DoesNotExist):
                 failed_count += 1
                 messages.error(request, _("Error finding wallet or request during processing."))
            except Exception as e:
                failed_count += 1
                messages.error(request, _("Unexpected error during approval transaction: {}").format(e))

        # --- Report Results ---
        if approved_count:
             self.message_user(request, _("{} request(s) approved and payout initiated/processed.").format(approved_count), messages.SUCCESS)
        if failed_count:
            self.message_user(request, _("{} request(s) failed during approval/payout. Check individual requests for reasons.").format(failed_count), messages.ERROR)
        if already_processed:
            self.message_user(request, _("{} selected request(s) were already processed.").format(already_processed), messages.WARNING)


    @admin.action(description=_('Reject selected pending requests'))
    def reject_selected_requests(self, request, queryset):
        # Using a generic reason for bulk action. Admins can edit individually.
        rejection_reason = _("Rejected via admin bulk action.")
        rejected_count = 0
        already_processed = 0
        admin_user = request.user

        pending_requests = queryset.filter(status=WithdrawalRequest.StatusChoices.PENDING)

        if not pending_requests.exists():
             self.message_user(request, _("No pending requests selected."), messages.WARNING)
             return

        for req in pending_requests:
            try:
                with transaction.atomic():
                    req_locked = WithdrawalRequest.objects.select_for_update().get(pk=req.pk)
                    wallet_locked = UserWallet.objects.select_for_update().get(user=req_locked.user)
                    amount_decimal = req_locked.amount

                    if req_locked.status != WithdrawalRequest.StatusChoices.PENDING:
                        already_processed += 1
                        continue

                    # Update status
                    req_locked.status = WithdrawalRequest.StatusChoices.REJECTED
                    req_locked.rejection_reason = rejection_reason
                    req_locked.processed_by = admin_user
                    req_locked.processed_at = timezone.now()
                    req_locked.save()

                    # Unlock funds
                    wallet_locked.locked_balance = F('locked_balance') - amount_decimal
                    wallet_locked.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                    wallet_locked.save()

                    rejected_count += 1

            except (UserWallet.DoesNotExist, WithdrawalRequest.DoesNotExist):
                 messages.error(request, _("Error finding wallet or request during rejection."))
            except Exception as e:
                 messages.error(request, _("Unexpected error rejecting request {}: {}").format(req.request_id, e))

        if rejected_count:
            self.message_user(request, _("{} request(s) rejected. Edit individually to provide specific reasons if needed.").format(rejected_count), messages.SUCCESS)
        if already_processed:
             self.message_user(request, _("{} selected request(s) were already processed.").format(already_processed), messages.WARNING)