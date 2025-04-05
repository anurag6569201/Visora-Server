from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import AnimationRequest, Contribution, Engagement, Notification
import json
from .models import OpenSourceVisionRequest, OpenSourceAttachment,OpenSourceContribution
from decimal import Decimal 

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





# Basic serializer for showing attachments (e.g., when retrieving a request)
class OpenSourceAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpenSourceAttachment
        fields = ['id', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class OpenSourceContributionSerializer(serializers.ModelSerializer):
    contributor_username = serializers.CharField(source='contributor.username', read_only=True)

    class Meta:
        model = OpenSourceContribution
        fields = ['id', 'contributor_username', 'amount', 'razorpay_payment_id', 'timestamp']
        read_only_fields = ['id', 'contributor_username', 'razorpay_payment_id', 'timestamp']

# Serializer for Creating and Reading OpenSourceVisionRequests
class OpenSourceVisionRequestSerializer(serializers.ModelSerializer):
    creator = serializers.SlugRelatedField(slug_field='username', read_only=True)
    current_funding = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    attachments = OpenSourceAttachmentSerializer(many=True, read_only=True)
    contributions = OpenSourceContributionSerializer(many=True, read_only=True)
    tags = serializers.ListField(
       child=serializers.CharField(max_length=50),
       write_only=True,
       required=False
    )

    class Meta:
        model = OpenSourceVisionRequest
        fields = [
            'id', 'creator', 'title', 'description', 'category', 'difficulty',
            'funding_goal', 'current_funding', 'collaboration_link', 'deadline', 'tags',
            'visibility', 'created_at', 'updated_at',
            'attachments', 
            'contributions'
        ]
        read_only_fields = [
            'id', 'creator', 'current_funding', 'created_at', 'updated_at',
            'attachments', 'contributions', 'tags' 
        ]


    def validate_tags(self, value):
        """Ensure tags is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be provided as a list.")
        if not all(isinstance(tag, str) for tag in value):
            raise serializers.ValidationError("All tags must be strings.")
        return value

    def create(self, validated_data):
        tags_list = validated_data.pop('tags', [])
        instance = OpenSourceVisionRequest.objects.create(**validated_data)
        instance.tags = tags_list
        instance.save()
        return instance

# Separate Serializer specifically for handling the creation input more easily
class OpenSourceVisionRequestCreateSerializer(serializers.ModelSerializer):
     tags = serializers.CharField(required=False, help_text="JSON stringified list of tags") # Expects JSON string from FormData

     class Meta:
        model = OpenSourceVisionRequest
        fields = [
            'title', 'description', 'category', 'difficulty',
            'funding_goal', 'collaboration_link', 'deadline',
            'visibility', 'tags' 
        ]

     def validate_tags(self, value):
        """Parse JSON string and validate format."""
        try:
            tags_list = json.loads(value)
            if not isinstance(tags_list, list):
                 raise serializers.ValidationError("Tags must be a JSON array (list).")
            if not all(isinstance(tag, str) for tag in tags_list):
                 raise serializers.ValidationError("All tags within the list must be strings.")
            return tags_list 
        except json.JSONDecodeError:
            raise serializers.ValidationError("Invalid JSON format for tags.")
        except Exception as e:
             raise serializers.ValidationError(f"Error processing tags: {e}")

     def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        instance = OpenSourceVisionRequest.objects.create(**validated_data)
        instance.tags = tags_data
        instance.save()
        return instance
     

class OpenSourceContributionCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('10.00')) # Min contribution (e.g. 10 INR)
    payment_id = serializers.CharField(max_length=100)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Contribution amount must be positive.")
        return value