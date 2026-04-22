"""
Production PO, PO Items, PO Status, PO Accessories
Extracted from server.py monolith.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from database import get_db
from auth import (verify_token, require_auth, check_role, hash_password, verify_password,
                  create_token, log_activity, serialize_doc, generate_password)
from routes.shared import new_id, now, parse_date, to_end_of_day, PO_STATUSES, enrich_with_product_photos
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["production_po"])

from cascade_delete import cascade_delete_po

async def enrich_with_product_photos(items, db):
    """Add product photo_url to items that have a product_name."""
    if not items: return items
    product_cache = {}
    for item in items:
        pname = item.get('product_name', '')
        if pname and pname not in product_cache:
            prod = await db.products.find_one({'product_name': pname}, {'_id': 0, 'photo_url': 1})
            product_cache[pname] = (prod or {}).get('photo_url', '')
        if pname:
            item['product_photo'] = product_cache.get(pname, '')
    return items


# ─── PRODUCTION POs ──────────────────────────────────────────────────────────
@router.get("/production-pos")
async def get_pos(request: Request):
    user = await require_auth(request)
    db = get_db()
    sp = request.query_params
    query = {}
    search = sp.get('search'); status = sp.get('status')
    if search: query['$or'] = [{'po_number': {'$regex': search, '$options': 'i'}}, {'customer_name': {'$regex': search, '$options': 'i'}}]
    if status: query['status'] = status
    pos = await db.production_pos.find(query, {'_id': 0}).sort('created_at', -1).to_list(None)
    result = []
    for po in pos:
        items = await db.po_items.find({'po_id': po['id']}, {'_id': 0}).to_list(None)
        serial_numbers = list(set(i.get('serial_number', '') for i in items if i.get('serial_number')))
        created = po.get('created_at')
        date_str = ''
        if created:
            if isinstance(created, datetime):
                date_str = created.strftime('%d/%m/%Y')
            else:
                date_str = str(created)[:10]
        composite_label = f"{po.get('po_number', '')} | {po.get('vendor_name', '')} | {date_str}"
        po_accessories = await db.po_accessories.find({'po_id': po['id']}, {'_id': 0}).to_list(None)
        
        # Calculate remaining qty to ship to buyer (total_ordered - total_shipped_to_buyer)
        total_ordered = sum(i.get('qty', 0) for i in items)
        total_shipped = 0
        for item in items:
            buyer_items = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
            total_shipped += sum(bi.get('qty_shipped', 0) for bi in buyer_items)
        remaining_qty_to_ship = total_ordered - total_shipped
        
        result.append({**serialize_doc(po), 'items': serialize_doc(items), 'item_count': len(items),
                       'total_qty': total_ordered,
                       'total_shipped_to_buyer': total_shipped,
                       'remaining_qty_to_ship': remaining_qty_to_ship,
                       'serial_numbers': serial_numbers, 'composite_label': composite_label,
                       'po_accessories': serialize_doc(po_accessories),
                       'po_accessories_count': len(po_accessories)})
    return result

@router.get("/production-pos/{po_id}")
async def get_po(po_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    po = await db.production_pos.find_one({'id': po_id}, {'_id': 0})
    if not po: raise HTTPException(404, 'Not found')
    items = await db.po_items.find({'po_id': po_id}, {'_id': 0}).to_list(None)
    wos = await db.work_orders.find({'po_id': po_id}, {'_id': 0}).to_list(None)
    po_accessories = await db.po_accessories.find({'po_id': po_id}, {'_id': 0}).sort('created_at', 1).to_list(None)
    items = await enrich_with_product_photos(items, db)
    result = serialize_doc(po)
    result['items'] = serialize_doc(items)
    result['distributions'] = serialize_doc(wos)
    result['po_accessories'] = serialize_doc(po_accessories)
    return result

@router.post("/production-pos")
async def create_po(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    if not body.get('po_number'): raise HTTPException(400, 'Nomor PO wajib diisi')
    vendor_name = ''
    if body.get('vendor_id'):
        vendor_doc = await db.garments.find_one({'id': body['vendor_id']})
        vendor_name = vendor_doc.get('garment_name', '') if vendor_doc else ''
    po_id = new_id()
    initial_status = 'Confirmed' if body.get('status') == 'Confirmed' else 'Draft'
    # Resolve buyer name from buyer_id if provided
    customer_name = body.get('customer_name', '')
    buyer_id = body.get('buyer_id')
    if buyer_id:
        buyer_doc = await db.buyers.find_one({'id': buyer_id})
        if buyer_doc:
            customer_name = buyer_doc.get('buyer_name', customer_name)
    po = {
        'id': po_id, 'po_number': body['po_number'], 'customer_name': customer_name,
        'buyer_id': buyer_id,
        'vendor_id': body.get('vendor_id'), 'vendor_name': vendor_name,
        'po_date': parse_date(body.get('po_date')) or now(),
        'deadline': parse_date(body.get('deadline')),
        'delivery_deadline': parse_date(body.get('delivery_deadline')),
        'status': initial_status, 'notes': body.get('notes', ''),
        'created_by': user['name'], 'created_at': now(), 'updated_at': now()
    }
    await db.production_pos.insert_one(po)
    items_data = body.get('items', [])
    inserted_items = []
    for item in items_data:
        variant = await db.product_variants.find_one({'id': item.get('variant_id')}) if item.get('variant_id') else None
        product = await db.products.find_one({'id': item.get('product_id')}) if item.get('product_id') else None
        po_item = {
            'id': new_id(), 'po_id': po_id, 'po_number': body['po_number'],
            'product_id': item.get('product_id'), 'product_name': (product or {}).get('product_name', ''),
            'variant_id': item.get('variant_id'), 'size': (variant or {}).get('size', item.get('size', '')),
            'color': (variant or {}).get('color', item.get('color', '')),
            'sku': (variant or {}).get('sku', item.get('sku', '')),
            'qty': int(item.get('qty', 0) or 0), 'serial_number': item.get('serial_number', ''),
            'selling_price_snapshot': float(item.get('selling_price_snapshot', 0) or (product or {}).get('selling_price', 0) or 0),
            'cmt_price_snapshot': float(item.get('cmt_price_snapshot', 0) or (product or {}).get('cmt_price', 0) or 0),
            'created_at': now()
        }
        await db.po_items.insert_one(po_item)
        inserted_items.append(po_item)
    await log_activity(user['id'], user['name'], 'Create', 'Production PO', f"Created PO: {po['po_number']} with {len(items_data)} items")
    result = serialize_doc(po)
    result['items'] = serialize_doc(inserted_items)
    return JSONResponse(result, status_code=201)

@router.post("/production-pos/{po_id}/close")
async def close_po(po_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    po = await db.production_pos.find_one({'id': po_id})
    if not po: raise HTTPException(404, 'PO not found')
    await db.production_pos.update_one({'id': po_id}, {'$set': {
        'status': 'Closed', 'close_reason': body.get('close_reason'),
        'close_notes': body.get('close_notes', ''), 'closed_by': user['name'],
        'closed_at': now(), 'updated_at': now()
    }})
    await log_activity(user['id'], user['name'], 'Close PO', 'Production PO', f"Closed PO: {po.get('po_number')}")
    return {'success': True}

@router.put("/production-pos/{po_id}")
async def update_po(po_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    existing = await db.production_pos.find_one({'id': po_id})
    if not existing: raise HTTPException(404, 'PO not found')
    if existing.get('status') == 'Closed' and user.get('role') != 'superadmin':
        raise HTTPException(403, 'PO ini sudah Closed.')
    body = await request.json()
    body.pop('_id', None); body.pop('id', None); body.pop('items', None)
    if body.get('deadline'): body['deadline'] = parse_date(body['deadline'])
    if body.get('delivery_deadline'): body['delivery_deadline'] = parse_date(body['delivery_deadline'])
    if body.get('po_date'): body['po_date'] = parse_date(body['po_date'])
    if body.get('vendor_id'):
        vd = await db.garments.find_one({'id': body['vendor_id']})
        body['vendor_name'] = vd.get('garment_name', '') if vd else ''
    await db.production_pos.update_one({'id': po_id}, {'$set': {**body, 'updated_at': now()}})
    await log_activity(user['id'], user['name'], 'Update', 'Production PO', f"Updated PO: {existing.get('po_number')}")
    return serialize_doc(await db.production_pos.find_one({'id': po_id}, {'_id': 0}))

@router.delete("/production-pos/{po_id}")
async def delete_po(po_id: str, request: Request):
    user = await require_auth(request)
    if user.get('role') != 'superadmin': raise HTTPException(403, 'Forbidden')
    db = get_db()
    doc = await db.production_pos.find_one({'id': po_id})
    if not doc: raise HTTPException(404, 'Not found')
    await cascade_delete_po(po_id)
    await log_activity(user['id'], user['name'], 'Delete', 'Production PO', f"Cascade deleted PO: {doc.get('po_number')}")
    return {'success': True}

# ─── PO ITEMS ────────────────────────────────────────────────────────────────
@router.get("/po-items")
async def get_po_items(request: Request):
    await require_auth(request)
    db = get_db()
    query = {}
    po_id = request.query_params.get('po_id')
    if po_id: query['po_id'] = po_id
    return serialize_doc(await db.po_items.find(query, {'_id': 0}).sort('created_at', 1).to_list(None))

@router.get("/po-items-produced")
async def get_po_items_produced(request: Request):
    await require_auth(request)
    db = get_db()
    po_id = request.query_params.get('po_id')
    if not po_id: raise HTTPException(400, 'po_id wajib diisi')
    po_items = await db.po_items.find({'po_id': po_id}, {'_id': 0}).sort('created_at', 1).to_list(None)
    enriched = []
    for item in po_items:
        job_items = await db.production_job_items.find({'po_item_id': item['id']}).to_list(None)
        total_produced = 0
        for ji in job_items:
            total_produced += ji.get('produced_qty', 0)
            parent_job = await db.production_jobs.find_one({'id': ji.get('job_id')})
            if parent_job:
                child_jobs = await db.production_jobs.find({'parent_job_id': parent_job['id']}).to_list(None)
                for cj in child_jobs:
                    cji = await db.production_job_items.find_one({'job_id': cj['id'], 'po_item_id': item['id']})
                    if cji: total_produced += cji.get('produced_qty', 0)
        return_items = await db.production_return_items.find({'po_item_id': item['id']}).to_list(None)
        total_returned = sum(r.get('return_qty', 0) for r in return_items)
        buyer_items = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
        total_shipped = sum(b.get('qty_shipped', 0) for b in buyer_items)
        enriched.append({**serialize_doc(item),
            'total_produced': total_produced, 'total_shipped': total_shipped,
            'total_returned': total_returned,
            'max_returnable': max(0, total_shipped - total_returned)})
    return enriched

@router.put("/po-items/{item_id}")
async def update_po_item(item_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    body.pop('_id', None); body.pop('id', None)
    await db.po_items.update_one({'id': item_id}, {'$set': {**body, 'updated_at': now()}})
    return serialize_doc(await db.po_items.find_one({'id': item_id}, {'_id': 0}))

@router.delete("/po-items/{item_id}")
async def delete_po_item(item_id: str, request: Request):
    user = await require_auth(request)
    if user.get('role') != 'superadmin': raise HTTPException(403, 'Forbidden')
    db = get_db()
    await db.po_items.delete_one({'id': item_id})
    return {'success': True}


# ─── PO STATUS TRANSITION ───────────────────────────────────────────────────
@router.post("/production-pos/{po_id}/status")
async def transition_po_status(po_id: str, request: Request):
    """Transition PO through staged statuses."""
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    new_status = body.get('status')
    if new_status not in PO_STATUSES:
        raise HTTPException(400, f"Invalid status. Valid: {PO_STATUSES}")
    po = await db.production_pos.find_one({'id': po_id})
    if not po: raise HTTPException(404, 'PO not found')
    update_data = {'status': new_status, 'updated_at': now()}
    if body.get('notes'): update_data['status_notes'] = body['notes']
    if new_status == 'Closed':
        update_data['closed_by'] = user['name']
        update_data['closed_at'] = now()
        update_data['close_reason'] = body.get('close_reason', '')
    await db.production_pos.update_one({'id': po_id}, {'$set': update_data})
    await log_activity(user['id'], user['name'], 'Status Change', 'Production PO',
                       f"PO {po.get('po_number')}: {po.get('status')} → {new_status}")
    return serialize_doc(await db.production_pos.find_one({'id': po_id}, {'_id': 0}))


# ─── PO QUANTITY SUMMARY ────────────────────────────────────────────────────
@router.get("/production-pos/{po_id}/quantity-summary")
async def po_quantity_summary(po_id: str, request: Request):
    """Get comprehensive quantity summary for a PO."""
    await require_auth(request)
    db = get_db()
    po = await db.production_pos.find_one({'id': po_id}, {'_id': 0})
    if not po: raise HTTPException(404, 'PO not found')
    items = await db.po_items.find({'po_id': po_id}, {'_id': 0}).to_list(None)
    summary_items = []
    totals = {'ordered': 0, 'received': 0, 'missing': 0, 'defect': 0, 
              'available': 0, 'produced': 0, 'shipped': 0, 'returned': 0}
    for item in items:
        # Get all shipment items for this po_item
        ship_items = await db.vendor_shipment_items.find({'po_item_id': item['id']}).to_list(None)
        # Get inspection data
        received = 0; missing = 0
        for si in ship_items:
            ship = await db.vendor_shipments.find_one({'id': si.get('shipment_id')})
            if ship and ship.get('inspection_status') == 'Inspected':
                insp = await db.vendor_material_inspections.find_one({'shipment_id': si['shipment_id']})
                if insp:
                    ii = await db.vendor_material_inspection_items.find_one({
                        'inspection_id': insp['id'], 'shipment_item_id': si['id']})
                    if ii:
                        received += ii.get('received_qty', 0)
                        missing += ii.get('missing_qty', 0)
                    else:
                        received += si.get('qty_sent', 0)
            elif ship and ship.get('status') == 'Received':
                received += si.get('qty_sent', 0)
        # Defects
        defects = await db.material_defect_reports.find({'po_item_id': item['id']}).to_list(None)
        total_defect = sum(d.get('defect_qty', 0) for d in defects)
        available = max(0, received - total_defect)
        # Production
        job_items = await db.production_job_items.find({'po_item_id': item['id']}).to_list(None)
        produced = sum(ji.get('produced_qty', 0) for ji in job_items)
        # Also count orphaned child items by sku+size+color
        orphan_ji = await db.production_job_items.find({
            '$or': [{'po_item_id': None}, {'po_item_id': ''}, {'po_item_id': {'$exists': False}}],
            'sku': item.get('sku', ''), 'size': item.get('size', ''), 'color': item.get('color', '')
        }).to_list(None)
        counted_ids = {j['id'] for j in job_items}
        for oji in orphan_ji:
            if oji['id'] not in counted_ids:
                produced += oji.get('produced_qty', 0)
        # Shipped
        buyer_items = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
        shipped = sum(bi.get('qty_shipped', 0) for bi in buyer_items)
        # Returns
        return_items = await db.production_return_items.find({'po_item_id': item['id']}).to_list(None)
        returned = sum(ri.get('return_qty', 0) for ri in return_items)
        ordered = item.get('qty', 0)
        over = max(0, produced - ordered)
        under = max(0, ordered - produced)
        summary_items.append({
            **serialize_doc(item),
            'ordered_qty': ordered, 'received_qty': received, 'missing_qty': missing,
            'defect_qty': total_defect, 'available_qty': available, 'produced_qty': produced,
            'shipped_qty': shipped, 'returned_qty': returned,
            'overproduction_qty': over, 'underproduction_qty': under
        })
        totals['ordered'] += ordered; totals['received'] += received
        totals['missing'] += missing; totals['defect'] += total_defect
        totals['available'] += available; totals['produced'] += produced
        totals['shipped'] += shipped; totals['returned'] += returned
    totals['overproduction'] = max(0, totals['produced'] - totals['ordered'])
    totals['underproduction'] = max(0, totals['ordered'] - totals['produced'])
    return {'po': serialize_doc(po), 'items': summary_items, 'totals': totals}


# ─── PO ACCESSORIES (add-on) ─────────────────────────────────────────────────
@router.get("/po-accessories")
async def get_po_accessories(request: Request):
    """Get accessories linked to a PO."""
    await require_auth(request)
    db = get_db()
    po_id = request.query_params.get('po_id')
    if not po_id: raise HTTPException(400, 'po_id required')
    return serialize_doc(await db.po_accessories.find({'po_id': po_id}, {'_id': 0}).sort('created_at', 1).to_list(None))

@router.post("/po-accessories")
async def add_po_accessory(request: Request):
    """Add accessory to a PO."""
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    po_id = body.get('po_id')
    if not po_id: raise HTTPException(400, 'po_id required')
    items = body.get('items', [])
    inserted = []
    for item in items:
        acc_doc = {
            'id': new_id(), 'po_id': po_id,
            'accessory_id': item.get('accessory_id'),
            'accessory_name': item.get('accessory_name', ''),
            'accessory_code': item.get('accessory_code', ''),
            'qty_needed': int(item.get('qty_needed', 0) or 0),
            'unit': item.get('unit', 'pcs'),
            'notes': item.get('notes', ''),
            'created_at': now()
        }
        await db.po_accessories.insert_one(acc_doc)
        inserted.append(acc_doc)
    await log_activity(user['id'], user['name'], 'Add Accessories', 'Production PO',
                       f"Added {len(inserted)} accessories to PO")
    return JSONResponse(serialize_doc(inserted), status_code=201)

@router.delete("/po-accessories/{acc_id}")
async def remove_po_accessory(acc_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    await db.po_accessories.delete_one({'id': acc_id})
    return {'success': True}

