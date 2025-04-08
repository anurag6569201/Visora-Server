# wallet/views.py
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication # Or JWTAuthentication etc.
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction # Keep if needed for Admin view
import uuid # For admin view lookup

from .models import UserWallet, WithdrawalRequest
from .serializers import (
    UserWalletSerializer,
    WithdrawalHistorySerializer,
    WithdrawalCreateSerializer,
)

# --- View to get User's Wallet Balance ---
class WalletBalanceView(views.APIView):
    """
    API endpoint that allows users to view their wallet balance.
    """
    authentication_classes = [TokenAuthentication] # Or your preferred auth
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        wallet, created = UserWallet.objects.get_or_create(user=request.user)
        serializer = UserWalletSerializer(wallet)
        return Response(serializer.data)

# --- View to list User's Withdrawal History ---
class UserWithdrawalHistoryView(generics.ListAPIView):
    """
    API endpoint that allows users to view their withdrawal history.
    """
    serializer_class = WithdrawalHistorySerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all the withdrawal requests
        for the currently authenticated user.
        """
        return WithdrawalRequest.objects.filter(user=self.request.user).order_by('-requested_at')

# --- View to create a new Withdrawal Request ---
class RequestWithdrawalView(generics.CreateAPIView):
    """
    API endpoint for users to submit a withdrawal request.
    Handles balance locking and creation of the request record.
    """
    serializer_class = WithdrawalCreateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # The actual creation logic, including wallet update and
        # request creation, is handled within the serializer's create method
        # using @transaction.atomic for safety.
        # We pass the request context to the serializer so it can access the user.
        serializer.save() # context={'request': self.request} is automatically passed by CreateAPIView

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                self.perform_create(serializer)
                # Don't return the full serializer.data() which might include sensitive validated_details
                # Return a success message or perhaps the request_id
                # The frontend refetches history anyway upon success.
                return Response(
                    {"message": "Withdrawal request submitted successfully. It is pending approval."},
                    status=status.HTTP_201_CREATED
                )
            except serializers.ValidationError as e:
                 # Catch validation errors raised during serializer.save() (e.g., insufficient balance)
                 return Response({"error": e.detail}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                # Log the exception e
                print(f"Unexpected error during withdrawal request: {e}")
                return Response({"error": "An unexpected error occurred. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Combine potential top-level and nested 'details' errors for frontend
            errors = serializer.errors
            if 'details' in errors and isinstance(errors['details'], dict) and errors['details']:
                # Flatten details errors slightly for better display maybe
                flat_errors = {f"details_{k}": v for k, v in errors['details'].items()}
                errors.update(flat_errors)
                # del errors['details'] # Or keep the nested structure if frontend handles it
                return Response({"error": "Validation failed.", "details": errors}, status=status.HTTP_400_BAD_REQUEST)
            else:
                 return Response({"error": "Validation failed.", "details": errors}, status=status.HTTP_400_BAD_REQUEST)


# --- Admin Action View (Placeholder - Requires Admin Permissions & Payout Logic) ---
class AdminWithdrawalActionView(views.APIView):
    """
    API endpoint for admins to approve or reject withdrawal requests.
    (Implementation requires admin permissions and payout gateway logic)
    """
    authentication_classes = [TokenAuthentication] # Or SessionAuthentication for Admin panel
    permission_classes = [permissions.IsAdminUser] # IMPORTANT: Only Admins

    def post(self, request, request_uuid, *args, **kwargs):
        action = request.data.get('action', '').lower() # 'approve' or 'reject'
        rejection_reason = request.data.get('rejection_reason', None)

        if action not in ['approve', 'reject']:
            return Response({"error": "Invalid action. Must be 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            withdrawal_request = get_object_or_404(WithdrawalRequest, request_id=request_uuid)
        except (ValueError, uuid.UUID.DoesNotExist):
             return Response({"error": "Invalid or not found withdrawal request ID."}, status=status.HTTP_404_NOT_FOUND)


        # --- Check Current Status ---
        if withdrawal_request.status != WithdrawalRequest.StatusChoices.PENDING:
            return Response(
                {"error": f"Request is already in '{withdrawal_request.get_status_display()}' status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Process Action ---
        with transaction.atomic():
            wallet = UserWallet.objects.select_for_update().get(user=withdrawal_request.user)

            if action == 'approve':
                # ** TODO: Implement Razorpay Payout Triggering Logic Here **
                # 1. Get withdrawal_request.razorpay_fund_account_id
                # 2. Call Razorpay Payout API: client.payout.create({...})
                # 3. Handle Razorpay API response (success/error)
                # 4. If payout initiated successfully:
                #    - Store razorpay_payout_id from response
                #    - Set status to APPROVED or PROCESSING (based on Razorpay sync/async response)
                #    - Set processed_by=request.user, processed_at=timezone.now()
                #    - Save withdrawal_request
                #    - **Note:** Balance remains locked until webhook confirms payout completion.
                # For Demonstration: Simulate approval without payout
                withdrawal_request.status = WithdrawalRequest.StatusChoices.APPROVED
                withdrawal_request.processed_by = request.user
                withdrawal_request.processed_at = timezone.now()
                withdrawal_request.razorpay_payout_id = f"sim_pout_{uuid.uuid4()}" # Simulated Payout ID
                withdrawal_request.save()
                # Balance remains locked in this simplified version. Real app needs webhook.
                return Response({"message": "Request approved (Payout simulation complete). Status updated."}, status=status.HTTP_200_OK)
                # --- End Payout Logic ---

            elif action == 'reject':
                if not rejection_reason:
                    return Response({"error": "Rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)

                # Unlock funds
                wallet.locked_balance -= withdrawal_request.amount
                wallet.withdrawable_balance += withdrawal_request.amount
                wallet.save()

                # Update request status
                withdrawal_request.status = WithdrawalRequest.StatusChoices.REJECTED
                withdrawal_request.rejection_reason = rejection_reason
                withdrawal_request.processed_by = request.user
                withdrawal_request.processed_at = timezone.now()
                withdrawal_request.save()

                return Response({"message": "Request rejected and funds unlocked."}, status=status.HTTP_200_OK)

        # Should not be reached if logic is correct
        return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)