from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import AnimationRequest, Contribution, Engagement, Notification
from .serializers import (
    UserSerializer, AnimationRequestSerializer, ContributionSerializer, 
    EngagementSerializer, NotificationSerializer, LeaderboardSerializer
)

User = get_user_model()


class AnimationRequestViewSet(viewsets.ModelViewSet):
    """View to manage animation requests"""
    queryset = AnimationRequest.objects.all().order_by('-created_at')
    serializer_class = AnimationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Assign logged-in user as request creator"""
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Allow only request creators or admins to delete"""
        instance = self.get_object()
        if request.user == instance.created_by or request.user.is_staff:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)


class ContributionViewSet(viewsets.ModelViewSet):
    """View to handle developer contributions"""
    queryset = Contribution.objects.all().order_by('-submitted_at')
    serializer_class = ContributionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        """Assign logged-in user as contributor"""
        serializer.save(developer=self.request.user)



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
