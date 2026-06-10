"""CORS middleware configuration tests."""

from fastapi.testclient import TestClient

from main import create_application


def test_local_expo_web_origin_can_preflight_auth_requests() -> None:
    client = TestClient(create_application())

    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"
