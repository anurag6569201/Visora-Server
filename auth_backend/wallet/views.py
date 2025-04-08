# wallet/views.py
import decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .models import UserWallet, WithdrawalRequest
from .serializers import UserWalletSerializer, WithdrawalRequestSerializer
from .services import ( # Import service functions
    create_razorpay_contact_fund_account,
    initiate_razorpay_payout,
    PayoutServiceError
)


class WalletBalanceView(APIView):
    """
    API endpoint to get the user's current wallet balances.
    If a wallet doesn't exist for the user, it creates one with zero balances.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserWalletSerializer # Use serializer class for clarity

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            # Try to get the existing wallet
            user_wallet = UserWallet.objects.get(user=user)
            serializer = self.serializer_class(user_wallet)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except UserWallet.DoesNotExist:
            # --- Wallet does not exist, create it ---
            try:
                # Create wallet with default values (0.00 defined in model)
                user_wallet = UserWallet.objects.create(user=user)
                print(f"Created new wallet for user {user.id}") # Optional: Log creation
                serializer = self.serializer_class(user_wallet)
                # Return the new wallet's data with status 200 OK
                # (as the resource is now available as requested)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception as creation_error:
                 # Handle potential errors during creation (e.g., database issues)
                 print(f"ERROR: Could not create wallet for user {user.id}: {creation_error}")
                 return Response({'error': 'Could not initialize user wallet.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            # Handle other unexpected errors during fetch
            print(f"Error fetching balance for user {user.id}: {e}")
            return Response({'error': 'Could not fetch balance due to an unexpected error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RequestWithdrawalView(APIView):
    """
    API endpoint for users to REQUEST a withdrawal.
    Validates input, creates Razorpay Contact/FundAccount, creates WithdrawalRequest record, and locks funds.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        amount_str = request.data.get('amount')
        payout_method = request.data.get('method') # 'upi' or 'bank'
        account_details = request.data.get('details') # Dict with details

        # --- Basic Input Validation ---
        if not amount_str or not payout_method or not account_details:
            return Response({'error': 'Missing required fields: amount, method, details'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_decimal = decimal.Decimal(amount_str)
            # Example: Minimum withdrawal check
            if amount_decimal < decimal.Decimal('1.00'):
                 return Response({'error': 'Minimum withdrawal amount is ₹1.00'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, decimal.InvalidOperation):
            return Response({'error': 'Invalid amount specified'}, status=status.HTTP_400_BAD_REQUEST)

        # --- Method and Details Validation ---
        method_choice = None
        required_details = {}
        if payout_method == 'upi':
            upi_id = account_details.get('upi_id', '').strip()
            if not upi_id or '@' not in upi_id:
                return Response({'error': 'Invalid or missing UPI ID (e.g., name@bank)'}, status=status.HTTP_400_BAD_REQUEST)
            method_choice = WithdrawalRequest.MethodChoices.UPI
            required_details = {'upi_id': upi_id}
        elif payout_method == 'bank':
            required_fields = ['name', 'account_number', 'ifsc']
            if not all(account_details.get(f, '').strip() for f in required_fields):
                return Response({'error': 'Missing required bank details (Name, Account Number, IFSC)'}, status=status.HTTP_400_BAD_REQUEST)

            # Add more specific validation if needed (e.g., IFSC format)
            ifsc = account_details['ifsc'].strip().upper()
            if len(ifsc) != 11 or not ifsc.isalnum(): # Basic check
                 return Response({'error': 'Invalid IFSC code format (should be 11 alphanumeric characters)'}, status=status.HTTP_400_BAD_REQUEST)

            method_choice = WithdrawalRequest.MethodChoices.BANK
            required_details = {
                'name': account_details['name'].strip(),
                'account_number': account_details['account_number'].strip(),
                'ifsc': ifsc
            }
        else:
            return Response({'error': "Invalid payout method. Use 'upi' or 'bank'."}, status=status.HTTP_400_BAD_REQUEST)

        # --- Pre-check Balance (Optional but good UX) ---
        try:
             user_wallet_check = UserWallet.objects.get(user=user)
             if user_wallet_check.withdrawable_balance < amount_decimal:
                   return Response({'error': f'Insufficient withdrawable balance. Available: ₹{user_wallet_check.withdrawable_balance}'}, status=status.HTTP_400_BAD_REQUEST)
        except UserWallet.DoesNotExist:
             return Response({'error': 'User wallet not found.'}, status=status.HTTP_404_NOT_FOUND)


        # --- Create Razorpay Contact & Fund Account ---
        try:
            contact_id, fund_account_id = create_razorpay_contact_fund_account(
                user=user,
                method=method_choice,
                details=required_details
            )
        except PayoutServiceError as e:
             # Service layer error (Razorpay API issue, config problem etc.)
             print(f"Razorpay Pre-registration Error for User {user.id}: {e}")
             return Response({'error': f'Failed to register payout details with provider: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
             # Other unexpected errors
             print(f"Unexpected Error during Rzp Pre-registration for User {user.id}: {e}")
             return Response({'error': 'An unexpected error occurred during payout setup.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not contact_id or not fund_account_id:
             return Response({'error': 'Failed to obtain necessary payout identifiers.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Create Request & Lock Balance (Transaction) ---
        try:
            with transaction.atomic():
                # Get wallet, locking the row
                user_wallet = UserWallet.objects.select_for_update().get(user=user)

                # Final balance check inside transaction
                if user_wallet.withdrawable_balance < amount_decimal:
                    # Balance changed between initial check and now
                    raise PayoutServiceError(f'Insufficient balance. Available: {user_wallet.withdrawable_balance}') # Raise custom error

                # Move funds from withdrawable to locked
                user_wallet.withdrawable_balance = F('withdrawable_balance') - amount_decimal
                user_wallet.locked_balance = F('locked_balance') + amount_decimal
                user_wallet.save()

                # Create the Withdrawal Request record
                withdrawal_request = WithdrawalRequest.objects.create(
                    user=user,
                    amount=amount_decimal,
                    status=WithdrawalRequest.StatusChoices.PENDING,
                    method=method_choice,
                    razorpay_contact_id=contact_id, # Store the obtained IDs
                    razorpay_fund_account_id=fund_account_id
                )

            # Return success response
            serializer = WithdrawalRequestSerializer(withdrawal_request) # Serialize the created request
            return Response({
                'message': 'Withdrawal request submitted successfully and is pending approval.',
                'request': serializer.data
                }, status=status.HTTP_201_CREATED)

        except UserWallet.DoesNotExist:
             # Should not happen if pre-check passed, but handle defensively
             return Response({'error': 'User wallet not found.'}, status=status.HTTP_404_NOT_FOUND)
        except PayoutServiceError as e: # Catch balance error from inside transaction
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Log the error
            print(f"Error creating withdrawal request for user {user.id}: {e}")
            # Return generic error
            return Response({'error': 'An error occurred while submitting your request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminWithdrawalActionView(APIView):
    """
    API endpoint for ADMINS to approve or reject pending withdrawal requests.
    Uses the Payout Service to initiate payout on approval.
    """
    permission_classes = [IsAdminUser] # Only admins

    def post(self, request, request_uuid, *args, **kwargs):
        action = request.data.get('action') # 'approve' or 'reject'
        rejection_reason = request.data.get('rejection_reason', '').strip()

        if action not in ['approve', 'reject']:
            return Response({'error': "Invalid action. Use 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'reject' and not rejection_reason:
            return Response({'error': "Rejection reason is required when rejecting."}, status=status.HTTP_400_BAD_REQUEST)

        admin_user = request.user # Admin performing the action

        try:
            # Use UUID for lookup
            withdrawal_request = get_object_or_404(WithdrawalRequest, request_id=request_uuid)
        except ValueError:
             return Response({'error': 'Invalid request ID format.'}, status=status.HTTP_400_BAD_REQUEST)

        if withdrawal_request.status != WithdrawalRequest.StatusChoices.PENDING:
            return Response({'error': f'This request is already processed (status: {withdrawal_request.get_status_display()}).'}, status=status.HTTP_400_BAD_REQUEST)

        target_user = withdrawal_request.user
        amount_decimal = withdrawal_request.amount

        try:
            with transaction.atomic():
                # Lock the request and wallet
                req_locked = WithdrawalRequest.objects.select_for_update().get(pk=withdrawal_request.pk)
                user_wallet = UserWallet.objects.select_for_update().get(user=target_user)

                # Double check status
                if req_locked.status != WithdrawalRequest.StatusChoices.PENDING:
                    return Response({'error': f'Request already processed (status: {req_locked.get_status_display()}).'}, status=status.HTTP_409_CONFLICT)

                if action == 'reject':
                    # Update request status
                    req_locked.status = WithdrawalRequest.StatusChoices.REJECTED
                    req_locked.rejection_reason = rejection_reason
                    req_locked.processed_by = admin_user
                    req_locked.processed_at = timezone.now()
                    req_locked.save()

                    # Unlock funds: Move back from locked to withdrawable
                    user_wallet.locked_balance = F('locked_balance') - amount_decimal
                    user_wallet.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                    user_wallet.save()

                    # TODO: Send notification to user about rejection

                    serializer = WithdrawalRequestSerializer(req_locked)
                    return Response({'message': 'Withdrawal request rejected successfully.', 'request': serializer.data}, status=status.HTTP_200_OK)

                elif action == 'approve':
                    # Mark as approved (Payout Service will change to PROCESSING/COMPLETED/FAILED)
                    req_locked.status = WithdrawalRequest.StatusChoices.APPROVED
                    req_locked.processed_by = admin_user
                    req_locked.processed_at = timezone.now()
                    req_locked.rejection_reason = None # Clear any previous reason
                    req_locked.save() # Save approved status before calling service

                    # --- Initiate Payout via Service ---
                    try:
                        payout_initiated_successfully = initiate_razorpay_payout(req_locked) # Pass the locked request instance

                        if payout_initiated_successfully:
                            # Payout service updated status to PROCESSING/COMPLETED
                            # Confirm wallet balance deduction (locked funds are spent)
                            user_wallet.locked_balance = F('locked_balance') - amount_decimal
                            user_wallet.save()

                            # TODO: Send notification to user about approval/processing

                            # Refresh request data after service update
                            req_locked.refresh_from_db()
                            serializer = WithdrawalRequestSerializer(req_locked)
                            return Response({
                                'message': f'Withdrawal approved. Payout Status: {req_locked.get_status_display()}.',
                                'request': serializer.data
                                }, status=status.HTTP_200_OK)
                        else:
                            # Payout service failed and set status to FAILED
                            # Rollback wallet balance (locked -> withdrawable)
                            user_wallet.locked_balance = F('locked_balance') - amount_decimal
                            user_wallet.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                            user_wallet.save()

                            # Refresh request data after service update
                            req_locked.refresh_from_db()
                            serializer = WithdrawalRequestSerializer(req_locked)
                            return Response({
                                'error': f'Payout initiation failed. Reason: {req_locked.rejection_reason}',
                                'request': serializer.data
                                }, status=status.HTTP_400_BAD_REQUEST)

                    except PayoutServiceError as service_err:
                        # Critical error from service layer (e.g., config)
                        print(f"CRITICAL: PayoutServiceError during admin approval for {req_locked.request_id}: {service_err}")
                        # Status might not have been updated by service, manually set to FAILED?
                        req_locked.status = WithdrawalRequest.StatusChoices.FAILED
                        req_locked.rejection_reason = f"Admin Approval Error: {service_err}"
                        req_locked.save()
                         # Rollback wallet funds if approval attempt failed critically
                        user_wallet.locked_balance = F('locked_balance') - amount_decimal
                        user_wallet.withdrawable_balance = F('withdrawable_balance') + amount_decimal
                        user_wallet.save()
                        return Response({'error': f"Internal payout service error: {service_err}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except WithdrawalRequest.DoesNotExist:
             return Response({'error': 'Withdrawal request not found.'}, status=status.HTTP_404_NOT_FOUND)
        except UserWallet.DoesNotExist:
             return Response({'error': 'Target user wallet not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"General Error in Admin Action for Request {request_uuid}: {e}")
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserWithdrawalHistoryView(generics.ListAPIView):
    """
    API endpoint for users to view their own withdrawal request history.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = WithdrawalRequestSerializer

    def get_queryset(self):
        # Return requests only for the currently authenticated user
        return WithdrawalRequest.objects.filter(user=self.request.user).order_by('-requested_at')