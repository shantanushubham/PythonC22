import logging


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}


def test_swagger_ui_is_served(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_openapi_describes_api_and_bearer_auth(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Reminders API"
    assert "/users/login" in schema["paths"]
    assert "/reminders/" in schema["paths"]
    schemes = schema["components"]["securitySchemes"]
    assert any(s.get("scheme") == "bearer" for s in schemes.values())


def test_requests_are_logged(client, caplog):
    # The "reminders" logger does not propagate, so attach caplog's handler to it.
    logger = logging.getLogger("reminders")
    logger.addHandler(caplog.handler)
    old_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        client.get("/")
    finally:
        logger.removeHandler(caplog.handler)
        logger.setLevel(old_level)
    assert any("GET / -> 200" in record.getMessage() for record in caplog.records)


def test_login_logs_never_contain_the_password(client, user, caplog):
    logger = logging.getLogger("reminders")
    logger.addHandler(caplog.handler)
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        client.post(
            "/users/login", json={"email": user["email"], "password": "secret-pass"}
        )
        client.post(
            "/users/login", json={"email": user["email"], "password": "wrong-pass"}
        )
    finally:
        logger.removeHandler(caplog.handler)
        logger.setLevel(old_level)
    text = caplog.text
    assert "secret-pass" not in text
    assert "wrong-pass" not in text
    assert "Login succeeded" in text
    assert "Login failed" in text
