# wallet/admin.py
import logging
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from django.utils.html import format_html
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

from .models import WithdrawalRequest, UserWallet
# --- Import the service and exception ---
# Service function name is kept the same for compatibility, but its implementation is now simulation
from .services import initiate_razorpay_payout, PayoutServiceError

logger = logging.getLogger(__name__)
User = get_user_model()

@admin.register(UserWallet)
class UserWalletAdmin(admin.ModelAdmin):
    # ... (rest of UserWalletAdmin remains unchanged - see previous versions) ...
    list_display = ('user_link', 'withdrawable_balance', 'locked_balance', 'total_balance_display', 'last_updated')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'last_updated', 'total_balance_display')
    list_select_related = ('user',)

    def get_user_admin_url(self, user_id):
        """Helper to get the user change URL dynamically."""
        user_model_name = User._meta.model_name
        user_app_label = User._meta.app_label
        try:
            return reverse(f"admin:{user_app_label}_{user_model_name}_change", args=[user_id])
        except NoReverseMatch:
            logger.warning(f"Could not reverse admin URL for user model {user_app_label}.{user_model_name}")
            return None

    def user_link(self, obj):
        """Creates a link to the user's admin page."""
        url = self.get_user_admin_url(obj.user.id)
        if url:
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return obj.user.username
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__username'

    def total_balance_display(self, obj):
         return obj.total_balance
    total_balance_display.short_description = _('Total Balance')

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    # ... (most of WithdrawalRequestAdmin remains unchanged - display, filters, fields, etc.) ...
    list_display = (
        'request_id', 'user_link', 'amount', 'method_display',
        'status_display_colored_in_list', 'requested_at', 'processed_at',
        'processed_by_link', 'razorpay_payout_id_link',
    )
    list_filter = ('status', 'method', 'requested_at')
    search_fields = ('user__username', 'user__email', 'request_id__iexact', 'razorpay_payout_id__iexact')
    date_hierarchy = 'requested_at'
    list_select_related = ('user', 'processed_by')

    readonly_fields = (
        'request_id', 'user_link', 'amount', 'method', 'requested_at',
        'status_display_colored', 'razorpay_contact_id', 'razorpay_fund_account_id',
        'processed_at', 'processed_by_link',
        'razorpay_payout_id_link', 'razorpay_payout_status'
    )
    fields = (
        ('request_id', 'status_display_colored'), ('user_link', 'amount', 'method'),
        ('requested_at', 'processed_at', 'processed_by_link'),
        ('razorpay_contact_id', 'razorpay_fund_account_id'),
        ('razorpay_payout_id_link', 'razorpay_payout_status'),
        'rejection_reason',
    )

    actions = ['approve_selected_requests', 'reject_selected_requests']

    # --- Helper methods (get_user_admin_url, user_link, processed_by_link, etc. unchanged) ---
    def get_user_admin_url(self, user_id):
        user_model_name = User._meta.model_name
        user_app_label = User._meta.app_label
        try:
            return reverse(f"admin:{user_app_label}_{user_model_name}_change", args=[user_id])
        except NoReverseMatch: return None
    def user_link(self, obj):
        url = self.get_user_admin_url(obj.user.id)
        if url: return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return obj.user.username
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__username'
    def processed_by_link(self, obj):
        if not obj.processed_by: return "-"
        url = self.get_user_admin_url(obj.processed_by.id)
        if url: return format_html('<a href="{}">{}</a>', url, obj.processed_by.username)
        return obj.processed_by.username
    processed_by_link.short_description = _('Processed By')
    processed_by_link.admin_order_field = 'processed_by__username'
    def razorpay_payout_id_link(self, obj):
        if obj.razorpay_payout_id: return obj.razorpay_payout_id
        return "-"
    razorpay_payout_id_link.short_description = _('Rzp Payout ID')
    razorpay_payout_id_link.admin_order_field = 'razorpay_payout_id'
    def _get_status_color(self, status_val):
        color_map = {
            WithdrawalRequest.StatusChoices.PENDING: 'orange', WithdrawalRequest.StatusChoices.APPROVED: 'blue',
            WithdrawalRequest.StatusChoices.PROCESSING: 'purple', WithdrawalRequest.StatusChoices.COMPLETED: 'green',
            WithdrawalRequest.StatusChoices.REJECTED: 'red', WithdrawalRequest.StatusChoices.FAILED: 'darkred',
            WithdrawalRequest.StatusChoices.CANCELLED: 'grey',
        }
        return color_map.get(status_val, 'black')
    def status_display_colored_in_list(self, obj):
        color = self._get_status_color(obj.status)
        return format_html('<strong style="color: {};">{}</strong>', color, obj.get_status_display())
    status_display_colored_in_list.short_description = _('Status')
    status_display_colored_in_list.admin_order_field = 'status'
    def status_display_colored(self, obj):
        color = self._get_status_color(obj.status)
        return format_html('<strong style="color: {};">{}</strong>', color, obj.get_status_display())
    status_display_colored.short_description = _('Current Status')
    def method_display(self, obj):
        return obj.get_method_display()
    method_display.short_description = _('Method')
    method_display.admin_order_field = 'method'
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.status in [WithdrawalRequest.StatusChoices.REJECTED, WithdrawalRequest.StatusChoices.FAILED]:
            if 'rejection_reason' in readonly: readonly.remove('rejection_reason')
        elif 'rejection_reason' not in readonly: readonly.append('rejection_reason')
        return tuple(readonly)
    # --- End Helper Methods ---


    # --- Admin Actions ---
    @admin.action(description=_('Approve selected pending requests (Mark as Completed - DEMO)')) # Modified Description
    def approve_selected_requests(self, request, queryset):
        """Admin action to mark pending requests as completed (DEMO)."""
        approved_count = 0
        # failed_initiation removed as we are not initiating external payout
        failed_db = 0
        already_processed = 0
        admin_user = request.user

        pending_requests = queryset.filter(status=WithdrawalRequest.StatusChoices.PENDING)
        total_selected = queryset.count()
        total_pending = pending_requests.count()

        if not pending_requests.exists():
            msg = _("No PENDING requests selected.")
            if total_selected > 0: msg += _(" ({}) non-pending requests were ignored.").format(total_selected)
            self.message_user(request, msg, messages.WARNING)
            return

        for req in pending_requests:
            logger.info(f"Admin {admin_user.username} attempting to approve request {req.request_id} (DEMO)")
            try:
                with transaction.atomic():
                    req_locked = WithdrawalRequest.objects.select_for_update().get(pk=req.pk)
                    wallet_locked = UserWallet.objects.select_for_update().get(user=req_locked.user)
                    amount_decimal = req_locked.amount

                    if req_locked.status != WithdrawalRequest.StatusChoices.PENDING:
                        logger.warning(f"Request {req_locked.request_id} was already processed before lock.")
                        already_processed += 1
                        continue

                    # 1. Set intermediate "APPROVED" status before calling service
                    # This helps track intent if service fails unexpectedly later
                    req_locked.status = WithdrawalRequest.StatusChoices.APPROVED
                    req_locked.processed_by = admin_user
                    req_locked.processed_at = timezone.now() # Mark approval time
                    req_locked.rejection_reason = None
                    req_locked.save(update_fields=['status', 'processed_by', 'processed_at', 'rejection_reason']) # Save approved state

                    # 2. Call the simplified "payout" service (which now just marks COMPLETED)
                    try:
                        # Service now directly marks as COMPLETED and saves
                        simulation_successful = initiate_razorpay_payout(req_locked)

                        if simulation_successful:
                            logger.info(f"Simulated completion successful for {req_locked.request_id}.")
                            # 3. Update Wallet: Deduct from locked balance
                            wallet_locked.locked_balance = F('locked_balance') - amount_decimal
                            wallet_locked.save()
                            approved_count += 1
                        else:
                             # Should not happen with the simplified service unless DB error occurs inside it
                             logger.error(f"Simulated completion service returned False unexpectedly for {req_locked.request_id}.")
                             # Wallet remains locked, status remains APPROVED (or whatever service set before failing)
                             failed_db += 1 # Count as DB/system error

                    # Catch PayoutServiceError (though less likely now) or other exceptions from service
                    except (PayoutServiceError, Exception) as service_err:
                         logger.exception(f"Error during payout simulation service call for {req_locked.request_id}: {service_err}")
                         # Don't roll back wallet - funds are still locked, status is APPROVED (or FAILED if service set it)
                         # Just report the failure
                         failed_db += 1
                         messages.error(request, f"Error processing {req_locked.request_id}: {service_err}")

            # Handle errors finding the DB records or transaction issues
            except (UserWallet.DoesNotExist, WithdrawalRequest.DoesNotExist):
                 logger.error(f"DB Error: Could not find Wallet or Request for pk={req.pk} during approval.")
                 failed_db += 1
            except Exception as e:
                 logger.exception(f"Unexpected transaction/DB error during approval for {req.request_id}: {e}")
                 failed_db += 1

        # --- Report summary results to the admin ---
        if approved_count:
             # Modified success message for Demo
             self.message_user(request, _("{} request(s) approved and marked as completed (DEMO).").format(approved_count), messages.SUCCESS)
        if failed_db:
             self.message_user(request, _("{} request(s) failed processing due to database/system errors.").format(failed_db), messages.ERROR)

        processed_in_loop = approved_count + failed_db
        ignored_count = total_pending - processed_in_loop + already_processed
        if ignored_count > 0 :
             self.message_user(request, _("{} selected pending request(s) were not processed or already handled.").format(ignored_count), messages.WARNING)
        elif already_processed > 0:
             self.message_user(request, _("{} request(s) were already processed before action started.").format(already_processed), messages.WARNING)


    @admin.action(description=_('Reject selected pending requests'))
    def reject_selected_requests(self, request, queryset):
        """Admin action to reject pending requests and unlock funds."""
        # --- This action remains unchanged as it doesn't call external services ---
        rejection_reason = _("Rejected via admin bulk action.")
        rejected_count = 0
        failed_db = 0
        already_processed = 0
        admin_user = request.user

        pending_requests = queryset.filter(status=WithdrawalRequest.StatusChoices.PENDING)
        total_selected = queryset.count()

        if not pending_requests.exists():
            msg = _("No PENDING requests selected.")
            if total_selected > 0: msg += _(" ({}) non-pending requests were ignored.").format(total_selected)
            self.message_user(request, msg, messages.WARNING)
            return

        for req in pending_requests:
            logger.info(f"Admin {admin_user.username} attempting to reject request {req.request_id}")
            try:
                with transaction.atomic():
                    req_locked = WithdrawalRequest.objects.select_for_update().get(pk=req.pk)
                    wallet_locked = UserWallet.objects.select_for_update().get(user=req_locked.user)
                    amount_decimal = req_locked.amount

                    if req_locked.status != WithdrawalRequest.StatusChoices.PENDING:
                        logger.warning(f"Request {req_locked.request_id} was already processed before reject lock.")
                        already_processed += 1
                        continue

                    req_locked.status = WithdrawalRequest.StatusChoices.REJECTED
                    req_locked.rejection_reason = rejection_reason
                    req_locked.processed_by = admin_user
                    req_locked.processed_at = timezone.now()
                    req_locked.save()

                    wallet_locked.locked_balance = F('locked_balance') - amount_decimal
                    wallet_locked.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                    wallet_locked.save()

                    rejected_count += 1
                    logger.info(f"Request {req_locked.request_id} rejected successfully.")

            except (UserWallet.DoesNotExist, WithdrawalRequest.DoesNotExist):
                 logger.error(f"DB Error: Could not find Wallet or Request for pk={req.pk} during rejection.")
                 failed_db += 1
            except Exception as e:
                 logger.exception(f"Unexpected transaction/DB error during rejection for {req.request_id}: {e}")
                 failed_db += 1

        if rejected_count:
            self.message_user(request, _("{} request(s) rejected successfully. Funds unlocked.").format(rejected_count), messages.SUCCESS)
        if failed_db:
             self.message_user(request, _("{} request(s) failed rejection due to database/system errors.").format(failed_db), messages.ERROR)

        processed_in_loop = rejected_count + failed_db
        ignored_count = pending_requests.count() - processed_in_loop + already_processed
        if ignored_count > 0:
             self.message_user(request, _("{} selected pending request(s) were not processed or already handled.").format(ignored_count), messages.WARNING)
        elif already_processed > 0:
             self.message_user(request, _("{} request(s) were already processed before action started.").format(already_processed), messages.WARNING)