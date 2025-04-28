from django.contrib import admin
from .models import (
    UserProfile,
    SellerVerification,
    Notification,
    Property,
    PropertyImage,
    Favorite,
    PropertyView,
    Conversation,
    Message
)


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_verified', 'phone')
    list_filter = ('role', 'is_verified')
    search_fields = ('user__username', 'user__email', 'phone')


class SellerVerificationAdmin(admin.ModelAdmin):
    list_display = ('seller', 'submitted_at', 'status', 'approved_by', 'approved_at')
    list_filter = ('status', 'approved')
    search_fields = ('seller__user__username',)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 3


class PropertyViewInline(admin.TabularInline):
    model = PropertyView
    extra = 0
    readonly_fields = ('user', 'viewed_at', 'session_key')


class PropertyAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'property_type', 'purpose', 'price', 'city', 'is_active', 'status', 'view_count')
    list_filter = ('property_type', 'purpose', 'is_active', 'is_featured')
    search_fields = ('title', 'description', 'address', 'city')
    inlines = [PropertyImageInline, PropertyViewInline]

    def view_count(self, obj):
        return obj.views.count()

    view_count.short_description = 'Views'


class PropertyViewAdmin(admin.ModelAdmin):
    list_display = ('property', 'user', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('property__title', 'user__username')
    date_hierarchy = 'viewed_at'


class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'property', 'added_at')
    list_filter = ('added_at',)
    search_fields = ('user__username', 'property__title')


class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'shortened_message', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'message')

    def shortened_message(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message

    shortened_message.short_description = 'Message'


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0


class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_participants', 'property', 'started_at', 'last_message_at')
    list_filter = ('started_at', 'last_message_at')
    inlines = [MessageInline]

    def get_participants(self, obj):
        return ", ".join([user.username for user in obj.participants.all()])

    get_participants.short_description = 'Participants'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('participants')


class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('sender__username', 'content')


admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(SellerVerification, SellerVerificationAdmin)
admin.site.register(Property, PropertyAdmin)
admin.site.register(PropertyImage)
admin.site.register(PropertyView, PropertyViewAdmin)
admin.site.register(Favorite, FavoriteAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(Conversation, ConversationAdmin)
admin.site.register(Message, MessageAdmin)