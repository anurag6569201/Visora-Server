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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

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

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt 
def manage_collaboration(request, pk=None): 
    project = get_object_or_404(OpenSourceVisionRequest, pk=pk)

    serializer = ManageCollaborationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    action_type = serializer.validated_data['action'] # Renamed from 'action' to avoid clash
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
            if action_type == 'approve':
                collab_request.status = 'approved'
                collab_request.responded_at = timezone.now()
                collab_request.save(update_fields=['status', 'responded_at'])
                project.collaborators.add(requester_user)
            elif action_type == 'reject':
                collab_request.status = 'rejected'
                collab_request.responded_at = timezone.now()
                collab_request.save(update_fields=['status', 'responded_at'])
                # Optionally remove collaborator if they were somehow added before rejection
                project.collaborators.remove(requester_user)

        return Response({'detail': f'Request {action_type}d successfully.'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error managing collaboration request {collab_request.id if collab_request else 'N/A'} for project {pk}: {e}")
        return Response({'detail': 'An error occurred while managing the request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


   
from django.db import IntegrityError, transaction
from rest_framework.permissions import IsAuthenticated

@api_view(['POST'])
@permission_classes([IsAuthenticated]) # User must be logged in to request
def request_collaboration_view(request, pk=None):
    """
    Handles a user's request to collaborate on a specific project.
    """
    project = get_object_or_404(OpenSourceVisionRequest, pk=pk)
    user = request.user

    # --- Pre-checks ---
    if project.creator == user:
        return Response({'detail': 'You cannot request to collaborate on your own project.'}, status=status.HTTP_400_BAD_REQUEST)

    if project.collaborators.filter(pk=user.pk).exists():
        return Response({'detail': 'You are already a collaborator on this project.'}, status=status.HTTP_400_BAD_REQUEST)

    # Check if a request already exists (pending or approved)
    existing_request = CollaborationRequest.objects.filter(project=project, requester=user).first()
    if existing_request:
        if existing_request.status == 'pending':
             return Response({'detail': 'You already have a pending collaboration request for this project.'}, status=status.HTTP_409_CONFLICT) # 409 Conflict is suitable here
        elif existing_request.status == 'approved':
             # This case should ideally be caught by the collaborator check above, but good fallback
             return Response({'detail': 'Your request was already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        elif existing_request.status == 'rejected':
            pass

    # --- Create the request ---
    try:
        with transaction.atomic():
            collab_request = CollaborationRequest.objects.create(
                project=project,
                requester=user,
                status='pending' # Default status
            )
        logger.info(f"Collaboration request created: User '{user.username}' for project '{project.title}' (ID: {project.id})")
        # You can serialize the created request if needed in the response
        return Response({'detail': 'Collaboration request submitted successfully.', 'request_id': collab_request.id}, status=status.HTTP_201_CREATED)
    except IntegrityError as e:
         # Catch potential unique_together constraint violation if the check above somehow missed it
         logger.warning(f"IntegrityError creating collaboration request for user '{user.username}' on project {pk}: {e}")
         return Response({'detail': 'Could not process request due to a conflict. You might already have a pending request.'}, status=status.HTTP_409_CONFLICT)
    except Exception as e:
        logger.exception(f"Error creating collaboration request for user '{user.username}' on project {pk}: {e}")
        return Response({'detail': 'An unexpected error occurred while submitting your request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def list_collaboration_requests(self, request, pk=None):
    project = self.get_object()

    pending_requests = CollaborationRequest.objects.filter(project=project, status='pending')
    serializer = CollaborationRequestSerializer(pending_requests, many=True, context={'request': request})
    return Response(serializer.data)





from .models import OpenSourceVisionRequest, CollaborativeCode, CodeChangeProposal
from .serializers import (
    CollaborativeCodeSerializer,
    CodeChangeProposalListSerializer,
    CodeChangeProposalCreateSerializer,
    CodeChangeProposalDetailSerializer,
    ManageCodeChangeProposalSerializer
)
from visions.permissions import IsProjectCollaboratorOrOwner, IsProposalOwner, IsProjectOwnerForProposal


class CollaborativeCodeAPIView(generics.RetrieveAPIView): # Use RetrieveAPIView for GET
    serializer_class = CollaborativeCodeSerializer
    permission_classes = [IsAuthenticated, IsProjectCollaboratorOrOwner]
    lookup_url_kwarg = 'pk' # Project PK from URL

    def get_object(self):
        """ Gets the CollaborativeCode instance for the project, creating if needed. """
        project_pk = self.kwargs.get(self.lookup_url_kwarg)
        project = get_object_or_404(OpenSourceVisionRequest, pk=project_pk)
        # Check permissions against the project itself first
        self.check_object_permissions(self.request, project)
        # Get or create the code instance
        code_instance, created = CollaborativeCode.objects.get_or_create(project=project)
        if created:
            logger.info(f"Created CollaborativeCode for project {project_pk}")
        return code_instance


# --- Views for Code Change Proposals ---

# List (for owner mainly) and Create (for collaborators)
class CodeChangeProposalListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsProjectCollaboratorOrOwner]
    lookup_url_kwarg = 'pk' # Project PK from URL

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CodeChangeProposalCreateSerializer
        return CodeChangeProposalListSerializer

    def get_queryset(self):
        """ Filter proposals for the specific project from URL. """
        project_pk = self.kwargs.get(self.lookup_url_kwarg)
        project = get_object_or_404(OpenSourceVisionRequest, pk=project_pk)
        # Check user has permission to view proposals for this project
        self.check_object_permissions(self.request, project)

        # Owner sees all? Collaborators see only their own? Adjust filter as needed.
        # Example: Owner sees all pending, collaborators see their own pending.
        user = self.request.user
        if project.creator == user:
            # Owner sees all pending proposals for this project
             return CodeChangeProposal.objects.filter(project=project, status='pending')
        else:
            # Collaborator sees only their own pending proposals
             return CodeChangeProposal.objects.filter(project=project, proposer=user, status='pending')
            # Alternatively, return all their proposals:
            # return CodeChangeProposal.objects.filter(project=project, proposer=user)


    def perform_create(self, serializer):
        """ Set proposer, project, and based_on_timestamp automatically. """
        project_pk = self.kwargs.get(self.lookup_url_kwarg)
        project = get_object_or_404(OpenSourceVisionRequest, pk=project_pk)

        # Ensure only collaborators (not owner) can create proposals via this view
        if project.creator == self.request.user:
             raise serializers.ValidationError("Project owner cannot submit proposals via this endpoint.")
        # Permission class already checks if user is collaborator or owner, but extra check is fine

        # Get the current timestamp of the main code
        main_code, _ = CollaborativeCode.objects.get_or_create(project=project)

        serializer.save(
            proposer=self.request.user,
            project=project,
            based_on_timestamp=main_code.last_approved_at # Record what version it's based on
        )
        logger.info(f"User {self.request.user.username} created proposal for project {project_pk}")


# Retrieve details of a specific proposal
class CodeChangeProposalDetailView(generics.RetrieveAPIView):
    serializer_class = CodeChangeProposalDetailSerializer
    permission_classes = [IsAuthenticated, IsProjectCollaboratorOrOwner] # Owner or Collaborator can view
    queryset = CodeChangeProposal.objects.select_related('proposer', 'reviewer', 'project').all()
    lookup_url_kwarg = 'proposal_pk' # Use proposal's PK from URL

    def get_object(self):
        """ Get the proposal and check permissions against its project. """
        proposal = super().get_object()
        # Check permissions based on the *project* linked to the proposal
        self.check_object_permissions(self.request, proposal.project)
        return proposal

# Manage (Approve/Reject) a specific proposal (Owner action)
class ManageCodeChangeProposalView(APIView):
    permission_classes = [IsAuthenticated, IsProjectOwnerForProposal] # Only project owner
    serializer_class = ManageCodeChangeProposalSerializer # For input validation

    def get_proposal(self, proposal_pk):
        """ Helper to get the proposal object. """
        proposal = get_object_or_404(CodeChangeProposal, pk=proposal_pk)
        # Check owner has permission for the project linked to this proposal
        self.check_object_permissions(self.request, proposal) # Checks IsProjectOwnerForProposal
        return proposal

    def post(self, request, proposal_pk):
        """ Handle approve or reject actions. """
        proposal = self.get_proposal(proposal_pk)

        if proposal.status != 'pending':
            return Response(
                {"detail": f"This proposal is already '{proposal.status}' and cannot be managed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']

        try:
            with transaction.atomic():
                proposal.reviewer = request.user
                proposal.reviewed_at = timezone.now()

                if action == 'approve':
                    proposal.status = 'approved' # Or 'merged'

                    # --- Merge the changes into the main CollaborativeCode ---
                    main_code, _ = CollaborativeCode.objects.select_for_update().get_or_create(project=proposal.project)

                    # --- Conflict Check (Simple: Check if main code changed since proposal) ---
                    # if proposal.based_on_timestamp and main_code.last_approved_at > proposal.based_on_timestamp:
                    #     logger.warning(f"Potential conflict approving proposal {proposal.pk}. Main code updated since proposal.")
                        # Raise error or allow overwrite? For now, allow overwrite ("last merge wins").
                        # return Response({"detail": "Conflict detected. The main code has been updated since this proposal was submitted."}, status=status.HTTP_409_CONFLICT)

                    main_code.main_html_content = proposal.proposed_html_content
                    main_code.main_css_content = proposal.proposed_css_content
                    main_code.main_js_content = proposal.proposed_js_content
                    main_code.last_approved_by = proposal.proposer
                    main_code.last_approved_at = proposal.reviewed_at # Match review time
                    main_code.save()
                    # --- End Merge ---

                    proposal.save()
                    logger.info(f"Owner {request.user.username} approved proposal {proposal.pk} by {proposal.proposer.username} for project {proposal.project.pk}")

                elif action == 'reject':
                    proposal.status = 'rejected'
                    proposal.save()
                    logger.info(f"Owner {request.user.username} rejected proposal {proposal.pk} by {proposal.proposer.username} for project {proposal.project.pk}")

                # Return detail of the updated proposal
                detail_serializer = CodeChangeProposalDetailSerializer(proposal)
                return Response(detail_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
             logger.exception(f"Error managing proposal {proposal.pk}: {e}")
             return Response({"detail": "An internal server error occurred while managing the proposal."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
