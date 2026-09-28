"""Unit tests for ReWear."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ClothingRequest, Event, EventSignup, Notification


def make_event(**overrides):
    defaults = {
        "title": "Thrift Swap - Weekend Edition",
        "description": "Bring up to 5 items.",
        "event_type": Event.TYPE_THRIFT_SWAP,
        "date": timezone.now() + timedelta(days=7),
        "location": "ReWear Facility, Tampines",
    }
    defaults.update(overrides)
    return Event.objects.create(**defaults)


class EventSignupModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amira", password="test-pass-123")
        self.event = make_event()

    def test_member_can_hold_both_roles_for_same_event(self):
        """Participant and volunteer are two independent rows on the same relationship."""
        EventSignup.objects.create(
            user=self.user, event=self.event, role=EventSignup.ROLE_PARTICIPANT
        )
        EventSignup.objects.create(
            user=self.user, event=self.event, role=EventSignup.ROLE_VOLUNTEER
        )
        roles = set(
            self.event.signups.filter(user=self.user).values_list("role", flat=True)
        )
        self.assertEqual(roles, {"participant", "volunteer"})

    def test_duplicate_role_for_same_event_is_rejected(self):
        EventSignup.objects.create(
            user=self.user, event=self.event, role=EventSignup.ROLE_PARTICIPANT
        )
        with self.assertRaises(IntegrityError):
            EventSignup.objects.create(
                user=self.user, event=self.event, role=EventSignup.ROLE_PARTICIPANT
            )


class EventSignupViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("amira", password="test-pass-123")
        self.event = make_event()
        self.url = reverse("event_signup", args=[self.event.pk, "participant"])

    def test_unauthenticated_visitor_is_redirected_to_login(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_signup_creates_row_and_notification(self):
        self.client.login(username="amira", password="test-pass-123")
        response = self.client.post(self.url)
        self.assertRedirects(response, self.event.get_absolute_url())
        self.assertTrue(
            EventSignup.objects.filter(
                user=self.user, event=self.event, role="participant"
            ).exists()
        )
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_repeat_signup_same_role_does_not_duplicate(self):
        self.client.login(username="amira", password="test-pass-123")
        self.client.post(self.url)
        self.client.post(self.url)
        self.assertEqual(
            EventSignup.objects.filter(user=self.user, event=self.event).count(), 1
        )
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_both_roles_via_view_coexist(self):
        self.client.login(username="amira", password="test-pass-123")
        self.client.post(self.url)
        self.client.post(reverse("event_signup", args=[self.event.pk, "volunteer"]))
        self.assertEqual(
            EventSignup.objects.filter(user=self.user, event=self.event).count(), 2
        )

    def test_cannot_sign_up_for_past_event(self):
        past_event = make_event(date=timezone.now() - timedelta(days=1))
        self.client.login(username="amira", password="test-pass-123")
        self.client.post(reverse("event_signup", args=[past_event.pk, "participant"]))
        self.assertFalse(
            EventSignup.objects.filter(user=self.user, event=past_event).exists()
        )


class AdminRequestFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin", password="admin-pass-123", is_staff=True
        )
        self.request_obj = ClothingRequest.objects.create(
            organisation_name="Hope Shelter",
            contact_name="Jane Tan",
            email="jane@hopeshelter.org",
            clothing_type="warm clothing",
            quantity="50 pieces",
        )

    def test_create_event_from_request_links_and_updates_status(self):
        self.client.login(username="admin", password="admin-pass-123")
        response = self.client.post(
            reverse("admin_event_create"),
            {
                "from_request": self.request_obj.pk,
                "title": "Warm Clothes Wednesday",
                "description": "Drive for Hope Shelter.",
                "event_type": Event.TYPE_DONATION_DRIVE,
                "date": (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M"),
                "location": "ReWear Facility, Tampines",
                "allow_participants": "on",
                "allow_volunteers": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        event = Event.objects.get(title="Warm Clothes Wednesday")
        self.assertEqual(event.created_from, self.request_obj)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, ClothingRequest.STATUS_EVENT_CREATED)

    def test_non_staff_cannot_access_admin_dashboard(self):
        User.objects.create_user("amira", password="test-pass-123")
        self.client.login(username="amira", password="test-pass-123")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)  # redirected away


class RoleToggleTests(TestCase):
    """Events can allow participants, request volunteers, or both."""

    def setUp(self):
        self.user = User.objects.create_user("amira", password="test-pass-123")
        self.client.login(username="amira", password="test-pass-123")

    def test_signup_rejected_when_role_disabled(self):
        event = make_event(allow_volunteers=False)
        self.client.post(reverse("event_signup", args=[event.pk, "volunteer"]))
        self.assertFalse(
            EventSignup.objects.filter(user=self.user, event=event).exists()
        )

    def test_signup_allowed_for_enabled_role(self):
        event = make_event(allow_volunteers=False)
        self.client.post(reverse("event_signup", args=[event.pk, "participant"]))
        self.assertTrue(
            EventSignup.objects.filter(
                user=self.user, event=event, role="participant"
            ).exists()
        )


class EventChangeNotificationTests(TestCase):
    """Members signed up to an event are notified when it changes or is cancelled"""

    def setUp(self):
        self.admin = User.objects.create_user(
            "admin", password="admin-pass-123", is_staff=True
        )
        self.member = User.objects.create_user("amira", password="test-pass-123")
        self.event = make_event()
        EventSignup.objects.create(
            user=self.member, event=self.event, role=EventSignup.ROLE_PARTICIPANT
        )
        self.client.login(username="admin", password="admin-pass-123")

    def test_editing_event_notifies_signed_up_members(self):
        response = self.client.post(
            reverse("admin_event_edit", args=[self.event.pk]),
            {
                "title": self.event.title,
                "description": self.event.description,
                "event_type": self.event.event_type,
                "date": (timezone.now() + timedelta(days=9)).strftime("%Y-%m-%dT%H:%M"),
                "location": "New Venue, Bedok",
                "allow_participants": "on",
                "allow_volunteers": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        note = Notification.objects.filter(user=self.member).latest("created_at")
        self.assertIn("Event updated", note.message)
        self.assertIn("location", note.message)

    def test_deleting_event_notifies_signed_up_members(self):
        title = self.event.title
        self.client.post(reverse("admin_event_delete", args=[self.event.pk]))
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())
        note = Notification.objects.filter(user=self.member).latest("created_at")
        self.assertIn("Event cancelled", note.message)
        self.assertIn(title, note.message)

    def test_member_who_did_not_sign_up_is_not_notified(self):
        outsider = User.objects.create_user("ben", password="test-pass-123")
        self.client.post(reverse("admin_event_delete", args=[self.event.pk]))
        self.assertFalse(Notification.objects.filter(user=outsider).exists())


class PostLoginRoutingTests(TestCase):
    def test_staff_login_lands_on_admin_dashboard(self):
        User.objects.create_user("admin", password="admin-pass-123", is_staff=True)
        response = self.client.post(
            reverse("login"),
            {"username": "admin", "password": "admin-pass-123"},
            follow=True,
        )
        self.assertEqual(response.request["PATH_INFO"], reverse("admin_dashboard"))

    def test_member_login_lands_on_member_dashboard(self):
        User.objects.create_user("amira", password="test-pass-123")
        response = self.client.post(
            reverse("login"),
            {"username": "amira", "password": "test-pass-123"},
            follow=True,
        )
        self.assertEqual(response.request["PATH_INFO"], reverse("dashboard"))


class PasswordChangeTests(TestCase):
    def test_member_can_change_password_from_profile_tab(self):
        user = User.objects.create_user("amira", password="old-pass-123")
        self.client.login(username="amira", password="old-pass-123")
        response = self.client.post(
            reverse("dashboard") + "?tab=profile",
            {
                "change_password": "1",
                "old_password": "old-pass-123",
                "new_password1": "brand-new-pass-456",
                "new_password2": "brand-new-pass-456",
            },
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.check_password("brand-new-pass-456"))


class PaginationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin", password="admin-pass-123", is_staff=True
        )

    def test_events_page_shows_six_upcoming_per_page(self):
        for i in range(8):
            make_event(title=f"Event {i}", date=timezone.now() + timedelta(days=i + 1))
        response = self.client.get(reverse("event_list"))
        self.assertEqual(len(response.context["upcoming_events"].object_list), 6)
        response = self.client.get(reverse("event_list") + "?page=2")
        self.assertEqual(len(response.context["upcoming_events"].object_list), 2)

    def test_events_page_shows_five_past_per_page(self):
        for i in range(7):
            make_event(title=f"Past {i}", date=timezone.now() - timedelta(days=i + 1))
        response = self.client.get(reverse("event_list"))
        self.assertEqual(len(response.context["past_events"].object_list), 5)

    def test_admin_requests_tab_shows_ten_per_page(self):
        for i in range(13):
            ClothingRequest.objects.create(
                organisation_name=f"Org {i}",
                contact_name="Contact",
                email="contact@example.org",
                clothing_type="clothes",
                quantity="10 pieces",
            )
        self.client.login(username="admin", password="admin-pass-123")
        response = self.client.get("/manage/?tab=requests")
        self.assertEqual(len(response.context["clothing_requests"].object_list), 10)
        response = self.client.get("/manage/?tab=requests&req_page=2")
        self.assertEqual(len(response.context["clothing_requests"].object_list), 3)

    def test_type_filter_is_preserved_in_pagination_querystring(self):
        for i in range(12):
            make_event(
                title=f"Drive {i}",
                event_type=Event.TYPE_DONATION_DRIVE,
                date=timezone.now() + timedelta(days=i + 1),
            )
        response = self.client.get(reverse("event_list") + "?type=drive")
        self.assertIn("type=drive", response.context["qs_page"])


class RequestDeleteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin", password="admin-pass-123", is_staff=True
        )
        self.client.login(username="admin", password="admin-pass-123")

    def test_deleting_request_keeps_linked_event(self):
        req = ClothingRequest.objects.create(
            organisation_name="Shelter Aid",
            contact_name="Jane",
            email="jane@example.org",
            clothing_type="jackets",
            quantity="100 pieces",
            status=ClothingRequest.STATUS_EVENT_CREATED,
        )
        event = make_event(created_from=req)
        self.client.post(reverse("admin_request_delete", args=[req.pk]))
        self.assertFalse(ClothingRequest.objects.filter(pk=req.pk).exists())
        event.refresh_from_db()  # event survives; created_from becomes NULL
        self.assertIsNone(event.created_from)


class SignupRemovalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin", password="admin-pass-123", is_staff=True
        )
        self.member = User.objects.create_user(
            "amira", password="test-pass-123", first_name="Amira", last_name="Yusof"
        )
        self.event = make_event()
        self.signup = EventSignup.objects.create(
            user=self.member, event=self.event, role=EventSignup.ROLE_PARTICIPANT
        )
        self.client.login(username="admin", password="admin-pass-123")

    def test_admin_can_remove_signup_and_member_is_notified(self):
        response = self.client.post(
            reverse("admin_signup_remove", args=[self.signup.pk])
        )
        self.assertRedirects(
            response, reverse("admin_event_signups", args=[self.event.pk])
        )
        self.assertFalse(EventSignup.objects.filter(pk=self.signup.pk).exists())
        note = Notification.objects.filter(user=self.member).latest("created_at")
        self.assertIn("removed", note.message)
        self.assertIn(self.event.title, note.message)

    def test_removed_member_can_rejoin(self):
        self.client.post(reverse("admin_signup_remove", args=[self.signup.pk]))
        self.client.logout()
        self.client.login(username="amira", password="test-pass-123")
        self.client.post(
            reverse("event_signup", args=[self.event.pk, "participant"])
        )
        self.assertTrue(
            EventSignup.objects.filter(
                user=self.member, event=self.event, role="participant"
            ).exists()
        )

    def test_non_staff_cannot_remove_signups(self):
        self.client.logout()
        self.client.login(username="amira", password="test-pass-123")
        self.client.post(reverse("admin_signup_remove", args=[self.signup.pk]))
        self.assertTrue(EventSignup.objects.filter(pk=self.signup.pk).exists())


class UsernameChangeTests(TestCase):
    def test_member_can_change_username(self):
        user = User.objects.create_user(
            "amira", password="test-pass-123", first_name="Amira", last_name="Yusof"
        )
        self.client.login(username="amira", password="test-pass-123")
        response = self.client.post(
            reverse("dashboard") + "?tab=profile",
            {
                "username": "amira_y",
                "first_name": "Amira",
                "last_name": "Yusof",
                "email": "amira@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.username, "amira_y")
        # Session stays valid, and the new username works for a fresh login.
        self.client.logout()
        self.assertTrue(
            self.client.login(username="amira_y", password="test-pass-123")
        )

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user("taken", password="x-pass-123")
        user = User.objects.create_user(
            "amira", password="test-pass-123", first_name="A", last_name="Y"
        )
        self.client.login(username="amira", password="test-pass-123")
        self.client.post(
            reverse("dashboard") + "?tab=profile",
            {"username": "taken", "first_name": "A", "last_name": "Y",
             "email": "a@example.com"},
        )
        user.refresh_from_db()
        self.assertEqual(user.username, "amira")


class AdminSignupBlockTests(TestCase):
    def test_admin_cannot_participate_or_volunteer(self):
        User.objects.create_user("admin", password="admin-pass-123", is_staff=True)
        event = make_event()
        self.client.login(username="admin", password="admin-pass-123")
        for role in ("participant", "volunteer"):
            self.client.post(reverse("event_signup", args=[event.pk, role]))
        self.assertEqual(EventSignup.objects.filter(event=event).count(), 0)


class SignupBackTabTests(TestCase):
    def test_back_tab_inferred_from_event_date(self):
        User.objects.create_user("admin", password="admin-pass-123", is_staff=True)
        self.client.login(username="admin", password="admin-pass-123")
        past_event = make_event(date=timezone.now() - timedelta(days=2))
        response = self.client.get(
            reverse("admin_event_signups", args=[past_event.pk])
        )
        self.assertEqual(response.context["back_tab"], "past")
        response = self.client.get(
            reverse("admin_event_signups", args=[past_event.pk]) + "?from=members"
        )
        self.assertEqual(response.context["back_tab"], "members")


class PastEventSignupLockTests(TestCase):
    """A past event's sign-up list is history: removal is blocked."""

    def setUp(self):
        self.admin = User.objects.create_user(
            "admin", password="admin-pass-123", is_staff=True
        )
        self.member = User.objects.create_user("amira", password="test-pass-123")
        self.past_event = make_event(date=timezone.now() - timedelta(days=3))
        self.signup = EventSignup.objects.create(
            user=self.member, event=self.past_event,
            role=EventSignup.ROLE_VOLUNTEER,
        )
        self.client.login(username="admin", password="admin-pass-123")

    def test_removal_from_past_event_is_rejected(self):
        self.client.post(reverse("admin_signup_remove", args=[self.signup.pk]))
        self.assertTrue(EventSignup.objects.filter(pk=self.signup.pk).exists())
        self.assertFalse(Notification.objects.filter(user=self.member).exists())

    def test_remove_button_hidden_on_past_event_signups_page(self):
        response = self.client.get(
            reverse("admin_event_signups", args=[self.past_event.pk])
        )
        self.assertNotContains(response, "admin_signup_remove")
        self.assertNotContains(response, "/remove/")


class EventDetailBackLinkTests(TestCase):
    def test_back_link_follows_from_parameter(self):
        event = make_event()
        cases = [
            ("", "Back to events"),
            ("?from=dash_upcoming", "Back to dashboard"),
            ("?from=dash_past", "Back to dashboard"),
            ("?from=admin_past", "Back to past events"),
        ]
        for suffix, label in cases:
            response = self.client.get(event.get_absolute_url() + suffix)
            self.assertContains(response, label)

    def test_unknown_from_falls_back_to_events_list(self):
        event = make_event()
        response = self.client.get(event.get_absolute_url() + "?from=nonsense")
        self.assertContains(response, "Back to events")


class UsernameLengthTests(TestCase):
    """ReWear caps usernames at 15 characters (Django's model allows 150)."""

    def test_registration_rejects_username_over_15_chars(self):
        response = self.client.post(reverse("register"), {
            "first_name": "Test", "last_name": "User",
            "username": "a_very_long_username",  # 20 chars
            "email": "t@example.com",
            "password1": "strong-pass-456", "password2": "strong-pass-456",
        })
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertFalse(User.objects.filter(email="t@example.com").exists())

    def test_registration_accepts_15_char_username(self):
        self.client.post(reverse("register"), {
            "first_name": "Test", "last_name": "User",
            "username": "exactly15chars_",
            "email": "t2@example.com",
            "password1": "strong-pass-456", "password2": "strong-pass-456",
        })
        self.assertTrue(User.objects.filter(username="exactly15chars_").exists())

    def test_profile_rejects_username_over_15_chars(self):
        user = User.objects.create_user(
            "amira", password="test-pass-123", first_name="A", last_name="Y"
        )
        self.client.login(username="amira", password="test-pass-123")
        self.client.post(reverse("dashboard") + "?tab=profile", {
            "username": "a_very_long_username", "first_name": "A",
            "last_name": "Y", "email": "a@example.com",
        })
        user.refresh_from_db()
        self.assertEqual(user.username, "amira")
