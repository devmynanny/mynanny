import pytest

from app.services.cancellation import calculate_cancellation_outcome


@pytest.mark.parametrize("cancelled_by", ["parent", "nanny"])
def test_boundary_exactly_24_hours_is_scenario_b(cancelled_by: str) -> None:
    out = calculate_cancellation_outcome(
        total_paid_cents=13000,
        wage_cents=10000,
        booking_fee_cents=3000,
        cancelled_by=cancelled_by,
        hours_until_start=24.0,
    )
    assert out["scenario"] == "B"
    assert out["company_retained_cents"] == 1500
    assert out["nanny_retained_cents"] == 0
    assert out["parent_refund_cents"] == 11500
    assert out["cancelled_by"] == cancelled_by


@pytest.mark.parametrize("cancelled_by", ["parent", "nanny"])
def test_boundary_exactly_15_hours_is_scenario_b(cancelled_by: str) -> None:
    out = calculate_cancellation_outcome(
        total_paid_cents=13000,
        wage_cents=10000,
        booking_fee_cents=3000,
        cancelled_by=cancelled_by,
        hours_until_start=15.0,
    )
    assert out["scenario"] == "B"
    assert out["company_retained_cents"] == 1500
    assert out["nanny_retained_cents"] == 0
    assert out["parent_refund_cents"] == 11500


@pytest.mark.parametrize("cancelled_by", ["parent", "nanny"])
def test_under_15_hours_is_scenario_c(cancelled_by: str) -> None:
    out = calculate_cancellation_outcome(
        total_paid_cents=13000,
        wage_cents=10000,
        booking_fee_cents=3000,
        cancelled_by=cancelled_by,
        hours_until_start=14.99,
    )
    assert out["scenario"] == "C"
    assert out["company_retained_cents"] == 2250
    assert out["nanny_retained_cents"] == 3000
    assert out["parent_refund_cents"] == 7750


@pytest.mark.parametrize("cancelled_by", ["parent", "nanny"])
def test_zero_wage_edge_case(cancelled_by: str) -> None:
    out = calculate_cancellation_outcome(
        total_paid_cents=3000,
        wage_cents=0,
        booking_fee_cents=3000,
        cancelled_by=cancelled_by,
        hours_until_start=5.0,
    )
    assert out["scenario"] == "C"
    assert out["company_retained_cents"] == 2250
    assert out["nanny_retained_cents"] == 0
    assert out["parent_refund_cents"] == 750


def test_rounding_behaviour_half_up() -> None:
    out = calculate_cancellation_outcome(
        total_paid_cents=666,
        wage_cents=333,
        booking_fee_cents=333,
        cancelled_by="parent",
        hours_until_start=15.0,
    )
    # 333 * 0.50 = 166.5 -> 167 with half-up rounding
    assert out["company_retained_cents"] == 167
    assert out["parent_refund_cents"] == 499


def test_invalid_cancelled_by_raises() -> None:
    with pytest.raises(ValueError):
        calculate_cancellation_outcome(
            total_paid_cents=1000,
            wage_cents=800,
            booking_fee_cents=200,
            cancelled_by="admin",
            hours_until_start=20.0,
        )

