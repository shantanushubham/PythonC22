from django.urls import path

from .views import (
    users,
    user_detail,
    user_tasks,
    create_user,
    login,
    tasks,
    task_detail,
    create_task,
    update_task,
    delete_task,
)

urlpatterns = [
    # Auth
    path("login/", login),
    # Users
    path("users/", users),
    path("users/<int:user_id>/tasks/", user_tasks),
    path("users/<int:user_id>/", user_detail),
    path("users/create/", create_user),
    # Tasks
    path("tasks/", tasks),
    path("tasks/<int:task_id>/", task_detail),
    path("tasks/create/", create_task),
    path("tasks/<int:task_id>/update/", update_task),
    path("tasks/<int:task_id>/delete/", delete_task),
]
