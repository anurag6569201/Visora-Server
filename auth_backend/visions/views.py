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
from .models import OpenSourceVisionRequest, OpenSourceAttachment,OpenSourceContribution,CollaborationRequest
from .serializers import (
    OpenSourceVisionRequestSerializer,
    OpenSourceVisionRequestCreateSerializer 
)
User = get_user_model()
from django.views.decorators.csrf import csrf_exempt

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
from .serializers import OpenSourceContributionCreateSerializer, OpenSourceContributionSerializer,ManageCollaborationSerializer,CollaborationRequestSerializer
from .models import Contribution 
from decimal import Decimal # Import Decimal
import logging
logger = logging.getLogger(__name__) # Setup logging in your settings.py
from django.utils import timezone

# --- View to handle creating a contribution ---
class ContributionCreateView(APIView):
    """
    Handles the creation of a new contribution for an OpenSourceVisionRequest.
    Verifies payment with Razorpay before saving.
    Allows contributions from both authenticated and anonymous users by default.
    """
    serializer_class = OpenSourceContributionCreateSerializer

    def get_project(self, pk):
        """Helper method to get the project or return None."""
        try:
            return OpenSourceVisionRequest.objects.get(pk=pk)
        except OpenSourceVisionRequest.DoesNotExist:
            return None

    def post(self, request, pk):
        """Handles POST request to create a contribution."""
        vision_request = self.get_project(pk)
        if not vision_request:
            logger.warning(f"Contribution attempt failed: Project with pk={pk} not found.")
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        goal = vision_request.funding_goal or Decimal('0')
        current = vision_request.current_funding or Decimal('0')

        if goal > 0 and current >= goal:
            logger.info(f"Contribution attempt rejected: Project pk={pk} already fully funded.")
            return Response({"detail": "This project has already reached its funding goal."}, status=status.HTTP_400_BAD_REQUEST)

        if goal <= 0:
             logger.info(f"Contribution attempt rejected: Project pk={pk} has no funding goal set (goal={goal}).")
             return Response({"detail": "Contributions are not accepted as no funding goal is set for this project."}, status=status.HTTP_400_BAD_REQUEST)

        # --- Validate Incoming Data ---
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"Contribution validation failed for request {pk}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        amount_contributed = validated_data['amount'] 
        payment_id = validated_data['payment_id']
        print(amount_contributed,payment_id)

        amount_needed = max(Decimal('0'), goal - current)
        if amount_contributed > amount_needed:
            logger.warning(f"Contribution amount {amount_contributed} exceeds needed {amount_needed} for request {pk}")
            return Response(
                {"amount": f"Contribution amount (₹{amount_contributed:.2f}) cannot exceed the amount still needed (₹{amount_needed:.2f})."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if OpenSourceContribution.objects.filter(razorpay_payment_id=payment_id).exists():
            logger.warning(f"Attempt to record duplicate contribution for payment_id {payment_id} on request {pk}")
            return Response({"detail": "This payment has already been successfully recorded as a contribution."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            contributor_user = request.user if request.user.is_authenticated else None
            contributor_log_name = contributor_user.username if contributor_user else "Anonymous"

            with transaction.atomic():
                contribution = OpenSourceContribution.objects.create(
                    contributor=contributor_user, # Can be None
                    request=vision_request,
                    amount=amount_contributed, # Use the validated Decimal amount
                    razorpay_payment_id=payment_id
                )

                opersourcevis=OpenSourceVisionRequest.objects.filter(pk=pk).first()
                opersourcevis.current_funding = opersourcevis.current_funding + amount_contributed
                opersourcevis.save()

                logger.info(f"Contribution {contribution.id} created for request {pk} by user '{contributor_log_name}'. Payment ID: {payment_id}, Amount: {amount_contributed}")

        except Exception as e:
            logger.exception(f"Database error during contribution save/update for request {pk}, payment {payment_id}: {e}")
            return Response(
                {"detail": "Payment verified, but a server error occurred while recording the contribution. Please contact support with your Payment ID."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                "detail": f"Successfully contributed ₹{amount_contributed:.2f}. Thank you!",
                "contribution_id": contribution.id 
            },
            status=status.HTTP_201_CREATED
        )
    
@csrf_exempt
def manage_collaboration(self, request, pk=None):
    """
    Action for the project owner to approve or reject collaboration requests.
    Requires IsProjectOwner permission.
    """
    project = self.get_object() 

    serializer = ManageCollaborationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    action = serializer.validated_data['action']
    request_id = serializer.validated_data.get('request_id')
    requester_id = serializer.validated_data.get('requester_id')

    collab_request = None
    try:
        if request_id:
            collab_request = CollaborationRequest.objects.get(pk=request_id, project=project)
        elif requester_id:
            collab_request = CollaborationRequest.objects.get(project=project, requester_id=requester_id)
        else:
                return Response({'detail': 'Missing request identifier.'}, status=status.HTTP_400_BAD_REQUEST)

        if collab_request.status != 'pending':
                return Response({'detail': f'This request is already {collab_request.status}.'}, status=status.HTTP_400_BAD_REQUEST)

    except CollaborationRequest.DoesNotExist:
        return Response({'detail': 'Collaboration request not found.'}, status=status.HTTP_404_NOT_FOUND)


    try:
        with transaction.atomic():
            requester_user = collab_request.requester
            if action == 'approve':
                collab_request.status = 'approved'
                collab_request.responded_at = timezone.now()
                collab_request.save(update_fields=['status', 'responded_at'])
                project.collaborators.add(requester_user)

            elif action == 'reject':
                collab_request.status = 'rejected'
                collab_request.responded_at = timezone.now()
                collab_request.save(update_fields=['status', 'responded_at'])
                project.collaborators.remove(requester_user)

        return Response({'detail': f'Request {action}d successfully.'}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'detail': 'An error occurred while managing the request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@action(detail=True, methods=['get'], url_path='collaboration-requests')
def list_collaboration_requests(self, request, pk=None):
    """
    Action for the project owner to view pending collaboration requests.
    Requires IsProjectOwner permission.
    """
    project = self.get_object() # Permission check via get_permissions

    # Filter for pending requests specifically for this project
    pending_requests = CollaborationRequest.objects.filter(project=project, status='pending')
    serializer = CollaborationRequestSerializer(pending_requests, many=True, context={'request': request})
    return Response(serializer.data)

