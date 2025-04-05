from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AnimationRequestViewSet, ContributionViewSet, 
    EngagementViewSet, NotificationViewSet, LeaderboardView,OpenSourceVisionRequestListCreateView,OpenSourceVisionRequestDetailView,ContributionCreateView,manage_collaboration
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
    path('api/visions/opensource-requests/<int:pk>/request-collaboration/', manage_collaboration, name='os-request-contribute'),
]
