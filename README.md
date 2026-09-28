# ReWear

**Author:** Khairul Hafiz
**Project:** ReWear - CM3070 Final Year Project

ReWear is a Django web application for a non-profit that organises
community clothing donation drives and thrift swap events. Visitors can
browse and register to join upcoming events as a participant or a volunteer,
organisations can submit clothing requests, and admins get a dedicated
dashboard to manage events, sign-ups, members, and incoming requests.
The stack is Django + SQLite + Bootstrap 5, with all static assets
(Bootstrap and webfonts) vendored locally so the site runs fully offline.

## Dependencies

- Python 3.10+
- Django >= 5.0 (see `requirements.txt`)
- SQLite (bundled with Python, no separate install needed)
- A modern browser - no external CDN calls, Bootstrap 5.3.3 and the
  Fraunces/Inter webfonts are vendored under `core/static/core/vendor/`

## Installation & setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply migrations
python manage.py migrate

# 4. Seed demo data (optional but recommended)
python manage.py seed_demo

# 5. Run the dev server
python manage.py runserver
```

Then open http://127.0.0.1:8000/

To create your own superuser instead of using the seeded `admin`
account, run `python manage.py createsuperuser`.

> **Note:** `seed_demo` clears and recreates all events, sign-ups,
> notifications, and clothing requests every time it's run, so the demo
> data stays deterministic. Don't run it against a database holding real
> data.

### Running tests

```bash
python manage.py test
```

The suite in `core/tests.py` covers sign-ups, notifications,
permissions, event role toggles, pagination, profile management,
username changes, request/signup deletion, and admin access control.

### Migrations

The schema ships as a single migration, `core/migrations/0001_initial.py`.
If you change the models during development and want to keep it that
way, delete `db.sqlite3` and the migration file, then run
`python manage.py makemigrations core` to regenerate one fresh initial
migration (followed by `migrate` and `seed_demo`).

## Project structure

```
rewear/
|-- core/                         # main app
|   |-- models.py                 # Event, EventSignup, ClothingRequest, Notification (+ built-in User)
|   |-- views.py                  # public pages, auth, member dashboard, admin dashboard
|   |-- forms.py                  # login/registration/event/request forms
|   |-- urls.py                   # app-level routes
|   |-- admin.py                  # Django admin registrations
|   |-- tests.py                  # unit tests
|   |-- management/
|   |   |-- commands/
|   |       |-- seed_demo.py      # demo data seeder
|   |-- migrations/
|   |   |-- 0001_initial.py
|   |-- templates/
|   |   |-- core/                 # app templates (home, events, dashboard, manage, etc.)
|   |   |-- registration/         # login/password templates
|   |-- static/
|       |-- core/
|           |-- css/rewear.css    # theme
|           |-- vendor/           # vendored Bootstrap 5 + webfonts (offline assets)
|
|-- rewear/                       # Django project package
|   |-- settings.py
|   |-- urls.py                   # project-level routes (admin, auth, includes core.urls)
|   |-- asgi.py / wsgi.py
|
|-- manage.py
|-- requirements.txt
```

## Demo accounts (from `seed_demo`)

| Account | Username | Password | Role |
|---|---|---|---|
| Admin / superuser | `admin` | `rewear-admin` | Staff + superuser |
| Member | `amira_yusof` | `rewear-demo` | Member |
| Member | `ben_tan88` | `rewear-demo` | Member |
| Member | `chloe.lim` | `rewear-demo` | Member |
| Member | `devi_nair04` | `rewear-demo` | Member |
| Member | `ethan_w` | `rewear-demo` | Member |

The `admin` account is a full Django superuser: it can use the custom
admin dashboard at `/manage/` **and** Django's built-in admin panel at
`/django-admin/`.

`seed_demo` also creates 11 upcoming events, 11 past events, and 3
clothing requests (one in each status: New, Reviewed, Event created).

## Endpoints

### Public

| Method | Path | Name | Description |
|---|---|---|---|
| GET | `/` | `home` | Landing page |
| GET | `/about/` | `about` | About page |
| GET | `/events/` | `event_list` | Browse all events |
| GET | `/events/<pk>/` | `event_detail` | Event details |
| GET | `/contact/` | `contact` | Contact page |
| GET, POST | `/register/` | `register` | New account registration |
| GET, POST | `/accounts/login/` | `login` | Log in (Django auth) |
| POST | `/accounts/logout/` | `logout` | Log out (Django auth) |
| - | `/accounts/...` | - | Other `django.contrib.auth` password-management views |

### Member (login required)

| Method | Path | Name | Description |
|---|---|---|---|
| GET | `/accounts/post-login/` | `post_login` | Redirects staff vs. members after login |
| POST | `/events/<pk>/signup/<role>/` | `event_signup` | Sign up as `participant` or `volunteer` |
| GET | `/dashboard/` | `dashboard` | Member dashboard (upcoming events, notifications, profile) |

### Admin (staff required)

| Method | Path | Name | Description |
|---|---|---|---|
| GET | `/manage/` | `admin_dashboard` | Admin dashboard (requests / events / past events / members) |
| GET, POST | `/manage/events/new/` | `admin_event_create` | Create a new event |
| GET, POST | `/manage/events/<pk>/edit/` | `admin_event_edit` | Edit an event |
| POST | `/manage/events/<pk>/delete/` | `admin_event_delete` | Delete an event |
| GET | `/manage/events/<pk>/signups/` | `admin_event_signups` | View sign-ups for an event |
| GET | `/manage/requests/` | `admin_requests` | View clothing requests |
| POST | `/manage/requests/<pk>/reviewed/` | `admin_request_mark_reviewed` | Mark a request as reviewed |
| POST | `/manage/requests/<pk>/delete/` | `admin_request_delete` | Delete a request |
| GET | `/manage/members/<pk>/` | `admin_member_detail` | View a member's profile/activity |
| POST | `/manage/signups/<pk>/remove/` | `admin_signup_remove` | Remove a member's sign-up |
| - | `/django-admin/` | - | Django's built-in admin site (superuser only) |