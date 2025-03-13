from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('developer', 'Developer'),
        ('animator', 'Animator'),
        ('researcher', 'Researcher'),
    ]
    
    phone_number = models.CharField(max_length=15)
    profile_picture = models.ImageField(upload_to="profile_pics/")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="student")  # Default role is "student"

    def __str__(self):
        return f"{self.username} ({self.role})"
