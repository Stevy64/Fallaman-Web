from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from .models import Profile

User = get_user_model()


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        # Le numéro du compte sert de WhatsApp par défaut : c'est celui que la
        # personne vient de saisir, inutile de le lui redemander.
        Profile.objects.get_or_create(
            user=instance,
            defaults={"whatsapp_number": instance.phone_number or ""},
        )
        if not instance.is_staff:
            from apps.notifications.models import Notification
            from apps.notifications.services import notify_staff

            notify_staff(
                Notification.Kind.STAFF_NEW_PROFILE,
                f"Nouveau profil : {instance.display_name} ({instance.phone_number})",
                url=reverse("dashboard:profile_detail", args=[instance.pk]),
            )
