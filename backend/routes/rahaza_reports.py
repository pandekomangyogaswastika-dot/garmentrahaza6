"""
PT Rahaza — Management Dashboard & Reports (Fase 10)

Endpoints (prefix /api/rahaza):
  - GET /management/overview         : KPI lengkap utk dashboard management
  - GET /management/daily-output     : output harian per proses (untuk chart 7 hari terakhir)
  - GET /management/top-models       : top model by output (30 hari)
  - GET /management/top-customers    : top customer by order value
  - GET /management/on-time-delivery : % WO completed tepat waktu
  - GET /management/payroll-summary  : ringkasan run payroll terakhir
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc
from datetime import datetime, timezone, date, timedelta
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-reports"])


def _today(): return date.today()


@router.get("/management/overview")
async def overview(request: Request):
    """
    KPI overview. Phase 13 — support date_from/date_to query params.
    Jika keduanya disupply, window analitis 7-hari akan direplace rentang
    custom. Semua metric tetap relatif (start7/start30 = from/to).
    """
    await require_auth(request)
    db = get_db()
    today = _today()
    t_iso = today.isoformat()

    # Phase 13.3 — custom period support
    sp = request.query_params
    date_from = sp.get("date_from") or None
    date_to = sp.get("date_to") or None
    if date_from and date_to:
        # Validate date format
        try:
            from datetime import datetime as _dt
            _dt.fromisoformat(date_from); _dt.fromisoformat(date_to)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Format tanggal tidak valid. Gunakan YYYY-MM-DD.")
        if date_to < date_from:
            raise HTTPException(status_code=400, detail="date_to tidak boleh lebih awal dari date_from.")
        start7 = date_from
        start30 = date_from
        t_iso = date_to
    else:
        start7 = (today - timedelta(days=7)).isoformat()
        start30 = (today - timedelta(days=30)).isoformat()

    # Produksi: total output pada window
    wip_7d = await db.rahaza_wip_events.aggregate([
        {"$match": {"event_type": "output", "event_date": {"$gte": start7, "$lte": t_iso}}},
        {"$group": {"_id": None, "total": {"$sum": "$qty"}, "count": {"$sum": 1}}}
    ]).to_list(None)
    output_7d = (wip_7d[0] if wip_7d else {}).get("total", 0) or 0

    # WO: active & completed counts
    wo_active = await db.rahaza_work_orders.count_documents({"status": {"$in": ["draft", "released", "in_production"]}})
    wo_completed = await db.rahaza_work_orders.count_documents({"status": "completed"})

    # Orders: in_production
    orders_active = await db.rahaza_orders.count_documents({"status": {"$in": ["confirmed", "in_production"]}})

    # Employees active
    emp_active = await db.rahaza_employees.count_documents({"active": True})

    # Attendance today
    att_today = await db.rahaza_attendance_events.aggregate([
        {"$match": {"date": t_iso}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]).to_list(None)
    att_summary = {a["_id"]: a["count"] for a in att_today}

    # QC stats (7d)
    qc_pass = await db.rahaza_wip_events.aggregate([
        {"$match": {"event_type": "qc_pass", "event_date": {"$gte": start7}}},
        {"$group": {"_id": None, "total": {"$sum": "$qty"}}}
    ]).to_list(None)
    qc_fail = await db.rahaza_wip_events.aggregate([
        {"$match": {"event_type": "qc_fail", "event_date": {"$gte": start7}}},
        {"$group": {"_id": None, "total": {"$sum": "$qty"}}}
    ]).to_list(None)
    qc_pass_qty = (qc_pass[0] if qc_pass else {}).get("total", 0) or 0
    qc_fail_qty = (qc_fail[0] if qc_fail else {}).get("total", 0) or 0
    qc_rate = (qc_pass_qty / (qc_pass_qty + qc_fail_qty) * 100) if (qc_pass_qty + qc_fail_qty) > 0 else 0

    # Finance
    ar = await db.rahaza_ar_invoices.aggregate([
        {"$match": {"status": {"$in": ["sent", "partial_paid", "overdue"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]).to_list(None)
    ap = await db.rahaza_ap_invoices.aggregate([
        {"$match": {"status": {"$in": ["sent", "partial_paid"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]).to_list(None)
    cash = await db.rahaza_cash_accounts.aggregate([
        {"$match": {"active": True}},
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]).to_list(None)

    # Low stock materials
    low_stock = await db.rahaza_material_stock.aggregate([
        {"$lookup": {"from": "rahaza_materials", "localField": "material_id", "foreignField": "id", "as": "m"}},
        {"$unwind": "$m"},
        {"$match": {"$expr": {"$lt": ["$qty_available", "$m.min_stock"]}}},
        {"$count": "n"}
    ]).to_list(None)
    low_count = (low_stock[0] if low_stock else {}).get("n", 0)

    return {
        "production": {
            "output_7d": output_7d,
            "wo_active": wo_active,
            "wo_completed": wo_completed,
            "orders_active": orders_active,
            "qc_pass_7d": qc_pass_qty,
            "qc_fail_7d": qc_fail_qty,
            "qc_rate_pct": round(qc_rate, 1),
        },
        "hr": {
            "employees_active": emp_active,
            "attendance_today": att_summary,
        },
        "finance": {
            "ar_outstanding": round((ar[0] if ar else {}).get("total", 0) or 0),
            "ap_outstanding": round((ap[0] if ap else {}).get("total", 0) or 0),
            "cash_balance": round((cash[0] if cash else {}).get("total", 0) or 0),
        },
        "warehouse": {
            "low_stock_materials": low_count,
        },
    }


@router.get("/management/daily-output")
async def daily_output(request: Request, days: int = 7):
    """
    Output per hari per proses. Phase 13 — accepts date_from/date_to
    to override the days window.
    """
    await require_auth(request)
    db = get_db()
    today = _today()
    sp = request.query_params
    date_from = sp.get("date_from") or None
    date_to = sp.get("date_to") or None
    if date_from and date_to:
        start = date_from
        end = date_to
    else:
        start = (today - timedelta(days=days-1)).isoformat()
        end = today.isoformat()
    rows = await db.rahaza_wip_events.aggregate([
        {"$match": {"event_type": "output", "event_date": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": {"date": "$event_date", "process_code": "$process_code"}, "qty": {"$sum": "$qty"}}},
        {"$sort": {"_id.date": 1}}
    ]).to_list(None)
    # Build timeline per date from [start..end]
    from datetime import datetime as _dt
    try:
        sd = _dt.fromisoformat(start).date()
        ed = _dt.fromisoformat(end).date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Format tanggal tidak valid. Gunakan YYYY-MM-DD.")
    if ed < sd:
        raise HTTPException(status_code=400, detail="date_to tidak boleh lebih awal dari date_from.")
    span = max(1, (ed - sd).days + 1)
    # Batas aman 365 hari untuk performa
    if span > 365:
        raise HTTPException(status_code=400, detail="Rentang maksimal 365 hari.")
    dates = [(sd + timedelta(days=i)).isoformat() for i in range(span)]
    timeline = {d: {"date": d, "total": 0, "by_process": {}} for d in dates}
    for r in rows:
        d = r["_id"]["date"]; p = r["_id"]["process_code"] or "UNK"; qty = r["qty"]
        if d in timeline:
            timeline[d]["total"] += qty
            timeline[d]["by_process"][p] = qty
    return {"days": span, "timeline": list(timeline.values()), "date_from": start, "date_to": end}


@router.get("/management/top-models")
async def top_models(request: Request, days: int = 30, limit: int = 10):
    await require_auth(request)
    db = get_db()
    start = (_today() - timedelta(days=days)).isoformat()
    rows = await db.rahaza_wip_events.aggregate([
        {"$match": {"event_type": "output", "event_date": {"$gte": start}}},
        {"$group": {"_id": "$model_id", "qty": {"$sum": "$qty"}}},
        {"$sort": {"qty": -1}}, {"$limit": limit},
    ]).to_list(None)
    mids = [r["_id"] for r in rows if r.get("_id")]
    models = await db.rahaza_models.find({"id": {"$in": mids}}, {"_id": 0}).to_list(None) if mids else []
    mmap = {m["id"]: m for m in models}
    out = []
    for r in rows:
        m = mmap.get(r["_id"]) or {}
        out.append({"model_id": r["_id"], "code": m.get("code"), "name": m.get("name"), "qty": r["qty"]})
    return {"days": days, "items": out}


@router.get("/management/top-customers")
async def top_customers(request: Request, limit: int = 10):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_orders.aggregate([
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {"_id": "$customer_id", "total_qty": {"$sum": "$total_qty"}, "orders": {"$sum": 1}}},
        {"$sort": {"total_qty": -1}}, {"$limit": limit},
    ]).to_list(None)
    cids = [r["_id"] for r in rows if r.get("_id")]
    cs = await db.rahaza_customers.find({"id": {"$in": cids}}, {"_id": 0}).to_list(None) if cids else []
    cmap = {c["id"]: c for c in cs}
    out = []
    for r in rows:
        c = cmap.get(r["_id"]) or {}
        out.append({"customer_id": r["_id"], "code": c.get("code"), "name": c.get("name"), "orders": r["orders"], "total_qty": r["total_qty"]})
    return {"items": out}


@router.get("/management/on-time-delivery")
async def on_time_delivery(request: Request, days: int = 30):
    await require_auth(request)
    db = get_db()
    start = (_today() - timedelta(days=days)).isoformat()
    rows = await db.rahaza_work_orders.find({"status": "completed", "end_date": {"$gte": start}}, {"_id": 0}).to_list(None)
    total = len(rows); on_time = 0
    for r in rows:
        due = r.get("target_date") or r.get("due_date")
        completed = r.get("end_date") or r.get("completed_at")
        if due and completed and completed <= due:
            on_time += 1
    rate = (on_time / total * 100) if total > 0 else 0
    return {"days": days, "total_wo": total, "on_time": on_time, "rate_pct": round(rate, 1)}


@router.get("/management/payroll-summary")
async def payroll_summary(request: Request):
    await require_auth(request)
    db = get_db()
    latest = await db.rahaza_payroll_runs.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    return {"latest_run": serialize_doc(latest) if latest else None}
