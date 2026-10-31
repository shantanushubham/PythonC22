from tests.conftest import PASSWORD, auth_header, login, register


def test_register_returns_user_without_password(client):
    body = register(client)
    assert body["email"] == "user@example.com"
    assert set(body) == {"id", "email", "created_at", "updated_at"}


def test_register_duplicate_email_is_rejected(client, user):
    response = client.post(
        "/users/", json={"email": user["email"], "password": PASSWORD}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_login_returns_both_tokens(client, user):
    body = login(client)
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


def test_login_with_wrong_password_is_unauthorized(client, user):
    response = client.post(
        "/users/login", json={"email": user["email"], "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_with_unknown_email_is_unauthorized(client):
    response = client.post(
        "/users/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_me_requires_a_token(client):
    assert client.get("/users/me").status_code == 401


def test_me_returns_signed_in_user(client, user, headers):
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == user["id"]


def test_refresh_token_cannot_call_protected_routes(client, tokens):
    response = client.get("/users/me", headers=auth_header(tokens["refresh_token"]))
    assert response.status_code == 401


def test_refresh_issues_a_working_access_token(client, tokens):
    response = client.post(
        "/users/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    new_tokens = response.json()
    me = client.get("/users/me", headers=auth_header(new_tokens["access_token"]))
    assert me.status_code == 200


def test_access_token_cannot_be_used_to_refresh(client, tokens):
    response = client.post(
        "/users/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert response.status_code == 401


def test_refresh_for_deleted_user_is_rejected(client, user, tokens, headers):
    client.delete(f"/users/{user['id']}", headers=headers)
    response = client.post(
        "/users/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


def test_list_users(client, user):
    response = client.get("/users/")
    assert response.status_code == 200
    assert [u["id"] for u in response.json()] == [user["id"]]


def test_list_users_pagination(client):
    for i in range(3):
        register(client, email=f"user{i}@example.com")
    response = client.get("/users/", params={"skip": 1, "limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_own_user(client, user, headers):
    response = client.get(f"/users/{user['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == user["email"]


def test_cannot_read_another_user(client, headers):
    other = register(client, email="other@example.com")
    response = client.get(f"/users/{other['id']}", headers=headers)
    assert response.status_code == 403


def test_update_own_user_changes_email_and_password(client, user, headers):
    response = client.put(
        f"/users/{user['id']}",
        headers=headers,
        json={"email": "renamed@example.com", "password": "new-pass"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "renamed@example.com"

    assert (
        client.post(
            "/users/login",
            json={"email": "renamed@example.com", "password": PASSWORD},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/users/login",
            json={"email": "renamed@example.com", "password": "new-pass"},
        ).status_code
        == 200
    )


def test_update_to_taken_email_is_rejected(client, user, headers):
    register(client, email="taken@example.com")
    response = client.put(
        f"/users/{user['id']}",
        headers=headers,
        json={"email": "taken@example.com", "password": PASSWORD},
    )
    assert response.status_code == 400


def test_update_keeping_own_email_is_allowed(client, user, headers):
    response = client.put(
        f"/users/{user['id']}",
        headers=headers,
        json={"email": user["email"], "password": "another-pass"},
    )
    assert response.status_code == 200


def test_cannot_update_another_user(client, headers):
    other = register(client, email="other@example.com")
    response = client.put(
        f"/users/{other['id']}",
        headers=headers,
        json={"email": "hijack@example.com", "password": "x"},
    )
    assert response.status_code == 403


def test_delete_own_user(client, user, headers):
    response = client.delete(f"/users/{user['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get("/users/").json() == []


def test_cannot_delete_another_user(client, headers):
    other = register(client, email="other@example.com")
    response = client.delete(f"/users/{other['id']}", headers=headers)
    assert response.status_code == 403
