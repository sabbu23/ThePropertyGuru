from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('seller-verification/', views.seller_verification_view, name='seller_verification'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('approve-seller/<int:verification_id>/', views.approve_seller, name='approve_seller'),
    path('reject-seller/<int:verification_id>/', views.reject_seller, name='reject_seller'),
    path('seller-dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller-verification-details/<int:verification_id>/', views.seller_verification_details,
         name='seller_verification_details'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),

    # Property related URLs
    path('properties/', views.property_list, name='property_list'),
    path('properties/<int:property_id>/', views.property_detail, name='property_detail'),
    path('add-property/', views.add_property, name='add_property'),
    path('edit-property/<int:property_id>/', views.edit_property, name='edit_property'),
    path('delete-property/<int:property_id>/', views.delete_property, name='delete_property'),
    path('upload-property-image/<int:property_id>/', views.upload_property_image, name='upload_property_image'),
    path('delete-property-image/<int:image_id>/', views.delete_property_image, name='delete_property_image'),
    path('set-primary-image/<int:image_id>/', views.set_primary_image, name='set_primary_image'),
    path('toggle-property-status/<int:property_id>/', views.toggle_property_status, name='toggle_property_status'),

    # Buyer specific URLs
    path('buy/', views.buy_properties, name='buy_properties'),
    path('rent/', views.rent_properties, name='rent_properties'),
    path('favorite/<int:property_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('my-favorites/', views.my_favorites, name='my_favorites'),

    # Seller specific URLs
    path('manage-properties/', views.manage_properties, name='manage_properties'),

    # Messaging URLs
    path('inbox/', views.inbox, name='inbox'),
    path('conversation/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('start-conversation/<int:user_id>/', views.start_conversation, name='start_conversation'),
    path('start-conversation/<int:user_id>/<int:property_id>/', views.start_conversation, name='start_conversation_property'),
    path('check-new-messages/<int:conversation_id>/', views.check_new_messages, name='check_new_messages'),
    path('unread-message-count/', views.unread_message_count, name='unread_message_count'),

    path('user-profile/<int:user_id>/', views.user_profile_view, name='user_profile'),
    # csrf token
    path('get-csrf-token/', views.get_csrf_token, name='get_csrf_token')
]
