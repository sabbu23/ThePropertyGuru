from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Property, Notification


@receiver(post_save, sender=Property)
def property_status_changed(sender, instance, created, **kwargs):
    """
    Signal to create notifications when a property's status changes to 'sold'
    """
    # Don't run this for newly created properties
    if created:
        return

    # Check if the status field was changed to 'sold'
    if instance.status == 'sold' and instance.tracker.has_changed('status') and instance.tracker.previous(
            'status') == 'available':
        # Create notification for the seller
        seller_user = instance.seller.user

        # Create a notification for the seller
        Notification.objects.create(
            user=seller_user,
            message=f"Congratulations! Your property '{instance.title}' has been marked as sold."
        )

        # Find users who favorited this property and notify them
        for favorite in instance.favorited_by.all():
            if favorite.user != seller_user:  # Don't notify seller twice
                Notification.objects.create(
                    user=favorite.user,
                    message=f"A property you favorited '{instance.title}' has been sold."
                )
