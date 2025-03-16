from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AnimationRequestViewSet, ContributionViewSet, 
    EngagementViewSet, NotificationViewSet, LeaderboardView
)

router = DefaultRouter()
router.register('requests', AnimationRequestViewSet, basename='requests')
router.register('contributions', ContributionViewSet, basename='contributions')
router.register('engagements', EngagementViewSet, basename='engagements')
router.register('notifications', NotificationViewSet, basename='notifications')

urlpatterns = [
    path('', include(router.urls)),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
]
