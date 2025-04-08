# wallet/services.py
import razorpay
import decimal
from django.conf import settings
from django.utils import timezone
from .models import WithdrawalRequest, UserWallet # Adjust import as needed

# Initialize Razorpay client
try:
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    client.set_app_details({"title" : "YourAppName", "version" : "1.0"}) # Replace YourAppName
except Exception as e:
    print(f"ERROR: Failed to initialize Razorpay client: {e}")
    client = None # Ensure client is None if init fails

class PayoutServiceError(Exception):
    """Custom exception for payout service errors."""
    pass

def create_razorpay_contact_fund_account(user, method, details):
    """
    Creates or retrieves Razorpay Contact and Fund Account for the user.
    Args:
        user: The Django user object.
        method (str): 'upi' or 'bank'.
        details (dict): Contains 'upi_id' or bank details ('name', 'account_number', 'ifsc').
    Returns:
        tuple: (contact_id, fund_account_id)
    Raises:
        PayoutServiceError: If contact or fund account creation/retrieval fails.
    """
    if not client:
        raise PayoutServiceError("Razorpay client not initialized.")

    contact_id = None
    fund_account_id = None

    # --- 1. Create/Fetch Contact ---
    try:
        # Check if contact exists by reference_id (user.id)
        # Note: Razorpay API might not directly support filtering by reference_id easily.
        # Using email/phone might be an alternative, but less reliable.
        # For simplicity, we'll try creating and handle potential duplicates or fetch later.

        contact_data = {
            "name": f"{user.first_name} {user.last_name}".strip() or user.username,
            "email": user.email or None, # Optional
            "contact": user.phone_number or None, # Optional
            "type": "customer", # Or 'vendor', 'employee' based on your use case
            "reference_id": str(user.id)
        }
        contact_data = {k: v for k, v in contact_data.items() if v is not None} # Clean None values

        # Ideally, query first:
        # existing_contacts = client.contact.all({'email': user.email}) # Example query
        # if existing_contacts['count'] > 0 and existing_contacts['items'][0]['reference_id'] == str(user.id):
        #    contact_id = existing_contacts['items'][0]['id']
        # else:
        #    contact = client.contact.create(contact_data)
        #    contact_id = contact['id']

        # Simplified: Try creating, handle error (less robust for finding existing)
        contact = client.contact.create(contact_data)
        contact_id = contact['id']

    except razorpay.errors.BadRequestError as e:
         # Check if it's a duplicate error (e.g., based on error description or specific code if available)
         # This part needs careful checking of Razorpay's actual error responses
         if 'contact already exists' in str(e).lower(): # Example check
             try:
                 # Attempt to find the existing contact if creation failed due to duplicate
                 existing = client.contact.all({'reference_id': str(user.id), 'count': 1})
                 if existing['count'] > 0:
                     contact_id = existing['items'][0]['id']
                 else:
                     raise PayoutServiceError(f"Contact creation failed and duplicate not found: {e}")
             except Exception as find_err:
                  raise PayoutServiceError(f"Failed to find existing contact after create error: {find_err}")
         else:
              raise PayoutServiceError(f"Razorpay contact creation failed: {e}")
    except Exception as e:
        raise PayoutServiceError(f"Error creating/fetching Razorpay contact: {e}")

    if not contact_id:
         raise PayoutServiceError("Could not obtain Razorpay contact ID.")

    # --- 2. Create Fund Account ---
    try:
        fund_account_data = {
            "contact_id": contact_id,
            "account_type": "bank_account", # Default
        }
        if method == WithdrawalRequest.MethodChoices.UPI:
            fund_account_data["account_type"] = "vpa"
            fund_account_data["vpa"] = {"address": details['upi_id']}
        elif method == WithdrawalRequest.MethodChoices.BANK:
            fund_account_data["account_type"] = "bank_account"
            fund_account_data["bank_account"] = {
                "name": details['name'],
                "account_number": details['account_number'],
                "ifsc": details['ifsc']
            }
        else:
             raise ValueError("Invalid payout method specified for Fund Account.") # Should not happen if validated before

        # Check if an identical fund account exists for this contact (optional but good)
        # existing_funds = client.fund_account.all({'contact_id': contact_id})
        # ... logic to compare details and find match ...

        # Simplified: Create the fund account
        fund_account = client.fund_account.create(fund_account_data)
        fund_account_id = fund_account['id']

    except razorpay.errors.BadRequestError as e:
         # Handle potential duplicate fund account errors or validation errors
         raise PayoutServiceError(f"Razorpay fund account creation failed: {e}. Check details.")
    except Exception as e:
        raise PayoutServiceError(f"Error creating Razorpay fund account: {e}")

    if not fund_account_id:
        raise PayoutServiceError("Could not obtain Razorpay fund account ID.")

    return contact_id, fund_account_id


def initiate_razorpay_payout(withdrawal_request: WithdrawalRequest):
    """
    Initiates the Razorpay payout for an approved withdrawal request.
    Updates the withdrawal_request object with payout info and status.

    Args:
        withdrawal_request: The WithdrawalRequest instance (should have status APPROVED).

    Returns:
        bool: True if payout initiated successfully (status processing/pending/queued), False otherwise.

    Raises:
        PayoutServiceError: For configuration or critical API errors.
    """
    if not client:
        raise PayoutServiceError("Razorpay client not initialized.")

    if withdrawal_request.status != WithdrawalRequest.StatusChoices.APPROVED:
        print(f"WARNING: Payout initiated for request {withdrawal_request.request_id} with status {withdrawal_request.status}, expected APPROVED.")
        # Decide if you want to raise an error or proceed cautiously
        # raise PayoutServiceError("Payout can only be initiated for APPROVED requests.")


    if not withdrawal_request.razorpay_fund_account_id:
        raise PayoutServiceError(f"Missing Razorpay Fund Account ID for request {withdrawal_request.request_id}.")

    amount_paise = int(withdrawal_request.amount * 100)
    payout_mode = "UPI" if withdrawal_request.method == WithdrawalRequest.MethodChoices.UPI else "IMPS" # Or NEFT based on amount/preference

    payout_data = {
        "account_number": settings.RAZORPAYX_ACCOUNT_NUMBER,
        "fund_account_id": withdrawal_request.razorpay_fund_account_id,
        "amount": amount_paise,
        "currency": "INR",
        "mode": payout_mode,
        "purpose": "payout", # Or 'refund', 'cashback' etc.
        "queue_if_low_balance": True, # Very important for production
        "reference_id": f"WD_{withdrawal_request.request_id}", # Link to our request
        "narration": f"Withdrawal payout for user {withdrawal_request.user.username}",
        "notes": {
            "user_id": str(withdrawal_request.user.id),
            "withdrawal_request_uuid": str(withdrawal_request.request_id)
        }
    }

    try:
        payout = client.payout.create(payout_data)
        payout_id = payout.get('id')
        payout_status_from_rzp = payout.get('status', 'unknown')

        # Update the withdrawal request object
        withdrawal_request.razorpay_payout_id = payout_id
        withdrawal_request.razorpay_payout_status = payout_status_from_rzp

        # Map Razorpay status to our internal status more granularly
        if payout_status_from_rzp in ['processing', 'pending', 'queued']:
            withdrawal_request.status = WithdrawalRequest.StatusChoices.PROCESSING
        elif payout_status_from_rzp == 'processed':
             # 'processed' usually means successfully sent to beneficiary bank
            withdrawal_request.status = WithdrawalRequest.StatusChoices.COMPLETED
        elif payout_status_from_rzp in ['reversed', 'cancelled', 'failed']:
             withdrawal_request.status = WithdrawalRequest.StatusChoices.FAILED
             # Add reason if possible from payout response details (payout.get('failure_reason'))
             withdrawal_request.rejection_reason = f"Razorpay Payout Status: {payout_status_from_rzp}. Reason: {payout.get('failure_reason', 'N/A')}"
        else: # Unknown status
            withdrawal_request.status = WithdrawalRequest.StatusChoices.PROCESSING # Default to processing? Or Failed?
            print(f"WARNING: Unknown Razorpay payout status '{payout_status_from_rzp}' for payout {payout_id}")

        withdrawal_request.processed_at = timezone.now() # Update timestamp
        # Note: processed_by (admin) should already be set before calling this
        withdrawal_request.save()

        # Return True if initiated (even if pending/processing), False only on initial API error
        return withdrawal_request.status not in [WithdrawalRequest.StatusChoices.FAILED, WithdrawalRequest.StatusChoices.REJECTED]

    except (razorpay.errors.BadRequestError, razorpay.errors.ServerError) as rzp_error:
        print(f"ERROR: Razorpay Payout API Error for Request {withdrawal_request.request_id}: {rzp_error}")
        withdrawal_request.status = WithdrawalRequest.StatusChoices.FAILED
        withdrawal_request.rejection_reason = f"Payout Initiation Failed: {rzp_error}"
        withdrawal_request.processed_at = timezone.now()
        withdrawal_request.save()
        return False
    except Exception as e:
        print(f"ERROR: Unexpected Error during Razorpay Payout for Request {withdrawal_request.request_id}: {e}")
        # Don't update status here maybe, let the calling function handle unexpected errors?
        # Or set to FAILED
        withdrawal_request.status = WithdrawalRequest.StatusChoices.FAILED
        withdrawal_request.rejection_reason = f"Internal Error during Payout: {e}"
        withdrawal_request.processed_at = timezone.now()
        withdrawal_request.save()
        # Re-raise or return False based on desired handling
        raise PayoutServiceError(f"Unexpected payout error: {e}") # Re-raising might be better here
        # return False