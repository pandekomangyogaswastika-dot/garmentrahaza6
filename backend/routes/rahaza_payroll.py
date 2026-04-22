"""
PT Rahaza — Payroll (Fase 8b + 8c)

Fase 8b — Payroll Profiles per Pegawai:
  - /payroll-profiles               (GET list, POST upsert by employee_id)
  - /payroll-profiles/{employee_id} (GET one, PUT, DELETE)

Fase 8c — Payroll Run & Payslip:
  - /payroll-runs                     (GET list, POST create + auto-generate payslips)
  - /payroll-runs/{id}                (GET detail, DELETE [draft only])
  - /payroll-runs/{id}/finalize       (POST lock)
  - /payroll-runs/{id}/export         (GET CSV)
  - /payslips?run_id=&employee_id=   (GET list)
  - /payslips/{id}                   (GET, PUT [edit deductions/notes; draft only])

Schemes (4):
  - pcs      : borongan per pcs — qty × rate (by process or default)
  - hourly   : borongan per jam — jam_kerja × rate
  - weekly   : mingguan — jumlah minggu × rate
  - monthly  : bulanan — 1 × rate (periode diset 1 bulan oleh user)

Aturan khusus (keputusan user):
  - Rework pcs dibayar 2x: hitung SEMUA event_type='output' per operator
    (operator Rajut dapat output awal, operator Washer/Sontek dapat output rework terpisah)
  - Overtime selalu manual input dari attendance.overtime_hours × overtime_rate
  - Deductions configurable per slip (array items label+amount)
  - Periode payroll configurable per-pegawai via profile, tapi run window menetapkan [period_from, period_to]
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
import io
import csv
from datetime import datetime, timezone, date, timedelta
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-payroll"])

VALID_SCHEMES = ["pcs", "hourly", "weekly", "monthly"]
VALID_PERIOD_TYPES = ["weekly", "monthly"]
VALID_RUN_STATUS = ["draft", "finalized", "cancelled"]


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


async def _require_hr(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin", "owner", "hr", "manager"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "hr.manage" in perms or "payroll.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission HR/payroll.")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ FASE 8b — PAYROLL PROFILES                                                ║
# ╚══════════════════════════════════════════════════════════════════════════╝

@router.get("/payroll-profiles")
async def list_profiles(request: Request, employee_id: Optional[str] = None, active_only: bool = True):
    await require_auth(request)
    db = get_db()
    q = {}
    if active_only:
        q["active"] = True
    if employee_id:
        q["employee_id"] = employee_id
    rows = await db.rahaza_payroll_profiles.find(q, {"_id": 0}).to_list(None)
    # Enrich with employee info
    emp_ids = list({r.get("employee_id") for r in rows if r.get("employee_id")})
    emps = await db.rahaza_employees.find({"id": {"$in": emp_ids}}, {"_id": 0}).to_list(None) if emp_ids else []
    e_map = {e["id"]: e for e in emps}
    for r in rows:
        e = e_map.get(r.get("employee_id")) or {}
        r["employee_code"] = e.get("employee_code")
        r["employee_name"] = e.get("name")
    rows.sort(key=lambda r: r.get("employee_code") or "")
    return serialize_doc(rows)


@router.get("/payroll-profiles/{employee_id}")
async def get_profile(employee_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    row = await db.rahaza_payroll_profiles.find_one({"employee_id": employee_id, "active": True}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Profile payroll belum dibuat untuk pegawai ini.")
    emp = await db.rahaza_employees.find_one({"id": employee_id}, {"_id": 0}) or {}
    row["employee_code"] = emp.get("employee_code")
    row["employee_name"] = emp.get("name")
    return serialize_doc(row)


def _normalize_profile(body: dict) -> dict:
    pay_scheme = (body.get("pay_scheme") or "monthly").lower()
    period_type = (body.get("period_type") or "monthly").lower()
    if pay_scheme not in VALID_SCHEMES:
        raise HTTPException(400, f"pay_scheme harus salah satu: {VALID_SCHEMES}")
    if period_type not in VALID_PERIOD_TYPES:
        raise HTTPException(400, f"period_type harus salah satu: {VALID_PERIOD_TYPES}")
    cutoff = body.get("cutoff_config") or {}
    # Defaults
    if period_type == "weekly" and "week_start_day" not in cutoff:
        cutoff["week_start_day"] = 1  # Monday
    if period_type == "monthly" and "start_day" not in cutoff:
        cutoff["start_day"] = 1  # 1st of month
    # Validate ranges
    wsd = cutoff.get("week_start_day")
    if wsd is not None and (not isinstance(wsd, int) or not (0 <= wsd <= 6)):
        raise HTTPException(400, "week_start_day harus 0..6 (0=Senin..6=Minggu)")
    sd = cutoff.get("start_day")
    if sd is not None and (not isinstance(sd, int) or not (1 <= sd <= 28)):
        raise HTTPException(400, "start_day harus 1..28")
    pcs_rates = body.get("pcs_process_rates") or []
    norm_pcs_rates = []
    for r in pcs_rates:
        if not r.get("process_id"):
            continue
        norm_pcs_rates.append({
            "process_id": r["process_id"],
            "process_code": (r.get("process_code") or "").upper(),
            "rate": float(r.get("rate") or 0),
        })
    return {
        "employee_id": body.get("employee_id"),
        "pay_scheme": pay_scheme,
        "period_type": period_type,
        "cutoff_config": cutoff,
        "base_rate": float(body.get("base_rate") or 0),
        "overtime_rate": float(body.get("overtime_rate") or 0),
        "pcs_process_rates": norm_pcs_rates,
        "notes": body.get("notes") or "",
    }


@router.post("/payroll-profiles")
async def upsert_profile(request: Request):
    user = await _require_hr(request)
    db = get_db()
    body = await request.json()
    emp_id = body.get("employee_id")
    if not emp_id:
        raise HTTPException(400, "employee_id wajib.")
    emp = await db.rahaza_employees.find_one({"id": emp_id}, {"_id": 0})
    if not emp:
        raise HTTPException(404, f"Pegawai dengan id={emp_id} tidak ditemukan.")
    doc = _normalize_profile(body)
    existing = await db.rahaza_payroll_profiles.find_one({"employee_id": emp_id, "active": True}, {"_id": 0})
    now = _now()
    doc.update({
        "active": True,
        "updated_at": now,
        "updated_by": user["id"],
        "updated_by_name": user.get("name", ""),
    })
    if existing:
        await db.rahaza_payroll_profiles.update_one({"id": existing["id"]}, {"$set": doc})
        out = await db.rahaza_payroll_profiles.find_one({"id": existing["id"]}, {"_id": 0})
    else:
        doc["id"] = _uid()
        doc["created_at"] = now
        doc["created_by"] = user["id"]
        doc["created_by_name"] = user.get("name", "")
        await db.rahaza_payroll_profiles.insert_one(doc)
        out = await db.rahaza_payroll_profiles.find_one({"id": doc["id"]}, {"_id": 0})
    await log_activity(user["id"], user.get("name", ""), "upsert", "rahaza.payroll_profile", emp_id)
    out["employee_code"] = emp.get("employee_code")
    out["employee_name"] = emp.get("name")
    return serialize_doc(out)


@router.put("/payroll-profiles/{pid}")
async def update_profile(pid: str, request: Request):
    user = await _require_hr(request)
    db = get_db()
    existing = await db.rahaza_payroll_profiles.find_one({"id": pid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Profile tidak ditemukan.")
    body = await request.json()
    body["employee_id"] = existing["employee_id"]  # cannot change
    doc = _normalize_profile(body)
    doc.update({
        "updated_at": _now(),
        "updated_by": user["id"],
        "updated_by_name": user.get("name", ""),
    })
    await db.rahaza_payroll_profiles.update_one({"id": pid}, {"$set": doc})
    out = await db.rahaza_payroll_profiles.find_one({"id": pid}, {"_id": 0})
    return serialize_doc(out)


@router.delete("/payroll-profiles/{pid}")
async def delete_profile(pid: str, request: Request):
    user = await _require_hr(request)
    db = get_db()
    res = await db.rahaza_payroll_profiles.update_one({"id": pid, "active": True}, {"$set": {"active": False, "updated_at": _now(), "updated_by": user["id"]}})
    if res.matched_count == 0:
        raise HTTPException(404, "Profile tidak ditemukan atau sudah nonaktif.")
    return {"status": "deleted"}


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ FASE 8c — PAYROLL RUN & PAYSLIP                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def _to_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _date_range_filter(from_iso: str, to_iso: str) -> dict:
    return {"$gte": from_iso, "$lte": to_iso}


async def _generate_run_number(db) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"PR-{today}-"
    count = await db.rahaza_payroll_runs.count_documents({"run_number": {"$regex": f"^{prefix}"}})
    return f"{prefix}{count+1:03d}"


async def _compute_payslip_for_employee(db, profile: dict, period_from: str, period_to: str, emp: dict) -> dict:
    """Hitung slip payroll untuk 1 pegawai berdasarkan profile + window."""
    scheme = profile["pay_scheme"]
    base_rate = float(profile.get("base_rate") or 0)
    ot_rate = float(profile.get("overtime_rate") or 0)
    emp_id = profile["employee_id"]

    earnings = []
    source_refs = {"wip_event_count": 0, "attendance_event_count": 0, "process_breakdown": {}}

    # Query attendance untuk periode
    att_rows = await db.rahaza_attendance_events.find({
        "employee_id": emp_id,
        "date": _date_range_filter(period_from, period_to),
    }, {"_id": 0}).to_list(None)
    source_refs["attendance_event_count"] = len(att_rows)
    total_hours = sum(float(r.get("hours_worked") or 0) for r in att_rows)
    total_ot = sum(float(r.get("overtime_hours") or 0) for r in att_rows)
    days_hadir = sum(1 for r in att_rows if r.get("status") == "hadir")

    if scheme == "pcs":
        # Sum WIP events output oleh operator ini dalam periode
        # Event date bisa dicompare via string ISO karena format ISO cocok lexicographic
        wip_rows = await db.rahaza_wip_events.find({
            "operator_id": emp_id,
            "event_type": "output",
            "event_date": _date_range_filter(period_from, period_to),
        }, {"_id": 0}).to_list(None)
        source_refs["wip_event_count"] = len(wip_rows)
        # Group by process_id
        proc_map = {}
        for ev in wip_rows:
            pid = ev.get("process_id") or "unknown"
            if pid not in proc_map:
                proc_map[pid] = {"qty": 0, "events": 0, "process_code": ev.get("process_code") or ""}
            proc_map[pid]["qty"] += int(ev.get("qty") or 0)
            proc_map[pid]["events"] += 1
            if ev.get("process_code"):
                proc_map[pid]["process_code"] = ev["process_code"]
        # Cari rate per process (override) atau base_rate
        rate_overrides = {r["process_id"]: r["rate"] for r in (profile.get("pcs_process_rates") or [])}
        for pid, info in proc_map.items():
            rate = float(rate_overrides.get(pid, base_rate))
            amount = round(info["qty"] * rate)
            label = f"Borongan pcs · {info.get('process_code') or 'Proses'}"
            earnings.append({
                "label": label,
                "qty": info["qty"],
                "unit": "pcs",
                "rate": rate,
                "amount": amount,
            })
            source_refs["process_breakdown"][info.get("process_code") or pid] = {
                "qty": info["qty"],
                "rate": rate,
                "amount": amount,
            }
    elif scheme == "hourly":
        amount = round(total_hours * base_rate)
        earnings.append({
            "label": "Borongan jam",
            "qty": round(total_hours, 2),
            "unit": "jam",
            "rate": base_rate,
            "amount": amount,
        })
    elif scheme == "weekly":
        try:
            d_from = _to_date(period_from)
            d_to = _to_date(period_to)
            days = (d_to - d_from).days + 1
            weeks = max(1, round(days / 7))
        except Exception:
            weeks = 1
        amount = round(weeks * base_rate)
        earnings.append({
            "label": "Gaji mingguan",
            "qty": weeks,
            "unit": "minggu",
            "rate": base_rate,
            "amount": amount,
        })
    elif scheme == "monthly":
        amount = round(base_rate)
        earnings.append({
            "label": "Gaji bulanan",
            "qty": 1,
            "unit": "bulan",
            "rate": base_rate,
            "amount": amount,
        })

    earnings_total = sum(e["amount"] for e in earnings)
    overtime_amount = round(total_ot * ot_rate)
    gross = earnings_total + overtime_amount

    payslip = {
        "id": _uid(),
        "employee_id": emp_id,
        "employee_code": emp.get("employee_code"),
        "employee_name": emp.get("name"),
        "pay_scheme": scheme,
        "period_from": period_from,
        "period_to": period_to,
        "earnings": earnings,
        "earnings_total": earnings_total,
        "overtime_hours": round(total_ot, 2),
        "overtime_rate": ot_rate,
        "overtime_amount": overtime_amount,
        "total_hours_worked": round(total_hours, 2),
        "days_hadir": days_hadir,
        "gross_pay": gross,
        "deductions": [],
        "deductions_total": 0,
        "net_pay": gross,
        "source_refs": source_refs,
        "notes": "",
    }
    return payslip


@router.get("/payroll-runs")
async def list_runs(request: Request, status: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if status:
        q["status"] = status
    rows = await db.rahaza_payroll_runs.find(q, {"_id": 0}).sort("created_at", -1).to_list(None)
    return serialize_doc(rows)


@router.post("/payroll-runs")
async def create_run(request: Request):
    user = await _require_hr(request)
    db = get_db()
    body = await request.json()
    period_from = (body.get("period_from") or "").strip()
    period_to = (body.get("period_to") or "").strip()
    if not (period_from and period_to):
        raise HTTPException(400, "period_from & period_to wajib (YYYY-MM-DD).")
    try:
        _to_date(period_from); _to_date(period_to)
    except Exception:
        raise HTTPException(400, "Format tanggal harus YYYY-MM-DD.")
    if period_from > period_to:
        raise HTTPException(400, "period_from tidak boleh > period_to.")

    # Ambil profile aktif
    employee_ids = body.get("employee_ids") or []
    q = {"active": True}
    if employee_ids:
        q["employee_id"] = {"$in": employee_ids}
    profiles = await db.rahaza_payroll_profiles.find(q, {"_id": 0}).to_list(None)
    if not profiles:
        raise HTTPException(400, "Tidak ada payroll profile aktif untuk diproses. Buat profile dulu di menu Payroll Profiles.")

    emp_ids = [p["employee_id"] for p in profiles]
    emps = await db.rahaza_employees.find({"id": {"$in": emp_ids}}, {"_id": 0}).to_list(None)
    e_map = {e["id"]: e for e in emps}

    # Create run header
    run_number = await _generate_run_number(db)
    run_id = _uid()
    now = _now()

    # Generate payslips
    payslips = []
    for p in profiles:
        emp = e_map.get(p["employee_id"])
        if not emp:
            continue
        slip = await _compute_payslip_for_employee(db, p, period_from, period_to, emp)
        slip.update({
            "run_id": run_id,
            "run_number": run_number,
            "created_at": now,
            "updated_at": now,
        })
        payslips.append(slip)

    if payslips:
        await db.rahaza_payslips.insert_many(payslips)

    total_gross = sum(s["gross_pay"] for s in payslips)
    total_ded = sum(s["deductions_total"] for s in payslips)
    total_net = sum(s["net_pay"] for s in payslips)

    run_doc = {
        "id": run_id,
        "run_number": run_number,
        "period_from": period_from,
        "period_to": period_to,
        "status": "draft",
        "total_employees": len(payslips),
        "total_gross": total_gross,
        "total_deductions": total_ded,
        "total_net": total_net,
        "notes": body.get("notes") or "",
        "created_at": now,
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "updated_at": now,
    }
    await db.rahaza_payroll_runs.insert_one(run_doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.payroll_run", run_number)
    out = await db.rahaza_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    return serialize_doc(out)


@router.get("/payroll-runs/{run_id}")
async def get_run(run_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    run = await db.rahaza_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Payroll run tidak ditemukan.")
    payslips = await db.rahaza_payslips.find({"run_id": run_id}, {"_id": 0}).sort("employee_code", 1).to_list(None)
    return serialize_doc({"run": run, "payslips": payslips})


@router.post("/payroll-runs/{run_id}/finalize")
async def finalize_run(run_id: str, request: Request):
    user = await _require_hr(request)
    db = get_db()
    run = await db.rahaza_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Payroll run tidak ditemukan.")
    if run.get("status") != "draft":
        raise HTTPException(400, f"Run sudah ber-status '{run.get('status')}', tidak bisa finalize.")
    # Recalc totals dari payslips (in case deductions diubah)
    payslips = await db.rahaza_payslips.find({"run_id": run_id}, {"_id": 0}).to_list(None)
    total_gross = sum(s.get("gross_pay", 0) for s in payslips)
    total_ded = sum(s.get("deductions_total", 0) for s in payslips)
    total_net = sum(s.get("net_pay", 0) for s in payslips)
    await db.rahaza_payroll_runs.update_one({"id": run_id}, {"$set": {
        "status": "finalized",
        "total_gross": total_gross,
        "total_deductions": total_ded,
        "total_net": total_net,
        "finalized_at": _now(),
        "finalized_by": user["id"],
        "finalized_by_name": user.get("name", ""),
        "updated_at": _now(),
    }})
    await log_activity(user["id"], user.get("name", ""), "finalize", "rahaza.payroll_run", run.get("run_number"))
    out = await db.rahaza_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    return serialize_doc(out)


@router.delete("/payroll-runs/{run_id}")
async def delete_run(run_id: str, request: Request):
    user = await _require_hr(request)
    db = get_db()
    run = await db.rahaza_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Payroll run tidak ditemukan.")
    if run.get("status") == "finalized":
        raise HTTPException(400, "Run yang sudah finalized tidak bisa dihapus. Gunakan cancel atau buat run baru.")
    await db.rahaza_payslips.delete_many({"run_id": run_id})
    await db.rahaza_payroll_runs.delete_one({"id": run_id})
    return {"status": "deleted"}


@router.get("/payroll-runs/{run_id}/export")
async def export_run_csv(run_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    run = await db.rahaza_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Payroll run tidak ditemukan.")
    payslips = await db.rahaza_payslips.find({"run_id": run_id}, {"_id": 0}).sort("employee_code", 1).to_list(None)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "run_number", "period_from", "period_to",
        "employee_code", "employee_name", "pay_scheme",
        "earnings_total", "overtime_hours", "overtime_amount",
        "gross_pay", "deductions_total", "net_pay",
        "days_hadir", "total_hours_worked",
    ])
    for s in payslips:
        w.writerow([
            run.get("run_number"), run.get("period_from"), run.get("period_to"),
            s.get("employee_code"), s.get("employee_name"), s.get("pay_scheme"),
            s.get("earnings_total", 0), s.get("overtime_hours", 0), s.get("overtime_amount", 0),
            s.get("gross_pay", 0), s.get("deductions_total", 0), s.get("net_pay", 0),
            s.get("days_hadir", 0), s.get("total_hours_worked", 0),
        ])
    buf.seek(0)
    filename = f"payroll_{run.get('run_number')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── PAYSLIPS ──────────────────────────────────────────────────────────────────
@router.get("/payslips")
async def list_payslips(request: Request, run_id: Optional[str] = None, employee_id: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if run_id: q["run_id"] = run_id
    if employee_id: q["employee_id"] = employee_id
    rows = await db.rahaza_payslips.find(q, {"_id": 0}).sort("employee_code", 1).to_list(None)
    return serialize_doc(rows)


@router.get("/payslips/{pid}")
async def get_payslip(pid: str, request: Request):
    await require_auth(request)
    db = get_db()
    row = await db.rahaza_payslips.find_one({"id": pid}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Payslip tidak ditemukan.")
    return serialize_doc(row)


@router.put("/payslips/{pid}")
async def update_payslip(pid: str, request: Request):
    """Update deductions & notes saja (untuk adjust manual). Hanya jika run masih draft."""
    user = await _require_hr(request)
    db = get_db()
    slip = await db.rahaza_payslips.find_one({"id": pid}, {"_id": 0})
    if not slip:
        raise HTTPException(404, "Payslip tidak ditemukan.")
    run = await db.rahaza_payroll_runs.find_one({"id": slip["run_id"]}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run induk tidak ditemukan.")
    if run.get("status") != "draft":
        raise HTTPException(400, "Run sudah di-finalize — slip tidak bisa diubah.")

    body = await request.json()
    deductions = body.get("deductions") or []
    norm_ded = []
    for d in deductions:
        label = (d.get("label") or "").strip()
        amount = float(d.get("amount") or 0)
        if not label or amount <= 0:
            continue
        norm_ded.append({"label": label, "amount": round(amount)})
    ded_total = sum(d["amount"] for d in norm_ded)
    gross = slip.get("gross_pay", 0)
    net = max(0, gross - ded_total)
    await db.rahaza_payslips.update_one({"id": pid}, {"$set": {
        "deductions": norm_ded,
        "deductions_total": ded_total,
        "net_pay": net,
        "notes": body.get("notes") or slip.get("notes", ""),
        "updated_at": _now(),
        "updated_by": user["id"],
        "updated_by_name": user.get("name", ""),
    }})
    out = await db.rahaza_payslips.find_one({"id": pid}, {"_id": 0})
    return serialize_doc(out)
