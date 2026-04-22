"""
PT Rahaza — HPP / Costing (Fase 9)

HPP per Work Order = (material_cost + labor_cost + overhead_cost) / qty_completed
  - material_cost: total biaya material yg di-issue ke WO (dari material_issue confirmed × unit_cost)
                   jika material tidak punya unit_cost, pakai default_yarn_cost_per_kg dari settings
  - labor_cost: alokasi dari payroll pcs yang tag ke WO (via wip_events.work_order_id)
                jika belum ada payroll run, estimasi dari rate × qty
  - overhead_cost: overhead_rate_per_pcs × qty_completed (dari rahaza_costing_settings)

Endpoints (prefix /api/rahaza):
  - GET  /costing-settings
  - PUT  /costing-settings
  - GET  /hpp/work-order/{wo_id}      : compute HPP real-time
  - POST /hpp/work-order/{wo_id}/snapshot : simpan snapshot HPP utk audit
  - GET  /hpp/snapshots               : list snapshots
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-hpp"])

SETTINGS_ID = "GLOBAL"


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


async def _require_fin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin", "owner", "accounting", "finance", "manager"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "finance.manage" in perms or "hpp.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission finance/HPP.")


@router.get("/costing-settings")
async def get_settings(request: Request):
    await require_auth(request)
    db = get_db()
    doc = await db.rahaza_costing_settings.find_one({"id": SETTINGS_ID}, {"_id": 0})
    if not doc:
        doc = {
            "id": SETTINGS_ID,
            "overhead_rate_per_pcs": 0,
            "default_yarn_cost_per_kg": 0,
            "default_accessory_cost_per_unit": 0,
            "labor_rate_fallback_per_pcs": 0,
            "notes": "",
            "updated_at": _now(),
        }
        await db.rahaza_costing_settings.insert_one(doc)
    return serialize_doc(doc)


@router.put("/costing-settings")
async def update_settings(request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    allowed = ["overhead_rate_per_pcs", "default_yarn_cost_per_kg", "default_accessory_cost_per_unit", "labor_rate_fallback_per_pcs", "notes"]
    upd = {k: body[k] for k in allowed if k in body}
    for k in ("overhead_rate_per_pcs", "default_yarn_cost_per_kg", "default_accessory_cost_per_unit", "labor_rate_fallback_per_pcs"):
        if k in upd:
            upd[k] = float(upd[k] or 0)
    upd["updated_at"] = _now()
    upd["updated_by"] = user["id"]
    await db.rahaza_costing_settings.update_one({"id": SETTINGS_ID}, {"$set": upd}, upsert=True)
    out = await db.rahaza_costing_settings.find_one({"id": SETTINGS_ID}, {"_id": 0})
    return serialize_doc(out)


async def _compute_hpp(db, wo_id: str):
    wo = await db.rahaza_work_orders.find_one({"id": wo_id}, {"_id": 0})
    if not wo:
        raise HTTPException(404, "Work order tidak ditemukan.")
    settings = await db.rahaza_costing_settings.find_one({"id": SETTINGS_ID}, {"_id": 0}) or {}
    default_yarn = float(settings.get("default_yarn_cost_per_kg") or 0)
    default_acc = float(settings.get("default_accessory_cost_per_unit") or 0)
    overhead_rate = float(settings.get("overhead_rate_per_pcs") or 0)
    labor_fallback = float(settings.get("labor_rate_fallback_per_pcs") or 0)

    # ── 1) Material cost from confirmed material_issues for this WO
    mi_rows = await db.rahaza_material_issues.find({"work_order_id": wo_id, "status": "issued"}, {"_id": 0}).to_list(None)
    material_cost = 0
    material_breakdown = []
    for mi in mi_rows:
        for item in (mi.get("items") or []):
            mat = await db.rahaza_materials.find_one({"id": item.get("material_id")}, {"_id": 0}) or {}
            unit_cost = float(mat.get("unit_cost") or 0)
            if unit_cost <= 0:
                unit_cost = default_yarn if (mat.get("type") == "yarn") else default_acc
            qty = float(item.get("qty_issued") or item.get("qty_required") or 0)
            amount = qty * unit_cost
            material_cost += amount
            material_breakdown.append({
                "material_id": item.get("material_id"), "material_name": mat.get("name") or item.get("material_name"),
                "type": mat.get("type") or item.get("type"),
                "qty": qty, "unit": item.get("unit") or mat.get("unit"),
                "unit_cost": unit_cost, "amount": round(amount),
            })

    # ── 2) Labor cost: sum of output events × rate for this WO
    wip = await db.rahaza_wip_events.find({"work_order_id": wo_id, "event_type": "output"}, {"_id": 0}).to_list(None)
    total_output = sum(int(e.get("qty") or 0) for e in wip)
    labor_cost = 0
    labor_breakdown = []
    # Group by operator → get their rate
    op_qty = {}
    for ev in wip:
        op_id = ev.get("operator_id")
        if not op_id: continue
        if op_id not in op_qty:
            op_qty[op_id] = {"qty": 0, "process_code": ev.get("process_code"), "process_id": ev.get("process_id")}
        op_qty[op_id]["qty"] += int(ev.get("qty") or 0)
    for op_id, info in op_qty.items():
        emp = await db.rahaza_employees.find_one({"id": op_id}, {"_id": 0}) or {}
        profile = await db.rahaza_payroll_profiles.find_one({"employee_id": op_id, "active": True}, {"_id": 0})
        rate = 0
        if profile and profile.get("pay_scheme") == "pcs":
            overrides = {r["process_id"]: r["rate"] for r in (profile.get("pcs_process_rates") or [])}
            rate = float(overrides.get(info["process_id"], profile.get("base_rate") or 0))
        if rate <= 0:
            rate = labor_fallback
        amount = info["qty"] * rate
        labor_cost += amount
        labor_breakdown.append({
            "operator_id": op_id, "operator_name": emp.get("name"),
            "process_code": info["process_code"], "qty": info["qty"], "rate": rate, "amount": round(amount),
        })

    # ── 3) Overhead: overhead_rate × qty_completed (completed = output di proses final, simplifikasi pakai qty order)
    qty_completed = int(wo.get("qty_completed") or 0) or int(wo.get("qty") or 0)
    overhead_cost = qty_completed * overhead_rate

    total_cost = material_cost + labor_cost + overhead_cost
    hpp_unit = total_cost / qty_completed if qty_completed > 0 else 0

    return {
        "work_order_id": wo_id,
        "wo_number": wo.get("wo_number"),
        "model_code": wo.get("model_code"),
        "size_code": wo.get("size_code"),
        "qty": wo.get("qty"),
        "qty_completed": qty_completed,
        "total_output_events": total_output,
        "material_cost": round(material_cost),
        "labor_cost": round(labor_cost),
        "overhead_cost": round(overhead_cost),
        "total_cost": round(total_cost),
        "hpp_unit": round(hpp_unit),
        "material_breakdown": material_breakdown,
        "labor_breakdown": labor_breakdown,
        "overhead_rate_per_pcs": overhead_rate,
        "computed_at": _now().isoformat(),
    }


@router.get("/hpp/work-order/{wo_id}")
async def hpp_for_wo(wo_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    return serialize_doc(await _compute_hpp(db, wo_id))


@router.post("/hpp/work-order/{wo_id}/snapshot")
async def snapshot_hpp(wo_id: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    data = await _compute_hpp(db, wo_id)
    data["id"] = _uid()
    data["created_at"] = _now()
    data["created_by"] = user["id"]
    data["created_by_name"] = user.get("name", "")
    await db.rahaza_hpp_snapshots.update_one({"work_order_id": wo_id}, {"$set": data}, upsert=True)
    return serialize_doc(data)


@router.get("/hpp/snapshots")
async def list_snapshots(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_hpp_snapshots.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    return serialize_doc(rows)
