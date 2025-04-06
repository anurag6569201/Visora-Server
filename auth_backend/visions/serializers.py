from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import AnimationRequest, Contribution, Engagement, Notification
import json
from .models import OpenSourceVisionRequest, OpenSourceAttachment,OpenSourceContribution,CollaborationRequest
from decimal import Decimal 
from .models import CollaborativeCode, CodeChangeProposal, OpenSourceVisionRequest # Import new models

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


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username')

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
    collaborators = SimpleUserSerializer(many=True, read_only=True)
    current_user_collaboration_status = serializers.SerializerMethodField()
    pending_requests = serializers.SerializerMethodField() # NEW FIELD

    class Meta:
        model = OpenSourceVisionRequest
        fields = (
            'id', 'title', 'description', 'creator',
            'funding_goal', 'current_funding',
            'created_at', 'updated_at', 'category', 'difficulty', 'deadline',
            'visibility', 'collaboration_link',
            'tags', 'attachments', 'contributions',
            'collaborators',
            'current_user_collaboration_status','pending_requests',
        )
        read_only_fields = ('creator', 'current_funding',
                            'created_at', 'updated_at', 'attachments', 'contributions',
                            'collaborators', 'current_user_collaboration_status','pending_requests')

    def get_current_user_collaboration_status(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        if not user or not user.is_authenticated:
            return 'anonymous'

        if obj.creator == user:
            return 'owner'

        if obj.collaborators.filter(pk=user.pk).exists():
            return 'approved'

        if CollaborationRequest.objects.filter(project=obj, requester=user, status='pending').exists():
            return 'pending'
        return 'none'
    
    def get_pending_requests(self, obj):
        request = self.context.get('request')
        user = request.user if request else None

        if user and user.is_authenticated and obj.creator == user:
            pending = CollaborationRequest.objects.filter(project=obj, status='pending').select_related('requester') # Optimization
            return CollaborationRequestSerializer(pending, many=True, context=self.context).data
        return None 



    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)
        instance = super().update(instance, validated_data)
        if tags_data is not None:
            instance.tags.set(tags_data)
        return instance

    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        validated_data['creator'] = self.context['request'].user
        instance = OpenSourceVisionRequest.objects.create(**validated_data)
        instance.tags.set(tags_data)
        return instance

class OpenSourceVisionRequestCreateSerializer(serializers.ModelSerializer):
     tags = serializers.CharField(required=False)

     class Meta:
        model = OpenSourceVisionRequest
        fields = [
            'title', 'description', 'category', 'difficulty',
            'funding_goal', 'collaboration_link', 'deadline',
            'visibility', 'tags'
        ]

     def validate_tags(self, value):
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
        instance.tags.set(tags_data) # Use set() for ManyToMany or JSONField assignment
        return instance

class OpenSourceContributionCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('10.00'))
    payment_id = serializers.CharField(max_length=100)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Contribution amount must be positive.")
        return value

class CollaborationRequestSerializer(serializers.ModelSerializer):
    requester = SimpleUserSerializer(read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)

    class Meta:
        model = CollaborationRequest
        fields = ('id', 'project', 'project_title', 'requester', 'status', 'requested_at', 'responded_at')
        read_only_fields = ('id', 'project', 'project_title', 'requester', 'requested_at', 'responded_at')

class ManageCollaborationSerializer(serializers.Serializer):
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]
    request_id = serializers.IntegerField(required=False)
    requester_id = serializers.IntegerField(required=False)
    action = serializers.ChoiceField(choices=ACTION_CHOICES)

    def validate(self, data):
        if not data.get('request_id') and not data.get('requester_id'):
            raise serializers.ValidationError("Either 'request_id' or 'requester_id' must be provided.")
        if data.get('request_id') and data.get('requester_id'):
             pass
        return data
    



class CollaborativeCodeSerializer(serializers.ModelSerializer):
    last_approved_by_username = serializers.SlugRelatedField(
        source='last_approved_by',
        slug_field='username',
        read_only=True
    )
    class Meta:
        model = CollaborativeCode
        fields = [
            'id',
            'project', # Keep project ID for reference
            'main_html_content',
            'main_css_content',
            'main_js_content',
            'last_approved_by_username',
            'last_approved_at'
        ]
        read_only_fields = [ # Typically read-only via this serializer
            'id', 'project', 'last_approved_by_username', 'last_approved_at'
            # Content might be read-only here if updates only happen via proposal approval
        ]


# Serializer for LISTING proposals (less detail)
class CodeChangeProposalListSerializer(serializers.ModelSerializer):
    proposer = SimpleUserSerializer(read_only=True) # Use existing simple user serializer

    class Meta:
        model = CodeChangeProposal
        fields = [
            'id', 'proposer', 'message', 'status', 'created_at', 'project'
        ]
        read_only_fields = fields


# Serializer for CREATING a proposal (collaborator perspective)
class CodeChangeProposalCreateSerializer(serializers.ModelSerializer):
    # Proposer and project will be set in the view based on context
    class Meta:
        model = CodeChangeProposal
        fields = [
            'proposed_html_content',
            'proposed_css_content',
            'proposed_js_content',
            'message',
            # 'based_on_timestamp' # Could be set automatically in view
        ]
        # Ensure content fields are required for creation
        extra_kwargs = {
            'proposed_html_content': {'required': True},
            'proposed_css_content': {'required': True},
            'proposed_js_content': {'required': True},
        }


# Serializer for viewing DETAIL of a proposal (includes proposed code)
class CodeChangeProposalDetailSerializer(serializers.ModelSerializer):
    proposer = SimpleUserSerializer(read_only=True)
    reviewer = SimpleUserSerializer(read_only=True)
    project = serializers.PrimaryKeyRelatedField(read_only=True) # Show project ID

    class Meta:
        model = CodeChangeProposal
        fields = [
            'id', 'project', 'proposer', 'message', 'status',
            'proposed_html_content', 'proposed_css_content', 'proposed_js_content',
            'created_at', 'reviewed_at', 'reviewer', 'based_on_timestamp',
        ]
        read_only_fields = fields


# Serializer for the OWNER managing a proposal (input)
class ManageCodeChangeProposalSerializer(serializers.Serializer):
    ACTION_CHOICES = [
        ('approve', 'Approve & Merge'),
        ('reject', 'Reject'),
    ]
    action = serializers.ChoiceField(choices=ACTION_CHOICES, required=True)
