from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import UserDetailsSerializer
from rest_framework import serializers
from .models import CustomUser,CustomUserSocielMedia

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
            "role": self.validated_data.get("role", "student"),
        })
        return data

    def save(self, request):
        user = super().save(request)
        user.first_name = self.validated_data.get("first_name", "")
        user.last_name = self.validated_data.get("last_name", "")
        user.phone_number = self.validated_data.get("phone_number", "")
        user.profile_picture = self.validated_data.get("profile_picture", None)
        user.role = self.validated_data.get("role", "student")
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