from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer
from rest_framework import serializers
from .models import CustomUser,CustomUserSocielMedia,Score

from dj_rest_auth.serializers import LoginSerializer
from rest_framework import serializers
from django.contrib.auth import authenticate

class CustomLoginSerializer(LoginSerializer):
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid email or password.")
        else:
            raise serializers.ValidationError("Must include 'email' and 'password'.")

        attrs['user'] = user
        return attrs


class CustomRegisterSerializer(RegisterSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    phone_number = serializers.CharField(required=True)
    profile_picture = serializers.ImageField(required=True)
    role = serializers.ChoiceField(choices=CustomUser.ROLE_CHOICES, default="student")

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.update({
            "phone_number": self.validated_data.get("phone_number", ""),
            "first_name": self.validated_data.get("first_name", ""),
            "last_name": self.validated_data.get("last_name", ""),
            "profile_picture": self.validated_data.get("profile_picture", None),
            "role": self.validated_data.get("role", "Student"),
        })
        return data

    def save(self, request):
        user = super().save(request)
        user.first_name = self.validated_data.get("first_name", "")
        user.last_name = self.validated_data.get("last_name", "")
        user.phone_number = self.validated_data.get("phone_number", "")
        user.profile_picture = self.validated_data.get("profile_picture", None)
        user.role = self.validated_data.get("role", "Student")
        user.save()
        return user



class CustomUserDetailsSerializer(UserDetailsSerializer):
    phone_number = serializers.CharField(read_only=True)
    profile_picture = serializers.ImageField(read_only=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "profile_picture", "role", "date_joined")



class CustomUserSocialMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUserSocielMedia
        fields = '__all__'



class CustomUserSerializer(serializers.ModelSerializer):
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ["id", "follower_count", "following_count"]

    def get_follower_count(self, obj):
        return obj.follower_count()

    def get_following_count(self, obj):
        return obj.following_count()
    

class ScoreSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")  # Extract username
    userpic = serializers.CharField(source="user.profile_picture")  # Extract username
    userid = serializers.IntegerField(source="user.id")  # Extract user ID

    class Meta:
        model = Score
        fields = ['id', 'username','userpic','userid', 'score', 'updated_at']


