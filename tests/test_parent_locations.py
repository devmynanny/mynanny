from uuid import uuid4

from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app
from app.routers import public as public_router
from app.routers.public import _create_access_token


client = TestClient(app)


def _seed_parent() -> tuple[int, dict[str, str]]:
    db = SessionLocal()
    try:
        user = models.User(
            name="Location Test Parent",
            role="parent",
            email=f"location-parent-{uuid4()}@example.com",
            password_hash="x",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(models.ParentProfile(user_id=user.id))
        db.commit()
        return user.id, {"Authorization": f"Bearer {_create_access_token(user)}"}
    finally:
        db.close()


def _reverse_result(lat: float, lng: float) -> dict:
    return {
        "place_id": "uat-geocode-result",
        "formatted_address": "21 Victoria Cres, Louwlardia, Centurion, 0157, South Africa",
        "street": "21 Victoria Cres",
        "suburb": "Louwlardia",
        "city": "Centurion",
        "province": "Gauteng",
        "postal_code": "0157",
        "country": "South Africa",
        "lat": lat,
        "lng": lng,
    }


def test_coordinate_only_location_is_reverse_geocoded_before_save(monkeypatch):
    user_id, headers = _seed_parent()
    monkeypatch.setattr(public_router, "_extract_reverse_fields", _reverse_result)

    response = client.post(
        "/parents/me/locations",
        headers=headers,
        json={"label": "Home", "lat": -25.90646, "lng": 28.17292, "is_default": True},
    )

    assert response.status_code == 200
    assert response.json()["formatted_address"].startswith("21 Victoria Cres")

    db = SessionLocal()
    try:
        location = db.query(models.ParentLocation).filter_by(parent_user_id=user_id).one()
        profile = db.query(models.ParentProfile).filter_by(user_id=user_id).one()
        assert location.formatted_address == response.json()["formatted_address"]
        assert location.city == "Centurion"
        assert profile.formatted_address == location.formatted_address
        assert profile.city == "Centurion"
    finally:
        db.close()


def test_existing_coordinate_only_location_is_enriched_without_duplication(monkeypatch):
    user_id, headers = _seed_parent()
    db = SessionLocal()
    try:
        db.add(
            models.ParentLocation(
                parent_user_id=user_id,
                label="Home",
                lat=-25.90646,
                lng=28.17292,
                lat_round=-25.90646,
                lng_round=28.17292,
                is_default=True,
            )
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(public_router, "_extract_reverse_fields", _reverse_result)
    response = client.post(
        "/parents/me/locations",
        headers=headers,
        json={"label": "Home", "lat": -25.90646, "lng": 28.17292, "is_default": True},
    )

    assert response.status_code == 200
    assert response.json()["formatted_address"].startswith("21 Victoria Cres")

    db = SessionLocal()
    try:
        locations = db.query(models.ParentLocation).filter_by(parent_user_id=user_id).all()
        profile = db.query(models.ParentProfile).filter_by(user_id=user_id).one()
        assert len(locations) == 1
        assert locations[0].place_id == "uat-geocode-result"
        assert profile.formatted_address == locations[0].formatted_address
    finally:
        db.close()


def test_coordinate_only_location_is_not_saved_when_address_lookup_fails(monkeypatch):
    user_id, headers = _seed_parent()
    monkeypatch.setattr(public_router, "_extract_reverse_fields", lambda lat, lng: None)

    response = client.post(
        "/parents/me/locations",
        headers=headers,
        json={"label": "Home", "lat": -25.90646, "lng": 28.17292, "is_default": True},
    )

    assert response.status_code == 503
    assert "could not identify a street address" in response.json()["detail"]

    db = SessionLocal()
    try:
        assert db.query(models.ParentLocation).filter_by(parent_user_id=user_id).count() == 0
    finally:
        db.close()
