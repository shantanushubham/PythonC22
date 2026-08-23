Django models also provide signals around model operations.

Some of the important ones are:
1. `pre_save`
2. `post_save`
3. `pre_delete`
4. `post_delete`

Signals let you run extra code when a model is saved or deleted, without putting that logic inside `save()` or `delete()` itself.

```text
task.save()
  → pre_save
  → INSERT / UPDATE
  → post_save

task.delete()
  → pre_delete
  → DELETE
  → post_delete
```

Register receivers in `tasks/signals.py` (or similar) and import them from `AppConfig.ready()` so they are connected when Django starts.

```python
from django.db.models.signals import (
    pre_save,
    post_save,
    pre_delete,
    post_delete,
)
from django.dispatch import receiver

from tasks.models import Task
```

## 1. `pre_save`

Runs **before** Django writes the row. Use it to tweak fields, log intent, or inspect whether this is a create vs update (`instance.pk` is `None` for a new unsaved object).

```python
@receiver(pre_save, sender=Task)
def before_task_save(sender, instance, **kwargs):
    print("pre_save:", instance.title)
    instance.title = instance.title.strip()
```

```python
task = Task(
    user=user,
    title="  Buy groceries  ",
    description="Milk and eggs",
    due_date="2026-08-24",
)
task.save()  # pre_save runs, then INSERT
```

## 2. `post_save`

Runs **after** the row is written. `created` is `True` on insert and `False` on update.

```python
@receiver(post_save, sender=Task)
def after_task_save(sender, instance, created, **kwargs):
    if created:
        print("Task created:", instance.id, instance.title)
    else:
        print("Task updated:", instance.id, instance.title)
```

```python
task = Task.objects.create(
    user=user,
    title="Buy groceries",
    description="Milk and eggs",
    due_date="2026-08-24",
)
# post_save with created=True

task.completed = True
task.save()
# post_save with created=False
```

`Task.objects.create(...)` is `Task(...)` plus `save()`, so both `pre_save` and `post_save` still fire.

## 3. `pre_delete`

Runs **before** the row is removed. The instance still exists in the database.

```python
@receiver(pre_delete, sender=Task)
def before_task_delete(sender, instance, **kwargs):
    print("About to delete task", instance.id, instance.title)
```

```python
task.delete()  # pre_delete, then DELETE
```

## 4. `post_delete`

Runs **after** the row is gone. The Python object still has field values in memory, but the row is no longer in the database.

```python
@receiver(post_delete, sender=Task)
def after_task_delete(sender, instance, **kwargs):
    print("Deleted task", instance.id, instance.title)
```

Related deletes also fire these signals. If a `User` is deleted, each related `Task` is deleted because of `on_delete=models.CASCADE`, and `pre_delete` / `post_delete` run for those tasks.

```python
user.delete()  # CASCADE deletes tasks → pre_delete / post_delete on each Task
```

## Connecting the receivers

```python
# tasks/apps.py
from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"

    def ready(self):
        import tasks.signals  # noqa: F401
```

Bulk queryset methods such as `QuerySet.update()` and `QuerySet.delete()` do **not** always call `save()` / `delete()` on each instance, so these signals may not run for every row. Use `instance.save()` / `instance.delete()` (or `bulk_create(..., signal handling as documented)`) when you need signals to fire.
