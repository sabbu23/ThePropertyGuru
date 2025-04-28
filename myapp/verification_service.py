from django.utils import timezone
from django.contrib.auth.models import User
from .models import SellerVerification, Notification


class VerificationService:
    """
    service class to handle seller verification processes.
    encapsulate verification logic
    """

    def __init__(self, verification_id=None):
        self.verification_id = verification_id
        self.verification = None
        if verification_id:
            self.load_verification()

    def load_verification(self):
        """Load the verification object"""
        try:
            self.verification = SellerVerification.objects.get(id=self.verification_id)
            return True
        except SellerVerification.DoesNotExist:
            return False

    def approve(self, admin_user):
        """Approve a seller verification"""
        if not self.verification:
            return False

        # Update verification
        self.verification.status = 'approved'
        self.verification.approved = True
        self.verification.approved_by = admin_user
        self.verification.approved_at = timezone.now()
        self.verification.save()

        # Update seller profile
        seller_profile = self.verification.seller
        seller_profile.is_verified = True
        seller_profile.save()

        # Create notification
        self._create_approval_notification(self.verification.seller.user)

        return True

    def reject(self, admin_user, reason):
        """Reject a seller verification with a reason"""
        if not self.verification:
            return False

        # Update verification
        self.verification.status = 'rejected'
        self.verification.approved = False
        self.verification.rejection_reason = reason
        self.verification.rejected_at = timezone.now()
        self.verification.rejected_by = admin_user
        self.verification.save()

        # Create notification
        self._create_rejection_notification(self.verification.seller.user, reason)

        return True

    def resubmit(self, profile_picture=None, identity_proof=None):
        """Resubmit a verification with new documents"""
        if not self.verification:
            return False

        # Update documents if provided
        if profile_picture:
            self.verification.profile_picture = profile_picture
        if identity_proof:
            self.verification.identity_proof = identity_proof

        # Reset verification status
        self.verification.status = 'pending'
        self.verification.approved = False
        self.verification.rejected_reason = None
        self.verification.save()

        return True

    def _create_approval_notification(self, user):
        """Create an approval notification"""
        Notification.objects.create(
            user=user,
            message="Congratulations! Your seller account has been verified. You can now list properties on our platform."
        )

    def _create_rejection_notification(self, user, reason):
        """Create a rejection notification with the reason"""
        Notification.objects.create(
            user=user,
            message=f"Your seller verification has been rejected. Reason: {reason}. Please update your documents and resubmit."
        )

    @staticmethod
    def create_verification(seller_profile, profile_picture, identity_proof):
        """Create a new verification entry"""
        verification = SellerVerification(
            seller=seller_profile,
            profile_picture=profile_picture,
            identity_proof=identity_proof,
            status='pending'
        )
        verification.save()
        return verification