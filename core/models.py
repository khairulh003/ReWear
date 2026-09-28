from django.conf import settings
from django.db import models
from django.urls import reverse


class ClothingRequest(models.Model):
    """
    A clothing request submitted by an external organisation via the
    Contact page. Reviewed by the admin, who may create an Event from it.
    """

    STATUS_NEW = "new"
    STATUS_REVIEWED = "reviewed"
    STATUS_EVENT_CREATED = "event_created"
    STATUS_CHOICES = [
        (STATUS_NEW, "New"),
        (STATUS_REVIEWED, "Reviewed"),
        (STATUS_EVENT_CREATED, "Event created"),
    ]

    organisation_name = models.CharField(max_length=120)
    contact_name = models.CharField(max_length=120)
    email = models.EmailField()
    clothing_type = models.CharField(
        max_length=120,
        help_text="e.g. warm clothing, children's wear, work attire",
    )
    quantity = models.CharField(
        max_length=80,
        help_text="Approximate amount needed, e.g. '50 pieces'",
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organisation_name} - {self.clothing_type}"


class Event(models.Model):
    """
    A community event (Donation Drive, Thrift Swap, ...).
    The central organising unit of the platform.
    """

    TYPE_DONATION_DRIVE = "donation_drive"
    TYPE_THRIFT_SWAP = "thrift_swap"
    TYPE_OTHER = "other"
    TYPE_CHOICES = [
        (TYPE_DONATION_DRIVE, "Donation Drive"),
        (TYPE_THRIFT_SWAP, "Thrift Swap"),
        (TYPE_OTHER, "Community Event"),
    ]

    title = models.CharField(max_length=140)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date = models.DateTimeField()
    location = models.CharField(max_length=140)
    allow_participants = models.BooleanField(
        default=True,
        verbose_name="Allow participants",
        help_text="Members can sign up to take part (bring/swap clothes).",
    )
    allow_volunteers = models.BooleanField(
        default=True,
        verbose_name="Requesting volunteers",
        help_text="Members can sign up to help sort, organise, and run the event.",
    )
    created_from = models.ForeignKey(
        ClothingRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
        help_text="The clothing request this event was created in response to, if any.",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="EventSignup",
        related_name="events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("event_detail", args=[self.pk])


    @property
    def css_type(self):
        """
        Maps event_type to the visual type classes ('drive' | 'swap' | 'community')
        used for card thumbs, hero gradients, and icon tiles.
        """
        return {
            self.TYPE_DONATION_DRIVE: "drive",
            self.TYPE_THRIFT_SWAP: "swap",
            self.TYPE_OTHER: "community",
        }.get(self.event_type, "drive")

    @property
    def display_icon(self):
        """
        Standardized event emojis: 🧺 Donation Drive, ♻️ Thrift Swap, 🫂 Community Event.
        """
        return {
            self.TYPE_DONATION_DRIVE: "🧺",
            self.TYPE_THRIFT_SWAP: "♻️",
            self.TYPE_OTHER: "🫂",
        }.get(self.event_type, "🧺")

    def role_is_open(self, role):
        if role == EventSignup.ROLE_PARTICIPANT:
            return self.allow_participants
        if role == EventSignup.ROLE_VOLUNTEER:
            return self.allow_volunteers
        return False

    @property
    def joined_count(self):
        """Distinct members signed up in any role."""
        return self.signups.values("user").distinct().count()

    @property
    def participant_count(self):
        return self.signups.filter(role=EventSignup.ROLE_PARTICIPANT).count()

    @property
    def volunteer_count(self):
        return self.signups.filter(role=EventSignup.ROLE_VOLUNTEER).count()


class EventSignup(models.Model):
    """
    The many-to-many 'through' model between User and Event, with a role
    field on the relationship itself. A member can hold BOTH roles for the
    same event as two independent rows.
    """

    ROLE_PARTICIPANT = "participant"
    ROLE_VOLUNTEER = "volunteer"
    ROLE_CHOICES = [
        (ROLE_PARTICIPANT, "Participant"),
        (ROLE_VOLUNTEER, "Volunteer"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signups"
    )
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="signups"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event", "role"], name="unique_user_event_role"
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.get_role_display()} - {self.event}"


class Notification(models.Model):
    """
    A simple dashboard notification for a member.
    Created whenever an EventSignup is made.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.CharField(max_length=255)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
