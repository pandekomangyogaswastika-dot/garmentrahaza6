"""
PT Rahaza — Bill of Materials (Fase 5b)

Endpoints (prefix /api/rahaza):
  - GET    /boms                       : List BOMs (filter by model_id)
  - GET    /boms/{id}                  : BOM detail
  - GET    /models/{model_id}/bom      : All BOMs for model (all sizes)
  - POST   /boms                       : Create/upsert BOM for (model, size)
  - PUT    /boms/{id}                  : Update BOM
  - DELETE /boms/{id}                  : Soft-delete
  - POST   /boms/{id}/copy-to-sizes    : Copy this BOM to other sizes (same model)

Schema (rahaza_boms):
  {
    id, model_id, size_id,
    yarn_materials:     [{name, code, yarn_type, qty_kg, notes}],
    accessory_materials: [{name, code, qty, unit, notes}],
    total_yarn_kg_per_pcs: <auto>,
    notes, active, created_at, updated_at
  }
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-bom"])


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


async def _require_admin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "prod.master.manage" in perms or "bom.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission BOM / prod.master.")


def _clean_yarns(raw):
    cleaned = []
    for y in raw or []:
        name = (y.get("name") or "").strip()
        qty  = float(y.get("qty_kg") or 0)
        if not name or qty <= 0:
            continue
        cleaned.append({
            "name": name,
            "code": (y.get("code") or "").strip().upper(),
            "yarn_type": (y.get("yarn_type") or "").strip(),
            "qty_kg": round(qty, 4),
            "notes": y.get("notes") or "",
        })
    return cleaned


def _clean_accessories(raw):
    cleaned = []
    for a in raw or []:
        name = (a.get("name") or "").strip()
        qty  = float(a.get("qty") or 0)
        if not name or qty <= 0:
            continue
        cleaned.append({
            "name": name,
            "code": (a.get("code") or "").strip().upper(),
            "qty": round(qty, 3),
            "unit": (a.get("unit") or "pcs").strip(),
            "notes": a.get("notes") or "",
        })
    return cleaned


async def _enrich_bom(db, bom):
    if not bom:
        return bom
    mod = await db.rahaza_models.find_one({"id": bom.get("model_id")}, {"_id": 0})
    sz  = await db.rahaza_sizes.find_one({"id": bom.get("size_id")},  {"_id": 0})
    bom["model_code"] = mod["code"] if mod else None
    bom["model_name"] = mod["name"] if mod else None
    bom["size_code"]  = sz["code"]  if sz else None
    bom["size_name"]  = sz["name"]  if sz else None
    # Totals
    bom["total_yarn_kg_per_pcs"] = round(sum(float(y.get("qty_kg") or 0) for y in (bom.get("yarn_materials") or [])), 4)
    bom["yarn_count"]      = len(bom.get("yarn_materials") or [])
    bom["accessory_count"] = len(bom.get("accessory_materials") or [])
    return bom


@router.get("/boms")
async def list_boms(request: Request, model_id: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {"active": True}
    if model_id:
        q["model_id"] = model_id
    rows = await db.rahaza_boms.find(q, {"_id": 0}).sort("updated_at", -1).to_list(None)
    for r in rows:
        await _enrich_bom(db, r)
    return serialize_doc(rows)


@router.get("/boms/{bid}")
async def get_bom(bid: str, request: Request):
    await require_auth(request)
    db = get_db()
    bom = await db.rahaza_boms.find_one({"id": bid}, {"_id": 0})
    if not bom:
        raise HTTPException(404, "BOM tidak ditemukan")
    await _enrich_bom(db, bom)
    return serialize_doc(bom)


@router.get("/models/{model_id}/bom")
async def get_model_bom(model_id: str, request: Request):
    """Return BOM summary for all sizes of a given model (matrix view)."""
    await require_auth(request)
    db = get_db()
    model = await db.rahaza_models.find_one({"id": model_id}, {"_id": 0})
    if not model:
        raise HTTPException(404, "Model tidak ditemukan")
    sizes = await db.rahaza_sizes.find({"active": True}, {"_id": 0}).sort("order_seq", 1).to_list(None)
    boms = await db.rahaza_boms.find({"model_id": model_id, "active": True}, {"_id": 0}).to_list(None)
    bom_by_size = {b["size_id"]: b for b in boms}
    matrix = []
    for s in sizes:
        b = bom_by_size.get(s["id"])
        matrix.append({
            "size_id": s["id"],
            "size_code": s["code"],
            "size_name": s["name"],
            "size_order_seq": s.get("order_seq", 0),
            "bom_id": b["id"] if b else None,
            "total_yarn_kg_per_pcs": round(sum(float(y.get("qty_kg") or 0) for y in (b.get("yarn_materials") or [])), 4) if b else 0,
            "yarn_count":      len(b.get("yarn_materials") or []) if b else 0,
            "accessory_count": len(b.get("accessory_materials") or []) if b else 0,
            "notes":           b.get("notes", "") if b else "",
        })
    return {
        "model": {"id": model["id"], "code": model["code"], "name": model["name"]},
        "matrix": matrix,
    }


@router.post("/boms")
async def create_bom(request: Request):
    user = await _require_admin(request)
    db = get_db()
    body = await request.json()
    model_id = body.get("model_id")
    size_id  = body.get("size_id")
    if not (model_id and size_id):
        raise HTTPException(400, "model_id & size_id wajib diisi.")
    # Ensure model + size exist
    if not await db.rahaza_models.find_one({"id": model_id}):
        raise HTTPException(404, "Model tidak ditemukan")
    if not await db.rahaza_sizes.find_one({"id": size_id}):
        raise HTTPException(404, "Size tidak ditemukan")
    # Prevent duplicate active BOM for (model, size)
    dup = await db.rahaza_boms.find_one({"model_id": model_id, "size_id": size_id, "active": True})
    if dup:
        raise HTTPException(409, "BOM untuk model & size ini sudah ada. Gunakan edit.")
    yarns = _clean_yarns(body.get("yarn_materials"))
    accs  = _clean_accessories(body.get("accessory_materials"))
    if not yarns and not accs:
        raise HTTPException(400, "BOM harus berisi minimal 1 benang atau 1 aksesoris.")
    doc = {
        "id": _uid(),
        "model_id": model_id,
        "size_id": size_id,
        "yarn_materials": yarns,
        "accessory_materials": accs,
        "notes": body.get("notes") or "",
        "active": True,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.rahaza_boms.insert_one(doc)
    await log_activity(user["id"], user.get("name", ""), "create", "rahaza.bom", doc["id"])
    await _enrich_bom(db, doc)
    return serialize_doc(doc)


@router.put("/boms/{bid}")
async def update_bom(bid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    bom = await db.rahaza_boms.find_one({"id": bid})
    if not bom:
        raise HTTPException(404, "BOM tidak ditemukan")
    body = await request.json()
    upd = {"updated_at": _now()}
    if "yarn_materials" in body:
        upd["yarn_materials"] = _clean_yarns(body["yarn_materials"])
    if "accessory_materials" in body:
        upd["accessory_materials"] = _clean_accessories(body["accessory_materials"])
    if "notes" in body:
        upd["notes"] = body.get("notes") or ""
    # Validate after update that BOM still has at least one material
    final_yarns = upd.get("yarn_materials", bom.get("yarn_materials") or [])
    final_accs  = upd.get("accessory_materials", bom.get("accessory_materials") or [])
    if not final_yarns and not final_accs:
        raise HTTPException(400, "BOM harus berisi minimal 1 benang atau 1 aksesoris.")
    await db.rahaza_boms.update_one({"id": bid}, {"$set": upd})
    out = await db.rahaza_boms.find_one({"id": bid}, {"_id": 0})
    await _enrich_bom(db, out)
    await log_activity(user["id"], user.get("name", ""), "update", "rahaza.bom", bid)
    return serialize_doc(out)


@router.delete("/boms/{bid}")
async def delete_bom(bid: str, request: Request):
    user = await _require_admin(request)
    db = get_db()
    res = await db.rahaza_boms.update_one({"id": bid}, {"$set": {"active": False, "updated_at": _now()}})
    if res.matched_count == 0:
        raise HTTPException(404, "BOM tidak ditemukan")
    await log_activity(user["id"], user.get("name", ""), "deactivate", "rahaza.bom", bid)
    return {"status": "deactivated"}


@router.post("/boms/{bid}/copy-to-sizes")
async def copy_bom_to_sizes(bid: str, request: Request):
    """
    Copy BOM (materials) from source BOM to target_size_ids of the same model.
    Body: { target_size_ids: [..], overwrite: bool }
    """
    user = await _require_admin(request)
    db = get_db()
    src = await db.rahaza_boms.find_one({"id": bid, "active": True}, {"_id": 0})
    if not src:
        raise HTTPException(404, "BOM sumber tidak ditemukan")
    body = await request.json()
    target_size_ids = body.get("target_size_ids") or []
    overwrite = bool(body.get("overwrite"))
    if not target_size_ids:
        raise HTTPException(400, "target_size_ids wajib diisi.")

    created, skipped, overwritten = [], [], []
    for sid in target_size_ids:
        if sid == src["size_id"]:
            skipped.append({"size_id": sid, "reason": "sama dengan sumber"})
            continue
        existing = await db.rahaza_boms.find_one({"model_id": src["model_id"], "size_id": sid, "active": True}, {"_id": 0})
        payload = {
            "yarn_materials": src.get("yarn_materials") or [],
            "accessory_materials": src.get("accessory_materials") or [],
            "notes": src.get("notes") or "",
            "updated_at": _now(),
        }
        if existing:
            if not overwrite:
                skipped.append({"size_id": sid, "reason": "sudah ada BOM aktif (pakai overwrite=true)"})
                continue
            await db.rahaza_boms.update_one({"id": existing["id"]}, {"$set": payload})
            overwritten.append(sid)
        else:
            doc = {
                "id": _uid(),
                "model_id": src["model_id"],
                "size_id": sid,
                **payload,
                "active": True,
                "created_at": _now(),
            }
            await db.rahaza_boms.insert_one(doc)
            created.append(sid)
    await log_activity(user["id"], user.get("name", ""), "copy", "rahaza.bom", bid)
    return {"created": created, "overwritten": overwritten, "skipped": skipped}
