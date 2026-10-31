from tests.conftest import auth_header, login, register

REMINDER = {
    "title": "Pay rent",
    "description": "Monthly",
    "due_date": "2026-11-01T12:00:00",
}


def create_reminder(client, headers, **overrides):
    response = client.post("/reminders/", headers=headers, json={**REMINDER, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def second_user_headers(client):
    register(client, email="other@example.com")
    return auth_header(login(client, email="other@example.com")["access_token"])


def test_reminder_routes_require_a_token(client):
    assert client.get("/reminders/").status_code == 401
    assert client.post("/reminders/", json=REMINDER).status_code == 401
    assert client.get("/reminders/1").status_code == 401
    assert client.put("/reminders/1", json={}).status_code == 401
    assert client.delete("/reminders/1").status_code == 401


def test_create_reminder_defaults_to_incomplete_and_owned(client, user, headers):
    reminder = create_reminder(client, headers)
    assert reminder["title"] == "Pay rent"
    assert reminder["is_completed"] is False
    assert reminder["user_id"] == user["id"]


def test_create_reminder_validates_body(client, headers):
    response = client.post("/reminders/", headers=headers, json={"title": "x"})
    assert response.status_code == 422


def test_list_returns_only_own_reminders(client, headers):
    mine = create_reminder(client, headers)
    other_headers = second_user_headers(client)
    create_reminder(client, other_headers, title="Not mine")

    response = client.get("/reminders/", headers=headers)
    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [mine["id"]]


def test_list_pagination(client, headers):
    for i in range(3):
        create_reminder(client, headers, title=f"Reminder {i}")
    response = client.get("/reminders/", headers=headers, params={"skip": 1, "limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_reminder(client, headers):
    reminder = create_reminder(client, headers)
    response = client.get(f"/reminders/{reminder['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == reminder["id"]


def test_get_missing_reminder_is_not_found(client, headers):
    assert client.get("/reminders/999", headers=headers).status_code == 404


def test_other_users_reminder_is_hidden(client, headers):
    reminder = create_reminder(client, headers)
    other_headers = second_user_headers(client)
    url = f"/reminders/{reminder['id']}"

    assert client.get(url, headers=other_headers).status_code == 404
    assert (
        client.put(
            url,
            headers=other_headers,
            json={**REMINDER, "is_completed": True},
        ).status_code
        == 404
    )
    assert client.delete(url, headers=other_headers).status_code == 404
    # Still intact for the owner.
    assert client.get(url, headers=headers).status_code == 200


def test_update_reminder(client, headers):
    reminder = create_reminder(client, headers)
    response = client.put(
        f"/reminders/{reminder['id']}",
        headers=headers,
        json={
            "title": "Paid rent",
            "description": "Done",
            "due_date": "2026-11-02T09:30:00",
            "is_completed": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Paid rent"
    assert body["is_completed"] is True
    assert body["due_date"] == "2026-11-02T09:30:00"
    assert body["updated_at"] >= reminder["updated_at"]


def test_update_missing_reminder_is_not_found(client, headers):
    response = client.put(
        "/reminders/999", headers=headers, json={**REMINDER, "is_completed": False}
    )
    assert response.status_code == 404


def test_delete_reminder(client, headers):
    reminder = create_reminder(client, headers)
    url = f"/reminders/{reminder['id']}"
    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


def test_delete_missing_reminder_is_not_found(client, headers):
    assert client.delete("/reminders/999", headers=headers).status_code == 404
