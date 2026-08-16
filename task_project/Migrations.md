# Django Migrations

A **migration** is a file Django generates to describe a change to your models (new table, new field, renamed column, etc.). Applying it updates the actual database schema.

Typical flow:

1. Change a model in `tasks/models.py`
2. Create a migration file (`makemigrations`)
3. Apply it to the database (`migrate`)

Run these from the project root (`task_project/`), with the virtualenv active.

---

## 1. Make migrations

Compares your models to existing migration files and writes a new one under `tasks/migrations/`.

```bash
python manage.py makemigrations
```

For a specific app:

```bash
python manage.py makemigrations tasks
```

Preview SQL without creating a file:

```bash
python manage.py makemigrations --dry-run
```

If nothing changed, Django prints `No changes detected`.

---

## 2. Migrate

Applies pending migration files to the database (Postgres `taskdb` in this project).

```bash
python manage.py migrate
```

For a specific app:

```bash
python manage.py migrate tasks
```

Show what is applied vs pending:

```bash
python manage.py showmigrations
```

---

## Adding a non-nullable field

If you add a field with `null=False` (Django's default for `CharField`) and the table already has rows, `makemigrations` will ask for a default. The database needs a value for existing rows.

```
It is impossible to add a non-nullable field 'name' to user without specifying a default.
 1) Provide a one-off default now (will be set on all existing rows)
 2) Quit and manually define a default value in models.py.
```

- **Option 1:** One-off default for this migration only. The model does not keep a `default=`. Existing rows get that value; the column is still `NOT NULL`.
- **Option 2:** Put `default=...` on the field in `models.py`, then run `makemigrations` again.

Example: `User.name` was added in `tasks/migrations/0002_user_name.py` with a one-off default of `""` (`preserve_default=False`).

---

## Order to remember

```bash
# 1. Edit tasks/models.py
# 2. Create the migration file
python manage.py makemigrations

# 3. Apply it to the database
python manage.py migrate
```

Do not edit old migration files after they have been applied. Change the model and make a new migration instead.
