from django.db import models
from django.contrib.auth import get_user_model
from custom_user.models import CustomUser
from django.conf import settings
import uuid
import json
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

User = get_user_model()

class AnimationRequest(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100)
    tags = models.JSONField(default=list)  
    difficulty = models.CharField(
        max_length=50, 
        choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')]
    )
    deadline = models.DateField(null=True, blank=True)
    budget = models.FloatField(null=True, blank=True)  # New field
    attachments = models.FileField(upload_to='animation_requests/', null=True, blank=True)  # New field
    visibility = models.BooleanField(default=True)  # Public or Private request
    views = models.IntegerField(default=0)  # Track number of views
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    payment_id = models.CharField(max_length=255, null=True, blank=True)  # New field
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Contribution(models.Model):
    animation_request = models.ForeignKey(AnimationRequest, on_delete=models.CASCADE, related_name="contributions")
    developer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="contributions")
    animation_link = models.URLField()  # Link to the hosted animation
    description = models.TextField()
    likes = models.PositiveIntegerField(default=0)
    comments = models.JSONField(default=list)  # Stores user comments as list of dicts
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

class Engagement(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE)
    liked = models.BooleanField(default=False)
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



def get_opensource_attachment_path(instance, filename):
    return f'vision_attachments/opensource/{instance.request.id}/{filename}'

class OpenSourceVisionRequest(models.Model):
    CATEGORY_CHOICES = [
        ('2D', '2D Animation'),
        ('3D', '3D Animation'),
        ('Motion Graphics', 'Motion Graphics'),
        ('Stop Motion', 'Stop Motion'),
        ('Mixed Media', 'Mixed Media'),
        ('Educational', 'Educational'),
        ('Explainer', 'Explainer Video'),
        ('Short Film', 'Short Film'),
        ('Other', 'Other'),
    ]
    DIFFICULTY_CHOICES = [
        ('Beginner Friendly', 'Beginner Friendly'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
        ('Expert', 'Expert'),
    ]

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='os_vision_requests')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    difficulty = models.CharField(max_length=50, choices=DIFFICULTY_CHOICES)
    tags = models.JSONField(default=list, encoder=DjangoJSONEncoder, blank=True)
    funding_goal = models.DecimalField(max_digits=10, decimal_places=2)
    current_funding = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    collaboration_link = models.URLField(max_length=300, blank=True, null=True)
    deadline = models.DateField(blank=True, null=True)
    visibility = models.BooleanField(default=True)
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='collaborating_visions',
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OS Vision: {self.title} by {self.creator.username}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Open Source Vision Request"
        verbose_name_plural = "Open Source Vision Requests"

class OpenSourceAttachment(models.Model):
    request = models.ForeignKey(OpenSourceVisionRequest, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=get_opensource_attachment_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.request.title} ({self.file.name})"


class CollaborationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    project = models.ForeignKey(
        OpenSourceVisionRequest,
        on_delete=models.CASCADE,
        related_name='collaboration_requests'
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='collaboration_requests_made'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('project', 'requester')
        ordering = ['-requested_at']

    def __str__(self):
        return f"Request from {self.requester.username} for {self.project.title} ({self.status})"


class OpenSourceContribution(models.Model):
    contributor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='OpenSourceContributions'
    )
    request = models.ForeignKey(
        OpenSourceVisionRequest,
        on_delete=models.CASCADE,
        related_name='OpenSourceContributions'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_payment_id = models.CharField(max_length=100, unique=True, help_text="Razorpay Payment ID")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        contributor_name = self.contributor.username if self.contributor else 'Anonymous'
        return f"{self.amount} INR by {contributor_name} for '{self.request.title}'"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Contribution"
        verbose_name_plural = "OpenSourceContributions"




class CollaborativeCode(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    project = models.OneToOneField(
        OpenSourceVisionRequest,
        on_delete=models.CASCADE,
        related_name='collaborative_code'
    )
    # Represents the currently approved/merged code
    main_html_content = models.TextField(blank=True, default="<html>\n<head>\n</head>\n<body>\n  <h1>Welcome</h1>\n</body>\n</html>")
    main_css_content = models.TextField(blank=True, default="/* Approved CSS styles */")
    main_js_content = models.TextField(blank=True, default="// Approved JavaScript code")

    # Track who made the last APPROVED change
    last_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='last_approved_code_changes'
    )
    last_approved_at = models.DateTimeField(default=timezone.now) # Track when last merge happened

    def __str__(self):
        return f"Main Code for '{self.project.title}'"

    class Meta:
        verbose_name = "Main Collaborative Code"
        verbose_name_plural = "Main Collaborative Codes"


# NEW MODEL: Represents a proposed change by a collaborator
class CodeChangeProposal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved & Merged'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    project = models.ForeignKey(
        OpenSourceVisionRequest,
        on_delete=models.CASCADE,
        related_name='code_proposals'
    )
    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, # If proposer deleted, remove proposal? Or SET_NULL?
        related_name='code_proposals_made'
    )
    # Store the full proposed content
    proposed_html_content = models.TextField()
    proposed_css_content = models.TextField()
    proposed_js_content = models.TextField()

    # Optional: Snapshot of the timestamp of the main code this was based on
    based_on_timestamp = models.DateTimeField(null=True, blank=True)

    message = models.TextField(blank=True, help_text="Describe the changes made.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    # Fields to track review by owner
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='code_proposals_reviewed',
        limit_choices_to={'is_staff': False} # Assuming owner is not necessarily staff
    )

    def __str__(self):
        return f"Proposal by {self.proposer.username} for '{self.project.title}' ({self.status})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Code Change Proposal"
        verbose_name_plural = "Code Change Proposals"