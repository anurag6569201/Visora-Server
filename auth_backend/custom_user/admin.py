from django.contrib import admin
from custom_user.models import CustomUser,CustomUserSocielMedia,Score

admin.site.register(CustomUser)
admin.site.register(CustomUserSocielMedia)
admin.site.register(Score)
