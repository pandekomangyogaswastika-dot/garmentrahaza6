"""
PT Rahaza Global Indonesia — Master Data Rajut

Endpoints (all under /api/rahaza):
  - /locations    : Gedung & Zona
  - /processes    : Proses produksi (seed static, read + toggle)
  - /shifts       : Shift kerja (CRUD)
  - /machines     : Mesin rajut (CRUD)
  - /lines        : Line Produksi (CRUD)
  - /employees    : Karyawan/Operator (CRUD)

Conventions:
  - All documents use UUID string `id`.
  - `active` flag (soft disable).
  - Timestamps in UTC.
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-master"])


def _uid() -> str:
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


# ─── SEED DEFAULTS ───────────────────────────────────────────────────────────
DEFAULT_LOCATIONS = [
    # Gedung utama
    {"code": "GED-A", "name": "Gedung A", "type": "gedung", "parent_id": None},
    {"code": "GED-B", "name": "Gedung B", "type": "gedung", "parent_id": None},
    # Zona produksi & gudang
    {"code": "ZNA-RAJUT",  "name": "Zona Rajut",    "type": "zona", "parent_code": "GED-A"},
    {"code": "ZNA-LINKING","name": "Zona Linking",  "type": "zona", "parent_code": "GED-A"},
    {"code": "ZNA-GDG-A",  "name": "Zona Gudang A", "type": "zona", "parent_code": "GED-A"},
    {"code": "ZNA-GDG-B",  "name": "Zona Gudang B", "type": "zona", "parent_code": "GED-B"},
]

# Proses produksi — urutan sesuai alur rajut PT Rahaza
DEFAULT_PROCESSES = [
    {"code": "RAJUT",   "name": "Rajut",   "order_seq": 1, "is_rework": False, "description": "Proses rajut benang membentuk panel"},
    {"code": "LINKING", "name": "Linking", "order_seq": 2, "is_rework": False, "description": "Penyambungan panel rajut"},
    {"code": "SEWING",  "name": "Sewing",  "order_seq": 3, "is_rework": False, "description": "Jahit, obras, lubang kancing, pasang kancing"},
    {"code": "QC",      "name": "QC",      "order_seq": 4, "is_rework": False, "description": "Quality control"},
    {"code": "STEAM",   "name": "Steam",   "order_seq": 5, "is_rework": False, "description": "Penyetrikaan uap"},
    {"code": "PACKING", "name": "Packing", "order_seq": 6, "is_rework": False, "description": "Pengemasan akhir"},
    {"code": "WASHER",  "name": "Washer",  "order_seq": 10,"is_rework": True,  "description": "Cuci noda (alur rework)"},
    {"code": "SONTEK",  "name": "Sontek",  "order_seq": 11,"is_rework": True,  "description": "Perbaikan manual (alur rework)"},
]

DEFAULT_SHIFTS = [
    {"code": "S1", "name": "Shift 1", "start_time": "07:00", "end_time": "15:00"},
    {"code": "S2", "name": "Shift 2", "start_time": "15:00", "end_time": "23:00"},
]


async def seed_rahaza_master_data():
    """Idempotent seed dipanggil dari server.py startup."""
    db = get_db()

    # Locations (2 Gedung + 4 Zona)
    code_to_id = {}
    for loc in DEFAULT_LOCATIONS:
        existing = await db.rahaza_locations.find_one({"code": loc["code"]})
        if existing:
            code_to_id[loc["code"]] = existing["id"]
            continue
        parent_code = loc.pop("parent_code", None)
        loc_doc = {
            "id": _uid(),
            "code": loc["code"],
            "name": loc["name"],
            "type": loc["type"],
            "parent_id": code_to_id.get(parent_code) if parent_code else loc.get("parent_id"),
            "active": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.rahaza_locations.insert_one(loc_doc)
        code_to_id[loc["code"]] = loc_doc["id"]
    print(f"  · Rahaza locations seeded (total codes: {len(code_to_id)})")

    # Processes (8 total)
    seeded_proc = 0
    for proc in DEFAULT_PROCESSES:
        existing = await db.rahaza_processes.find_one({"code": proc["code"]})
        if existing:
            continue
        await db.rahaza_processes.insert_one({
            "id": _uid(),
            **proc,
            "active": True,
            "created_at": _now(),
            "updated_at": _now(),
        })
        seeded_proc += 1
    if seeded_proc:
        print(f"  · Rahaza processes seeded ({seeded_proc} baru)")

    # Shifts
    seeded_shift = 0
    for sh in DEFAULT_SHIFTS:
        existing = await db.rahaza_shifts.find_one({"code": sh["code"]})
        if existing:
            continue
        await db.rahaza_shifts.insert_one({
            "id": _uid(),
            **sh,
            "active": True,
            "created_at": _now(),
            "updated_at": _now(),
        })
        seeded_shift += 1
    if seeded_shift:
        print(f"  · Rahaza shifts seeded ({seeded_shift} baru)")


# ─── Generic helpers ─────────────────────────────────────────────────────────
async def _require_admin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role not in ("superadmin", "admin"):
        perms = user.get("_permissions") or []
        if "*" not in perms and "prod.master.manage" not in perms:
            raise HTTPException(403, "Forbidden: butuh permission prod.master.manage")
    return user


# ─── LOCATIONS (Gedung & Zona) ───────────────────────────────────────────────
@router.get("/locations")
async def list_locations(request: Request, include_inactive: bool = False):
    await require_auth(request)
    db = get_db()
    q = {} if include_inactive else {"active": True}
    rows = await db.rahaza_locations.find(q, {"_id": 0}).sort([("type", 1), ("name", 1)]).to_list(None)
    # Enrich with parent name
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        if r.get("parent_id"):
            parent = by_id.get(r["parent_id"])
            r["parent_name"] = parent["name"] if parent else None
    return serialize_doc(rows)


@router.post("/locations")
async def create_location(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip()
    type_ = (body.get("type") or "zona").lower()
    if not code or not name:
        raise HTTPException(400, "code & name required")
    if type_ not in ("gedung", "zona"):
        raise HTTPException(400, "type must be 'gedung' or 'zona'")
    if await db.rahaza_locations.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai (aktif). Gunakan kode lain.")
    doc = {
        "id": _uid(),
        "code": code,
        "name": name,
        "type": type_,
        "parent_id": body.get("parent_id") if type_ == "zona" else None,
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.rahaza_locations.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.location", f"{code} {name}")
    return serialize_doc(doc)


@router.put("/locations/{loc_id}")
async def update_location(loc_id: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    if "code" in body:
        body["code"] = body["code"].strip().upper()
    res = await db.rahaza_locations.update_one({"id": loc_id}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.location", loc_id)
    return serialize_doc(await db.rahaza_locations.find_one({"id": loc_id}, {"_id": 0}))


@router.delete("/locations/{loc_id}")
async def deactivate_location(loc_id: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_locations.update_one({"id": loc_id}, {"$set": {"active": False, "updated_at": _now()}})
    await log_activity(user["id"], user.get("name", ""), "deactivate", "rahaza.location", loc_id)
    return {"status": "deactivated"}


# ─── PROCESSES (static, bisa toggle active) ──────────────────────────────────
@router.get("/processes")
async def list_processes(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_processes.find({}, {"_id": 0}).sort("order_seq", 1).to_list(None)
    return serialize_doc(rows)


@router.put("/processes/{pid}")
async def update_process(pid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    allowed = {k: body[k] for k in ("active", "description", "name") if k in body}
    if not allowed:
        return serialize_doc(await db.rahaza_processes.find_one({"id": pid}, {"_id": 0}))
    allowed["updated_at"] = _now()
    await db.rahaza_processes.update_one({"id": pid}, {"$set": allowed})
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.process", pid)
    return serialize_doc(await db.rahaza_processes.find_one({"id": pid}, {"_id": 0}))


# ─── SHIFTS ──────────────────────────────────────────────────────────────────
@router.get("/shifts")
async def list_shifts(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_shifts.find({}, {"_id": 0}).sort("start_time", 1).to_list(None)
    return serialize_doc(rows)


@router.post("/shifts")
async def create_shift(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(400, "code & name required")
    if await db.rahaza_shifts.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai (aktif). Gunakan kode lain.")
    doc = {
        "id": _uid(),
        "code": code,
        "name": name,
        "start_time": body.get("start_time", ""),
        "end_time": body.get("end_time", ""),
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.rahaza_shifts.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.shift", f"{code} {name}")
    return serialize_doc(doc)


@router.put("/shifts/{sid}")
async def update_shift(sid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    if "code" in body:
        body["code"] = body["code"].strip().upper()
    res = await db.rahaza_shifts.update_one({"id": sid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.shift", sid)
    return serialize_doc(await db.rahaza_shifts.find_one({"id": sid}, {"_id": 0}))


@router.delete("/shifts/{sid}")
async def deactivate_shift(sid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_shifts.update_one({"id": sid}, {"$set": {"active": False, "updated_at": _now()}})
    await log_activity(user["id"], user.get("name", ""), "deactivate", "rahaza.shift", sid)
    return {"status": "deactivated"}


# ─── MACHINES (Mesin Rajut) ─────────────────────────────────────────────────
@router.get("/machines")
async def list_machines(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_machines.find({}, {"_id": 0}).sort("code", 1).to_list(None)
    # enrich with location
    loc_ids = [r["location_id"] for r in rows if r.get("location_id")]
    loc_map = {}
    if loc_ids:
        locs = await db.rahaza_locations.find({"id": {"$in": loc_ids}}, {"_id": 0}).to_list(None)
        loc_map = {l["id"]: l["name"] for l in locs}
    for r in rows:
        r["location_name"] = loc_map.get(r.get("location_id"))
    return serialize_doc(rows)


@router.post("/machines")
async def create_machine(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip() or code
    if not code:
        raise HTTPException(400, "code required")
    if await db.rahaza_machines.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai (aktif). Gunakan kode lain.")
    doc = {
        "id": _uid(),
        "code": code,
        "name": name,
        "machine_type": body.get("machine_type") or "Rajut",
        "gauge": body.get("gauge") or "",
        "location_id": body.get("location_id") or None,
        "status": body.get("status") or "idle",  # idle | active | maintenance
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.rahaza_machines.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.machine", code)
    return serialize_doc(doc)


@router.put("/machines/{mid}")
async def update_machine(mid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    if "code" in body:
        body["code"] = body["code"].strip().upper()
    res = await db.rahaza_machines.update_one({"id": mid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.machine", mid)
    return serialize_doc(await db.rahaza_machines.find_one({"id": mid}, {"_id": 0}))


@router.delete("/machines/{mid}")
async def deactivate_machine(mid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_machines.update_one({"id": mid}, {"$set": {"active": False, "updated_at": _now()}})
    await log_activity(user["id"], user.get("name", ""), "deactivate", "rahaza.machine", mid)
    return {"status": "deactivated"}


# ─── LINES (Line Produksi) ───────────────────────────────────────────────────
@router.get("/lines")
async def list_lines(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_lines.find({}, {"_id": 0}).sort("code", 1).to_list(None)
    proc_ids = [r["process_id"] for r in rows if r.get("process_id")]
    loc_ids  = [r["location_id"] for r in rows if r.get("location_id")]
    procs = await db.rahaza_processes.find({"id": {"$in": proc_ids}}, {"_id": 0}).to_list(None) if proc_ids else []
    locs  = await db.rahaza_locations.find({"id": {"$in": loc_ids}}, {"_id": 0}).to_list(None) if loc_ids else []
    proc_map = {p["id"]: p["name"] for p in procs}
    loc_map  = {l["id"]: l["name"] for l in locs}
    for r in rows:
        r["process_name"]  = proc_map.get(r.get("process_id"))
        r["location_name"] = loc_map.get(r.get("location_id"))
    return serialize_doc(rows)


@router.post("/lines")
async def create_line(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip() or code
    if not code:
        raise HTTPException(400, "code required")
    if await db.rahaza_lines.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai (aktif). Gunakan kode lain.")
    doc = {
        "id": _uid(),
        "code": code,
        "name": name,
        "process_id": body.get("process_id") or None,
        "location_id": body.get("location_id") or None,
        "capacity_per_hour": body.get("capacity_per_hour") or 0,
        "notes": body.get("notes") or "",
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.rahaza_lines.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.line", code)
    return serialize_doc(doc)


@router.put("/lines/{lid}")
async def update_line(lid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    if "code" in body:
        body["code"] = body["code"].strip().upper()
    res = await db.rahaza_lines.update_one({"id": lid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.line", lid)
    return serialize_doc(await db.rahaza_lines.find_one({"id": lid}, {"_id": 0}))


@router.delete("/lines/{lid}")
async def deactivate_line(lid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_lines.update_one({"id": lid}, {"$set": {"active": False, "updated_at": _now()}})
    await log_activity(user["id"], user.get("name", ""), "deactivate", "rahaza.line", lid)
    return {"status": "deactivated"}


# ─── EMPLOYEES (Karyawan / Operator) ─────────────────────────────────────────
@router.get("/employees")
async def list_employees(request: Request):
    await require_auth(request)
    db = get_db()
    rows = await db.rahaza_employees.find({}, {"_id": 0}).sort("employee_code", 1).to_list(None)
    loc_ids = [r["location_id"] for r in rows if r.get("location_id")]
    loc_map = {}
    if loc_ids:
        locs = await db.rahaza_locations.find({"id": {"$in": loc_ids}}, {"_id": 0}).to_list(None)
        loc_map = {l["id"]: l["name"] for l in locs}
    for r in rows:
        r["location_name"] = loc_map.get(r.get("location_id"))
    return serialize_doc(rows)


@router.post("/employees")
async def create_employee(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("employee_code") or "").strip().upper()
    name = (body.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(400, "employee_code & name required")
    if await db.rahaza_employees.find_one({"employee_code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai (aktif). Gunakan kode lain.")
    doc = {
        "id": _uid(),
        "employee_code": code,
        "name": name,
        "job_title": body.get("job_title") or "Operator",  # Operator, Supervisor, Linking, Sewing, QC, dsb
        "location_id": body.get("location_id") or None,
        "phone": body.get("phone") or "",
        "wage_scheme": body.get("wage_scheme") or "borongan_pcs",  # borongan_pcs | borongan_jam | mingguan | bulanan
        "base_rate": body.get("base_rate") or 0,
        "joined_at": body.get("joined_at") or _now().isoformat(),
        "active": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.rahaza_employees.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.employee", f"{code} {name}")
    return serialize_doc(doc)


@router.put("/employees/{eid}")
async def update_employee(eid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    if "employee_code" in body:
        body["employee_code"] = body["employee_code"].strip().upper()
    res = await db.rahaza_employees.update_one({"id": eid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.employee", eid)
    return serialize_doc(await db.rahaza_employees.find_one({"id": eid}, {"_id": 0}))


@router.delete("/employees/{eid}")
async def deactivate_employee(eid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    await db.rahaza_employees.update_one({"id": eid}, {"$set": {"active": False, "updated_at": _now()}})
    await log_activity(user["id"], user.get("name", ""), "deactivate", "rahaza.employee", eid)
    return {"status": "deactivated"}
