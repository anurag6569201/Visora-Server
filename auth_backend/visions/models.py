from django.db import models
from django.contrib.auth import get_user_model
from custom_user.models import CustomUser
from django.conf import settings

import json
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


# Helper function to define upload path per request
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
    tags = models.JSONField(default=list, encoder=DjangoJSONEncoder, blank=True) # Store tags as a JSON list of strings
    funding_goal = models.DecimalField(max_digits=10, decimal_places=2)
    current_funding = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    collaboration_link = models.URLField(max_length=300, blank=True, null=True)
    deadline = models.DateField(blank=True, null=True)
    visibility = models.BooleanField(default=True)
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='collaborating_visions',
        blank=True  # Users might not collaborate initially
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


# NEW: Collaboration Request Model
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
    responded_at = models.DateTimeField(null=True, blank=True) # Set when owner approves/rejects

    class Meta:
        # Ensure a user can only request to join a specific project once
        unique_together = ('project', 'requester')
        ordering = ['-requested_at']

    def __str__(self):
        return f"Request from {self.requester.username} for {self.project.title} ({self.status})"

  

class OpenSourceContribution(models.Model):
    contributor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Keep contribution record even if user is deleted
        null=True,
        related_name='OpenSourceContributions'
    )
    request = models.ForeignKey(
        OpenSourceVisionRequest,
        on_delete=models.CASCADE, # Delete contribution if request is deleted
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