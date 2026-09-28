from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import formats, timezone
from django.views.decorators.http import require_POST

from .forms import (
    ClothingRequestForm,
    EventForm,
    PasswordChangeStyledForm,
    ProfileForm,
    RegisterForm,
)
from .models import ClothingRequest, Event, EventSignup, Notification


def _qs_without(request, param):
    """
    The current querystring minus 'param', ready to prefix pagination
    links; lets several paginators (and the tab/type filters) coexist.
    """
    params = request.GET.copy()
    params.pop(param, None)
    encoded = params.urlencode()
    return encoded + "&" if encoded else ""


def _page(request, queryset, per_page, param):
    return Paginator(queryset, per_page).get_page(request.GET.get(param))


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

# Manually maintained figure; garments aren't tracked per-item in the system.
GARMENTS_COLLECTED = 1240


def home(request):
    """
    Homepage with impact statistics. Event/cause counts are derived;
    the garment figure is maintained manually.
    """
    now = timezone.now()
    stats = {
        "garments_collected": GARMENTS_COLLECTED,
        "events_hosted": Event.objects.filter(date__lt=now).count(),
        "causes_supported": ClothingRequest.objects.filter(
            status=ClothingRequest.STATUS_EVENT_CREATED
        ).count(),
    }
    upcoming = Event.objects.filter(date__gte=now)
    return render(request, "core/home.html", {"stats": stats, "upcoming": upcoming})


def about(request):
    """Static about page, containing organisation's missions"""
    return render(request, "core/about.html")


def event_list(request):
    """
    Public events listing. Upcoming events can be filtered and are paginated 6 per page.
    Past events are paginated separately (5 per page).
    """
    now = timezone.now()
    active_filter = request.GET.get("type", "all")
    upcoming = Event.objects.filter(date__gte=now)
    if active_filter == "drive":
        upcoming = upcoming.filter(event_type=Event.TYPE_DONATION_DRIVE)
    elif active_filter == "swap":
        upcoming = upcoming.filter(event_type=Event.TYPE_THRIFT_SWAP)
    elif active_filter == "community":
        upcoming = upcoming.filter(event_type=Event.TYPE_OTHER)
    past = Event.objects.filter(date__lt=now).order_by("-date")
    return render(
        request,
        "core/event_list.html",
        {
            "upcoming_events": _page(request, upcoming, 6, "page"),
            "past_events": _page(request, past, 5, "past_page"),
            "active_filter": active_filter,
            "qs_page": _qs_without(request, "page"),
            "qs_past": _qs_without(request, "past_page"),
        },
    )


# Where an event-detail visit came from, and where "back" should lead.
DETAIL_BACK = {
    "dash_upcoming": ("/dashboard/?tab=upcoming", "Back to dashboard"),
    "dash_past": ("/dashboard/?tab=past", "Back to dashboard"),
    "admin_past": ("/manage/?tab=past", "Back to past events"),
}


def event_detail(request, pk):
    """
    Public detail page for a single event, with context-aware back links
    and role buttons (showing signup or confirmed) for the logged-in member.
    """
    event = get_object_or_404(Event, pk=pk)
    back_url, back_label = DETAIL_BACK.get(
        request.GET.get("from"), (reverse("event_list"), "Back to events")
    )
    my_roles = set()
    if request.user.is_authenticated:
        my_roles = set(
            event.signups.filter(user=request.user).values_list("role", flat=True)
        )
    return render(
        request,
        "core/event_detail.html",
        {
            "event": event,
            "back_url": back_url,
            "back_label": back_label,
            "is_participating": EventSignup.ROLE_PARTICIPANT in my_roles,
            "is_volunteering": EventSignup.ROLE_VOLUNTEER in my_roles,
            "is_past": event.date < timezone.now(),
        },
    )


def contact(request):
    """
    Contact page containing the clothing request form. Submitting does not
    require an account - it represents an external organisation reaching out.
    """
    if request.method == "POST":
        form = ClothingRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Your clothing request has been received. "
                "Our team will review it and be in touch.",
            )
            return redirect("contact")
    else:
        form = ClothingRequestForm()
    return render(request, "core/contact.html", {"form": form})


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@login_required
def post_login(request):
    """
    Landing point after login: admins go to the admin dashboard,
    members to the member dashboard.
    """
    if request.user.is_staff:
        return redirect("admin_dashboard")
    return redirect("dashboard")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to ReWear! Your account is ready.")
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


# ---------------------------------------------------------------------------
# Member actions & dashboard
# ---------------------------------------------------------------------------

@login_required
@require_POST
def event_signup(request, pk, role):
    """
    The core feature: Participate / Volunteer as two independent actions
    on the same event. An unauthenticated visitor is redirected to Login by
    @login_required.
    """
    event = get_object_or_404(Event, pk=pk)
    if request.user.is_staff:
        messages.error(
            request,
            "Admin accounts can't participate or volunteer in events. "
            "Use a member account to join.",
        )
        return redirect(event)
    valid_roles = {EventSignup.ROLE_PARTICIPANT, EventSignup.ROLE_VOLUNTEER}
    if role not in valid_roles:
        messages.error(request, "Unknown sign-up role.")
        return redirect(event)
    if event.date < timezone.now():
        messages.error(request, "This event has already taken place.")
        return redirect(event)
    if not event.role_is_open(role):
        messages.error(request, "This event isn't taking sign-ups for that role.")
        return redirect(event)

    signup, created = EventSignup.objects.get_or_create(
        user=request.user, event=event, role=role
    )
    if created:
        Notification.objects.create(
            user=request.user,
            message=(
                f"You're confirmed: "
                f"{signup.get_role_display()} - {event.title}"
            ),
        )
        messages.success(
            request,
            f"You're confirmed as a {signup.get_role_display().lower()} "
            f'for "{event.title}".',
        )
    else:
        messages.info(request, "You had already signed up for this role.")
    return redirect(event)


@login_required
def dashboard(request):
    now = timezone.now()

    profile_form = ProfileForm(instance=request.user)
    password_form = PasswordChangeStyledForm(user=request.user)
    if request.method == "POST":
        if "change_password" in request.POST:
            password_form = PasswordChangeStyledForm(
                user=request.user, data=request.POST
            )
            if password_form.is_valid():
                password_form.save()
                # Keep the member logged in after the password change.
                update_session_auth_hash(request, request.user)
                messages.success(request, "Your password has been changed.")
                return redirect("/dashboard/?tab=profile")
        else:
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your information has been saved.")
                return redirect("/dashboard/?tab=profile")
    my_signups = request.user.signups.select_related("event")

    def grouped(signups):
        """
        Group a member's signups by event so an event they joined in both
        roles appears once, with both role tags.
        """
        events = {}
        for s in signups:
            events.setdefault(s.event, set()).add(s.role)
        return sorted(events.items(), key=lambda item: item[0].date)

    upcoming = grouped(my_signups.filter(event__date__gte=now))
    past = grouped(my_signups.filter(event__date__lt=now))
    notifications = request.user.notifications.all()
    unread_count = notifications.filter(read=False).count()

    response = render(
        request,
        "core/dashboard.html",
        {
            "upcoming": upcoming,
            "past": past,
            "notifications": notifications,
            "unread_count": unread_count,
            "profile_form": profile_form,
            "password_form": password_form,
            "active_tab": request.GET.get("tab", "upcoming"),
        },
    )
    # Viewing the notifications tab marks them as read.
    if request.GET.get("tab") == "notifications":
        notifications.filter(read=False).update(read=True)
    return response


# ---------------------------------------------------------------------------
# Admin dashboard (staff-only)
# ---------------------------------------------------------------------------

@staff_member_required
def admin_dashboard(request):
    """
    The staff-only management hub at /manage/.

    One view renders four tabs (requests|events|past|members), each
    with its own paginator parameter so switching pages in one tab keeps
    the other tabs' state intact. `new_request_count` feeds the red badge
    on the Clothing requests tab.
    """
    now = timezone.now()
    return render(
        request,
        "core/admin/dashboard.html",
        {
            "upcoming_events": _page(
                request, Event.objects.filter(date__gte=now), 10, "up_page"
            ),
            "past_events": _page(
                request,
                Event.objects.filter(date__lt=now).order_by("-date"),
                10,
                "past_page",
            ),
            "clothing_requests": _page(
                request, ClothingRequest.objects.all(), 10, "req_page"
            ),
            "new_request_count": ClothingRequest.objects.filter(
                status=ClothingRequest.STATUS_NEW
            ).count(),
            "members": _page(
                request,
                User.objects.filter(is_staff=False).order_by(
                    "first_name", "last_name"
                ),
                10,
                "mem_page",
            ),
            "active_tab": request.GET.get("tab", "requests"),
            "qs_up": _qs_without(request, "up_page"),
            "qs_past": _qs_without(request, "past_page"),
            "qs_req": _qs_without(request, "req_page"),
            "qs_mem": _qs_without(request, "mem_page"),
        },
    )


@staff_member_required
def admin_member_detail(request, pk):
    """
    Staff view of one member: their details plus every event they have
    joined, grouped so an event joined in both roles appears once with two
    role tags, split into upcoming/past tabs.
    """
    member = get_object_or_404(User, pk=pk, is_staff=False)
    now = timezone.now()
    signups = member.signups.select_related("event")

    def grouped(qs):
        events = {}
        for s in qs:
            events.setdefault(s.event, set()).add(s.role)
        return sorted(events.items(), key=lambda item: item[0].date)

    return render(
        request,
        "core/admin/member_detail.html",
        {
            "member": member,
            "upcoming": _page(
                request, grouped(signups.filter(event__date__gte=now)), 10, "page"
            ),
            "past": _page(
                request, grouped(signups.filter(event__date__lt=now)), 10, "page"
            ),
            "active_tab": request.GET.get("tab", "events"),
            "qs_page": _qs_without(request, "page"),
        },
    )


@staff_member_required
def admin_event_create(request):
    """Create an event, optionally pre-filled from a ClothingRequest."""
    prefill_request = None
    request_id = request.GET.get("from_request")
    if request_id:
        prefill_request = get_object_or_404(ClothingRequest, pk=request_id)

    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            from_request_id = request.POST.get("from_request")
            if from_request_id:
                source = get_object_or_404(ClothingRequest, pk=from_request_id)
                event.created_from = source
                source.status = ClothingRequest.STATUS_EVENT_CREATED
                source.save()
            event.save()
            messages.success(request, f'Event "{event.title}" created.')
            return redirect("admin_dashboard")
    else:
        initial = {}
        if prefill_request:
            initial = {
                "title": f"Drive: {prefill_request.clothing_type.capitalize()}",
                "description": (
                    f"Organised in response to a request from "
                    f"{prefill_request.organisation_name} for "
                    f"{prefill_request.quantity} of {prefill_request.clothing_type}."
                ),
                "event_type": Event.TYPE_DONATION_DRIVE,
            }
        form = EventForm(initial=initial)
    return render(
        request,
        "core/admin/event_form.html",
        {"form": form, "prefill_request": prefill_request, "mode": "create"},
    )


FIELD_LABELS = {
    "title": "title",
    "description": "description",
    "event_type": "event type",
    "date": "date/time",
    "location": "location",
    "allow_participants": "participant sign-ups",
    "allow_volunteers": "volunteer sign-ups",
}


def notify_event_members(event, message):
    """
    Create a Notification for every distinct member signed up to the event (in any role).
    """
    user_ids = event.signups.values_list("user", flat=True).distinct()
    Notification.objects.bulk_create(
        [Notification(user_id=user_id, message=message) for user_id in user_ids]
    )


@staff_member_required
def admin_event_edit(request, pk):
    """
    Edit an event. If anything changed, every signed-up member gets a
    notification naming the changed fields.
    """
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            changed = [FIELD_LABELS.get(f, f) for f in form.changed_data]
            form.save()
            if changed:
                notify_event_members(
                    event,
                    f'Event updated: "{event.title}" - changes to '
                    f'{", ".join(changed)}. Check the event page for details.',
                )
            messages.success(request, f'Event "{event.title}" updated.')
            return redirect("admin_dashboard")
    else:
        form = EventForm(instance=event)
    return render(
        request,
        "core/admin/event_form.html",
        {"form": form, "event": event, "mode": "edit"},
    )


@staff_member_required
def admin_event_delete(request, pk):
    """
    Confirm-then-delete for an event. Members are notified *before* the
    delete because their EventSignup rows cascade away with the event.
    """
    event = get_object_or_404(Event, pk=pk)
    if request.method == "POST":
        title = event.title
        notify_event_members(
            event,
            f'Event cancelled: "{title}" on '
            f'{formats.date_format(timezone.localtime(event.date), "D, j M")} '
            "will no longer take place.",
        )
        event.delete()
        messages.success(request, f'Event "{title}" deleted.')
        return redirect("admin_dashboard")
    return render(request, "core/admin/event_delete.html", {"event": event})


@staff_member_required
def admin_event_signups(request, pk):
    """
    Participant and volunteer lists for one event, alphabetical by name.
    `is_past` hides the Remove buttons: a finished event's sign-up list is a 
    historical record.
    """
    event = get_object_or_404(Event, pk=pk)
    back_tab = request.GET.get("from")
    if back_tab not in {"events", "past", "members"}:
        back_tab = "past" if event.date < timezone.now() else "events"
    return render(
        request,
        "core/admin/event_signups.html",
        {
            "event": event,
            "back_tab": back_tab,
            "is_past": event.date < timezone.now(),
            "participants": event.signups.filter(role=EventSignup.ROLE_PARTICIPANT)
            .select_related("user")
            .order_by("user__first_name", "user__last_name"),
            "volunteers": event.signups.filter(role=EventSignup.ROLE_VOLUNTEER)
            .select_related("user")
            .order_by("user__first_name", "user__last_name"),
        },
    )


@staff_member_required
def admin_requests(request):
    """Requests is a tab of the admin dashboard"""
    return redirect("/manage/?tab=requests")


@staff_member_required
@require_POST
def admin_signup_remove(request, pk):
    """
    Remove one member's sign-up for one role (they may keep the other
    role, and may rejoin later). Blocked for past events; the member is
    notified so the removal never happens silently.
    """
    signup = get_object_or_404(
        EventSignup.objects.select_related("user", "event"), pk=pk
    )
    event = signup.event
    if event.date < timezone.now():
        messages.error(
            request,
            "This event has already taken place - its sign-up list is a "
            "record and can no longer be edited.",
        )
        return redirect(reverse("admin_event_signups", args=[event.pk]))
    Notification.objects.create(
        user=signup.user,
        message=(
            f'You\'ve been removed as a '
            f"{signup.get_role_display().lower()} from \"{event.title}\". "
            "You can rejoin from the event page if this was unexpected."
        ),
    )
    signup.delete()
    messages.success(
        request,
        f"{signup.user.get_full_name() or signup.user.username} removed "
        f"({signup.get_role_display()}).",
    )
    back = request.POST.get("from", "")
    suffix = f"?from={back}" if back in {"events", "past", "members"} else ""
    return redirect(reverse("admin_event_signups", args=[event.pk]) + suffix)


@staff_member_required
@require_POST
def admin_request_delete(request, pk):
    """
    Delete a clothing request. Safe by design: Event.created_from is
    SET_NULL, so an event created from the request survives its deletion.
    """
    clothing_request = get_object_or_404(ClothingRequest, pk=pk)
    name = clothing_request.organisation_name
    # Events created from this request keep existing: created_from is SET_NULL.
    clothing_request.delete()
    messages.success(request, f'Request from "{name}" deleted.')
    return redirect("/manage/?tab=requests")


@staff_member_required
@require_POST
def admin_request_mark_reviewed(request, pk):
    """Change the status of a request from 'new' to 'reviewed' (one-way; idempotent)."""
    clothing_request = get_object_or_404(ClothingRequest, pk=pk)
    if clothing_request.status == ClothingRequest.STATUS_NEW:
        clothing_request.status = ClothingRequest.STATUS_REVIEWED
        clothing_request.save()
        messages.success(request, "Request marked as reviewed.")
    return redirect("/manage/?tab=requests")
