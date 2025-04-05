from rest_framework import viewsets, permissions, status,generics
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import AnimationRequest, Contribution, Engagement, Notification
from .serializers import (
    UserSerializer, AnimationRequestSerializer, ContributionSerializer, 
    EngagementSerializer, NotificationSerializer, LeaderboardSerializer
)
from .models import OpenSourceVisionRequest, OpenSourceAttachment
from .serializers import (
    OpenSourceVisionRequestSerializer,
    OpenSourceVisionRequestCreateSerializer 
)
User = get_user_model()


class AnimationRequestViewSet(viewsets.ModelViewSet):
    """View to manage animation requests"""
    queryset = AnimationRequest.objects.all().order_by('-created_at')
    serializer_class = AnimationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Assign logged-in user as request creator and return the created object"""
        animation_request = serializer.save(created_by=self.request.user)
        print("let see the created animation id ",animation_request.id)
        return Response(animation_request.id)

    def destroy(self, request, *args, **kwargs):
        """Allow only request creators or admins to delete"""
        instance = self.get_object()
        if request.user == instance.created_by or request.user.is_staff:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
    
class ContributionViewSet(viewsets.ModelViewSet):
    """View to handle developer contributions"""
    serializer_class = ContributionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter contributions based on animation_request ID"""
        animation_request_id = self.request.query_params.get("request")  # Fetch request ID from query params
        queryset = Contribution.objects.all().order_by("-submitted_at")

        if animation_request_id:
            queryset = queryset.filter(animation_request_id=animation_request_id)

        return queryset

    def perform_create(self, serializer):
        """Ensure one contribution per user per animation request"""
        animation_request = serializer.validated_data.get("animation_request")
        developer = self.request.user

        # Check if the user has already contributed to this animation request
        if Contribution.objects.filter(animation_request=animation_request, developer=developer).exists():
            raise serializers.ValidationError(
                {"detail": "You have already submitted a contribution for this request."}
            )

        # Save the new contribution
        serializer.save(developer=developer)

    @action(detail=True, methods=["patch"], permission_classes=[permissions.IsAuthenticated])
    def approve(self, request, pk=None):
        """Approve a contribution"""
        contribution = self.get_object()
        contribution.approved = True
        contribution.save()
        return Response({"detail": "Contribution approved successfully."}, status=status.HTTP_200_OK)
    
    
class EngagementViewSet(viewsets.ModelViewSet):
    """View to manage likes and comments"""
    queryset = Engagement.objects.all().order_by('-created_at')
    serializer_class = EngagementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Set user automatically on engagement"""
        serializer.save(user=self.request.user)



class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """View to list notifications (Read-Only)"""
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return notifications for the logged-in user"""
        return self.queryset.filter(user=self.request.user)



from django.db.models import Count, Sum
from rest_framework.views import APIView

class LeaderboardView(APIView):
    """Leaderboard API showing top contributors"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        top_devs = (
            User.objects.annotate(
                total_likes=Sum('contributions__likes'),
                total_contributions=Count('contributions')
            ).order_by('-total_likes', '-total_contributions')[:10]  # Top 10
        )
        serializer = LeaderboardSerializer(top_devs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class OpenSourceVisionRequestListCreateView(generics.ListCreateAPIView):
    """
    List all Open Source Vision Requests (GET) or create a new one (POST).
    """
    queryset = OpenSourceVisionRequest.objects.filter(visibility=True).order_by('-created_at')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Allow anyone to list, only auth users to create

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OpenSourceVisionRequestCreateSerializer
        return OpenSourceVisionRequestSerializer

    def perform_create(self, serializer):
        instance = serializer.save(creator=self.request.user)

        attachments = self.request.FILES.getlist('attachments') # Key must match frontend FormData
        for file in attachments:
            OpenSourceAttachment.objects.create(request=instance, file=file)

# Optional: View for retrieving/updating/deleting a specific request
class OpenSourceVisionRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = OpenSourceVisionRequest.objects.all()
    serializer_class = OpenSourceVisionRequestSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Basic permissions example

    # Example permission: Allow only creator to update/delete
    # def get_permissions(self):
    #     if self.request.method in ['PUT', 'PATCH', 'DELETE']:
    #         return [permissions.IsAuthenticated(), IsOwnerOrReadOnly()] # Define IsOwnerOrReadOnly permission class
    #     return [permissions.IsAuthenticatedOrReadOnly()]




import razorpay
from django.conf import settings
from django.db import transaction 
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView 
from .serializers import OpenSourceContributionCreateSerializer, OpenSourceContributionSerializer 
from .models import Contribution 
from decimal import Decimal # Import Decimal


# --- View to handle creating a contribution ---
class ContributionCreateView(APIView):
    """
    Handles the creation of a new contribution after successful Razorpay payment.
    Verifies the payment with Razorpay before saving.
    """
    permission_classes = [permissions.IsAuthenticated] # Must be logged in to contribute

    def post(self, request, pk):
        # Find the Open Source Vision Request
        vision_request = get_object_or_404(OpenSourceVisionRequest, pk=pk)

        # Validate input data (amount, payment_id)
        serializer = OpenSourceContributionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        amount_contributed = validated_data['amount']
        razorpay_payment_id = validated_data['payment_id']

        # --- Check if project is still accepting funding ---
        if vision_request.current_funding >= vision_request.funding_goal:
            return Response(
                {"detail": "This project has already reached its funding goal."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- Initialize Razorpay client ---
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            # --- Verify payment with Razorpay ---
            payment_info = client.payment.fetch(razorpay_payment_id)

            # Important checks: Status, Amount, Currency
            if payment_info.get('status') != 'captured':
                return Response({"detail": "Payment not captured successfully."}, status=status.HTTP_400_BAD_REQUEST)

            # Razorpay amount is in paise, convert our amount to paise for comparison
            amount_in_paise = int(amount_contributed * 100)
            if payment_info.get('amount') != amount_in_paise:
                 return Response({"detail": "Payment amount mismatch."}, status=status.HTTP_400_BAD_REQUEST)

            if payment_info.get('currency') != 'INR':
                 return Response({"detail": "Payment currency mismatch."}, status=status.HTTP_400_BAD_REQUEST)


        except razorpay.errors.BadRequestError as e:
             return Response({"detail": f"Razorpay validation error: Invalid Payment ID?"}, status=status.HTTP_400_BAD_REQUEST)
        except razorpay.errors.ServerError as e:
             return Response({"detail": "Error communicating with payment gateway. Please try again later."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            print(f"Unexpected error during Razorpay verification: {e}") # Log this error
            return Response({"detail": "An unexpected error occurred during payment verification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        try:
            with transaction.atomic():
                request_locked = OpenSourceVisionRequest.objects.select_for_update().get(pk=vision_request.pk)

                if request_locked.current_funding >= request_locked.funding_goal:
                     return Response(
                         {"detail": "Funding goal reached while processing. Contribution not applied to this request."},
                         status=status.HTTP_400_BAD_REQUEST
                     )

                contribution = Contribution.objects.create(
                    contributor=request.user,
                    request=request_locked,
                    amount=amount_contributed,
                    razorpay_payment_id=razorpay_payment_id
                )

                # Update the request's current funding
                request_locked.current_funding += amount_contributed

                # Optional: Cap funding at the goal
                if request_locked.current_funding > request_locked.funding_goal:
                    request_locked.current_funding = request_locked.funding_goal

                request_locked.save()

            # Return the newly created contribution details
            response_serializer = ContributionSerializer(contribution)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(f"Database error during contribution saving: {e}") # Log this error
            return Response(
                {"detail": "Payment successful, but there was an error recording your contribution. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )