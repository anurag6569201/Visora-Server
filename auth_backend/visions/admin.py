from django.contrib import admin
from .models import AnimationRequest, Contribution, Engagement, Notification
from .models import OpenSourceVisionRequest, OpenSourceAttachment,OpenSourceContribution


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



class OpenSourceAttachmentInline(admin.TabularInline): 
    model = OpenSourceAttachment
    extra = 1
    readonly_fields = ('uploaded_at',)

@admin.register(OpenSourceVisionRequest)
class OpenSourceVisionRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'category', 'difficulty', 'funding_goal', 'current_funding', 'visibility', 'created_at')
    list_filter = ('category', 'difficulty', 'visibility', 'created_at')
    search_fields = ('title', 'description', 'creator__username')
    readonly_fields = ('creator', 'current_funding', 'created_at', 'updated_at')
    inlines = [OpenSourceAttachmentInline] 

    # Override save_model to set creator if created via admin (optional)
    # def save_model(self, request, obj, form, change):
    #     if not obj.pk: # If creating a new object
    #         obj.creator = request.user
    #     super().save_model(request, obj, form, change)



class ContributionInline(admin.TabularInline):
    model = Contribution
    extra = 0 # Don't show empty forms by default
    readonly_fields = ('contributor', 'amount', 'razorpay_payment_id', 'timestamp')
    can_delete = False # Prevent deleting contributions from request admin
    ordering = ('-timestamp',)


@admin.register(OpenSourceContribution)
class OpenSourceContributionAdmin(admin.ModelAdmin):
    list_display = ('request_title', 'contributor_username', 'amount', 'timestamp', 'razorpay_payment_id')
    list_filter = ('timestamp', 'request__category')
    search_fields = ('request__title', 'contributor__username', 'razorpay_payment_id')
    readonly_fields = ('contributor', 'request', 'amount', 'razorpay_payment_id', 'timestamp')

    def request_title(self, obj):
        return obj.request.title
    request_title.short_description = 'Vision Request'

    def contributor_username(self, obj):
        return obj.contributor.username if obj.contributor else 'Anonymous'
    contributor_username.short_description = 'Contributor'