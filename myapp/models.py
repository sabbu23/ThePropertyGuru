
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from model_utils import FieldTracker

# User roles as choices
USER_ROLES = (
    ('buyer', 'Buyer'),
    ('seller', 'Seller'),
    ('admin', 'Admin'),
)


# User profile with role and verification
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=USER_ROLES, default='buyer')
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)  # For sellers requiring verification

    def __str__(self):
        return f"{self.user.username} - {self.role}"


# Seller verification status choices
VERIFICATION_STATUS = (
    ('pending', 'Pending Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
)


# Seller verification documents
class SellerVerification(models.Model):
    seller = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='verification')
    profile_picture = models.ImageField(upload_to='seller_profiles/')
    identity_proof = models.ImageField(upload_to='seller_verification/')
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=VERIFICATION_STATUS, default='pending')
    approved = models.BooleanField(default=False)  # For backward compatibility
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approvals')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='rejections')

    def __str__(self):
        return f"Verification for {self.seller.user.username}"


# Notification model for system messages
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:30]}..."


# Property types and purposes
PROPERTY_TYPES = (
    ('house', 'House'),
    ('apartment', 'Apartment'),
    ('villa', 'Villa'),
    ('land', 'Land'),
    ('commercial', 'Commercial'),
    ('office', 'Office Space'),
)

PROPERTY_PURPOSES = (
    ('sale', 'For Sale'),
    ('rent', 'For Rent'),
)

PROPERTY_STATUS = (
    ('available', 'Available'),
    ('sold', 'Sold'),
)

CITIES = (
    ('kathmandu', 'Kathmandu'),
    ('pokhara', 'Pokhara'),
    ('lalitpur', 'Lalitpur'),
    ('bhaktapur', 'Bhaktapur'),
)


# Property model
class Property(models.Model):
    seller = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=200)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    purpose = models.CharField(max_length=10, choices=PROPERTY_PURPOSES)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    area_size = models.DecimalField(max_digits=10, decimal_places=2, help_text="Size in square feet")
    bedrooms = models.PositiveSmallIntegerField(default=0)
    bathrooms = models.PositiveSmallIntegerField(default=0)
    address = models.TextField()
    city = models.CharField(max_length=100, choices=CITIES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tracker = FieldTracker(fields=['status'])
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=PROPERTY_STATUS, default='available')

    class Meta:
        verbose_name_plural = "Properties"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_primary_image(self):
        primary = self.images.filter(is_primary=True).first()
        if primary:
            return primary
        # Return first image if no primary is set
        return self.images.first()


# Property images
class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='property_images/')
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'uploaded_at']

    def __str__(self):
        return f"Image for {self.property.title}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Set all other images of this property as not primary
            PropertyImage.objects.filter(property=self.property, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


# Favorite properties for users
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='favorited_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'property')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} favorited {self.property.title}"


# For property view count
class PropertyView(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='property_views')
    viewed_at = models.DateTimeField(default=timezone.now)
    session_key = models.CharField(max_length=40, blank=True, null=True)

    class Meta:
        ordering = ['-viewed_at']
        # Adding a unique constraint to prevent duplicate views from the same user on same property
        unique_together = ('property', 'user')

    def __str__(self):
        return f"View of {self.property.title} at {self.viewed_at}"


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='conversations', null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-last_message_at']

    def get_other_participant(self, user):
        """Get the other participant in the conversation"""
        return self.participants.exclude(id=user.id).first()

    def mark_read(self, user):
        """Mark all messages as read for a user"""
        self.messages.filter(sender__pk=self.get_other_participant(user).pk, is_read=False).update(is_read=True)

    def unread_count(self, user):
        """Count unread messages for a user"""
        return self.messages.filter(sender__pk=self.get_other_participant(user).pk, is_read=False).count()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
