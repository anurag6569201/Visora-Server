from django.shortcuts import render

def home(request):
    return render(request,'home.html')


from rest_framework.generics import RetrieveUpdateAPIView
from dj_rest_auth.views import UserDetailsView
from rest_framework.permissions import IsAuthenticated
from .serializers import CustomUserDetailsSerializer
from .models import CustomUser

class CustomUserView(RetrieveUpdateAPIView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

