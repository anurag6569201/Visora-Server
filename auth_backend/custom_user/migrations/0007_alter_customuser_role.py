# Generated by Django 5.1.7 on 2025-03-19 18:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("custom_user", "0006_score"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                choices=[
                    ("Student", "Student"),
                    ("Teacher", "Teacher"),
                    ("Developer", "Developer"),
                    ("Animator", "Animator"),
                    ("Researcher", "Researcher"),
                ],
                default="Student",
                max_length=20,
            ),
        ),
    ]
