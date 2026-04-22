"""
PT Rahaza — Attendance (Fase 8a)

Endpoints (prefix /api/rahaza):
  Supervisor:
    - GET  /attendance?date=&employee_id=      : list (optionally filtered)
    - GET  /attendance/grid?date=YYYY-MM-DD     : grid semua karyawan aktif + status hari itu (untuk bulk input)
    - POST /attendance                          : create/upsert 1 record
    - POST /attendance/bulk                     : bulk upsert banyak record sekaligus
    - PUT  /attendance/{id}
    - DELETE /attendance/{id}
    - GET  /attendance/summary?from=&to=&employee_id=
  Operator self-service:
    - POST /attendance/clock-in                 : body {employee_id, shift_id}
    - POST /attendance/clock-out                : body {employee_id}
    - GET  /attendance/my-today?employee_id=

Schema (rahaza_attendance_events):
  {
    id, employee_id, date (YYYY-MM-DD), shift_id?,
    clock_in: ISO | null, clock_out: ISO | null,
    hours_worked: float (dihitung dari clock_in→out; boleh override manual),
    overtime_hours: float,
    status: 'hadir' | 'izin' | 'sakit' | 'alfa' | 'cuti' | 'libur',
    notes, source: 'operator' | 'supervisor',
    created_by, created_by_name, created_at, updated_at
  }
Unique index pada (employee_id, date) supaya 1 record per hari per karyawan.
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-attendance"])

VALID_STATUSES = ["hadir", "izin", "sakit", "alfa", "cuti", "libur"]


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


def _today_iso(): return date.today().isoformat()


def _parse_iso(s: Optional[str]):
    if not s: return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _calc_hours(cin, cout) -> float:
    if not (cin and cout): return 0.0
    try:
        delta = (cout - cin).total_seconds() / 3600
        return round(max(0.0, delta), 2)
    except Exception:
        return 0.0


async def _require_hr(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin", "owner", "hr", "supervisor", "manager"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "hr.manage" in perms or "attendance.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission HR / attendance.")


async def _enrich(db, rows):
    if not rows: return rows
    emp_ids = list({r.get("employee_id") for r in rows if r.get("employee_id")})
    sh_ids  = list({r.get("shift_id") for r in rows if r.get("shift_id")})
    emps = await db.rahaza_employees.find({"id": {"$in": emp_ids}}, {"_id": 0}).to_list(None) if emp_ids else []
    shs  = await db.rahaza_shifts.find({"id": {"$in": sh_ids}}, {"_id": 0}).to_list(None) if sh_ids else []
    e_map = {e["id"]: e for e in emps}; s_map = {s["id"]: s for s in shs}
    for r in rows:
        e = e_map.get(r.get("employee_id")) or {}
        s = s_map.get(r.get("shift_id")) or {}
        r["employee_code"] = e.get("employee_code"); r["employee_name"] = e.get("name")
        r["shift_name"] = s.get("name")
    return rows


def _norm_record(body, user, existing=None):
    date_str = (body.get("date") or "").strip() or _today_iso()
    status   = (body.get("status") or "hadir").strip().lower()
    if status not in VALID_STATUSES:
        raise HTTPException(400, f"status harus salah satu: {VALID_STATUSES}")
    cin  = _parse_iso(body.get("clock_in"))
    cout = _parse_iso(body.get("clock_out"))
    hours_override = body.get("hours_worked")
    hours = float(hours_override) if hours_override not in (None, "") else _calc_hours(cin, cout)
    ot    = float(body.get("overtime_hours") or 0)
    doc = {
        "employee_id": body.get("employee_id"),
        "date": date_str,
        "shift_id": body.get("shift_id") or None,
        "clock_in":  cin,
        "clock_out": cout,
        "hours_worked": round(max(0.0, hours), 2),
        "overtime_hours": round(max(0.0, ot), 2),
        "status": status,
        "notes": body.get("notes") or "",
        "source": (body.get("source") or "supervisor").lower(),
        "updated_by": user["id"], "updated_by_name": user.get("name", ""),
        "updated_at": _now(),
    }
    if not existing:
        doc["id"] = _uid()
        doc["created_by"] = user["id"]
        doc["created_by_name"] = user.get("name", "")
        doc["created_at"] = _now()
    return doc


# ── LIST & DETAIL ─────────────────────────────────────────────────────────────
@router.get("/attendance")
async def list_attendance(request: Request, date: Optional[str] = None, employee_id: Optional[str] = None, from_: Optional[str] = None, to: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if date: q["date"] = date
    if employee_id: q["employee_id"] = employee_id
    if from_ or to:
        range_q = {}
        if from_: range_q["$gte"] = from_
        if to:    range_q["$lte"] = to
        q["date"] = range_q
    rows = await db.rahaza_attendance_events.find(q, {"_id": 0}).sort("date", -1).to_list(None)
    await _enrich(db, rows)
    return serialize_doc(rows)


@router.get("/attendance/grid")
async def attendance_grid(request: Request, date: Optional[str] = None):
    """Grid bulk-entry: semua karyawan aktif + status hari itu."""
    await require_auth(request)
    db = get_db()
    d = date or _today_iso()
    emps = await db.rahaza_employees.find({"active": True}, {"_id": 0}).sort("employee_code", 1).to_list(None)
    existing = await db.rahaza_attendance_events.find({"date": d}, {"_id": 0}).to_list(None)
    by_emp = {r["employee_id"]: r for r in existing}
    shifts = await db.rahaza_shifts.find({"active": True}, {"_id": 0}).sort("start_time", 1).to_list(None)
    rows = []
    for e in emps:
        r = by_emp.get(e["id"])
        rows.append({
            "employee_id": e["id"],
            "employee_code": e["employee_code"],
            "employee_name": e["name"],
            "role": e.get("role"),
            "line_id": e.get("line_id"),
            "existing_id": r["id"] if r else None,
            "status":     (r or {}).get("status",   "hadir"),
            "shift_id":   (r or {}).get("shift_id") or None,
            "clock_in":   (r or {}).get("clock_in"),
            "clock_out":  (r or {}).get("clock_out"),
            "hours_worked":    (r or {}).get("hours_worked", 0),
            "overtime_hours":  (r or {}).get("overtime_hours", 0),
            "notes":      (r or {}).get("notes", ""),
            "source":     (r or {}).get("source", "supervisor"),
        })
    return {"date": d, "shifts": serialize_doc(shifts), "rows": serialize_doc(rows)}


@router.get("/attendance/summary")
async def attendance_summary(request: Request, from_: Optional[str] = None, to: Optional[str] = None, employee_id: Optional[str] = None):
    """Agregasi per-karyawan untuk periode tertentu (dipakai payroll)."""
    await require_auth(request)
    db = get_db()
    q = {}
    if from_ or to:
        rg = {}
        if from_: rg["$gte"] = from_
        if to: rg["$lte"] = to
        q["date"] = rg
    if employee_id: q["employee_id"] = employee_id
    rows = await db.rahaza_attendance_events.find(q, {"_id": 0}).to_list(None)
    # Aggregate
    summary = {}
    for r in rows:
        eid = r["employee_id"]
        s = summary.setdefault(eid, {"employee_id": eid, "days_hadir": 0, "days_izin": 0, "days_sakit": 0, "days_alfa": 0, "days_cuti": 0, "days_libur": 0, "total_hours": 0, "total_overtime": 0})
        k = f"days_{r.get('status', 'hadir')}"
        if k in s: s[k] += 1
        s["total_hours"]   += float(r.get("hours_worked") or 0)
        s["total_overtime"]+= float(r.get("overtime_hours") or 0)
    # Enrich
    eids = list(summary.keys())
    emps = await db.rahaza_employees.find({"id": {"$in": eids}}, {"_id": 0}).to_list(None) if eids else []
    e_map = {e["id"]: e for e in emps}
    out = []
    for eid, s in summary.items():
        e = e_map.get(eid) or {}
        out.append({**s, "employee_code": e.get("employee_code"), "employee_name": e.get("name"), "role": e.get("role")})
    out.sort(key=lambda r: r.get("employee_code") or "")
    return {"from": from_, "to": to, "summary": out}


# ── CREATE / UPSERT (supervisor) ──────────────────────────────────────────────
@router.post("/attendance")
async def create_or_upsert(request: Request):
    user = await _require_hr(request)
    db = get_db()
    body = await request.json()
    if not body.get("employee_id"):
        raise HTTPException(400, "employee_id wajib.")
    d = body.get("date") or _today_iso()
    existing = await db.rahaza_attendance_events.find_one({"employee_id": body["employee_id"], "date": d}, {"_id": 0})
    doc = _norm_record({**body, "date": d}, user, existing=existing)
    if existing:
        await db.rahaza_attendance_events.update_one({"id": existing["id"]}, {"$set": doc})
        out = await db.rahaza_attendance_events.find_one({"id": existing["id"]}, {"_id": 0})
    else:
        await db.rahaza_attendance_events.insert_one(doc)
        out = await db.rahaza_attendance_events.find_one({"id": doc["id"]}, {"_id": 0})
    await _enrich(db, [out])
    await log_activity(user["id"], user.get("name", ""), "upsert", "rahaza.attendance", f"{body['employee_id']}|{d}")
    return serialize_doc(out)


@router.post("/attendance/bulk")
async def bulk_upsert(request: Request):
    """Body: {date, entries: [{employee_id, status, shift_id?, clock_in?, clock_out?, hours_worked?, overtime_hours?, notes?}]}."""
    user = await _require_hr(request)
    db = get_db()
    body = await request.json()
    d = body.get("date") or _today_iso()
    entries = body.get("entries") or []
    if not isinstance(entries, list) or not entries:
        raise HTTPException(400, "entries wajib diisi (list).")
    upserted, created = [], 0
    for e in entries:
        if not e.get("employee_id"):
            continue
        existing = await db.rahaza_attendance_events.find_one({"employee_id": e["employee_id"], "date": d}, {"_id": 0})
        doc = _norm_record({**e, "date": d}, user, existing=existing)
        if existing:
            await db.rahaza_attendance_events.update_one({"id": existing["id"]}, {"$set": doc})
            upserted.append(existing["id"])
        else:
            await db.rahaza_attendance_events.insert_one(doc)
            upserted.append(doc["id"])
            created += 1
    await log_activity(user["id"], user.get("name", ""), f"bulk:{len(upserted)}", "rahaza.attendance", d)
    return {"date": d, "upserted": len(upserted), "created": created}


@router.put("/attendance/{aid}")
async def update_attendance(aid: str, request: Request):
    user = await _require_hr(request)
    db = get_db()
    existing = await db.rahaza_attendance_events.find_one({"id": aid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Attendance tidak ditemukan.")
    body = await request.json()
    doc = _norm_record({**existing, **body, "employee_id": existing["employee_id"], "date": existing["date"]}, user, existing=existing)
    await db.rahaza_attendance_events.update_one({"id": aid}, {"$set": doc})
    out = await db.rahaza_attendance_events.find_one({"id": aid}, {"_id": 0})
    await _enrich(db, [out])
    return serialize_doc(out)


@router.delete("/attendance/{aid}")
async def delete_attendance(aid: str, request: Request):
    user = await _require_hr(request)
    db = get_db()
    res = await db.rahaza_attendance_events.delete_one({"id": aid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Attendance tidak ditemukan.")
    return {"status": "deleted"}


# ── CLOCK IN/OUT (operator) ───────────────────────────────────────────────────────
@router.post("/attendance/clock-in")
async def clock_in(request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    emp_id = body.get("employee_id")
    if not emp_id:
        raise HTTPException(400, "employee_id wajib.")
    d = _today_iso()
    existing = await db.rahaza_attendance_events.find_one({"employee_id": emp_id, "date": d}, {"_id": 0})
    if existing and existing.get("clock_in"):
        raise HTTPException(400, "Sudah clock-in hari ini.")
    now = _now()
    doc = {
        "id": existing["id"] if existing else _uid(),
        "employee_id": emp_id, "date": d,
        "shift_id": body.get("shift_id") or (existing or {}).get("shift_id"),
        "clock_in": now,
        "clock_out": (existing or {}).get("clock_out"),
        "hours_worked": (existing or {}).get("hours_worked", 0),
        "overtime_hours": (existing or {}).get("overtime_hours", 0),
        "status": "hadir",
        "notes": (existing or {}).get("notes", ""),
        "source": "operator",
        "updated_by": user["id"], "updated_by_name": user.get("name", ""),
        "updated_at": now,
    }
    if existing:
        await db.rahaza_attendance_events.update_one({"id": existing["id"]}, {"$set": doc})
    else:
        doc["created_by"] = user["id"]; doc["created_by_name"] = user.get("name", ""); doc["created_at"] = now
        await db.rahaza_attendance_events.insert_one(doc)
    out = await db.rahaza_attendance_events.find_one({"id": doc["id"]}, {"_id": 0})
    return serialize_doc(out)


@router.post("/attendance/clock-out")
async def clock_out(request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    emp_id = body.get("employee_id")
    if not emp_id:
        raise HTTPException(400, "employee_id wajib.")
    d = _today_iso()
    existing = await db.rahaza_attendance_events.find_one({"employee_id": emp_id, "date": d}, {"_id": 0})
    if not existing or not existing.get("clock_in"):
        raise HTTPException(400, "Belum clock-in hari ini.")
    if existing.get("clock_out"):
        raise HTTPException(400, "Sudah clock-out hari ini.")
    now = _now()
    cin = existing["clock_in"]
    if isinstance(cin, str): cin = _parse_iso(cin)
    hours = _calc_hours(cin, now)
    await db.rahaza_attendance_events.update_one({"id": existing["id"]}, {"$set": {
        "clock_out": now, "hours_worked": hours, "source": "operator", "updated_at": now,
        "updated_by": user["id"], "updated_by_name": user.get("name", ""),
    }})
    out = await db.rahaza_attendance_events.find_one({"id": existing["id"]}, {"_id": 0})
    return serialize_doc(out)


@router.get("/attendance/my-today")
async def my_today(request: Request, employee_id: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    if not employee_id:
        raise HTTPException(400, "employee_id wajib.")
    d = _today_iso()
    rec = await db.rahaza_attendance_events.find_one({"employee_id": employee_id, "date": d}, {"_id": 0})
    if not rec:
        return {"date": d, "employee_id": employee_id, "status": None, "has_clock_in": False, "has_clock_out": False, "record": None}
    return {
        "date": d, "employee_id": employee_id,
        "status": rec.get("status"),
        "has_clock_in": bool(rec.get("clock_in")),
        "has_clock_out": bool(rec.get("clock_out")),
        "record": serialize_doc(rec),
    }
