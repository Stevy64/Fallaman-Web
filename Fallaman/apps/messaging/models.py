"""Discussions éphémères entre un pourvoyeur et un candidat.

La messagerie est volontairement temporaire : Fallaman met en relation, puis
s'efface au profit du téléphone ou de WhatsApp. Deux échéances courent donc en
parallèle, et c'est la **plus proche** qui fait foi (``effective_expiry``) :

* ``expires_at`` — inactivité. Repoussée à chaque message par ``touch()``, de
  ``CONVERSATION_IDLE_HOURS`` (72 h par défaut).
* ``hard_expires_at`` — plafond absolu, fixé à la création à
  ``CONVERSATION_MAX_DAYS`` (7 jours). Jamais repoussé : une discussion ne peut
  pas durer indéfiniment à coups de messages.

À l'expiration, les messages sont **supprimés** (voir
``tasks.expire_conversations`` et la vue du fil) : ne comptez pas sur cette
table pour un historique.

Les deux participants sont rangés dans ``user_low``/``user_high`` par ordre de
clé primaire. Ce n'est pas cosmétique : c'est ce qui permet à la contrainte
d'unicité de garantir une seule discussion par couple et par annonce, quel que
soit celui qui écrit en premier. Passez toujours par
``Conversation.objects.get_or_create_for()``.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class ConversationQuerySet(models.QuerySet):
    def visible_for(self, user):
        return self.filter(models.Q(user_low=user) | models.Q(user_high=user), is_expired=False)


class ConversationManager(models.Manager):
    def get_queryset(self):
        return ConversationQuerySet(self.model, using=self._db)

    def visible_for(self, user):
        return self.get_queryset().visible_for(user)

    def get_or_create_for(self, listing, user_a, user_b):
        low, high = (user_a, user_b) if user_a.pk < user_b.pk else (user_b, user_a)
        now = timezone.now()
        conversation, created = self.get_or_create(
            listing=listing,
            user_low=low,
            user_high=high,
            defaults={
                "last_message_at": now,
                "expires_at": now + timedelta(hours=settings.CONVERSATION_IDLE_HOURS),
                "hard_expires_at": now + timedelta(days=settings.CONVERSATION_MAX_DAYS),
            },
        )
        return conversation


class Conversation(models.Model):
    listing = models.ForeignKey("listings.Listing", related_name="conversations", on_delete=models.CASCADE)
    user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="conversations_low", on_delete=models.CASCADE
    )
    user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="conversations_high", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    hard_expires_at = models.DateTimeField()
    is_expired = models.BooleanField(default=False)

    objects = ConversationManager()

    class Meta:
        unique_together = ("listing", "user_low", "user_high")
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Discussion {self.listing_id}"

    def get_absolute_url(self):
        return reverse("messaging:thread", args=[self.pk])

    def other_user(self, user):
        return self.user_high if user == self.user_low else self.user_low

    def has_member(self, user):
        return user in {self.user_low, self.user_high}

    def touch(self):
        now = timezone.now()
        idle = now + timedelta(hours=settings.CONVERSATION_IDLE_HOURS)
        self.last_message_at = now
        self.expires_at = min(idle, self.hard_expires_at)
        self.save(update_fields=["last_message_at", "expires_at"])

    @property
    def remaining(self):
        delta = self.effective_expiry - timezone.now()
        return delta if delta.total_seconds() > 0 else timedelta(0)

    @property
    def effective_expiry(self):
        return min(self.expires_at, self.hard_expires_at)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, related_name="messages", on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="sent_messages", on_delete=models.CASCADE)
    body = models.TextField(max_length=2000)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.pk}"
