from django.db import models
from django.contrib.auth.models import User

# for adding additional user fields later, a profile model can be created:
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.user.username