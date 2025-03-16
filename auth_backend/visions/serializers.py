from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import AnimationRequest, Contribution, Engagement, Notification

User = get_user_model()

# User Serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role','profile_picture']

# Animation Request Serializer
class AnimationRequestSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = AnimationRequest
        fields = '__all__'
        read_only_fields = ['created_by', 'status', 'created_at']

# Contribution Serializer
class ContributionSerializer(serializers.ModelSerializer):
    developer = UserSerializer(read_only=True)

    class Meta:
        model = Contribution
        fields = '__all__'
        read_only_fields = ['developer', 'likes', 'comments', 'submitted_at', 'approved']

# Engagement Serializer
class EngagementSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Engagement
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

# Notification Serializer
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['created_at']

# Leaderboard Serializer
class LeaderboardSerializer(serializers.Serializer):
    developer = UserSerializer()
    total_likes = serializers.IntegerField()
    total_contributions = serializers.IntegerField()
