from __future__ import annotations

from urllib.parse import quote


def test_root_redirects_to_dashboard(app_client):
    response = app_client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/dashboard")


def test_dashboard_uses_fixture_file(app_client):
    response = app_client.get("/dashboard")

    assert response.status_code == 200
    assert "ОПиОП BI" in response.text


def test_debug_routes_available_when_debug_enabled(app_client):
    response = app_client.get("/debug")

    assert response.status_code == 200
    assert "Debug-инструменты" in response.text


def test_path_routes_support_slashes_in_class_and_service(app_client):
    class_name = quote("экспорт/сибур", safe="/")
    service_name = quote("Комплексная/услуга 2", safe="/")

    response = app_client.get(f"/dashboard/class/{class_name}/service/{service_name}")

    assert response.status_code == 200
    assert "Комплексная/услуга 2" in response.text


def test_active_file_cookie_does_not_change_latest(app_client):
    files_before = app_client.get("/api/files").json()
    latest_id = files_before["latest_file_id"]

    response = app_client.post(f"/api/session/active-file/{latest_id}")
    files_after = response.json()["files"]

    assert response.status_code == 200
    assert files_after["active_file_id"] == latest_id
    assert files_after["latest_file_id"] == latest_id
