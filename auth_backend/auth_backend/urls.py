
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from auth_backend import views
from dj_rest_auth.registration.views import RegisterView
from custom_user.serializers import CustomRegisterSerializer

app_name='auth_backend'

router = DefaultRouter()

urlpatterns = [
    path('',views.home,name='home'),
    path('admin/', admin.site.urls),
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', RegisterView.as_view(serializer_class=CustomRegisterSerializer)),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
