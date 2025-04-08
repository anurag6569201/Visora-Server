# wallet/services.py
import logging
from django.utils import timezone
from .models import WithdrawalRequest # Import only necessary model

# Setup logger
logger = logging.getLogger(__name__)

class PayoutServiceError(Exception):
    """Custom exception for payout service errors (kept for consistency, but won't be raised for Razorpay issues)."""
    pass

# REMOVED: create_razorpay_contact_fund_account function is not needed for demo.

def initiate_razorpay_payout(withdrawal_request: WithdrawalRequest):
    """
    SIMULATES the completion of a payout for an approved withdrawal request.
    Updates the withdrawal_request object status directly to COMPLETED.
    THIS DOES NOT CALL ANY EXTERNAL PAYMENT GATEWAY.

    Args:
        withdrawal_request: The WithdrawalRequest instance (status should be APPROVED).

    Returns:
        bool: Always True in this simulation, unless an unexpected DB error occurs.

    Raises:
        Exception: For unexpected errors during DB update.
    """
    logger.info(f"Simulating payout completion for Request {withdrawal_request.request_id}")

    # Basic check - shouldn't ideally be called if not approved, but good practice
    if withdrawal_request.status != WithdrawalRequest.StatusChoices.APPROVED:
        logger.warning(f"Simulated payout initiated for request {withdrawal_request.request_id} with status {withdrawal_request.status}, expected APPROVED.")
        # You could choose to return False or raise an error here if needed
        # For demo, let's proceed but log it.

    try:
        # --- Directly mark as Completed for Demonstration ---
        withdrawal_request.status = WithdrawalRequest.StatusChoices.COMPLETED
        withdrawal_request.processed_at = timezone.now() # Mark processing time
        withdrawal_request.rejection_reason = None # Clear any previous reason
        # You could optionally set a simulated payout ID for display if desired:
        # withdrawal_request.razorpay_payout_id = f"DEMO_{withdrawal_request.request_id.hex[:8]}"
        # withdrawal_request.razorpay_payout_status = "processed"
        update_fields = ['status', 'processed_at', 'rejection_reason']
        # If setting demo payout ID/status:
        # update_fields.extend(['razorpay_payout_id', 'razorpay_payout_status'])

        withdrawal_request.save(update_fields=update_fields)
        logger.info(f"Request {withdrawal_request.request_id} marked as COMPLETED (Demo).")
        return True # Signal success to the calling admin action

    except Exception as e:
        # Handle unexpected errors during the DB save
        logger.error(f"Unexpected Error during simulated payout completion for Request {withdrawal_request.request_id}: {e}", exc_info=True)
        # Don't change status here, let the caller handle DB errors if needed
        # Re-raise the exception so the transaction in admin action rolls back
        raise e