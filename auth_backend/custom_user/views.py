from django.shortcuts import render
from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from rest_framework.response import Response



from rest_framework.generics import RetrieveUpdateAPIView
from dj_rest_auth.views import UserDetailsView
from rest_framework.permissions import IsAuthenticated
from .serializers import CustomUserDetailsSerializer,CustomUserSocialMediaSerializer
from .models import CustomUser,CustomUserSocielMedia


def home(request):
    return render(request,'home.html')


class CustomUserView(RetrieveUpdateAPIView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user



class CustomUserSocialMediaViewSet(viewsets.ViewSet):
    
    def list(self, request):
        queryset = CustomUserSocielMedia.objects.all()
        serializer = CustomUserSocialMediaSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        user_social_media = get_object_or_404(CustomUserSocielMedia, user_id=pk)
        serializer = CustomUserSocialMediaSerializer(user_social_media)
        return Response(serializer.data)