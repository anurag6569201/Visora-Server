from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('Student', 'Student'),
        ('Teacher', 'Teacher'),
        ('Developer', 'Developer'),
        ('Animator', 'Animator'),
        ('Researcher', 'Researcher'),
    ]
    
    phone_number = models.CharField(max_length=15)
    profile_picture = models.ImageField(upload_to="profile_pics/")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="Student")  # Default role is "student"

# Followers & Following System
    followers = models.ManyToManyField("self", symmetrical=False, related_name="following", blank=True)

    def follow(self, user):
        """Follow another user"""
        if user != self:
            self.following.add(user)

    def unfollow(self, user):
        """Unfollow another user"""
        if user in self.following.all():
            self.following.remove(user)

    def is_following(self, user):
        """Check if the user is following another user"""
        return self.following.filter(id=user.id).exists()

    def is_followed_by(self, user):
        """Check if the user is followed by another user"""
        return self.followers.filter(id=user.id).exists()

    def follower_count(self):
        """Return count of followers"""
        return self.followers.count()

    def following_count(self):
        """Return count of following"""
        return self.following.count()

    def __str__(self):
        return f"{self.username} ({self.role})"



class CustomUserSocielMedia(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    youtube = models.URLField(blank=True, null=True)
    medium = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Social Media"


class Score(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    score = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.score}"
