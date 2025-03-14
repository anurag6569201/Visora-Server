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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="student")  # Default role is "student"

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


