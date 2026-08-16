# Docker Compose (Postgres)

This project runs **PostgreSQL** in Docker. The compose file is `docker-compose.yml` at the **project root** (`task_project/`).

Run all commands from that folder. If you are in a subdirectory, Compose looks for a config file there and fails with `no configuration file provided: not found`.

---

## What it starts

| Setting | Value |
|---|---|
| Image | `postgres:latest` |
| Container name | `taskdb` |
| Database | `taskdb` |
| User | `postgres` |
| Password | `postgres` |
| Port | `5432` (host → container) |
| Volume | `taskdb_data` (data survives container restarts) |

Django connects with the same values in `config/settings.py` (`HOST`: `localhost`, `PORT`: `5432`).

---

## 1. Pull the image

Downloads (or updates) `postgres:latest`:

```bash
docker compose pull
```

---

## 2. Start the database

Start in the background:

```bash
docker compose up -d
```

First run creates the container and volume. Later runs reuse them.

Check that it is running:

```bash
docker compose ps
```

Follow logs if it does not become healthy:

```bash
docker compose logs -f db
```

---

## 3. Stop the database

Stop the container (data in `taskdb_data` is kept):

```bash
docker compose stop
```

Stop and remove the container (volume still kept):

```bash
docker compose down
```

Stop and **delete** the database volume as well (all `taskdb` data is gone):

```bash
docker compose down -v
```

---

## Order to remember

```bash
# From task_project/
docker compose pull
docker compose up -d

# Then run Django against localhost:5432
python manage.py migrate
python manage.py runserver
```

Use `docker compose` (plugin). `docker-compose` is the older separate CLI; both work if installed, but they still need to be run from the folder that contains `docker-compose.yml`.
