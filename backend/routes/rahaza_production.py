"""
PT Rahaza Global Indonesia — Production Execution (Fase 4+)

Endpoints (all under /api/rahaza):
  - /models             : Model produk (Sweater V-Neck, dsb)  [CRUD]
  - /sizes              : Size (S/M/L/XL)                     [CRUD]
  - /line-assignments   : Assign operator+shift+target ke Line [CRUD]
  - /wip/events         : WIP event ledger (POST to record; GET to query)
  - /wip/summary        : Aggregated WIP per proses (computed)

WIP semantics (MVP):
  - Event type 'output' = operator line menghasilkan X pcs pada proses P
  - WIP di proses P = Σ output(P) − Σ output(next_of_P)
  - Urutan proses ditentukan oleh field `order_seq` pada rahaza_processes
  - Proses rework (is_rework=True) diperlakukan sebagai side-stream untuk
    perhitungan lanjut (akan diperluas di Fase 6).
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
from datetime import datetime, timezone, date
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-production"])


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


# ── Seed defaults for sizes ─────────────────────────────────────────────────
DEFAULT_SIZES = [
    {"code": "S",   "name": "S",   "order_seq": 1},
    {"code": "M",   "name": "M",   "order_seq": 2},
    {"code": "L",   "name": "L",   "order_seq": 3},
    {"code": "XL",  "name": "XL",  "order_seq": 4},
    {"code": "XXL", "name": "XXL", "order_seq": 5},
]


async def seed_rahaza_production_data():
    db = get_db()
    seeded_size = 0
    for s in DEFAULT_SIZES:
        existing = await db.rahaza_sizes.find_one({"code": s["code"]})
        if existing:
            continue
        await db.rahaza_sizes.insert_one({
            "id": _uid(), **s, "active": True,
            "created_at": _now(), "updated_at": _now(),
        })
        seeded_size += 1
    if seeded_size:
        print(f"  · Rahaza sizes seeded ({seeded_size} baru)")


async def _require_admin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "prod.master.manage" in perms or "prod.line.manage" in perms or "prod.process.input" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission produksi")


# ── MODELS (Model Produk) ───────────────────────────────────────────────────
@router.get("/models")
async def list_models(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_models.find({}, {"_id": 0}).sort("code", 1).to_list(None)
    return serialize_doc(rows)


@router.post("/models")
async def create_model(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(400, "code & name required")
    if await db.rahaza_models.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai (aktif). Gunakan kode lain.")
    doc = {
        "id": _uid(),
        "code": code,
        "name": name,
        "category": body.get("category") or "Sweater",
        "yarn_kg_per_pcs": float(body.get("yarn_kg_per_pcs") or 0),
        "bundle_size": int(body.get("bundle_size") or 30),  # Phase 17A: default 30 pcs per bundle
        "description": body.get("description") or "",
        "active": True,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.rahaza_models.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.model", code)
    return serialize_doc(doc)


@router.put("/models/{mid}")
async def update_model(mid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    if "code" in body:
        body["code"] = body["code"].strip().upper()
    # Phase 17A: sanitize bundle_size
    if "bundle_size" in body:
        try:
            body["bundle_size"] = max(1, int(body["bundle_size"]))
        except (TypeError, ValueError):
            body.pop("bundle_size")
    res = await db.rahaza_models.update_one({"id": mid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.model", mid)
    return serialize_doc(await db.rahaza_models.find_one({"id": mid}, {"_id": 0}))


@router.delete("/models/{mid}")
async def deactivate_model(mid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_models.update_one({"id": mid}, {"$set": {"active": False, "updated_at": _now()}})
    await log_activity(user["id"], user.get("name", ""), "deactivate", "rahaza.model", mid)
    return {"status": "deactivated"}


# ── SIZES ────────────────────────────────────────────────────────────────────
@router.get("/sizes")
async def list_sizes(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_sizes.find({}, {"_id": 0}).sort("order_seq", 1).to_list(None)
    return serialize_doc(rows)


@router.post("/sizes")
async def create_size(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip() or code
    if not code:
        raise HTTPException(400, "code required")
    if await db.rahaza_sizes.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai (aktif). Gunakan kode lain.")
    doc = {
        "id": _uid(),
        "code": code,
        "name": name,
        "order_seq": int(body.get("order_seq") or 0),
        "active": True,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.rahaza_sizes.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.size", code)
    return serialize_doc(doc)


@router.put("/sizes/{sid}")
async def update_size(sid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    if "code" in body:
        body["code"] = body["code"].strip().upper()
    res = await db.rahaza_sizes.update_one({"id": sid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    return serialize_doc(await db.rahaza_sizes.find_one({"id": sid}, {"_id": 0}))


@router.delete("/sizes/{sid}")
async def deactivate_size(sid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_sizes.update_one({"id": sid}, {"$set": {"active": False, "updated_at": _now()}})
    return {"status": "deactivated"}


# ── LINE ASSIGNMENTS ────────────────────────────────────────────────────────
@router.get("/line-assignments")
async def list_assignments(request: Request, line_id: Optional[str] = None, assign_date: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if line_id: q["line_id"] = line_id
    if assign_date: q["assign_date"] = assign_date  # YYYY-MM-DD
    rows = await db.rahaza_line_assignments.find(q, {"_id": 0}).sort([("assign_date", -1), ("line_id", 1)]).to_list(None)
    # Enrich with joined names
    line_ids = list({r["line_id"] for r in rows if r.get("line_id")})
    emp_ids  = list({r["operator_id"] for r in rows if r.get("operator_id")})
    shift_ids= list({r["shift_id"] for r in rows if r.get("shift_id")})
    model_ids= list({r["model_id"] for r in rows if r.get("model_id")})
    size_ids = list({r["size_id"] for r in rows if r.get("size_id")})

    async def _name_map(col, ids, id_field="id", name_field="name"):
        if not ids: return {}
        docs = await db[col].find({id_field: {"$in": ids}}, {"_id": 0}).to_list(None)
        return {d[id_field]: d.get(name_field) for d in docs}

    ln_map    = await _name_map("rahaza_lines", line_ids)
    emp_map   = await _name_map("rahaza_employees", emp_ids)
    sh_map    = await _name_map("rahaza_shifts", shift_ids)
    mod_map   = await _name_map("rahaza_models", model_ids)
    sz_map    = await _name_map("rahaza_sizes", size_ids)

    for r in rows:
        r["line_name"]     = ln_map.get(r.get("line_id"))
        r["operator_name"] = emp_map.get(r.get("operator_id"))
        r["shift_name"]    = sh_map.get(r.get("shift_id"))
        r["model_name"]    = mod_map.get(r.get("model_id"))
        r["size_name"]     = sz_map.get(r.get("size_id"))
    return serialize_doc(rows)


@router.post("/line-assignments")
async def create_assignment(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    line_id = body.get("line_id")
    if not line_id:
        raise HTTPException(400, "line_id required")
    assign_date = body.get("assign_date") or date.today().isoformat()
    # Check collision on line+date+shift
    existing = await db.rahaza_line_assignments.find_one({
        "line_id": line_id, "assign_date": assign_date,
        "shift_id": body.get("shift_id"), "active": True,
    })
    if existing:
        raise HTTPException(409, f"Line sudah di-assign untuk tanggal & shift tersebut.")
    doc = {
        "id": _uid(),
        "line_id": line_id,
        "operator_id": body.get("operator_id") or None,
        "shift_id": body.get("shift_id") or None,
        "model_id": body.get("model_id") or None,
        "size_id":  body.get("size_id") or None,
        "target_qty": int(body.get("target_qty") or 0),
        "assign_date": assign_date,
        "notes": body.get("notes") or "",
        "active": True,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.rahaza_line_assignments.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.line_assignment", doc["id"])
    return serialize_doc(doc)


@router.put("/line-assignments/{aid}")
async def update_assignment(aid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    res = await db.rahaza_line_assignments.update_one({"id": aid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    return serialize_doc(await db.rahaza_line_assignments.find_one({"id": aid}, {"_id": 0}))


@router.delete("/line-assignments/{aid}")
async def deactivate_assignment(aid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_line_assignments.update_one({"id": aid}, {"$set": {"active": False, "updated_at": _now()}})
    return {"status": "deactivated"}


# ── WIP EVENTS ──────────────────────────────────────────────────────────────
@router.post("/wip/events")
async def record_wip_event(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    line_id = body.get("line_id")
    process_id = body.get("process_id")
    qty = int(body.get("qty") or 0)
    if not (line_id and process_id and qty > 0):
        raise HTTPException(400, "line_id, process_id, qty(>0) required")

    # Look up context
    line = await db.rahaza_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(404, "Line not found")

    event = {
        "id": _uid(),
        "timestamp": _now(),
        "line_id": line_id,
        "process_id": process_id,
        "location_id": line.get("location_id"),
        "model_id": body.get("model_id") or None,
        "size_id": body.get("size_id") or None,
        "line_assignment_id": body.get("line_assignment_id") or None,
        "work_order_id": body.get("work_order_id") or None,
        "event_type": body.get("event_type") or "output",
        "qty": qty,
        "notes": body.get("notes") or "",
        "created_by": user["id"],
        "created_by_name": user.get("name", ""),
    }
    await db.rahaza_wip_events.insert_one(event)
    return serialize_doc(event)


@router.get("/wip/events")
async def list_wip_events(request: Request, line_id: Optional[str] = None, process_id: Optional[str] = None, limit: int = 100):
    await require_auth(request)
    db = get_db()
    q = {}
    if line_id: q["line_id"] = line_id
    if process_id: q["process_id"] = process_id
    rows = await db.rahaza_wip_events.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(None)
    return serialize_doc(rows)


@router.get("/wip/summary")
async def wip_summary(request: Request):
    """
    Return WIP per proses: qty yang masih berada di proses tsb.
    WIP at process P = Σ output(P) − Σ output(next_of_P)
    """
    await require_auth(request)
    db = get_db()

    processes = await db.rahaza_processes.find(
        {"active": True, "is_rework": False}, {"_id": 0}
    ).sort("order_seq", 1).to_list(None)

    # Aggregate total output per process (event_type=output)
    pipeline = [
        {"$match": {"event_type": "output"}},
        {"$group": {"_id": "$process_id", "total": {"$sum": "$qty"}}},
    ]
    raw = await db.rahaza_wip_events.aggregate(pipeline).to_list(None)
    total_by_proc = {r["_id"]: r["total"] for r in raw}

    # WIP = output(P) - output(P+1) ; for last process WIP = output(P)
    summary = []
    for idx, p in enumerate(processes):
        out_p = total_by_proc.get(p["id"], 0)
        out_next = 0
        if idx + 1 < len(processes):
            out_next = total_by_proc.get(processes[idx + 1]["id"], 0)
        wip = max(0, out_p - out_next)
        summary.append({
            "process_id": p["id"],
            "process_code": p["code"],
            "process_name": p["name"],
            "order_seq": p["order_seq"],
            "total_output": out_p,
            "wip_qty": wip,
        })
    return {"processes": summary, "updated_at": _now().isoformat()}


@router.get("/line-board")
async def line_board(request: Request, assign_date: Optional[str] = None):
    """
    Line Board per proses (non-rework) untuk tanggal tertentu (default hari ini).
    Struktur: { process: [{line, assignment, output_today, target}] }
    """
    await require_auth(request)
    db = get_db()
    today = assign_date or date.today().isoformat()

    lines = await db.rahaza_lines.find({"active": True}, {"_id": 0}).to_list(None)
    procs = await db.rahaza_processes.find({"active": True, "is_rework": False}, {"_id": 0}).sort("order_seq", 1).to_list(None)
    assignments = await db.rahaza_line_assignments.find({"assign_date": today, "active": True}, {"_id": 0}).to_list(None)

    # Enrich helper
    async def _name_map(col, ids, id_field="id"):
        if not ids: return {}
        docs = await db[col].find({id_field: {"$in": list(ids)}}, {"_id": 0}).to_list(None)
        return {d[id_field]: d for d in docs}

    emp_map = await _name_map("rahaza_employees", {a.get("operator_id") for a in assignments if a.get("operator_id")})
    sh_map  = await _name_map("rahaza_shifts",    {a.get("shift_id") for a in assignments if a.get("shift_id")})
    mod_map = await _name_map("rahaza_models",    {a.get("model_id") for a in assignments if a.get("model_id")})
    sz_map  = await _name_map("rahaza_sizes",     {a.get("size_id") for a in assignments if a.get("size_id")})
    loc_map = await _name_map("rahaza_locations", {l.get("location_id") for l in lines if l.get("location_id")})

    # Output today per line (event_type=output)
    start = datetime.combine(date.fromisoformat(today), datetime.min.time()).replace(tzinfo=timezone.utc)
    end   = datetime.combine(date.fromisoformat(today), datetime.max.time()).replace(tzinfo=timezone.utc)
    pipe = [
        {"$match": {"event_type": "output", "timestamp": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": "$line_id", "total": {"$sum": "$qty"}}},
    ]
    out_agg = await db.rahaza_wip_events.aggregate(pipe).to_list(None)
    out_today = {r["_id"]: r["total"] for r in out_agg}

    # Group lines by process
    by_proc = {p["id"]: [] for p in procs}
    assign_by_line = {}
    for a in assignments:
        assign_by_line.setdefault(a["line_id"], []).append(a)

    for ln in lines:
        pid = ln.get("process_id")
        if pid not in by_proc:
            continue
        loc = loc_map.get(ln.get("location_id"))
        line_assigns = []
        for a in assign_by_line.get(ln["id"], []):
            op  = emp_map.get(a.get("operator_id"))
            sh  = sh_map.get(a.get("shift_id"))
            mod = mod_map.get(a.get("model_id"))
            sz  = sz_map.get(a.get("size_id"))
            line_assigns.append({
                "id": a["id"],
                "operator_id": a.get("operator_id"),
                "operator_name": op.get("name") if op else None,
                "shift_id": a.get("shift_id"),
                "shift_name": sh.get("name") if sh else None,
                "model_id": a.get("model_id"),
                "model_name": mod.get("name") if mod else None,
                "size_id": a.get("size_id"),
                "size_code": sz.get("code") if sz else None,
                "target_qty": a.get("target_qty") or 0,
            })
        by_proc[pid].append({
            "line_id": ln["id"],
            "line_code": ln["code"],
            "line_name": ln["name"],
            "location_id": ln.get("location_id"),
            "location_name": loc.get("name") if loc else None,
            "capacity_per_hour": ln.get("capacity_per_hour") or 0,
            "output_today": out_today.get(ln["id"], 0),
            "assignments": line_assigns,
        })

    board = []
    for p in procs:
        board.append({
            "process_id": p["id"],
            "process_code": p["code"],
            "process_name": p["name"],
            "order_seq": p["order_seq"],
            "lines": by_proc[p["id"]],
        })
    return {"date": today, "board": board}
