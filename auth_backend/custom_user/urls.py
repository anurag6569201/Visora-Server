
from django.urls import path
from custom_user import views
from custom_user.views import CustomUserView

app_name='custom_user'


urlpatterns = [
    path('',views.home,name='home'),

    path('auth/user/', CustomUserView.as_view(), name='custom_user'),
]
