"""Regression tests for the parent Paystack card-authorization flow."""

from datetime import datetime

from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app
from app.routers import public as public_router
from app.routers.public import _create_access_token


client = TestClient(app)


def _seed_parent() -> models.User:
    with SessionLocal() as db:
        user = models.User(
            name="Payment Test Parent",
            role="parent",
            email=f"payment_{datetime.utcnow().timestamp()}@example.com",
            password_hash="x",
            is_admin=False,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def _auth(user: models.User) -> dict:
    return {"Authorization": f"Bearer {_create_access_token(user)}"}


def test_initialize_payment_method_uses_r1_and_parent_metadata(monkeypatch):
    parent = _seed_parent()
    captured = {}

    def fake_initialize(**kwargs):
        captured.update(kwargs)
        return True, {
            "data": {
                "authorization_url": "https://checkout.paystack.test/authorize",
                "access_code": "access_test",
                "reference": kwargs["reference"],
            }
        }

    monkeypatch.setattr(public_router, "initialize_transaction", fake_initialize)
    response = client.post(
        "/parent/payment-method/initialize",
        headers=_auth(parent),
        json={"callback_url": "https://app.example.com/payment-return"},
    )

    assert response.status_code == 200
    body = response.json()
    assert captured["amount_kobo"] == 100
    assert captured["currency"] == "ZAR"
    assert captured["metadata"] == {"purpose": "save_parent_card", "parent_user_id": parent.id}
    assert captured["reference"].startswith(f"MN-CARD-{parent.id}-")
    assert body["amount_cents"] == 100
    assert body["authorization_url"] == "https://checkout.paystack.test/authorize"


def test_verify_saves_masked_metadata_and_refunds_r1(monkeypatch):
    parent = _seed_parent()
    reference = f"MN-CARD-{parent.id}-testreference"
    refunds = []

    monkeypatch.setattr(
        public_router,
        "verify_transaction",
        lambda supplied_reference: (
            True,
            {
                "data": {
                    "id": 98765,
                    "reference": supplied_reference,
                    "status": "success",
                    "amount": 100,
                    "metadata": {"purpose": "save_parent_card", "parent_user_id": parent.id},
                    "authorization": {
                        "authorization_code": "AUTH_reusable_test",
                        "last4": "4081",
                        "card_type": "visa",
                    },
                    "customer": {"customer_code": "CUS_test_parent"},
                }
            },
        ),
    )
    monkeypatch.setattr(
        public_router,
        "create_refund",
        lambda transaction, amount: (refunds.append((transaction, amount)) or True, {"data": {"status": "pending"}}),
    )

    response = client.post(
        "/parent/payment-method/verify",
        headers=_auth(parent),
        json={"reference": reference},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_card"] is True
    assert body["card_brand"] == "visa"
    assert body["card_last4"] == "4081"
    assert body["refund_status"] == "requested"
    assert "authorization_code" not in body
    assert refunds == [("98765", 100)]

    with SessionLocal() as db:
        saved = db.query(models.User).filter(models.User.id == parent.id).one()
        assert saved.paystack_auth_code == "AUTH_reusable_test"
        assert saved.paystack_customer_code == "CUS_test_parent"
        assert saved.card_last4 == "4081"
        assert saved.card_brand == "visa"
        assert saved.card_saved_at is not None


def test_verify_rejects_another_parents_reference(monkeypatch):
    parent = _seed_parent()
    other_parent = _seed_parent()
    called = False

    def fake_verify(_reference):
        nonlocal called
        called = True
        return True, {}

    monkeypatch.setattr(public_router, "verify_transaction", fake_verify)
    response = client.post(
        "/parent/payment-method/verify",
        headers=_auth(parent),
        json={"reference": f"MN-CARD-{other_parent.id}-stolenreference"},
    )

    assert response.status_code == 403
    assert called is False


def test_verify_rejects_mismatched_paystack_metadata(monkeypatch):
    parent = _seed_parent()
    other_parent = _seed_parent()
    reference = f"MN-CARD-{parent.id}-testreference"
    monkeypatch.setattr(
        public_router,
        "verify_transaction",
        lambda _reference: (
            True,
            {
                "data": {
                    "reference": reference,
                    "status": "success",
                    "metadata": {"purpose": "save_parent_card", "parent_user_id": other_parent.id},
                    "authorization": {"authorization_code": "AUTH_wrong_parent"},
                }
            },
        ),
    )

    response = client.post(
        "/parent/payment-method/verify",
        headers=_auth(parent),
        json={"reference": reference},
    )

    assert response.status_code == 403
    with SessionLocal() as db:
        saved = db.query(models.User).filter(models.User.id == parent.id).one()
        assert saved.paystack_auth_code is None


def test_verify_rejects_unsuccessful_transaction(monkeypatch):
    parent = _seed_parent()
    reference = f"MN-CARD-{parent.id}-failedreference"
    monkeypatch.setattr(
        public_router,
        "verify_transaction",
        lambda _reference: (True, {"data": {"reference": reference, "status": "failed"}}),
    )

    response = client.post(
        "/parent/payment-method/verify",
        headers=_auth(parent),
        json={"reference": reference},
    )

    assert response.status_code == 400
