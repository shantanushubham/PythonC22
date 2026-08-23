Task Model -> Python Object -> Validated -> Saved -> Database -> Updated -> Deleted

## 1. Model Definition:
```python
class Task(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    title = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)
```

Django uses this to construct the model class when the application starts.

## 2. Creating an instance:
```python
task = Task(
    user=user,
    title="Buy groceries"
)
```
When we write the above code, we have created a Python object. At this point the object exists inside the RAM of your Python process, but is not saved in the DB.

## 3. Saving
```python
task.save()
```
Django persists it insde the DB.

```sql
INSERT INTO task (...)
VALUES (...);
```

## 4. Create
```python
task = Task.objects.create(
    user=user,
    title="Buy groceries"
)
```

This combines 2 and 3.

## 5. Validation
```python
task.save()
task.full_clean()
```



