"""
PT Rahaza — Work Orders (Fase 5c)

Endpoints (prefix /api/rahaza):
  - GET    /work-orders                         : List (filters: status, order_id, model_id)
  - GET    /work-orders/{wid}                   : Detail + progress
  - POST   /work-orders                         : Create manually
  - PUT    /work-orders/{wid}                   : Edit (draft only)
  - POST   /work-orders/{wid}/status            : Status transition
  - DELETE /work-orders/{wid}                   : Delete (draft/cancelled only)
  - POST   /orders/{oid}/generate-work-orders   : Auto-generate WO for all eligible items
                                                  (body optional: { item_ids: [..], priority, target_start_date, target_end_date })

Schema (rahaza_work_orders):
  {
    id, wo_number, order_id, order_number_snapshot,
    order_item_id, model_id, size_id, qty,
    customer_snapshot, is_internal,
    priority,   # normal | high | urgent
    target_start_date, target_end_date,
    bom_snapshot: { yarn_materials, accessory_materials, total_yarn_kg_per_pcs },
    total_yarn_kg_required,
    status,      # draft | released | in_production | completed | cancelled
    completed_qty, # derived from WIP events of final process
    notes, created_at, updated_at, released_at, started_at, completed_at, cancelled_at,
    created_by, created_by_name,
  }
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
from routes.rahaza_audit import log_audit
import uuid
from datetime import datetime, timezone, date
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-work-orders"])


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


WO_STATUSES = ["draft", "released", "in_production", "completed", "cancelled"]
WO_TRANSITIONS = {
    "draft":          ["released", "cancelled"],
    "released":       ["in_production", "cancelled"],
    "in_production":  ["completed", "cancelled"],
    "completed":      [],
    "cancelled":      [],
}


async def _require_admin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "wo.manage" in perms or "order.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission Work Order / Order.")


async def _gen_wo_number(db):
    today = date.today().strftime("%Y%m%d")
    prefix = f"WO-{today}"
    count = await db.rahaza_work_orders.count_documents({"wo_number": {"$regex": f"^{prefix}"}})
    return f"{prefix}-{count+1:03d}"


async def _get_bom_snapshot(db, model_id: str, size_id: str):
    """Return frozen BOM snapshot for WO, or None if no BOM."""
    bom = await db.rahaza_boms.find_one({"model_id": model_id, "size_id": size_id, "active": True}, {"_id": 0})
    if not bom:
        return None
    yarns = bom.get("yarn_materials") or []
    accs  = bom.get("accessory_materials") or []
    total = round(sum(float(y.get("qty_kg") or 0) for y in yarns), 4)
    return {
        "bom_id": bom["id"],
        "yarn_materials": yarns,
        "accessory_materials": accs,
        "total_yarn_kg_per_pcs": total,
    }


async def _compute_progress(db, wo: dict):
    """
    Compute completed_qty: sum of WIP events (event_type='output') on the *last*
    non-rework process for this work_order_id.
    Also returns per-process breakdown.
    """
    wo_id = wo["id"]
    procs = await db.rahaza_processes.find({"active": True, "is_rework": False}, {"_id": 0}).sort("order_seq", 1).to_list(None)
    if not procs:
        return 0, []
    last_proc = procs[-1]
    pipe_all = [
        {"$match": {"event_type": "output", "work_order_id": wo_id}},
        {"$group": {"_id": "$process_id", "total": {"$sum": "$qty"}}},
    ]
    raw = await db.rahaza_wip_events.aggregate(pipe_all).to_list(None)
    by_proc = {r["_id"]: r["total"] for r in raw}
    breakdown = [
        {"process_id": p["id"], "process_code": p["code"], "process_name": p["name"],
         "order_seq": p["order_seq"], "total_output": by_proc.get(p["id"], 0)}
        for p in procs
    ]
    completed = by_proc.get(last_proc["id"], 0)
    return completed, breakdown


async def _enrich_wo(db, wo: dict, with_progress: bool = False):
    if not wo:
        return wo
    mod = await db.rahaza_models.find_one({"id": wo.get("model_id")}, {"_id": 0})
    sz  = await db.rahaza_sizes.find_one({"id": wo.get("size_id")},  {"_id": 0})
    wo["model_code"] = mod["code"] if mod else None
    wo["model_name"] = mod["name"] if mod else None
    wo["size_code"]  = sz["code"]  if sz else None
    qty = int(wo.get("qty") or 0)
    snap = wo.get("bom_snapshot") or {}
    yarn_per_pcs = float(snap.get("total_yarn_kg_per_pcs") or 0)
    wo["total_yarn_kg_required"] = round(qty * yarn_per_pcs, 4)
    # Phase 17A: bundle count for this WO
    try:
        bc = await db.rahaza_bundles.count_documents({"work_order_id": wo["id"]})
        wo["bundle_count"] = bc
        wo["bundles_generated"] = bc > 0
    except Exception:
        wo["bundle_count"] = 0
        wo["bundles_generated"] = False
    if with_progress:
        completed, breakdown = await _compute_progress(db, wo)
        wo["completed_qty"] = completed
        wo["progress_pct"] = round((completed / qty) * 100, 1) if qty > 0 else 0
        wo["progress_breakdown"] = breakdown
    return wo


# ── LIST / DETAIL ──────────────────────────────────────────────
@router.get("/work-orders")
async def list_work_orders(
    request: Request,
    status: Optional[str] = None,
    order_id: Optional[str] = None,
    model_id: Optional[str] = None,
):
    await require_auth(request)
    db = get_db()
    q = {}
    if status:   q["status"]   = status
    if order_id: q["order_id"] = order_id
    if model_id: q["model_id"] = model_id
    rows = await db.rahaza_work_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(None)
    for wo in rows:
        await _enrich_wo(db, wo, with_progress=False)
    # Batch progress for list
    wo_ids = [w["id"] for w in rows]
    if wo_ids:
        procs = await db.rahaza_processes.find({"active": True, "is_rework": False}, {"_id": 0}).sort("order_seq", 1).to_list(None)
        last_pid = procs[-1]["id"] if procs else None
        if last_pid:
            pipe = [
                {"$match": {"event_type": "output", "work_order_id": {"$in": wo_ids}, "process_id": last_pid}},
                {"$group": {"_id": "$work_order_id", "total": {"$sum": "$qty"}}},
            ]
            done_raw = await db.rahaza_wip_events.aggregate(pipe).to_list(None)
            done_map = {r["_id"]: r["total"] for r in done_raw}
            for w in rows:
                q_  = int(w.get("qty") or 0)
                c_  = int(done_map.get(w["id"], 0))
                w["completed_qty"] = c_
                w["progress_pct"]  = round((c_ / q_) * 100, 1) if q_ > 0 else 0
    return serialize_doc(rows)


@router.get("/work-orders/{wid}")
async def get_work_order(wid: str, request: Request):
    await require_auth(request)
    db = get_db()
    wo = await db.rahaza_work_orders.find_one({"id": wid}, {"_id": 0})
    if not wo:
        raise HTTPException(404, "Work Order tidak ditemukan")
    await _enrich_wo(db, wo, with_progress=True)
    return serialize_doc(wo)


# ── CREATE (manual) ───────────────────────────────────────────
@router.post("/work-orders")
async def create_wo(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    order_id = body.get("order_id") or None
    model_id = body.get("model_id")
    size_id  = body.get("size_id")
    qty      = int(body.get("qty") or 0)
    if not (model_id and size_id and qty > 0):
        raise HTTPException(400, "model_id, size_id, qty(>0) wajib diisi.")
    # Validate model & size
    if not await db.rahaza_models.find_one({"id": model_id}):
        raise HTTPException(404, "Model tidak ditemukan")
    if not await db.rahaza_sizes.find_one({"id": size_id}):
        raise HTTPException(404, "Size tidak ditemukan")
    order_number_snapshot = ""
    order_item_id = body.get("order_item_id") or None
    customer_snapshot = ""
    is_internal = False
    if order_id:
        order = await db.rahaza_orders.find_one({"id": order_id}, {"_id": 0})
        if not order:
            raise HTTPException(404, "Order tidak ditemukan")
        order_number_snapshot = order.get("order_number", "")
        customer_snapshot = order.get("customer_name_snapshot") or ""
        is_internal = bool(order.get("is_internal"))
    # BOM snapshot (optional — allow WO without BOM, will warn in UI)
    bom_snap = await _get_bom_snapshot(db, model_id, size_id)
    doc = {
        "id": _uid(),
        "wo_number": await _gen_wo_number(db),
        "order_id": order_id,
        "order_number_snapshot": order_number_snapshot,
        "order_item_id": order_item_id,
        "model_id": model_id,
        "size_id":  size_id,
        "qty": qty,
        "customer_snapshot": customer_snapshot,
        "is_internal": is_internal,
        "priority": (body.get("priority") or "normal").lower(),
        "target_start_date": body.get("target_start_date") or None,
        "target_end_date":   body.get("target_end_date") or None,
        "bom_snapshot": bom_snap,
        "status": "draft",
        "notes": body.get("notes") or "",
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
        "created_at": _now(), "updated_at": _now(),
    }
    await db.rahaza_work_orders.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.wo", doc["wo_number"])
    await log_audit(db, entity_type="rahaza_work_order", entity_id=doc["id"], action="create",
                    before=None, after={k: v for k, v in doc.items() if k != "_id"},
                    user=user, request=request)
    await _enrich_wo(db, doc, with_progress=False)
    doc["completed_qty"] = 0; doc["progress_pct"] = 0
    return serialize_doc(doc)


@router.put("/work-orders/{wid}")
async def update_wo(wid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    wo = await db.rahaza_work_orders.find_one({"id": wid}, {"_id": 0})
    if not wo:
        raise HTTPException(404, "Work Order tidak ditemukan")
    if wo.get("status") != "draft":
        raise HTTPException(400, f"WO status '{wo.get('status')}' tidak bisa diedit.")
    body = await request.json()
    allowed = {}
    for k in ("qty", "priority", "target_start_date", "target_end_date", "notes"):
        if k in body: allowed[k] = body[k]
    if "qty" in allowed:
        try:
            allowed["qty"] = int(allowed["qty"])
        except Exception:
            raise HTTPException(400, "qty harus angka.")
        if allowed["qty"] <= 0:
            raise HTTPException(400, "qty harus > 0.")
    allowed["updated_at"] = _now()
    await db.rahaza_work_orders.update_one({"id": wid}, {"$set": allowed})
    out = await db.rahaza_work_orders.find_one({"id": wid}, {"_id": 0})
    await _enrich_wo(db, out, with_progress=True)
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.wo", wid)
    return serialize_doc(out)


@router.post("/work-orders/{wid}/status")
async def transition_wo(wid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    new_status = (body.get("status") or "").lower()
    if new_status not in WO_STATUSES:
        raise HTTPException(400, f"Status tidak valid. Pilih: {', '.join(WO_STATUSES)}")
    wo = await db.rahaza_work_orders.find_one({"id": wid}, {"_id": 0})
    if not wo:
        raise HTTPException(404, "WO tidak ditemukan")
    current = wo.get("status", "draft")
    if new_status not in WO_TRANSITIONS.get(current, []):
        raise HTTPException(400, f"Tidak bisa pindah dari '{current}' ke '{new_status}'. Valid: {WO_TRANSITIONS.get(current, [])}")
    upd = {"status": new_status, "updated_at": _now()}
    if new_status == "released":      upd["released_at"]  = _now()
    if new_status == "in_production": upd["started_at"]   = _now()
    if new_status == "completed":     upd["completed_at"] = _now()
    if new_status == "cancelled":     upd["cancelled_at"] = _now()
    await db.rahaza_work_orders.update_one({"id": wid}, {"$set": upd})
    # Sync parent order: if first WO enters in_production, move order to in_production too
    if new_status == "in_production" and wo.get("order_id"):
        order = await db.rahaza_orders.find_one({"id": wo["order_id"]}, {"_id": 0})
        if order and order.get("status") == "confirmed":
            await db.rahaza_orders.update_one(
                {"id": wo["order_id"]},
                {"$set": {"status": "in_production", "in_production_at": _now(), "updated_at": _now()}},
            )
    await log_activity(user["id"], user.get("name", ""), f"status:{new_status}", "rahaza.wo", wid)
    await log_audit(db, entity_type="rahaza_work_order", entity_id=wid, action="status_change",
                    before={"status": current}, after={"status": new_status},
                    user=user, request=request)
    return {"status": new_status, "work_order_id": wid}


@router.delete("/work-orders/{wid}")
async def delete_wo(wid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    wo = await db.rahaza_work_orders.find_one({"id": wid}, {"_id": 0})
    if not wo:
        raise HTTPException(404, "WO tidak ditemukan")
    if wo.get("status") not in ("draft", "cancelled"):
        raise HTTPException(400, "Hanya WO Draft atau Cancelled yang bisa dihapus.")
    await db.rahaza_work_orders.delete_one({"id": wid})
    await log_activity(user["id"], user.get("name", ""), "delete", "rahaza.wo", wid)
    return {"status": "deleted"}


# ── AUTO GENERATE FROM ORDER ─────────────────────────────────────
@router.post("/orders/{oid}/generate-work-orders")
async def generate_work_orders(oid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    order = await db.rahaza_orders.find_one({"id": oid}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order tidak ditemukan")
    if order.get("status") in ("cancelled", "closed"):
        raise HTTPException(400, f"Order status '{order.get('status')}' tidak bisa generate WO.")
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    requested_item_ids = body.get("item_ids") or []
    priority = (body.get("priority") or "normal").lower()
    target_start_date = body.get("target_start_date") or None
    target_end_date   = body.get("target_end_date") or order.get("due_date") or None

    items = order.get("items") or []
    if requested_item_ids:
        items = [i for i in items if i.get("id") in requested_item_ids]
    if not items:
        raise HTTPException(400, "Tidak ada item untuk di-generate.")

    # Skip items that already have a non-cancelled WO
    existing_wos = await db.rahaza_work_orders.find(
        {"order_id": oid, "status": {"$ne": "cancelled"}}, {"_id": 0, "order_item_id": 1}
    ).to_list(None)
    taken_item_ids = {w.get("order_item_id") for w in existing_wos if w.get("order_item_id")}

    created = []
    skipped = []
    for it in items:
        if it.get("id") in taken_item_ids:
            skipped.append({"item_id": it.get("id"), "reason": "sudah punya WO aktif"})
            continue
        bom_snap = await _get_bom_snapshot(db, it["model_id"], it["size_id"])
        doc = {
            "id": _uid(),
            "wo_number": await _gen_wo_number(db),
            "order_id": oid,
            "order_number_snapshot": order.get("order_number", ""),
            "order_item_id": it.get("id"),
            "model_id": it["model_id"],
            "size_id":  it["size_id"],
            "qty":      int(it["qty"]),
            "customer_snapshot": order.get("customer_name_snapshot") or "",
            "is_internal": bool(order.get("is_internal")),
            "priority": priority,
            "target_start_date": target_start_date,
            "target_end_date":   target_end_date,
            "bom_snapshot": bom_snap,
            "status": "draft",
            "notes": it.get("notes") or "",
            "created_by": user["id"],
            "created_by_name": user.get("name", ""),
            "created_at": _now(), "updated_at": _now(),
        }
        await db.rahaza_work_orders.insert_one(doc)
        created.append({"id": doc["id"], "wo_number": doc["wo_number"], "item_id": it.get("id")})

    # Auto-confirm order if it was draft and we just created WOs
    if created and order.get("status") == "draft":
        await db.rahaza_orders.update_one(
            {"id": oid},
            {"$set": {"status": "confirmed", "confirmed_at": _now(), "updated_at": _now()}},
        )

    await log_activity(user["id"], user.get("name", ""), f"generate:{len(created)}", "rahaza.wo", oid)
    return {"created": created, "skipped": skipped, "total_created": len(created)}


# ── STATUS HELPERS ──────────────────────────────────────────────
@router.get("/work-orders-statuses")
async def get_wo_statuses(request: Request):
    await require_auth(request)
    labels = {
        "draft":         "Draft",
        "released":      "Released",
        "in_production": "In Production",
        "completed":     "Completed",
        "cancelled":     "Cancelled",
    }
    return [{"value": s, "label": labels[s], "allowed_next": WO_TRANSITIONS[s]} for s in WO_STATUSES]
