from django.urls import path

from . import views

urlpatterns = [
    # Public pages
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("events/", views.event_list, name="event_list"),
    path("events/<int:pk>/", views.event_detail, name="event_detail"),
    path("contact/", views.contact, name="contact"),

    # Auth
    path("register/", views.register, name="register"),
    path("accounts/post-login/", views.post_login, name="post_login"),

    # Member
    path("events/<int:pk>/signup/<str:role>/", views.event_signup, name="event_signup"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # Admin dashboard
    path("manage/", views.admin_dashboard, name="admin_dashboard"),
    path("manage/events/new/", views.admin_event_create, name="admin_event_create"),
    path("manage/events/<int:pk>/edit/", views.admin_event_edit, name="admin_event_edit"),
    path("manage/events/<int:pk>/delete/", views.admin_event_delete, name="admin_event_delete"),
    path("manage/events/<int:pk>/signups/", views.admin_event_signups, name="admin_event_signups"),
    path("manage/requests/", views.admin_requests, name="admin_requests"),
    path("manage/requests/<int:pk>/reviewed/", views.admin_request_mark_reviewed, name="admin_request_mark_reviewed"),
    path("manage/requests/<int:pk>/delete/", views.admin_request_delete, name="admin_request_delete"),
    path("manage/members/<int:pk>/", views.admin_member_detail, name="admin_member_detail"),
    path("manage/signups/<int:pk>/remove/", views.admin_signup_remove, name="admin_signup_remove"),
]
