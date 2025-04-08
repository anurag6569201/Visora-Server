from django.urls import path, include
from rest_framework.routers import DefaultRouter
from custom_user.views import CustomUserSocialMediaViewSet
from custom_user import views
from custom_user.views import CustomUserView,ScoreViewSet
from .views import follow_user, unfollow_user, user_follow_stats

app_name = 'custom_user'
router = DefaultRouter()
router.register(r'scores', ScoreViewSet)

urlpatterns = [
    path('auth/user/', CustomUserView.as_view(), name='custom_user'),
    path('auth/user/<int:user_id>/', views.UserByIdView, name='user_by_id'),

    path('', views.home, name='home'),
    path('auth/user/social/<int:pk>/', CustomUserSocialMediaViewSet.as_view({'get': 'retrieve','put':'update'}), name="social-detail"),

    path("follow/<int:user_id>/", follow_user, name="follow_user"),
    path("unfollow/<int:user_id>/", unfollow_user, name="unfollow_user"),
    path("user/<int:user_id>/stats/", user_follow_stats, name="user_follow_stats"),

    path('api/', include(router.urls)),
    
]
