from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AnimationRequestViewSet, ContributionViewSet, 
    EngagementViewSet, NotificationViewSet, LeaderboardView,OpenSourceVisionRequestListCreateView,OpenSourceVisionRequestDetailView,ContributionCreateView,manage_collaboration,request_collaboration_view
)
from .views import (
    CollaborativeCodeAPIView, # View main code
    CodeChangeProposalListCreateView, # List/Create proposals
    CodeChangeProposalDetailView, # View proposal detail
    ManageCodeChangeProposalView, # Approve/Reject proposal
)

router = DefaultRouter()
router.register('requests', AnimationRequestViewSet, basename='requests')
router.register('contributions', ContributionViewSet, basename='contributions')
router.register('engagements', EngagementViewSet, basename='engagements')
router.register('notifications', NotificationViewSet, basename='notifications')

urlpatterns = [
    path('', include(router.urls)),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('api/visions/opensource-requests/', OpenSourceVisionRequestListCreateView.as_view(), name='os-request-list-create'),
    path('api/visions/opensource-requests/<int:pk>/', OpenSourceVisionRequestDetailView.as_view(), name='os-request-detail'),
    path('api/visions/opensource-requests/<int:pk>/contribute/', ContributionCreateView.as_view(), name='os-request-contribute'),
    # --- URL for OWNER to MANAGE (approve/reject) requests ---
    path('api/visions/opensource-requests/<int:pk>/manage-collaboration/', manage_collaboration, name='os-manage-collaboration'),

    # --- CORRECT URL for USER to REQUEST collaboration ---
    path('api/visions/opensource-requests/<int:pk>/request-collaboration/', request_collaboration_view, name='os-request-collaboration'),
    
    path('api/visions/opensource-requests/<int:pk>/code/',
         CollaborativeCodeAPIView.as_view(),
         name='os-request-code-detail'),

    # List proposals (owner) or Create a new proposal (collaborator)
    path('api/visions/opensource-requests/<int:pk>/proposals/',
         CodeChangeProposalListCreateView.as_view(),
         name='os-request-proposal-list-create'),

    # Get detail of a specific proposal
    path('api/visions/opensource-requests/proposals/<uuid:proposal_pk>/', # Use proposal UUID
         CodeChangeProposalDetailView.as_view(),
         name='os-request-proposal-detail'),

    # Approve/Reject a specific proposal (Owner action)
    path('api/visions/opensource-requests/proposals/<uuid:proposal_pk>/manage/', # Use proposal UUID
         ManageCodeChangeProposalView.as_view(),
         name='os-request-proposal-manage'),
]
