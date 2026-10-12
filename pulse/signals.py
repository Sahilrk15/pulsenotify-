from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Every new User automatically gets a UserProfile (role defaults to USER)."""
    if created:
        UserProfile.objects.create(user=instance)
