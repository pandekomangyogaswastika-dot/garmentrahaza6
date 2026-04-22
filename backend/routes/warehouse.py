"""
Warehouse Management Routes
Domain: Warehouse Locations, Stock Control, Receiving, Stock Movements
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, check_role, log_activity, serialize_doc
from routes.shared import check_portal_access
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/warehouse", tags=["warehouse"])


# ─── HELPERS ─────────────────────────────────────────────────────────────────
def new_id():
    return str(uuid.uuid4())

def now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
# WAREHOUSE LOCATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/locations")
async def list_locations(request: Request):
    user = await require_auth(request)
    db = get_db()
    locations = await db.warehouse_locations.find({}, {"_id": 0}).sort("name", 1).to_list(None)
    return serialize_doc(locations)


@router.post("/locations")
async def create_location(request: Request):
    user = await require_auth(request)
    if not check_role(user, ["superadmin", "admin"]):
        raise HTTPException(403, "Not authorized")
    body = await request.json()
    
    loc = {
        "id": new_id(),
        "code": body.get("code", "").strip().upper(),
        "name": body.get("name", "").strip(),
        "type": body.get("type", "warehouse"),  # warehouse, zone, bin
        "parent_id": body.get("parent_id"),
        "zone": body.get("zone", ""),
        "rack": body.get("rack", ""),
        "shelf": body.get("shelf", ""),
        "bin_code": body.get("bin_code", ""),
        "capacity": body.get("capacity", 0),
        "status": "active",
        "created_at": now(),
        "updated_at": now(),
    }
    
    if not loc["code"] or not loc["name"]:
        raise HTTPException(400, "Code and name are required")
    
    db = get_db()
    # Check for duplicate code
    existing = await db.warehouse_locations.find_one({"code": loc["code"]})
    if existing:
        raise HTTPException(400, f"Location code '{loc['code']}' already exists")
    
    await db.warehouse_locations.insert_one(loc)
    await log_activity(user["id"], user["name"], "create", "warehouse_location", f"Created location {loc['code']} - {loc['name']}")
    return serialize_doc(loc)


@router.put("/locations/{location_id}")
async def update_location(location_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ["superadmin", "admin"]):
        raise HTTPException(403, "Not authorized")
    
    db = get_db()
    existing = await db.warehouse_locations.find_one({"id": location_id})
    if not existing:
        raise HTTPException(404, "Location not found")
    
    body = await request.json()
    updates = {
        "name": body.get("name", existing["name"]),
        "type": body.get("type", existing["type"]),
        "zone": body.get("zone", existing.get("zone", "")),
        "rack": body.get("rack", existing.get("rack", "")),
        "shelf": body.get("shelf", existing.get("shelf", "")),
        "bin_code": body.get("bin_code", existing.get("bin_code", "")),
        "capacity": body.get("capacity", existing.get("capacity", 0)),
        "status": body.get("status", existing.get("status", "active")),
        "updated_at": now(),
    }
    
    await db.warehouse_locations.update_one({"id": location_id}, {"$set": updates})
    await log_activity(user["id"], user["name"], "update", "warehouse_location", f"Updated location {existing['code']}")
    return {**serialize_doc(existing), **updates}


@router.delete("/locations/{location_id}")
async def delete_location(location_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ["superadmin", "admin"]):
        raise HTTPException(403, "Not authorized")
    
    db = get_db()
    loc = await db.warehouse_locations.find_one({"id": location_id})
    if not loc:
        raise HTTPException(404, "Location not found")
    
    # Check if stock exists at this location
    stock_count = await db.warehouse_stock.count_documents({"location_id": location_id, "quantity": {"$gt": 0}})
    if stock_count > 0:
        raise HTTPException(400, "Cannot delete location with existing stock")
    
    await db.warehouse_locations.delete_one({"id": location_id})
    await log_activity(user["id"], user["name"], "delete", "warehouse_location", f"Deleted location {loc['code']}")
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# RECEIVING (GOODS RECEIPT)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/receiving")
async def list_receiving(request: Request):
    user = await require_auth(request)
    db = get_db()
    receipts = await db.warehouse_receiving.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    return serialize_doc(receipts)


@router.post("/receiving")
async def create_receiving(request: Request):
    user = await require_auth(request)
    body = await request.json()
    db = get_db()
    
    # Generate receipt number
    count = await db.warehouse_receiving.count_documents({})
    receipt_number = f"GR-{count + 1:05d}"
    
    receipt = {
        "id": new_id(),
        "receipt_number": receipt_number,
        "source_type": body.get("source_type", "supplier"),  # supplier, production, transfer
        "source_ref": body.get("source_ref", ""),  # PO number or reference
        "supplier_name": body.get("supplier_name", ""),
        "location_id": body.get("location_id", ""),
        "location_name": body.get("location_name", ""),
        "status": "draft",  # draft, inspecting, passed, failed, partial, received
        "items": [],
        "notes": body.get("notes", ""),
        "received_by": user["name"],
        "received_by_id": user["id"],
        "created_at": now(),
        "updated_at": now(),
    }
    
    # Process items
    for item in body.get("items", []):
        receipt_item = {
            "id": new_id(),
            "product_name": item.get("product_name", ""),
            "sku": item.get("sku", ""),
            "expected_qty": item.get("expected_qty", 0),
            "received_qty": item.get("received_qty", 0),
            "rejected_qty": item.get("rejected_qty", 0),
            "unit": item.get("unit", "pcs"),
            "inspection_status": "pending",  # pending, passed, failed
            "inspection_notes": "",
        }
        receipt["items"].append(receipt_item)
    
    await db.warehouse_receiving.insert_one(receipt)
    await log_activity(user["id"], user["name"], "create", "warehouse_receiving", f"Created goods receipt {receipt_number}")
    return serialize_doc(receipt)


@router.put("/receiving/{receipt_id}")
async def update_receiving(receipt_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    
    existing = await db.warehouse_receiving.find_one({"id": receipt_id})
    if not existing:
        raise HTTPException(404, "Receipt not found")
    
    body = await request.json()
    updates = {}
    
    if "status" in body:
        updates["status"] = body["status"]
    if "items" in body:
        updates["items"] = body["items"]
    if "notes" in body:
        updates["notes"] = body["notes"]
    
    updates["updated_at"] = now()
    
    # If status changed to "received", update stock
    if body.get("status") == "received" and existing.get("status") != "received":
        for item in (body.get("items") or existing.get("items", [])):
            received_qty = item.get("received_qty", 0) - item.get("rejected_qty", 0)
            if received_qty > 0:
                # Upsert stock at location
                stock_key = {
                    "location_id": existing.get("location_id", ""),
                    "sku": item.get("sku", ""),
                    "product_name": item.get("product_name", ""),
                }
                existing_stock = await db.warehouse_stock.find_one(stock_key)
                if existing_stock:
                    await db.warehouse_stock.update_one(
                        {"id": existing_stock["id"]},
                        {"$inc": {"quantity": received_qty, "total_received": received_qty}, "$set": {"updated_at": now()}}
                    )
                else:
                    await db.warehouse_stock.insert_one({
                        **stock_key,
                        "id": new_id(),
                        "quantity": received_qty,
                        "reserved": 0,
                        "available": received_qty,
                        "total_received": received_qty,
                        "unit": item.get("unit", "pcs"),
                        "created_at": now(),
                        "updated_at": now(),
                    })
                
                # Record stock movement
                await db.warehouse_movements.insert_one({
                    "id": new_id(),
                    "type": "receive",
                    "receipt_id": receipt_id,
                    "receipt_number": existing.get("receipt_number", ""),
                    "location_id": existing.get("location_id", ""),
                    "location_name": existing.get("location_name", ""),
                    "sku": item.get("sku", ""),
                    "product_name": item.get("product_name", ""),
                    "quantity": received_qty,
                    "unit": item.get("unit", "pcs"),
                    "performed_by": user["name"],
                    "performed_by_id": user["id"],
                    "notes": f"Goods receipt {existing.get('receipt_number', '')}",
                    "created_at": now(),
                })
    
    await db.warehouse_receiving.update_one({"id": receipt_id}, {"$set": updates})
    await log_activity(user["id"], user["name"], "update", "warehouse_receiving", 
                       f"Updated receipt {existing.get('receipt_number', '')} status to {body.get('status', 'updated')}")
    
    updated = await db.warehouse_receiving.find_one({"id": receipt_id}, {"_id": 0})
    return serialize_doc(updated)


@router.delete("/receiving/{receipt_id}")
async def delete_receiving(receipt_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ["superadmin", "admin"]):
        raise HTTPException(403, "Not authorized")
    
    db = get_db()
    receipt = await db.warehouse_receiving.find_one({"id": receipt_id})
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    if receipt.get("status") == "received":
        raise HTTPException(400, "Cannot delete already received goods receipt")
    
    await db.warehouse_receiving.delete_one({"id": receipt_id})
    await log_activity(user["id"], user["name"], "delete", "warehouse_receiving", f"Deleted receipt {receipt.get('receipt_number', '')}")
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK CONTROL
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/stock")
async def list_stock(request: Request):
    user = await require_auth(request)
    db = get_db()
    
    location_id = request.query_params.get("location_id")
    query = {}
    if location_id:
        query["location_id"] = location_id
    
    stock = await db.warehouse_stock.find(query, {"_id": 0}).sort("product_name", 1).to_list(None)
    return serialize_doc(stock)


@router.get("/stock/summary")
async def stock_summary(request: Request):
    user = await require_auth(request)
    db = get_db()
    
    pipeline = [
        {"$group": {
            "_id": {"sku": "$sku", "product_name": "$product_name"},
            "total_quantity": {"$sum": "$quantity"},
            "total_reserved": {"$sum": "$reserved"},
            "total_available": {"$sum": "$available"},
            "locations_count": {"$sum": 1},
        }},
        {"$sort": {"_id.product_name": 1}},
    ]
    
    results = await db.warehouse_stock.aggregate(pipeline).to_list(None)
    summary = [{
        "sku": r["_id"]["sku"],
        "product_name": r["_id"]["product_name"],
        "total_quantity": r["total_quantity"],
        "total_reserved": r["total_reserved"],
        "total_available": r["total_available"],
        "locations_count": r["locations_count"],
    } for r in results]
    
    total_skus = len(summary)
    total_qty = sum(s["total_quantity"] for s in summary)
    total_locations = await db.warehouse_locations.count_documents({"status": "active"})
    
    return {
        "items": summary,
        "total_skus": total_skus,
        "total_quantity": total_qty,
        "total_locations": total_locations,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK MOVEMENTS LOG
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/movements")
async def list_movements(request: Request):
    user = await require_auth(request)
    db = get_db()
    
    limit = int(request.query_params.get("limit", "50"))
    movements = await db.warehouse_movements.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return serialize_doc(movements)


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD METRICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def warehouse_dashboard(request: Request):
    user = await require_auth(request)
    if not check_portal_access(user, "warehouse"):
        raise HTTPException(403, "No access to warehouse portal")
    db = get_db()
    
    total_locations = await db.warehouse_locations.count_documents({"status": "active"})
    total_receipts = await db.warehouse_receiving.count_documents({})
    pending_receipts = await db.warehouse_receiving.count_documents({"status": {"$in": ["draft", "inspecting"]}})
    
    # Stock summary
    stock_pipeline = [
        {"$group": {
            "_id": None,
            "total_skus": {"$addToSet": "$sku"},
            "total_quantity": {"$sum": "$quantity"},
        }}
    ]
    stock_agg = await db.warehouse_stock.aggregate(stock_pipeline).to_list(1)
    stock_info = stock_agg[0] if stock_agg else {"total_skus": [], "total_quantity": 0}
    
    # Recent movements
    recent_movements = await db.warehouse_movements.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    
    return {
        "total_locations": total_locations,
        "total_receipts": total_receipts,
        "pending_receipts": pending_receipts,
        "total_skus": len(stock_info.get("total_skus", [])),
        "total_stock_qty": stock_info.get("total_quantity", 0),
        "recent_movements": serialize_doc(recent_movements),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PUT-AWAY (Assign stock to bin locations)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/putaway")
async def create_putaway(request: Request):
    """Move stock from a holding area to a specific bin location."""
    user = await require_auth(request)
    body = await request.json()
    db = get_db()
    
    source_stock_id = body.get("stock_id")
    target_location_id = body.get("target_location_id")
    qty = int(body.get("qty", 0))
    
    if not source_stock_id or not target_location_id or qty <= 0:
        raise HTTPException(400, "stock_id, target_location_id, and qty > 0 required")
    
    source = await db.warehouse_stock.find_one({"id": source_stock_id})
    if not source:
        raise HTTPException(404, "Source stock not found")
    if source.get("quantity", 0) < qty:
        raise HTTPException(400, f"Insufficient stock. Available: {source.get('quantity', 0)}")
    
    target_loc = await db.warehouse_locations.find_one({"id": target_location_id})
    if not target_loc:
        raise HTTPException(404, "Target location not found")
    
    # Decrease source
    await db.warehouse_stock.update_one(
        {"id": source_stock_id},
        {"$inc": {"quantity": -qty, "available": -qty}, "$set": {"updated_at": now()}}
    )
    
    # Upsert target
    target_key = {"location_id": target_location_id, "sku": source.get("sku", ""), "product_name": source.get("product_name", "")}
    existing_target = await db.warehouse_stock.find_one(target_key)
    if existing_target:
        await db.warehouse_stock.update_one(
            {"id": existing_target["id"]},
            {"$inc": {"quantity": qty, "available": qty}, "$set": {"updated_at": now()}}
        )
    else:
        await db.warehouse_stock.insert_one({
            **target_key,
            "id": new_id(), "quantity": qty, "reserved": 0, "available": qty,
            "total_received": 0, "unit": source.get("unit", "pcs"),
            "created_at": now(), "updated_at": now(),
        })
    
    # Record movement
    await db.warehouse_movements.insert_one({
        "id": new_id(), "type": "putaway",
        "location_id": target_location_id,
        "location_name": target_loc.get("name", ""),
        "sku": source.get("sku", ""), "product_name": source.get("product_name", ""),
        "quantity": qty, "unit": source.get("unit", "pcs"),
        "performed_by": user["name"], "performed_by_id": user["id"],
        "notes": f"Put-away to {target_loc.get('code', '')} - {target_loc.get('name', '')}",
        "created_at": now(),
    })
    
    await log_activity(user["id"], user["name"], "putaway", "warehouse",
                       f"Put-away {qty} {source.get('sku', '')} to {target_loc.get('code', '')}")
    return {"success": True, "moved_qty": qty, "target_location": target_loc.get("code", "")}


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK OPNAME (Cycle Count)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/opname")
async def list_opname(request: Request):
    user = await require_auth(request)
    db = get_db()
    opnames = await db.warehouse_opname.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    return serialize_doc(opnames)

@router.post("/opname")
async def create_opname(request: Request):
    """Create a stock opname (cycle count) session."""
    user = await require_auth(request)
    body = await request.json()
    db = get_db()
    
    count = await db.warehouse_opname.count_documents({})
    
    # Get current stock for the location
    location_id = body.get("location_id", "")
    query = {"location_id": location_id} if location_id else {}
    current_stock = await db.warehouse_stock.find(query, {"_id": 0}).to_list(None)
    
    items = []
    for s in current_stock:
        items.append({
            "id": new_id(),
            "stock_id": s.get("id", ""),
            "sku": s.get("sku", ""),
            "product_name": s.get("product_name", ""),
            "system_qty": s.get("quantity", 0),
            "physical_qty": None,  # To be filled during count
            "discrepancy": 0,
            "notes": "",
        })
    
    # Also allow manually added items from body
    for item in body.get("items", []):
        items.append({
            "id": new_id(),
            "stock_id": item.get("stock_id", ""),
            "sku": item.get("sku", ""),
            "product_name": item.get("product_name", ""),
            "system_qty": item.get("system_qty", 0),
            "physical_qty": item.get("physical_qty"),
            "discrepancy": 0,
            "notes": item.get("notes", ""),
        })
    
    opname = {
        "id": new_id(),
        "opname_number": f"OP-{count + 1:05d}",
        "location_id": location_id,
        "location_name": body.get("location_name", ""),
        "status": "counting",  # counting, review, approved, adjusted
        "items": items,
        "counted_by": user["name"],
        "approved_by": None,
        "approval_date": None,
        "created_at": now(),
        "updated_at": now(),
    }
    
    await db.warehouse_opname.insert_one(opname)
    await log_activity(user["id"], user["name"], "create", "warehouse_opname", f"Created opname {opname['opname_number']}")
    return serialize_doc(opname)

@router.put("/opname/{opname_id}")
async def update_opname(opname_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    existing = await db.warehouse_opname.find_one({"id": opname_id})
    if not existing:
        raise HTTPException(404, "Opname not found")
    
    body = await request.json()
    updates = {}
    
    if "items" in body:
        items = body["items"]
        for item in items:
            phys = item.get("physical_qty")
            sys_qty = item.get("system_qty", 0)
            if phys is not None:
                item["discrepancy"] = int(phys) - int(sys_qty)
        updates["items"] = items
    
    if "status" in body:
        updates["status"] = body["status"]
        if body["status"] == "approved":
            updates["approved_by"] = user["name"]
            updates["approval_date"] = now()
        
        # If approved → adjust stock
        if body["status"] == "adjusted":
            for item in (body.get("items") or existing.get("items", [])):
                if item.get("physical_qty") is not None and item.get("discrepancy", 0) != 0:
                    stock_id = item.get("stock_id")
                    if stock_id:
                        await db.warehouse_stock.update_one(
                            {"id": stock_id},
                            {"$set": {"quantity": int(item["physical_qty"]), "available": int(item["physical_qty"]), "updated_at": now()}}
                        )
                        # Record adjustment movement
                        await db.warehouse_movements.insert_one({
                            "id": new_id(), "type": "adjustment",
                            "location_id": existing.get("location_id", ""),
                            "location_name": existing.get("location_name", ""),
                            "sku": item.get("sku", ""), "product_name": item.get("product_name", ""),
                            "quantity": item.get("discrepancy", 0),
                            "unit": "pcs",
                            "performed_by": user["name"], "performed_by_id": user["id"],
                            "notes": f"Stock opname adjustment {existing.get('opname_number', '')}",
                            "created_at": now(),
                        })
    
    updates["updated_at"] = now()
    await db.warehouse_opname.update_one({"id": opname_id}, {"$set": updates})
    await log_activity(user["id"], user["name"], "update", "warehouse_opname",
                       f"Updated opname {existing.get('opname_number', '')} -> {body.get('status', 'updated')}")
    return serialize_doc(await db.warehouse_opname.find_one({"id": opname_id}, {"_id": 0}))
