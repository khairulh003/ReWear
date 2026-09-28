"""
Populate the database with demo data.

Seeds:
- 1 admin
- 5 members
- 11 upcoming events
- 11 past events
- 3 clothing requests (one per status)

Usage: python manage.py seed_demo

Re-running clears previously seeded events, sign-ups, notifications,
and requests so the data stays deterministic. 
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import ClothingRequest, Event, EventSignup, Notification


UPCOMING_EVENTS = [
    # (title, type, allow_participants, allow_volunteers)
    ("Donation Drive @ Tampines", Event.TYPE_DONATION_DRIVE, True, True),
    ("Thrift Swap - Vintage Edition", Event.TYPE_THRIFT_SWAP, True, True),
    ("Warm Clothes Collection", Event.TYPE_DONATION_DRIVE, True, True),
    ("Kids Clothing Swap", Event.TYPE_THRIFT_SWAP, True, True),
    ("Community Mending Circle", Event.TYPE_OTHER, True, False),
    ("School Uniform Drive", Event.TYPE_DONATION_DRIVE, True, True),
    ("Sneaker & Accessories Swap", Event.TYPE_THRIFT_SWAP, True, True),
    ("Workwear Donation Drive", Event.TYPE_DONATION_DRIVE, False, True),
    ("Upcycling Workshop", Event.TYPE_OTHER, True, True),
    ("Office Attire Swap", Event.TYPE_THRIFT_SWAP, True, True),
    ("Rainwear & Outerwear Drive", Event.TYPE_DONATION_DRIVE, True, True),
]

PAST_EVENTS = [
    ("Donation Drive: Spring Clear-out", Event.TYPE_DONATION_DRIVE),
    ("Thrift Swap - Launch Edition", Event.TYPE_THRIFT_SWAP),
    ("Blanket & Outerwear Drive", Event.TYPE_DONATION_DRIVE),
    ("Denim Swap", Event.TYPE_THRIFT_SWAP),
    ("Clothing Repair Café", Event.TYPE_OTHER),
    ("Back-to-School Drive", Event.TYPE_DONATION_DRIVE),
    ("Family Clothing Swap", Event.TYPE_THRIFT_SWAP),
    ("Wardrobe Declutter Workshop", Event.TYPE_OTHER),
    ("Formal Wear Drive", Event.TYPE_DONATION_DRIVE),
    ("Activewear Swap", Event.TYPE_THRIFT_SWAP),
    ("Textile Recycling Talk", Event.TYPE_OTHER),
]

DESCRIPTIONS = {
    Event.TYPE_DONATION_DRIVE: (
        "Bring your gently used clothes to our facility and drop them "
        "straight into our sorting bins. Every drive directly restocks the "
        "items we redistribute to our partner causes."
    ),
    Event.TYPE_THRIFT_SWAP: (
        "Bring up to 5 items you no longer wear and swap them for something "
        "new to you. Keeping good clothes circulating beats letting them sit "
        "in a closet."
    ),
    Event.TYPE_OTHER: (
        "A community gathering at our facility. Learn, repair, share, and "
        "meet the neighbours who make ReWear possible."
    ),
}

MEMBERS = [
    # (username, first, last)
    ("amira_yusof", "Amira", "Yusof"),
    ("ben_tan88", "Ben", "Tan"),
    ("chloe.lim", "Chloe", "Lim"),
    ("devi_nair04", "Devi", "Nair"),
    ("ethan_w", "Ethan", "Wong"),
]

# (username, event index, list, role) with a spread of participation patterns:
# some members participate only, some volunteer only, some do both.
SIGNUPS = [
    ("amira_yusof", 0, "upcoming", EventSignup.ROLE_PARTICIPANT),
    ("amira_yusof", 0, "upcoming", EventSignup.ROLE_VOLUNTEER),
    ("amira_yusof", 1, "upcoming", EventSignup.ROLE_PARTICIPANT),
    ("amira_yusof", 0, "past", EventSignup.ROLE_VOLUNTEER),
    ("ben_tan88", 0, "upcoming", EventSignup.ROLE_VOLUNTEER),
    ("ben_tan88", 2, "upcoming", EventSignup.ROLE_VOLUNTEER),
    ("ben_tan88", 1, "past", EventSignup.ROLE_VOLUNTEER),
    ("chloe.lim", 1, "upcoming", EventSignup.ROLE_PARTICIPANT),
    ("chloe.lim", 4, "upcoming", EventSignup.ROLE_PARTICIPANT),
    ("chloe.lim", 3, "past", EventSignup.ROLE_PARTICIPANT),
    ("devi_nair04", 2, "upcoming", EventSignup.ROLE_PARTICIPANT),
    ("devi_nair04", 2, "upcoming", EventSignup.ROLE_VOLUNTEER),
    ("devi_nair04", 4, "past", EventSignup.ROLE_PARTICIPANT),
    ("ethan_w", 5, "upcoming", EventSignup.ROLE_PARTICIPANT),
    ("ethan_w", 7, "upcoming", EventSignup.ROLE_VOLUNTEER),
    ("ethan_w", 2, "past", EventSignup.ROLE_PARTICIPANT),
]

class Command(BaseCommand):
    help = "Seed the database with demo members, events, sign-ups and requests."

    def handle(self, *args, **options):
        now = timezone.now()

        # --- Clear previously seeded demo rows for a deterministic result --
        EventSignup.objects.all().delete()
        Notification.objects.all().delete()
        Event.objects.all().delete()
        ClothingRequest.objects.all().delete()

        # --- Accounts -----------------------------------------------------
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults={
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Admin",
                "last_name": "ReWear",
            },
        )
        if created:
            admin.set_password("rewear-admin")
            admin.save()

        users = {}
        for username, first, last in MEMBERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@example.com",
                },
            )
            if created:
                user.set_password("rewear-demo")
                user.save()
            users[username] = user

        # --- Events -------------------------------------------------------
        upcoming = []
        for i, (title, event_type, allow_p, allow_v) in enumerate(UPCOMING_EVENTS):
            upcoming.append(Event.objects.create(
                title=title,
                description=DESCRIPTIONS[event_type],
                event_type=event_type,
                date=now + timedelta(days=4 + i * 3, hours=2),
                location="ReWear Facility, Tampines",
                allow_participants=allow_p,
                allow_volunteers=allow_v,
            ))

        past = []
        for i, (title, event_type) in enumerate(PAST_EVENTS):
            past.append(Event.objects.create(
                title=title,
                description=DESCRIPTIONS[event_type],
                event_type=event_type,
                date=now - timedelta(days=6 + i * 9),
                location="ReWear Facility, Tampines",
            ))

        # --- Clothing requests: one of each status ------------------------
        shelter_aid = ClothingRequest.objects.create(
            organisation_name="Shelter Aid Singapore",
            contact_name="Jane Tan",
            email="jane@shelteraid.org",
            clothing_type="warm jackets",
            quantity="100 pieces",
            message="For families affected by extreme cold.",
            status=ClothingRequest.STATUS_EVENT_CREATED,
        )
        warm_clothes = upcoming[2]  # "Warm Clothes Collection"
        warm_clothes.created_from = shelter_aid
        warm_clothes.description = (
            "Created in response to a request from Shelter Aid Singapore, who "
            "support families affected by extreme cold. We're collecting warm "
            "jackets, sweaters, and thermal wear for direct redistribution."
        )
        warm_clothes.save()

        ClothingRequest.objects.create(
            organisation_name="Hope Family Services",
            contact_name="Priya Raj",
            email="priya@hopefamily.org",
            clothing_type="work attire for job seekers",
            quantity="60 pieces",
            message="Supporting adults re-entering the workforce.",
            status=ClothingRequest.STATUS_REVIEWED,
        )
        ClothingRequest.objects.create(
            organisation_name="Bright Beginnings Shelter",
            contact_name="Marcus Lee",
            email="marcus@brightbeginnings.org",
            clothing_type="children's clothing, ages 4-10",
            quantity="80 pieces",
            message="Ahead of the new school term.",
        )

        # --- Sign-ups & notifications ------------------------------------
        lists = {"upcoming": upcoming, "past": past}
        for username, index, which, role in SIGNUPS:
            event = lists[which][index]
            if not event.role_is_open(role):
                continue
            signup, created = EventSignup.objects.get_or_create(
                user=users[username], event=event, role=role
            )
            if created:
                Notification.objects.create(
                    user=users[username],
                    message=(
                        f"You're confirmed: {signup.get_role_display()} - "
                        f"{event.title}"
                    ),
                )

        self.stdout.write(self.style.SUCCESS(
            "Demo data ready: 5 members, 11 upcoming + 11 past events, "
            "3 requests (New / Reviewed / Event created). "
            "Log in as admin/rewear-admin or amira_yusof/rewear-demo "
            "(ben_tan88, chloe.lim, devi_nair04, ethan_w share the same demo password)."
        ))
