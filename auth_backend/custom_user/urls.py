from django.urls import path, include
from rest_framework.routers import DefaultRouter
from custom_user.views import CustomUserSocialMediaViewSet
from custom_user import views
from custom_user.views import CustomUserView

app_name = 'custom_user'

urlpatterns = [
    path('auth/user/', CustomUserView.as_view(), name='custom_user'),

    path('', views.home, name='home'),
    path('auth/user/social/<int:pk>/', CustomUserSocialMediaViewSet.as_view({'get': 'retrieve'}), name="social-detail"),
]
