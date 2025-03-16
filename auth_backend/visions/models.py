from django.db import models
from django.contrib.auth import get_user_model
from custom_user.models import CustomUser
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
    tags = models.JSONField(default=list)  # Example: ["Physics", "Math", "Electromagnetism"]
    difficulty = models.CharField(max_length=50, choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')])
    deadline = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)


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
