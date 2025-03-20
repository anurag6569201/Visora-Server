from django.db import models
from django.contrib.auth import get_user_model
from custom_user.models import CustomUser
from django.conf import settings
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
