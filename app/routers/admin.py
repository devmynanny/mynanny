


from datetime import date, time, datetime, timedelta
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, or_, Numeric
from app.db import SessionLocal
from app import models
from app.routers.public import require_admin as require_admin_user, _require_user, _parse_iso_dt, get_rating_12m_for_nanny
from app.services.audit import log_audit
from app.services.paystack import create_refund

router = APIRouter(prefix="/admin", tags=["admin"])


class RefundRequest(BaseModel):
    amount_cents: Optional[int] = None


class RefundDecision(BaseModel):
    amount_cents: Optional[int] = None
    reason: Optional[str] = None


def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()

def require_admin(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
	require_admin_user(authorization, db)


@router.get("/pricing", dependencies=[Depends(require_admin)])
def get_pricing_settings(db: Session = Depends(get_db)):
    row = db.query(models.PricingSettings).first()
    if not row:
        row = models.PricingSettings(
            id=1,
            weekday_half_day=250,
            weekday_full_day=300,
            weekend_half_day=300,
            weekend_full_day=350,
            sleepover_add=150,
            sleepover_only_weekday=400,
            sleepover_only_weekend=450,
            sleepover_extra_hour_over14=50,
            after17_weekday=30,
            after17_weekend=35,
            over9_weekday=45,
            over9_weekend=50,
            sleepover_start_hour=14,
            sleepover_end_hour=7,
            sleepover_after7_hourly=45,
            booking_fee_pct_1_5=0.30,
            booking_fee_pct_6_10=0.27,
            booking_fee_pct_10_plus=0.25,
            cancellation_fee_window_hours=12,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return {
        "weekday_half_day": row.weekday_half_day,
        "weekday_full_day": row.weekday_full_day,
        "weekend_half_day": row.weekend_half_day,
        "weekend_full_day": row.weekend_full_day,
        "sleepover_add": row.sleepover_add,
        "sleepover_only_weekday": row.sleepover_only_weekday,
        "sleepover_only_weekend": row.sleepover_only_weekend,
        "sleepover_extra_hour_over14": row.sleepover_extra_hour_over14,
        "after17_weekday": row.after17_weekday,
        "after17_weekend": row.after17_weekend,
        "over9_weekday": row.over9_weekday,
        "over9_weekend": row.over9_weekend,
        "sleepover_start_hour": row.sleepover_start_hour,
        "sleepover_end_hour": row.sleepover_end_hour,
        "sleepover_after7_hourly": row.sleepover_after7_hourly,
        "booking_fee_pct_1_5": float(row.booking_fee_pct_1_5),
        "booking_fee_pct_6_10": float(row.booking_fee_pct_6_10),
        "booking_fee_pct_10_plus": float(row.booking_fee_pct_10_plus),
        "cancellation_fee_window_hours": int(getattr(row, "cancellation_fee_window_hours", 12) or 12),
    }


@router.put("/pricing", dependencies=[Depends(require_admin)])
def update_pricing_settings(payload: dict, db: Session = Depends(get_db)):
    row = db.query(models.PricingSettings).first()
    if not row:
        row = models.PricingSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)

    for key in [
        "weekday_half_day","weekday_full_day","weekend_half_day","weekend_full_day",
        "sleepover_add","sleepover_only_weekday","sleepover_only_weekend","sleepover_extra_hour_over14",
        "after17_weekday","after17_weekend","over9_weekday","over9_weekend",
        "sleepover_start_hour","sleepover_end_hour","sleepover_after7_hourly",
        "booking_fee_pct_1_5","booking_fee_pct_6_10","booking_fee_pct_10_plus",
        "cancellation_fee_window_hours",
    ]:
        if key in payload:
            value = payload[key]
            if key == "cancellation_fee_window_hours":
                try:
                    value = max(0, int(value))
                except Exception:
                    raise HTTPException(status_code=400, detail="cancellation_fee_window_hours must be a valid number")
            setattr(row, key, value)
    db.commit()
    return {"ok": True}


@router.get("/reports/jobs", dependencies=[Depends(require_admin)])
def report_jobs(
    range: Optional[str] = Query(default="month"),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    if start and end:
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date range")
    else:
        if range == "day":
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "week":
            start_dt = now - timedelta(days=7)
        elif range == "quarter":
            start_dt = now - timedelta(days=90)
        elif range == "year":
            start_dt = now - timedelta(days=365)
        else:
            start_dt = now - timedelta(days=30)
        end_dt = now

    rows = (
        db.query(models.BookingRequest)
        .filter(
            models.BookingRequest.payment_status == "paid",
            models.BookingRequest.requested_starts_at >= start_dt,
            models.BookingRequest.requested_starts_at <= end_dt,
        )
        .all()
    )

    total = len(rows)
    accepted = len([r for r in rows if r.status == "approved"])
    cancelled = len([r for r in rows if r.status == "cancelled"])
    completed = len([r for r in rows if r.end_dt and _parse_iso_dt(r.end_dt) < now])
    in_progress = len([r for r in rows if r.start_dt and r.end_dt and _parse_iso_dt(r.start_dt) <= now <= _parse_iso_dt(r.end_dt)])

    company_income = 0
    nanny_income = 0
    refunded = 0
    for r in rows:
        if r.status == "cancelled" and r.company_retained_cents is not None:
            company_income += r.company_retained_cents
        else:
            company_income += (r.booking_fee_cents or 0)
        if r.status == "cancelled" and r.nanny_retained_cents is not None:
            nanny_income += r.nanny_retained_cents
        else:
            nanny_income += (r.wage_cents or 0)
        if (r.refund_status == "processed") and r.refund_cents:
            refunded += r.refund_cents
    total_paid = sum(r.total_cents or 0 for r in rows)

    return {
        "range_start": start_dt.isoformat(),
        "range_end": end_dt.isoformat(),
        "total_paid_jobs": total,
        "accepted": accepted,
        "cancelled": cancelled,
        "in_progress": in_progress,
        "completed": completed,
        "company_income_cents": company_income,
        "nanny_income_cents": nanny_income,
        "total_paid_cents": total_paid,
        "refunded_cents": refunded,
        "net_company_income_cents": company_income,
    }


@router.post("/booking-requests/{job_id}/refund", dependencies=[Depends(require_admin)])
def refund_booking_request(
    job_id: int,
    payload: Optional[RefundRequest] = None,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin_user = _require_user(authorization, db)
    rows = (
        db.query(models.BookingRequest)
        .filter(
            or_(models.BookingRequest.group_id == job_id, models.BookingRequest.id == job_id),
            models.BookingRequest.payment_status == "paid",
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Paid booking request not found")

    candidates = [r for r in rows if r.status == "approved"]
    if not candidates:
        candidates = rows

    def rating_key(r):
        avg, cnt = get_rating_12m_for_nanny(db, r.nanny_id)
        return (avg or 0.0, cnt or 0, -r.id)

    req = max(candidates, key=rating_key)

    if req.refund_status in ("pending", "processed"):
        raise HTTPException(status_code=400, detail="Refund already requested or processed")

    if req.status != "cancelled":
        raise HTTPException(status_code=400, detail="Booking must be cancelled before refund")

    base_total = (req.wage_cents or 0) + (req.booking_fee_cents or 0)
    if req.company_retained_cents is not None or req.nanny_retained_cents is not None:
        retained = (req.company_retained_cents or 0) + (req.nanny_retained_cents or 0)
        base_refund = max(0, base_total - retained)
    else:
        base_refund = base_total

    amount_cents = payload.amount_cents if payload else None
    refund_amount = amount_cents if amount_cents is not None else base_refund
    if refund_amount <= 0:
        raise HTTPException(status_code=400, detail="Refund amount must be greater than zero")
    if base_total and refund_amount > base_total:
        raise HTTPException(status_code=400, detail="Refund amount exceeds total paid")

    transaction = req.paystack_transaction_id or req.paystack_reference
    if not transaction:
        raise HTTPException(status_code=400, detail="Missing Paystack transaction reference")

    req.refund_cents = refund_amount
    req.refund_status = "pending"
    req.refund_requested_at = datetime.utcnow()

    ok, data = create_refund(str(transaction), int(refund_amount))
    if not ok:
        req.refund_status = "failed"
        req.refund_failed_at = datetime.utcnow()
        req.refund_failure_reason = data.get("message") if isinstance(data, dict) else "Paystack error"
        db.commit()
        raise HTTPException(status_code=400, detail=req.refund_failure_reason or "Paystack refund failed")

    refund_ref = None
    if isinstance(data, dict):
        refund_ref = (data.get("data") or {}).get("reference") or (data.get("data") or {}).get("refund_reference")
    if refund_ref:
        req.paystack_refund_reference = refund_ref

    db.commit()

    log_audit(
        db,
        actor_user=admin_user,
        target_user_id=req.parent_user_id,
        entity="booking_requests",
        entity_id=req.id,
        action="refund_request",
        before_obj={},
        after_obj={"refund_status": req.refund_status, "refund_cents": req.refund_cents},
        changed_fields=["refund_status", "refund_cents"],
        request=None,
    )

    return {"ok": True, "refund_status": req.refund_status, "refund_cents": req.refund_cents}


@router.get("/refunds", dependencies=[Depends(require_admin)])
def list_refunds(status: Optional[str] = Query(default="pending_review"), db: Session = Depends(get_db)):
    q = db.query(models.BookingRequest).filter(models.BookingRequest.payment_status == "paid")
    if status:
        q = q.filter(models.BookingRequest.refund_status == status)
    rows = q.order_by(models.BookingRequest.updated_at.desc()).limit(100).all()
    results = []
    for r in rows:
        results.append({
            "job_id": r.group_id or r.id,
            "request_id": r.id,
            "status": r.status,
            "refund_status": r.refund_status,
            "refund_cents": r.refund_cents,
            "parent_user_id": r.parent_user_id,
            "nanny_id": r.nanny_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"results": results}


@router.post("/booking-requests/{job_id}/refund/approve", dependencies=[Depends(require_admin)])
def approve_refund(
    job_id: int,
    payload: Optional[RefundDecision] = None,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin_user = _require_user(authorization, db)
    req = (
        db.query(models.BookingRequest)
        .filter(or_(models.BookingRequest.group_id == job_id, models.BookingRequest.id == job_id))
        .order_by(models.BookingRequest.updated_at.desc())
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Job not found")
    if req.refund_status not in ("pending_review", None):
        raise HTTPException(status_code=400, detail="Refund is not pending review")

    req.refund_reviewed_at = datetime.utcnow()
    req.refund_reviewed_by = admin_user.id
    req.refund_review_reason = payload.reason if payload else None
    db.commit()

    return refund_booking_request(job_id, RefundRequest(amount_cents=payload.amount_cents if payload else None), authorization, db)


@router.post("/booking-requests/{job_id}/refund/deny", dependencies=[Depends(require_admin)])
def deny_refund(
    job_id: int,
    payload: Optional[RefundDecision] = None,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    admin_user = _require_user(authorization, db)
    req = (
        db.query(models.BookingRequest)
        .filter(or_(models.BookingRequest.group_id == job_id, models.BookingRequest.id == job_id))
        .order_by(models.BookingRequest.updated_at.desc())
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Job not found")
    if req.refund_status not in ("pending_review", None):
        raise HTTPException(status_code=400, detail="Refund is not pending review")

    req.refund_status = "denied"
    req.refund_reviewed_at = datetime.utcnow()
    req.refund_reviewed_by = admin_user.id
    req.refund_review_reason = payload.reason if payload else None
    db.commit()

    log_audit(
        db,
        actor_user=admin_user,
        target_user_id=req.parent_user_id,
        entity="booking_requests",
        entity_id=req.id,
        action="refund_denied",
        before_obj={},
        after_obj={"refund_status": req.refund_status, "reason": req.refund_review_reason},
        changed_fields=["refund_status", "refund_review_reason"],
        request=None,
    )

    return {"ok": True, "refund_status": req.refund_status}


@router.post("/availability", dependencies=[Depends(require_admin)])
def set_availability(
	nanny_id: int = Query(...),
	day: date = Query(...),
	start_time: time = Query(time(0, 0)),
	end_time: time = Query(time(23, 59)),
	is_available: bool = Query(True),
	notes: Optional[str] = Query(None),
	db: Session = Depends(get_db),
):
	if start_time >= end_time:
		raise HTTPException(status_code=400, detail="start_time must be before end_time")
	# Overlap check
	existing_slots = db.query(models.NannyAvailability).filter_by(
		nanny_id=nanny_id,
		date=day
	).all()
	for slot in existing_slots:
		if (slot.start_time < end_time) and (start_time < slot.end_time):
			raise HTTPException(status_code=409, detail="Availability overlaps an existing slot")
	row = db.query(models.NannyAvailability).filter_by(
		nanny_id=nanny_id,
		date=day,
		start_time=start_time,
		end_time=end_time,
	).first()
	if row:
		row.is_available = is_available
		row.notes = notes
	else:
		row = models.NannyAvailability(
			nanny_id=nanny_id,
			date=day,
			start_time=start_time,
			end_time=end_time,
			is_available=is_available,
			notes=notes,
			created_by="admin",
		)
		db.add(row)
	db.commit()
	db.refresh(row)
	return row

@router.get("/availability", dependencies=[Depends(require_admin)])
def list_availability(
	nanny_id: int = Query(...),
	day: Optional[date] = Query(None),
	db: Session = Depends(get_db),
):
	q = db.query(models.NannyAvailability).filter_by(nanny_id=nanny_id)
	if day:
		q = q.filter_by(date=day)
	return q.all()


@router.post("/reviews/{review_id}/approve", dependencies=[Depends(require_admin)])
def approve_review(review_id: int, db: Session = Depends(get_db)):
	review = db.query(models.Review).filter_by(id=review_id).first()
	if not review:
		raise HTTPException(status_code=404, detail="Review not found")
	if not review.approved:
		review.approved = True
		db.commit()
		db.refresh(review)
	# If already approved, do not update or error, just return 200 with review
	return review


@router.get("/reviews", dependencies=[Depends(require_admin)])
def list_reviews(approved: bool = Query(False), db: Session = Depends(get_db)):
	return db.query(models.Review).filter_by(approved=approved).order_by(models.Review.created_at.desc()).all()


@router.get("/audit-logs", dependencies=[Depends(require_admin)])
def list_audit_logs(
	entity: Optional[str] = Query(default=None),
	entity_id: Optional[str] = Query(default=None),
	target_user_id: Optional[int] = Query(default=None),
	actor_user_id: Optional[int] = Query(default=None),
	action: Optional[str] = Query(default=None),
	q: Optional[str] = Query(default=None),
	limit: int = Query(default=50, ge=1, le=200),
	offset: int = Query(default=0, ge=0),
	from_ts: Optional[datetime] = Query(default=None),
	to_ts: Optional[datetime] = Query(default=None),
	db: Session = Depends(get_db),
):
	actor_user = aliased(models.User)
	target_user = aliased(models.User)

	query = (
		db.query(models.AuditLog, actor_user.email.label("actor_email"), target_user.email.label("target_email"))
		.outerjoin(actor_user, actor_user.id == models.AuditLog.actor_user_id)
		.outerjoin(target_user, target_user.id == models.AuditLog.target_user_id)
	)

	if entity:
		query = query.filter(models.AuditLog.entity == entity)
	if entity_id:
		query = query.filter(models.AuditLog.entity_id == str(entity_id))
	if target_user_id is not None:
		query = query.filter(models.AuditLog.target_user_id == target_user_id)
	if actor_user_id is not None:
		query = query.filter(models.AuditLog.actor_user_id == actor_user_id)
	if action:
		query = query.filter(models.AuditLog.action == action)
	if from_ts:
		query = query.filter(models.AuditLog.created_at >= from_ts)
	if to_ts:
		query = query.filter(models.AuditLog.created_at <= to_ts)

	if q:
		like = f"%{q.lower()}%"
		query = query.filter(
			or_(
				func.lower(models.AuditLog.entity).like(like),
				func.lower(models.AuditLog.entity_id).like(like),
				func.lower(actor_user.email).like(like),
				func.lower(target_user.email).like(like),
			)
		)

	total = query.count()
	rows = (
		query.order_by(models.AuditLog.created_at.desc())
		.offset(offset)
		.limit(limit)
		.all()
	)

	results = []
	for log, actor_email, target_email in rows:
		changed_fields = None
		if log.changed_fields:
			try:
				changed_fields = json.loads(log.changed_fields)
			except Exception:
				changed_fields = log.changed_fields
		results.append(
			{
				"id": log.id,
				"created_at": log.created_at,
				"actor_user_id": log.actor_user_id,
				"actor_role": log.actor_role,
				"actor_email": actor_email,
				"target_user_id": log.target_user_id,
				"target_email": target_email,
				"entity": log.entity,
				"entity_id": log.entity_id,
				"action": log.action,
				"changed_fields": changed_fields,
			}
		)

	return {"total": total, "results": results}


@router.get("/audit-logs/{audit_id}", dependencies=[Depends(require_admin)])
def get_audit_log(audit_id: int, db: Session = Depends(get_db)):
	log = db.query(models.AuditLog).filter(models.AuditLog.id == audit_id).first()
	if not log:
		raise HTTPException(status_code=404, detail="Audit log not found")

	def parse_json(value: Optional[str]):
		if not value:
			return None
		try:
			return json.loads(value)
		except Exception:
			return value

	return {
		"id": log.id,
		"created_at": log.created_at,
		"actor_user_id": log.actor_user_id,
		"actor_role": log.actor_role,
		"target_user_id": log.target_user_id,
		"entity": log.entity,
		"entity_id": log.entity_id,
		"action": log.action,
		"before_json": parse_json(log.before_json),
		"after_json": parse_json(log.after_json),
		"changed_fields": parse_json(log.changed_fields),
		"ip": log.ip,
		"user_agent": log.user_agent,
	}
