# Creating a Django Application (Mac / Linux / Windows)

This guide covers setting up a Django project with a **virtual environment (`venv`)** and the **`django-admin`** CLI.

---

## Concepts

### Virtual environment (`venv`)

A **virtual environment** is an isolated Python environment for one project. Packages you install (Django, DRF, etc.) live inside `.venv` instead of your system Python.

**Why use it:**
- Avoid version conflicts between projects
- Keep dependencies reproducible
- Do not pollute the global Python install

### Django Admin (`django-admin`)

**`django-admin`** is Django’s command-line utility. After installing Django in your venv, you use it to:

- Create a project: `django-admin startproject`
- Create an app: `python manage.py startapp` (same tool family; project-level commands go through `manage.py`)

Common commands:

| Command | Purpose |
|---------|---------|
| `django-admin startproject config .` | Create a project named `config` in the current folder |
| `python manage.py startapp api` | Create an app named `api` |
| `python manage.py migrate` | Apply database migrations |
| `python manage.py createsuperuser` | Create an admin user |
| `python manage.py runserver` | Start the development server |

---

## Prerequisites

1. **Python 3** installed
   - Mac / Linux: `python3 --version`
   - Windows: `python --version`
2. **pip** available (usually comes with Python)
3. A terminal / command prompt in your project folder

---

## Step 1 — Create a project folder

**Mac / Linux:**
```bash
mkdir first-django-project
cd first-django-project
```

**Windows (Command Prompt or PowerShell):**
```bat
mkdir first-django-project
cd first-django-project
```

---

## Step 2 — Create and activate a virtual environment

### Create the venv

**Mac / Linux:**
```bash
python3 -m venv .venv
```

**Windows:**
```bat
python -m venv .venv
```

### Activate the venv

**Mac / Linux:**
```bash
source .venv/bin/activate
```

**Windows (Command Prompt):**
```bat
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

When active, your prompt usually shows `(.venv)`.

### Deactivate later (any OS)

```bash
deactivate
```

---

## Step 3 — Install Django

With the venv **activated**:

```bash
pip install django
```

Optional (API apps, as in this project):

```bash
pip install djangorestframework
```

Confirm Django is available:

```bash
django-admin --version
```

---

## Step 4 — Create the Django project with `django-admin`

Create a project named `config` in the current directory:

```bash
django-admin startproject config .
```

The trailing `.` means “use this folder” (so you get `manage.py` here, not nested inside another folder).

You should see something like:

```text
first-django-project/
├── .venv/
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── manage.py
```

---

## Step 5 — Create a Django app

```bash
python manage.py startapp api
```

Register the app in `config/settings.py` under `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "api",
]
```

If you installed Django REST Framework, also add `"rest_framework"`.

---

## Step 6 — Run migrations

Django’s built-in apps (including **Django Admin**) need database tables:

```bash
python manage.py migrate
```

This creates `db.sqlite3` by default.

---

## Step 7 — Create a superuser (Django Admin)

Django Admin is the built-in web UI at `/admin/` for managing models.

```bash
python manage.py createsuperuser
```

Enter username, email (optional), and password when prompted.

---

## Step 8 — Start the development server

```bash
python manage.py runserver
```

Then open:

| URL | What you get |
|-----|----------------|
| http://127.0.0.1:8000/ | Your site (configure URLs as you build) |
| http://127.0.0.1:8000/admin/ | Django Admin login |

Stop the server with `Ctrl + C`.

---

## Quick reference by OS

| Step | Mac / Linux | Windows |
|------|-------------|---------|
| Create venv | `python3 -m venv .venv` | `python -m venv .venv` |
| Activate | `source .venv/bin/activate` | `.venv\Scripts\activate.bat` or `Activate.ps1` |
| Install | `pip install django` | same (with venv active) |
| Start project | `django-admin startproject config .` | same |
| Start app | `python manage.py startapp api` | same |
| Migrate | `python manage.py migrate` | same |
| Superuser | `python manage.py createsuperuser` | same |
| Run server | `python manage.py runserver` | same |

---

## Tips

1. **Always activate the venv** before installing packages or running `manage.py`.
2. If `django-admin` is “not found”, the venv is probably not active.
3. On Windows PowerShell, if activation is blocked, run once (as admin if needed):
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
4. Add `.venv/` to `.gitignore` so the environment is not committed.
5. Freeze dependencies when ready:
   ```bash
   pip freeze > requirements.txt
   ```
   Others can recreate the env with:
   ```bash
   pip install -r requirements.txt
   ```
