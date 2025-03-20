from django.shortcuts import render
from rest_framework import viewsets
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from dj_rest_auth.app_settings import api_settings
from django.views.decorators.debug import sensitive_post_parameters
from dj_rest_auth.models import TokenModel
from rest_framework.generics import RetrieveUpdateAPIView
from dj_rest_auth.views import UserDetailsView
from rest_framework.permissions import IsAuthenticated
from .serializers import CustomUserDetailsSerializer,CustomUserSocialMediaSerializer,ScoreSerializer
from .models import CustomUser,CustomUserSocielMedia,Score
from rest_framework.generics import CreateAPIView
from django.utils.decorators import method_decorator
from allauth.account import app_settings as allauth_account_settings
from rest_framework import status
from dj_rest_auth.utils import jwt_encode
from allauth.account.utils import complete_signup
import requests
from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.decorators import api_view, permission_classes
from rest_framework import serializers, viewsets, pagination, filters

def home(request):
    return render(request,'home.html')


class CustomUserView(RetrieveUpdateAPIView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters('password1', 'password2'),
)

class CustomRegisterView(CreateAPIView):
    """
    Registers a new user.

    Accepts the following POST parameters: username, email, password1, password2.
    """
    serializer_class = api_settings.REGISTER_SERIALIZER
    permission_classes = api_settings.REGISTER_PERMISSION_CLASSES
    token_model = TokenModel
    throttle_scope = 'dj_rest_auth'

    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_response_data(self, user):
        if allauth_account_settings.EMAIL_VERIFICATION == \
                allauth_account_settings.EmailVerificationMethod.MANDATORY:
            return {'detail': _('Verification e-mail sent.')}

        if api_settings.USE_JWT:
            data = {
                'user': user,
                'access': self.access_token,
                'refresh': self.refresh_token,
            }
            return api_settings.JWT_SERIALIZER(data, context=self.get_serializer_context()).data
        elif self.token_model:
            return api_settings.TOKEN_SERIALIZER(user.auth_token, context=self.get_serializer_context()).data
        return None

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        data = self.get_response_data(user)
        print(user.profile_picture.url)
        print(user.id)
        print(user.role)
        visiora_data_url = settings.VISIORA_DATA_API_URL + "/username/"
        payload = {
            "username": user.username,
            "email": user.email,
            "profile_picture": user.profile_picture.url,
            "userid": user.id,
            "role": user.role
        }
        headers = {
            "X-Visiora-Backend-Key": settings.VISIORA_BACKEND_SECRET_KEY
        }

        try:
            response = requests.post(visiora_data_url, json=payload, headers=headers, timeout=5)
            if user.role in ["Developer", "Animator"]:
                user_score, created = Score.objects.get_or_create(user_id=user.id)

            if response.status_code != 201:
                raise APIException("Failed to create user in Visiora-Data.")
        except requests.exceptions.RequestException:
            raise APIException("Error communicating with Visiora-Data.")
        if data:
            response = Response(
                data,
                status=status.HTTP_201_CREATED,
                headers=headers,
            )
        else:
            response = Response(status=status.HTTP_204_NO_CONTENT, headers=headers)

        return response

    def perform_create(self, serializer):
        user = serializer.save(self.request)
        if allauth_account_settings.EMAIL_VERIFICATION != \
                allauth_account_settings.EmailVerificationMethod.MANDATORY:
            if api_settings.USE_JWT:
                self.access_token, self.refresh_token = jwt_encode(user)
            elif self.token_model:
                api_settings.TOKEN_CREATOR(self.token_model, user, serializer)

        complete_signup(
            self.request._request, user,
            allauth_account_settings.EMAIL_VERIFICATION,
            None,
        )
        return user


class CustomUserSocialMediaViewSet(viewsets.ViewSet):
    
    def list(self, request):
        queryset = CustomUserSocielMedia.objects.all()
        serializer = CustomUserSocialMediaSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        user_social_media = get_object_or_404(CustomUserSocielMedia, user_id=pk)
        serializer = CustomUserSocialMediaSerializer(user_social_media)
        return Response(serializer.data)
    
    def update(self, request, pk=None):
        user_social_media, created = CustomUserSocielMedia.objects.get_or_create(user_id=pk)  # Fetch or create
        serializer = CustomUserSocialMediaSerializer(user_social_media, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def follow_user(request, user_id):
    """Follow a user"""
    user_to_follow = get_object_or_404(CustomUser, id=user_id)
    request.user.follow(user_to_follow)
    return Response({"message": f"You are now following {user_to_follow.username}"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unfollow_user(request, user_id):
    """Unfollow a user"""
    user_to_unfollow = get_object_or_404(CustomUser, id=user_id)
    request.user.unfollow(user_to_unfollow)
    return Response({"message": f"You have unfollowed {user_to_unfollow.username}"}, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_follow_stats(request, user_id):
    """Get follower and following count"""
    user = get_object_or_404(CustomUser, id=user_id)
    data = {
        "followers": user.follower_count(),
        "following": user.following_count(),
    }
    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def UserByIdView(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    serializer = CustomUserDetailsSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


class ScorePagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

# ViewSet
class ScoreViewSet(viewsets.ModelViewSet):
    queryset = Score.objects.all().order_by('-score')
    serializer_class = ScoreSerializer
    pagination_class = ScorePagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['score', 'updated_at']