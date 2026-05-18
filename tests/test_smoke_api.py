from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_redirects_to_login() -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers.get("location") == "/static/login.html"


def test_auth_me_requires_authentication() -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_auth_login_requires_password_field() -> None:
    response = client.post("/auth/login", json={"email": "missing-password@example.com"})
    assert response.status_code == 422
