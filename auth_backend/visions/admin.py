from django.contrib import admin
from .models import AnimationRequest, Contribution, Engagement, Notification

@admin.register(AnimationRequest)
class AnimationRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description', 'created_by__username')
    ordering = ('-created_at',)

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ('get_animation_request', 'developer', 'likes', 'comments', 'submitted_at', 'approved')
    list_filter = ('approved', 'submitted_at')
    search_fields = ('animation_request__title', 'developer__username')
    ordering = ('-submitted_at',)

    def get_animation_request(self, obj):
        return obj.animation_request.title  # Ensure 'animation_request' is a ForeignKey in Contribution model
    get_animation_request.short_description = "Animation Request"

@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    list_display = ('user', 'contribution', 'get_engagement_type', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'contribution__animation_request__title')
    ordering = ('-created_at',)

    def get_engagement_type(self, obj):
        return obj.get_engagement_type_display()  # Use this if 'engagement_type' is a choice field
    get_engagement_type.short_description = "Engagement Type"

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'message')
    ordering = ('-created_at',)
