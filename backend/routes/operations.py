"""
Operations: Accessories, Reminders, Serial Tracking, Reports, Import/Export, PDF
Extracted from server.py monolith.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from database import get_db
from auth import (verify_token, require_auth, check_role, hash_password, verify_password,
                  create_token, log_activity, serialize_doc, generate_password)
from routes.shared import new_id, now, parse_date, to_end_of_day, PO_STATUSES, enrich_with_product_photos, _fmt_date, _fmt_num, _fmt_money
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["operations"])

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm, cm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors as rl_colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    pass

try:
    import openpyxl
except ImportError:
    pass

# ─── ACCESSORY MANAGEMENT ───────────────────────────────────────────────────
@router.get("/accessories")
async def get_accessories(request: Request):
    await require_auth(request)
    db = get_db()
    sp = request.query_params
    query = {}
    if sp.get('search'):
        query['$or'] = [{'name': {'$regex': sp['search'], '$options': 'i'}},
                        {'code': {'$regex': sp['search'], '$options': 'i'}}]
    if sp.get('status'): query['status'] = sp['status']
    return serialize_doc(await db.accessories.find(query, {'_id': 0}).sort('created_at', -1).to_list(None))

@router.post("/accessories")
async def create_accessory(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    acc = {'id': new_id(), **body, 'status': body.get('status', 'active'),
           'created_at': now(), 'updated_at': now()}
    await db.accessories.insert_one(acc)
    await log_activity(user['id'], user['name'], 'Create', 'Accessories', f"Created accessory: {body.get('name')}")
    return JSONResponse(serialize_doc(acc), status_code=201)

@router.put("/accessories/{acc_id}")
async def update_accessory(acc_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    body.pop('_id', None); body.pop('id', None)
    await db.accessories.update_one({'id': acc_id}, {'$set': {**body, 'updated_at': now()}})
    return serialize_doc(await db.accessories.find_one({'id': acc_id}, {'_id': 0}))

@router.delete("/accessories/{acc_id}")
async def delete_accessory(acc_id: str, request: Request):
    user = await require_auth(request)
    if user.get('role') != 'superadmin': raise HTTPException(403, 'Forbidden')
    db = get_db()
    await db.accessories.delete_one({'id': acc_id})
    return {'success': True}


# ─── ACCESSORY SHIPMENTS ────────────────────────────────────────────────────
@router.get("/accessory-shipments")
async def get_accessory_shipments(request: Request):
    user = await require_auth(request)
    db = get_db()
    query = {}
    sp = request.query_params
    if sp.get('po_id'): query['po_id'] = sp['po_id']
    if sp.get('vendor_id'): query['vendor_id'] = sp['vendor_id']
    if user.get('role') == 'vendor': query['vendor_id'] = user.get('vendor_id')
    shipments = await db.accessory_shipments.find(query, {'_id': 0}).sort('created_at', -1).to_list(None)
    result = []
    for s in shipments:
        items = await db.accessory_shipment_items.find({'shipment_id': s['id']}, {'_id': 0}).to_list(None)
        result.append({**serialize_doc(s), 'items': serialize_doc(items)})
    return result

@router.post("/accessory-shipments")
async def create_accessory_shipment(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    vendor = await db.garments.find_one({'id': body.get('vendor_id')})
    if not vendor: raise HTTPException(404, 'Vendor not found')
    ship_id = new_id()
    shipment = {
        'id': ship_id, 'shipment_number': body.get('shipment_number'),
        'vendor_id': body['vendor_id'], 'vendor_name': vendor.get('garment_name', ''),
        'po_id': body.get('po_id'), 'po_number': body.get('po_number', ''),
        'shipment_date': parse_date(body.get('shipment_date')) or now(),
        'status': 'Sent', 'notes': body.get('notes', ''),
        'created_by': user['name'], 'created_at': now(), 'updated_at': now()
    }
    await db.accessory_shipments.insert_one(shipment)
    inserted_items = []
    for item in body.get('items', []):
        si = {
            'id': new_id(), 'shipment_id': ship_id,
            'accessory_id': item.get('accessory_id'),
            'accessory_name': item.get('accessory_name', ''),
            'accessory_code': item.get('accessory_code', ''),
            'qty_sent': int(item.get('qty_sent', 0) or 0),
            'unit': item.get('unit', 'pcs'),
            'notes': item.get('notes', ''), 'created_at': now()
        }
        await db.accessory_shipment_items.insert_one(si)
        inserted_items.append(si)
    await log_activity(user['id'], user['name'], 'Create', 'Accessory Shipment',
                       f"Created accessory shipment {body.get('shipment_number')}")
    result = serialize_doc(shipment)
    result['items'] = serialize_doc(inserted_items)
    return JSONResponse(result, status_code=201)

@router.put("/accessory-shipments/{sid}")
async def update_accessory_shipment(sid: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    body.pop('_id', None); body.pop('id', None); body.pop('items', None)
    await db.accessory_shipments.update_one({'id': sid}, {'$set': {**body, 'updated_at': now()}})
    return serialize_doc(await db.accessory_shipments.find_one({'id': sid}, {'_id': 0}))

@router.delete("/accessory-shipments/{sid}")
async def delete_accessory_shipment(sid: str, request: Request):
    user = await require_auth(request)
    if user.get('role') != 'superadmin': raise HTTPException(403, 'Forbidden')
    db = get_db()
    await db.accessory_shipment_items.delete_many({'shipment_id': sid})
    await db.accessory_shipments.delete_one({'id': sid})
    return {'success': True}


# ─── ACCESSORY INSPECTIONS ───────────────────────────────────────────────────
@router.get("/accessory-inspections")
async def get_acc_inspections(request: Request):
    user = await require_auth(request)
    db = get_db()
    query = {}
    sp = request.query_params
    if sp.get('shipment_id'): query['shipment_id'] = sp['shipment_id']
    if sp.get('vendor_id'): query['vendor_id'] = sp['vendor_id']
    if user.get('role') == 'vendor': query['vendor_id'] = user.get('vendor_id')
    return serialize_doc(await db.accessory_inspections.find(query, {'_id': 0}).sort('created_at', -1).to_list(None))

@router.post("/accessory-inspections")
async def create_acc_inspection(request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    vendor_id = user.get('vendor_id') if user.get('role') == 'vendor' else body.get('vendor_id')
    shipment = await db.accessory_shipments.find_one({'id': body.get('shipment_id')}) if body.get('shipment_id') else None
    if not shipment: raise HTTPException(404, 'Accessory shipment tidak ditemukan')
    existing = await db.accessory_inspections.find_one({'shipment_id': body['shipment_id']})
    if existing: raise HTTPException(400, 'Inspeksi sudah dilakukan untuk shipment ini')
    insp_id = new_id()
    items_data = body.get('items', [])
    total_received = sum(int(i.get('received_qty', 0) or 0) for i in items_data)
    total_missing = sum(int(i.get('missing_qty', 0) or 0) for i in items_data)
    inspection = {
        'id': insp_id, 'shipment_id': body['shipment_id'],
        'vendor_id': vendor_id, 'vendor_name': shipment.get('vendor_name', ''),
        'po_id': shipment.get('po_id'), 'po_number': shipment.get('po_number', ''),
        'inspection_date': parse_date(body.get('inspection_date')) or now(),
        'total_received': total_received, 'total_missing': total_missing,
        'notes': body.get('notes', ''), 'status': 'Submitted',
        'submitted_by': user['name'], 'created_at': now(), 'updated_at': now()
    }
    await db.accessory_inspections.insert_one(inspection)
    for item in items_data:
        await db.accessory_inspection_items.insert_one({
            'id': new_id(), 'inspection_id': insp_id,
            'shipment_item_id': item.get('shipment_item_id'),
            'accessory_name': item.get('accessory_name', ''), 'accessory_code': item.get('accessory_code', ''),
            'qty_sent': int(item.get('qty_sent', 0) or 0),
            'received_qty': int(item.get('received_qty', 0) or 0),
            'missing_qty': int(item.get('missing_qty', 0) or 0),
            'condition_notes': item.get('condition_notes', ''), 'created_at': now()
        })
    await db.accessory_shipments.update_one({'id': body['shipment_id']}, {'$set': {
        'inspection_status': 'Inspected', 'total_received': total_received,
        'total_missing': total_missing, 'updated_at': now()
    }})
    await log_activity(user['id'], user['name'], 'Create', 'Accessory Inspection',
                       f"Inspeksi aksesoris shipment {shipment.get('shipment_number')}")
    result = serialize_doc(inspection)
    items_docs = await db.accessory_inspection_items.find({'inspection_id': insp_id}, {'_id': 0}).to_list(None)
    result['items'] = serialize_doc(items_docs)
    return JSONResponse(result, status_code=201)


# ─── ACCESSORY DEFECTS ──────────────────────────────────────────────────────
@router.get("/accessory-defects")
async def get_acc_defects(request: Request):
    user = await require_auth(request)
    db = get_db()
    query = {}
    if user.get('role') == 'vendor': query['vendor_id'] = user.get('vendor_id')
    if request.query_params.get('vendor_id'): query['vendor_id'] = request.query_params['vendor_id']
    return serialize_doc(await db.accessory_defects.find(query, {'_id': 0}).sort('created_at', -1).to_list(None))

@router.post("/accessory-defects")
async def create_acc_defect(request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    vendor_id = user.get('vendor_id') if user.get('role') == 'vendor' else body.get('vendor_id')
    if not vendor_id: raise HTTPException(400, 'vendor_id diperlukan')
    defect = {
        'id': new_id(), 'vendor_id': vendor_id,
        'po_id': body.get('po_id'), 'shipment_id': body.get('shipment_id'),
        'accessory_name': body.get('accessory_name', ''), 'accessory_code': body.get('accessory_code', ''),
        'defect_qty': int(body.get('defect_qty', 0) or 0),
        'defect_type': body.get('defect_type', 'Material Cacat'),
        'description': body.get('description', ''),
        'report_date': parse_date(body.get('report_date')) or now(),
        'status': 'Reported', 'reported_by': user['name'],
        'created_at': now(), 'updated_at': now()
    }
    await db.accessory_defects.insert_one(defect)
    await log_activity(user['id'], user['name'], 'Create', 'Accessory Defect',
                       f"Laporan cacat aksesoris: {body.get('accessory_name')} - {body.get('defect_qty')} pcs")
    return JSONResponse(serialize_doc(defect), status_code=201)


# ─── ACCESSORY REQUESTS ─────────────────────────────────────────────────────
@router.get("/accessory-requests")
async def get_acc_requests(request: Request):
    user = await require_auth(request)
    db = get_db()
    query = {}
    sp = request.query_params
    if user.get('role') == 'vendor': query['vendor_id'] = user.get('vendor_id')
    if sp.get('status'): query['status'] = sp['status']
    if sp.get('request_type'): query['request_type'] = sp['request_type']
    return serialize_doc(await db.accessory_requests.find(query, {'_id': 0}).sort('created_at', -1).to_list(None))

@router.post("/accessory-requests")
async def create_acc_request(request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    vendor_id = user.get('vendor_id') if user.get('role') == 'vendor' else body.get('vendor_id')
    if not vendor_id: raise HTTPException(400, 'vendor_id diperlukan')
    if body.get('request_type') not in ['ADDITIONAL', 'REPLACEMENT']:
        raise HTTPException(400, 'request_type harus ADDITIONAL atau REPLACEMENT')
    seq = (await db.accessory_requests.count_documents({})) + 1
    prefix = 'ACC-ADD' if body['request_type'] == 'ADDITIONAL' else 'ACC-RPL'
    req_doc = {
        'id': new_id(), 'request_number': f"{prefix}-{str(seq).zfill(4)}",
        'request_type': body['request_type'],
        'vendor_id': vendor_id,
        'original_shipment_id': body.get('original_shipment_id'),
        'po_id': body.get('po_id'), 'po_number': body.get('po_number', ''),
        'items': body.get('items', []),
        'total_requested_qty': sum(int(i.get('requested_qty', 0) or 0) for i in body.get('items', [])),
        'reason': body.get('reason', ''), 'status': 'Pending',
        'created_by': user['name'], 'created_at': now(), 'updated_at': now()
    }
    await db.accessory_requests.insert_one(req_doc)
    await log_activity(user['id'], user['name'], 'Create', 'Accessory Request',
                       f"Request aksesoris {body['request_type']}: {req_doc['request_number']}")
    return JSONResponse(serialize_doc(req_doc), status_code=201)

@router.put("/accessory-requests/{req_id}")
async def update_acc_request(req_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    req = await db.accessory_requests.find_one({'id': req_id})
    if not req: raise HTTPException(404, 'Request tidak ditemukan')
    new_status = body.get('status')
    if new_status == 'Approved' and req.get('status') == 'Pending':
        orig_ship = await db.accessory_shipments.find_one({'id': req.get('original_shipment_id')})
        if orig_ship:
            existing_children = await db.accessory_shipments.count_documents({
                'parent_shipment_id': req['original_shipment_id']})
            suffix = f"A{existing_children + 1}" if req['request_type'] == 'ADDITIONAL' else f"R{existing_children + 1}"
            child_number = f"{orig_ship.get('shipment_number', '')}-{suffix}"
            child_id = new_id()
            child_ship = {
                'id': child_id, 'shipment_number': child_number,
                'vendor_id': orig_ship.get('vendor_id'), 'vendor_name': orig_ship.get('vendor_name', ''),
                'po_id': orig_ship.get('po_id'), 'po_number': orig_ship.get('po_number', ''),
                'shipment_date': now(), 'shipment_type': req['request_type'],
                'parent_shipment_id': req['original_shipment_id'],
                'status': 'Sent', 'notes': f"Child accessory shipment ({req['request_type']})",
                'created_by': user['name'], 'created_at': now(), 'updated_at': now()
            }
            await db.accessory_shipments.insert_one(child_ship)
            for ri in req.get('items', []):
                await db.accessory_shipment_items.insert_one({
                    'id': new_id(), 'shipment_id': child_id,
                    'accessory_name': ri.get('accessory_name', ''), 'accessory_code': ri.get('accessory_code', ''),
                    'qty_sent': int(ri.get('requested_qty', 0) or 0), 'unit': ri.get('unit', 'pcs'),
                    'created_at': now()
                })
            await db.accessory_requests.update_one({'id': req_id}, {'$set': {
                'status': 'Approved', 'admin_notes': body.get('admin_notes', ''),
                'approved_by': user['name'], 'approved_at': now(),
                'child_shipment_id': child_id, 'child_shipment_number': child_number,
                'updated_at': now()
            }})
            result = serialize_doc(await db.accessory_requests.find_one({'id': req_id}, {'_id': 0}))
            result['child_shipment'] = serialize_doc(child_ship)
            return result
    if new_status == 'Rejected':
        await db.accessory_requests.update_one({'id': req_id}, {'$set': {
            'status': 'Rejected', 'admin_notes': body.get('admin_notes', ''), 'updated_at': now()
        }})
    else:
        upd = {k: v for k, v in body.items() if k not in ('_id', 'id')}
        await db.accessory_requests.update_one({'id': req_id}, {'$set': {**upd, 'updated_at': now()}})
    return serialize_doc(await db.accessory_requests.find_one({'id': req_id}, {'_id': 0}))



# ─── REMINDER SYSTEM ─────────────────────────────────────────────────────────
@router.get("/reminders")
async def get_reminders(request: Request):
    user = await require_auth(request)
    db = get_db()
    query = {}
    if user.get('role') == 'vendor':
        query['vendor_id'] = user.get('vendor_id')
    sp = request.query_params
    if sp.get('status'): query['status'] = sp['status']
    if sp.get('vendor_id') and user.get('role') != 'vendor': query['vendor_id'] = sp['vendor_id']
    reminders = await db.reminders.find(query, {'_id': 0}).sort('created_at', -1).to_list(None)
    return serialize_doc(reminders)

@router.post("/reminders")
async def create_reminder(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    vendor_id = body.get('vendor_id')
    if not vendor_id: raise HTTPException(400, 'vendor_id required')
    vendor = await db.garments.find_one({'id': vendor_id})
    reminder = {
        'id': new_id(),
        'vendor_id': vendor_id, 'vendor_name': (vendor or {}).get('garment_name', ''),
        'po_id': body.get('po_id', ''), 'po_number': body.get('po_number', ''),
        'reminder_type': body.get('reminder_type', 'general'),
        'subject': body.get('subject', ''), 'message': body.get('message', ''),
        'priority': body.get('priority', 'normal'),
        'status': 'pending', 'response': None, 'response_date': None,
        'created_by': user.get('name', ''), 'created_at': now(), 'updated_at': now()
    }
    await db.reminders.insert_one(reminder)
    await log_activity(user['id'], user.get('name', ''), 'create', 'reminder', f"Sent reminder to {(vendor or {}).get('garment_name', vendor_id)}")
    return JSONResponse(serialize_doc({k: v for k, v in reminder.items() if k != '_id'}), status_code=201)

@router.put("/reminders/{reminder_id}")
async def update_reminder(reminder_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    existing = await db.reminders.find_one({'id': reminder_id})
    if not existing: raise HTTPException(404, 'Reminder not found')
    update = {'updated_at': now()}
    # Vendor responding
    if user.get('role') == 'vendor' and body.get('response'):
        update['response'] = body['response']
        update['response_date'] = now()
        update['responded_by'] = user.get('name', '')
        update['status'] = 'responded'
    # Admin updating
    if user.get('role') in ['admin', 'superadmin']:
        if 'status' in body: update['status'] = body['status']
        if 'message' in body: update['message'] = body['message']
    await db.reminders.update_one({'id': reminder_id}, {'$set': update})
    return serialize_doc(await db.reminders.find_one({'id': reminder_id}, {'_id': 0}))

@router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    await db.reminders.delete_one({'id': reminder_id})
    return {'success': True}



# ─── SERIAL TRACKING TIMELINE ───────────────────────────────────────────────
@router.get("/serial-list")
async def serial_list(request: Request):
    """Get list of all serial numbers with status info."""
    user = await require_auth(request)
    db = get_db()
    sp = request.query_params
    search = sp.get('search', '').strip()
    status_filter = sp.get('status', '')  # ongoing, completed, all
    # Build query
    query = {}
    if search:
        query['serial_number'] = {'$regex': search, '$options': 'i'}
    if user.get('role') == 'vendor':
        # Only show serials for vendor's POs
        vendor_pos = await db.production_pos.find({'vendor_id': user.get('vendor_id')}, {'id': 1}).to_list(None)
        vendor_po_ids = [p['id'] for p in vendor_pos]
        query['po_id'] = {'$in': vendor_po_ids}
    po_items = await db.po_items.find(query, {'_id': 0}).sort('created_at', -1).to_list(None)
    result = []
    for item in po_items:
        if not item.get('serial_number'): continue
        po = await db.production_pos.find_one({'id': item.get('po_id')}, {'_id': 0})
        # Get production status - by po_item_id + fallback for orphaned child items
        ji_list = await db.production_job_items.find({'po_item_id': item['id']}).to_list(None)
        produced = sum(j.get('produced_qty', 0) for j in ji_list)
        # Also check orphaned child items by sku+size+color
        orphan_ji = await db.production_job_items.find({
            '$or': [{'po_item_id': None}, {'po_item_id': ''}, {'po_item_id': {'$exists': False}}],
            'sku': item.get('sku', ''), 'size': item.get('size', ''), 'color': item.get('color', '')
        }).to_list(None)
        counted_ids = {j['id'] for j in ji_list}
        for oji in orphan_ji:
            if oji['id'] not in counted_ids:
                produced += oji.get('produced_qty', 0)
        # Get shipment status
        bi_list = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
        shipped = sum(b.get('qty_shipped', 0) for b in bi_list)
        ordered = item.get('qty', 0)
        remaining = max(0, ordered - shipped)
        # Determine status
        if shipped >= ordered:
            serial_status = 'completed'
        elif produced > 0 or ji_list:
            serial_status = 'ongoing'
        else:
            serial_status = 'pending'
        if status_filter and status_filter != 'all' and serial_status != status_filter:
            continue
        # Get vendor shipment info
        vs_items = await db.vendor_shipment_items.find({'po_item_id': item['id']}).to_list(None)
        received_qty = 0
        for vsi in vs_items:
            insp = await db.vendor_material_inspection_items.find_one({'shipment_item_id': vsi['id']})
            if insp: received_qty += insp.get('received_qty', 0)
            else: received_qty += vsi.get('qty_sent', 0)
        result.append({
            'serial_number': item.get('serial_number'),
            'po_number': (po or {}).get('po_number', ''),
            'po_id': item.get('po_id'),
            'customer_name': (po or {}).get('customer_name', ''),
            'vendor_name': (po or {}).get('vendor_name', ''),
            'product_name': item.get('product_name', ''),
            'sku': item.get('sku', ''),
            'size': item.get('size', ''),
            'color': item.get('color', ''),
            'ordered_qty': ordered,
            'received_qty': received_qty,
            'produced_qty': produced,
            'shipped_qty': shipped,
            'remaining_qty': remaining,
            'status': serial_status,
            'po_status': (po or {}).get('status', ''),
            'deadline': serialize_doc((po or {}).get('deadline')),
        })
    return result

@router.get("/serial-trace")
async def serial_trace(request: Request):
    """Get full lifecycle timeline + PO-wide summary for a serial number."""
    await require_auth(request)
    db = get_db()
    serial = request.query_params.get('serial', '').strip()
    if not serial: raise HTTPException(400, 'serial parameter required')
    timeline = []
    # 1. PO items with this serial
    po_items = await db.po_items.find({'serial_number': serial}, {'_id': 0}).to_list(None)
    po_ids = list(set(pi.get('po_id') for pi in po_items if pi.get('po_id')))
    po_item_ids = [pi['id'] for pi in po_items]
    # 2. Get ALL items from the same POs (all serials in the PO)
    all_po_items = []
    po_details = {}
    for pid in po_ids:
        po = await db.production_pos.find_one({'id': pid}, {'_id': 0})
        if po: po_details[pid] = po
        items = await db.po_items.find({'po_id': pid}, {'_id': 0}).to_list(None)
        all_po_items.extend(items)
    all_po_item_ids = [pi['id'] for pi in all_po_items]
    # 3. Build summary for ALL items in the PO (not just searched serial)
    summary_items = []
    totals = {'ordered': 0, 'produced': 0, 'shipped': 0, 'not_produced': 0, 'not_shipped': 0}
    vendors_set = set()
    buyer_names = set()
    for item in all_po_items:
        po = po_details.get(item.get('po_id'), {})
        vendors_set.add(po.get('vendor_name', ''))
        buyer_names.add(po.get('customer_name', ''))
        ji_list = await db.production_job_items.find({'po_item_id': item['id']}).to_list(None)
        produced = sum(j.get('produced_qty', 0) for j in ji_list)
        # Also count orphaned child items by sku+size+color
        orphan_ji = await db.production_job_items.find({
            '$or': [{'po_item_id': None}, {'po_item_id': ''}, {'po_item_id': {'$exists': False}}],
            'sku': item.get('sku', ''), 'size': item.get('size', ''), 'color': item.get('color', '')
        }).to_list(None)
        counted_ids = {j['id'] for j in ji_list}
        for oji in orphan_ji:
            if oji['id'] not in counted_ids:
                produced += oji.get('produced_qty', 0)
        bi_list = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
        shipped = sum(b.get('qty_shipped', 0) for b in bi_list)
        ordered = item.get('qty', 0)
        summary_items.append({
            'po_item_id': item['id'], 'serial_number': item.get('serial_number', ''),
            'product_name': item.get('product_name', ''), 'sku': item.get('sku', ''),
            'size': item.get('size', ''), 'color': item.get('color', ''),
            'ordered_qty': ordered, 'produced_qty': produced, 'shipped_qty': shipped,
            'not_produced': max(0, ordered - produced), 'not_shipped': max(0, ordered - shipped),
            'is_searched_serial': item.get('serial_number') == serial,
            'po_number': item.get('po_number', po.get('po_number', ''))
        })
        totals['ordered'] += ordered; totals['produced'] += produced; totals['shipped'] += shipped
    totals['not_produced'] = max(0, totals['ordered'] - totals['produced'])
    totals['not_shipped'] = max(0, totals['ordered'] - totals['shipped'])
    # 4. Build timeline events for the SEARCHED serial only
    for pi in po_items:
        po = po_details.get(pi.get('po_id'), {})
        timeline.append({
            'step': 'PO Created', 'event': 'PO Dibuat', 'details': f"PO {po.get('po_number','')} - {pi.get('product_name','')} ({pi.get('sku','')}) x{pi.get('qty',0)}",
            'date': serialize_doc(pi.get('created_at')),
            'module': 'production-po', 'po_number': pi.get('po_number'),
            'po_item_id': pi['id'], 'qty': pi.get('qty', 0),
            'sku': pi.get('sku'), 'size': pi.get('size'), 'color': pi.get('color'),
            'customer_name': po.get('customer_name', ''),
            'vendor_name': po.get('vendor_name', ''), 'status': po.get('status', '')
        })
    for poi_id in po_item_ids:
        ship_items = await db.vendor_shipment_items.find({'po_item_id': poi_id}, {'_id': 0}).to_list(None)
        for si in ship_items:
            ship = await db.vendor_shipments.find_one({'id': si.get('shipment_id')}, {'_id': 0})
            ship_type = (ship or {}).get('shipment_type', 'NORMAL')
            ship_num = (ship or {}).get('shipment_number', '')
            timeline.append({
                'step': f"Vendor Shipment ({ship_type})",
                'event': f"Pengiriman Vendor ({ship_type})",
                'details': f"Shipment {ship_num} - dikirim {si.get('qty_sent', 0)} pcs",
                'date': serialize_doc((ship or {}).get('shipment_date', si.get('created_at'))),
                'module': 'vendor-shipments', 'shipment_number': ship_num,
                'qty_sent': si.get('qty_sent', 0), 'status': (ship or {}).get('status', ''),
                'inspection_status': (ship or {}).get('inspection_status', 'Pending')
            })
    for poi_id in po_item_ids:
        sis = await db.vendor_shipment_items.find({'po_item_id': poi_id}).to_list(None)
        for si in sis:
            insp = await db.vendor_material_inspections.find_one({'shipment_id': si.get('shipment_id')})
            if insp:
                ii = await db.vendor_material_inspection_items.find_one({'inspection_id': insp['id'], 'shipment_item_id': si['id']})
                if ii:
                    timeline.append({'step': 'Material Inspection',
                        'event': 'Inspeksi Material',
                        'details': f"Diterima: {ii.get('received_qty', 0)}, Missing: {ii.get('missing_qty', 0)}, Defect: {ii.get('defect_qty', 0)}",
                        'date': serialize_doc(insp.get('inspection_date')),
                        'module': 'inspections', 'received_qty': ii.get('received_qty', 0),
                        'missing_qty': ii.get('missing_qty', 0), 'condition_notes': ii.get('condition_notes', '')})
    for poi_id in po_item_ids:
        ji_list = await db.production_job_items.find({'po_item_id': poi_id}, {'_id': 0}).to_list(None)
        for ji in ji_list:
            job = await db.production_jobs.find_one({'id': ji.get('job_id')}, {'_id': 0})
            timeline.append({'step': 'Production Job',
                'event': 'Job Produksi Dibuat',
                'details': f"Job {(job or {}).get('job_number', '')} - tersedia {ji.get('available_qty', 0)} pcs, diproduksi {ji.get('produced_qty', 0)} pcs",
                'date': serialize_doc(ji.get('created_at')),
                'module': 'production-jobs', 'job_number': (job or {}).get('job_number', ''),
                'available_qty': ji.get('available_qty', 0), 'produced_qty': ji.get('produced_qty', 0),
                'status': (job or {}).get('status', '')})
    for poi_id in po_item_ids:
        ji_list = await db.production_job_items.find({'po_item_id': poi_id}).to_list(None)
        for ji in ji_list:
            progs = await db.production_progress.find({'job_item_id': ji['id']}, {'_id': 0}).sort('progress_date', 1).to_list(None)
            for p in progs:
                timeline.append({'step': 'Production Progress',
                    'event': 'Progres Produksi',
                    'details': f"Selesai {p.get('completed_quantity', 0)} pcs - {p.get('notes', '')}",
                    'date': serialize_doc(p.get('progress_date')),
                    'module': 'production-progress', 'completed_quantity': p.get('completed_quantity', 0),
                    'notes': p.get('notes', ''), 'recorded_by': p.get('recorded_by', '')})
    for poi_id in po_item_ids:
        bis = await db.buyer_shipment_items.find({'po_item_id': poi_id}, {'_id': 0}).sort('dispatch_seq', 1).to_list(None)
        for bi in bis:
            bs = await db.buyer_shipments.find_one({'id': bi.get('shipment_id')}, {'_id': 0})
            timeline.append({'step': f"Buyer Dispatch #{bi.get('dispatch_seq', 1)}",
                'event': f"Pengiriman ke Buyer #{bi.get('dispatch_seq', 1)}",
                'details': f"Shipment {(bs or {}).get('shipment_number', '')} - dikirim {bi.get('qty_shipped', 0)} pcs",
                'date': serialize_doc(bi.get('dispatch_date', bi.get('created_at'))),
                'module': 'buyer-shipments', 'shipment_number': (bs or {}).get('shipment_number', ''),
                'qty_shipped': bi.get('qty_shipped', 0), 'ordered_qty': bi.get('ordered_qty', 0)})
    for poi_id in po_item_ids:
        ris = await db.production_return_items.find({'po_item_id': poi_id}, {'_id': 0}).to_list(None)
        for ri in ris:
            ret = await db.production_returns.find_one({'id': ri.get('return_id')}, {'_id': 0})
            timeline.append({'step': 'Production Return',
                'event': 'Retur Produksi',
                'details': f"Return {(ret or {}).get('return_number', '')} - {ri.get('return_qty', 0)} pcs",
                'date': serialize_doc((ret or {}).get('return_date')),
                'module': 'production-returns', 'return_number': (ret or {}).get('return_number', ''),
                'return_qty': ri.get('return_qty', 0), 'status': (ret or {}).get('status', '')})
    timeline.sort(key=lambda x: x.get('date', '') or '')
    # Build PO info
    po_info = []
    for pid in po_ids:
        po = po_details.get(pid, {})
        po_info.append({'po_id': pid, 'po_number': po.get('po_number', ''),
            'customer_name': po.get('customer_name', ''), 'vendor_name': po.get('vendor_name', ''),
            'status': po.get('status', ''), 'deadline': serialize_doc(po.get('deadline'))})
    return {
        'serial_number': serial, 'po_item_count': len(po_items),
        'po_count': len(po_ids), 'po_info': po_info,
        'summary': {
            'buyer': ', '.join(filter(None, buyer_names)),
            'vendors': ', '.join(filter(None, vendors_set)),
            'total_ordered': totals['ordered'], 'total_produced': totals['produced'],
            'total_not_produced': totals['not_produced'], 'total_shipped': totals['shipped'],
            'total_not_shipped': totals['not_shipped'],
            'all_serials': list(set(i.get('serial_number', '') for i in all_po_items if i.get('serial_number'))),
        },
        'all_items': summary_items, 'timeline': timeline
    }


# ─── REPORTS ─────────────────────────────────────────────────────────────────
@router.get("/reports/{report_type}")
async def get_report(report_type: str, request: Request):
    await require_auth(request)
    db = get_db()
    sp = request.query_params
    if report_type == 'production':
        po_query = {}
        if sp.get('status'): po_query['status'] = sp['status']
        pos = await db.production_pos.find(po_query, {'_id': 0}).sort('created_at', -1).to_list(None)
        rows = []
        for po in pos:
            if sp.get('vendor_id') and po.get('vendor_id') != sp['vendor_id']: continue
            items = await db.po_items.find({'po_id': po['id']}).to_list(None)
            for item in items:
                if sp.get('serial_number') and item.get('serial_number') != sp['serial_number']: continue
                # Get actual produced qty from production job items
                ji_list = await db.production_job_items.find({'po_item_id': item['id']}).to_list(None)
                produced_qty = sum(j.get('produced_qty', 0) for j in ji_list)
                # Also check orphaned child items by sku+size+color
                orphan_ji = await db.production_job_items.find({
                    '$or': [{'po_item_id': None}, {'po_item_id': ''}, {'po_item_id': {'$exists': False}}],
                    'sku': item.get('sku', ''), 'size': item.get('size', ''), 'color': item.get('color', '')
                }).to_list(None)
                counted_ids = {j['id'] for j in ji_list}
                for oji in orphan_ji:
                    if oji['id'] not in counted_ids:
                        produced_qty += oji.get('produced_qty', 0)
                # Get shipped to buyer
                buyer_items = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
                shipped_qty = sum(bi.get('qty_shipped', 0) for bi in buyer_items)
                ordered_qty = item.get('qty', 0)
                harga = item.get('selling_price_snapshot', 0)
                hpp = item.get('cmt_price_snapshot', 0)
                rows.append({
                    'tanggal': serialize_doc(po.get('po_date', po.get('created_at'))),
                    'no_po': po.get('po_number'), 'no_seri': item.get('serial_number', ''),
                    'kode_produk': item.get('sku', ''),
                    'nama_produk': item.get('product_name', ''), 'sku': item.get('sku', ''),
                    'kategori': item.get('category', ''),
                    'size': item.get('size', ''), 'warna': item.get('color', ''),
                    'output_qty': ordered_qty,
                    'harga': harga, 'hpp': hpp,
                    'hasil_po': ordered_qty * harga,
                    'total_hpp': ordered_qty * hpp,
                    'garment': po.get('vendor_name', ''), 'po_status': po.get('status'),
                    'note': po.get('notes', ''),
                    'qty_sudah_diproduksi': produced_qty,
                    'qty_belum_diproduksi': max(0, ordered_qty - produced_qty),
                    'qty_sudah_dikirim': shipped_qty,
                })
        return rows
    if report_type == 'financial':
        inv_query = {}
        if sp.get('status'): inv_query['status'] = sp['status']
        invoices = await db.invoices.find(inv_query, {'_id': 0}).sort('created_at', -1).to_list(None)
        return serialize_doc(invoices)
    if report_type == 'shipment':
        vs = await db.vendor_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
        bs = await db.buyer_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
        rows = []
        for v in vs:
            if sp.get('vendor_id') and v.get('vendor_id') != sp['vendor_id']: continue
            items = await db.vendor_shipment_items.find({'shipment_id': v['id']}).to_list(None)
            rows.append({'direction': 'VENDOR → PRODUKSI', 'shipment_number': v.get('shipment_number'),
                         'shipment_type': v.get('shipment_type', 'NORMAL'),
                         'vendor_name': v.get('vendor_name', ''), 'status': v.get('status'),
                         'inspection_status': v.get('inspection_status', 'Pending'),
                         'date': serialize_doc(v.get('shipment_date', v.get('created_at'))),
                         'total_qty': sum(i.get('qty_sent', 0) for i in items), 'item_count': len(items)})
        for b in bs:
            if sp.get('vendor_id') and b.get('vendor_id') != sp['vendor_id']: continue
            items = await db.buyer_shipment_items.find({'shipment_id': b['id']}).to_list(None)
            rows.append({'direction': 'PRODUKSI → BUYER', 'shipment_number': b.get('shipment_number'),
                         'shipment_type': 'NORMAL', 'vendor_name': b.get('vendor_name', ''),
                         'status': b.get('status', b.get('ship_status', '')),
                         'date': serialize_doc(b.get('created_at')),
                         'total_qty': sum(i.get('qty_shipped', 0) for i in items), 'item_count': len(items)})
        return rows
    if report_type == 'progress':
        progs = await db.production_progress.find({}, {'_id': 0}).sort('progress_date', 1).to_list(None)
        rows = []
        # Track cumulative per po_item_id (or job_item_id)
        cumulative_produced = {}
        for p in progs:
            ji = await db.production_job_items.find_one({'id': p.get('job_item_id')}) if p.get('job_item_id') else None
            job = await db.production_jobs.find_one({'id': p.get('job_id')}) if p.get('job_id') else None
            if sp.get('vendor_id') and (job or {}).get('vendor_id') != sp['vendor_id']: continue
            # Track cumulative produced per po_item_id
            poi_id = (ji or {}).get('po_item_id') or p.get('job_item_id', '')
            if poi_id not in cumulative_produced:
                cumulative_produced[poi_id] = 0
            cumulative_produced[poi_id] += p.get('completed_quantity', 0)
            # Get cumulative shipped for this po_item_id
            cum_shipped = 0
            if (ji or {}).get('po_item_id'):
                buyer_items = await db.buyer_shipment_items.find({'po_item_id': ji['po_item_id']}).to_list(None)
                cum_shipped = sum(bi.get('qty_shipped', 0) for bi in buyer_items)
            rows.append({
                'date': serialize_doc(p.get('progress_date')),
                'job_number': (job or {}).get('job_number', ''),
                'po_number': (job or {}).get('po_number', ''),
                'vendor_name': (job or {}).get('vendor_name', ''),
                'vendor': (job or {}).get('vendor_name', ''),
                'serial_number': (ji or {}).get('serial_number', ''),
                'sku': (ji or {}).get('sku', p.get('sku', '')),
                'product_name': (ji or {}).get('product_name', p.get('product_name', '')),
                'qty_progress': p.get('completed_quantity', 0),
                'cumulative_produced': cumulative_produced[poi_id],
                'cumulative_shipped': cum_shipped,
                'status': (job or {}).get('status', ''),
                'notes': p.get('notes', ''),
                'operator': p.get('recorded_by', ''),
                'recorded_by': p.get('recorded_by', '')
            })
        # Reverse to show newest first
        rows.reverse()
        return rows
    if report_type == 'defect':
        defects = await db.material_defect_reports.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
        rows = []
        for d in defects:
            if sp.get('vendor_id') and d.get('vendor_id') != sp['vendor_id']: continue
            rows.append({
                'date': serialize_doc(d.get('report_date', d.get('created_at'))),
                'vendor_id': d.get('vendor_id'), 'sku': d.get('sku', ''),
                'product_name': d.get('product_name', ''),
                'size': d.get('size', ''), 'color': d.get('color', ''),
                'defect_qty': d.get('defect_qty', 0), 'defect_type': d.get('defect_type', ''),
                'description': d.get('description', ''), 'status': d.get('status', '')
            })
        return rows
    if report_type == 'return':
        returns = await db.production_returns.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
        rows = []
        for r in returns:
            items = await db.production_return_items.find({'return_id': r['id']}).to_list(None)
            rows.append({
                'return_number': r.get('return_number', ''),
                'po_number': r.get('reference_po_number', ''),
                'customer_name': r.get('customer_name', ''),
                'return_date': serialize_doc(r.get('return_date')),
                'total_qty': sum(i.get('return_qty', 0) for i in items),
                'item_count': len(items), 'reason': r.get('return_reason', ''),
                'status': r.get('status', ''), 'notes': r.get('notes', '')
            })
        return rows
    if report_type == 'missing-material':
        reqs = await db.material_requests.find({'request_type': 'ADDITIONAL'}, {'_id': 0}).sort('created_at', -1).to_list(None)
        rows = []
        for r in reqs:
            if sp.get('vendor_id') and r.get('vendor_id') != sp['vendor_id']: continue
            # Get request items for detail
            req_items = r.get('items', [])
            if not req_items:
                # Try to get items from a separate collection if stored there
                req_items_db = await db.material_request_items.find({'request_id': r['id']}).to_list(None)
                if req_items_db:
                    req_items = req_items_db
            if req_items:
                for ri in req_items:
                    rows.append({
                        'request_number': r.get('request_number', ''), 'request_type': r.get('request_type'),
                        'vendor_name': r.get('vendor_name', ''), 'po_number': r.get('po_number', ''),
                        'serial_number': ri.get('serial_number', r.get('serial_number', '')),
                        'sku': ri.get('sku', ''),
                        'requested_qty': ri.get('requested_qty', ri.get('qty', 0)),
                        'total_requested_qty': r.get('total_requested_qty', 0),
                        'reason': r.get('reason', ''), 'status': r.get('status', ''),
                        'child_shipment_number': r.get('child_shipment_number', ''),
                        'created_at': serialize_doc(r.get('created_at'))
                    })
            else:
                rows.append({
                    'request_number': r.get('request_number', ''), 'request_type': r.get('request_type'),
                    'vendor_name': r.get('vendor_name', ''), 'po_number': r.get('po_number', ''),
                    'serial_number': r.get('serial_number', ''),
                    'sku': r.get('sku', ''),
                    'requested_qty': r.get('total_requested_qty', 0),
                    'total_requested_qty': r.get('total_requested_qty', 0),
                    'reason': r.get('reason', ''), 'status': r.get('status', ''),
                    'child_shipment_number': r.get('child_shipment_number', ''),
                    'created_at': serialize_doc(r.get('created_at'))
                })
        return rows
    if report_type == 'replacement':
        reqs = await db.material_requests.find({'request_type': 'REPLACEMENT'}, {'_id': 0}).sort('created_at', -1).to_list(None)
        rows = []
        for r in reqs:
            if sp.get('vendor_id') and r.get('vendor_id') != sp['vendor_id']: continue
            req_items = r.get('items', [])
            if not req_items:
                req_items_db = await db.material_request_items.find({'request_id': r['id']}).to_list(None)
                if req_items_db:
                    req_items = req_items_db
            if req_items:
                for ri in req_items:
                    rows.append({
                        'request_number': r.get('request_number', ''), 'request_type': r.get('request_type'),
                        'vendor_name': r.get('vendor_name', ''), 'po_number': r.get('po_number', ''),
                        'serial_number': ri.get('serial_number', r.get('serial_number', '')),
                        'sku': ri.get('sku', ''),
                        'requested_qty': ri.get('requested_qty', ri.get('qty', 0)),
                        'total_requested_qty': r.get('total_requested_qty', 0),
                        'reason': r.get('reason', ''), 'status': r.get('status', ''),
                        'child_shipment_number': r.get('child_shipment_number', ''),
                        'created_at': serialize_doc(r.get('created_at'))
                    })
            else:
                rows.append({
                    'request_number': r.get('request_number', ''), 'request_type': r.get('request_type'),
                    'vendor_name': r.get('vendor_name', ''), 'po_number': r.get('po_number', ''),
                    'serial_number': r.get('serial_number', ''),
                    'sku': r.get('sku', ''),
                    'requested_qty': r.get('total_requested_qty', 0),
                    'total_requested_qty': r.get('total_requested_qty', 0),
                    'reason': r.get('reason', ''), 'status': r.get('status', ''),
                    'child_shipment_number': r.get('child_shipment_number', ''),
                    'created_at': serialize_doc(r.get('created_at'))
                })
        return rows
    if report_type == 'accessory':
        acc_ships = await db.accessory_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
        rows = []
        for s in acc_ships:
            if sp.get('vendor_id') and s.get('vendor_id') != sp['vendor_id']: continue
            items = await db.accessory_shipment_items.find({'shipment_id': s['id']}).to_list(None)
            for item in items:
                rows.append({
                    'shipment_number': s.get('shipment_number', ''),
                    'vendor_name': s.get('vendor_name', ''), 'po_number': s.get('po_number', ''),
                    'date': serialize_doc(s.get('shipment_date')),
                    'accessory_name': item.get('accessory_name', ''), 'accessory_code': item.get('accessory_code', ''),
                    'qty_sent': item.get('qty_sent', 0), 'unit': item.get('unit', 'pcs'),
                    'status': s.get('status', ''), 'inspection_status': s.get('inspection_status', 'Pending')
                })
        return rows
    return {'error': 'Unknown report type', 'available_types': [
        'production', 'financial', 'shipment', 'progress', 'defect', 'return',
        'missing-material', 'replacement', 'accessory']}


# ─── IMPORT DATA ─────────────────────────────────────────────────────────────
@router.post("/import-data")
async def import_data(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    import_type = body.get('type', '')
    data_rows = body.get('data', [])
    imported = 0
    errors = []
    if import_type == 'products':
        for row in data_rows:
            try:
                prod_id = new_id()
                prod = {'id': prod_id, 'product_code': row.get('product_code', ''),
                        'product_name': row.get('product_name', ''), 'category': row.get('category', ''),
                        'cmt_price': float(row.get('cmt_price', 0) or 0),
                        'selling_price': float(row.get('selling_price', 0) or 0),
                        'status': 'active', 'created_at': now(), 'updated_at': now()}
                await db.products.insert_one(prod)
                # Import variants if provided
                for v in row.get('variants', []):
                    await db.product_variants.insert_one({
                        'id': new_id(), 'product_id': prod_id,
                        'product_code': prod['product_code'], 'product_name': prod['product_name'],
                        'sku': v.get('sku', ''), 'size': v.get('size', ''), 'color': v.get('color', ''),
                        'status': 'active', 'created_at': now()})
                imported += 1
            except Exception as e: errors.append(f"Row {imported+1}: {str(e)}")
    elif import_type == 'garments':
        for row in data_rows:
            try:
                gid = new_id()
                code_slug = (row.get('garment_code', gid)).lower()
                code_slug = ''.join(c for c in code_slug if c.isalnum())
                email = f"vendor.{code_slug}@garment.com"
                raw_pw = generate_password(10)
                await db.users.insert_one({'id': new_id(), 'name': row.get('garment_name', ''),
                    'email': email, 'password': hash_password(raw_pw), 'role': 'vendor',
                    'vendor_id': gid, 'status': 'active', 'created_at': now(), 'updated_at': now()})
                await db.garments.insert_one({'id': gid, **row, 'status': 'active',
                    'login_email': email, 'vendor_password_plain': raw_pw,
                    'created_at': now(), 'updated_at': now()})
                imported += 1
            except Exception as e: errors.append(f"Row {imported+1}: {str(e)}")
    elif import_type == 'production-pos':
        for row in data_rows:
            try:
                vendor_name = ''
                if row.get('vendor_id'):
                    vd = await db.garments.find_one({'id': row['vendor_id']})
                    vendor_name = (vd or {}).get('garment_name', '')
                po_id = new_id()
                po = {'id': po_id, 'po_number': row.get('po_number', ''),
                      'customer_name': row.get('customer_name', ''),
                      'vendor_id': row.get('vendor_id'), 'vendor_name': vendor_name,
                      'po_date': parse_date(row.get('po_date')) or now(),
                      'deadline': parse_date(row.get('deadline')),
                      'status': 'Draft', 'notes': row.get('notes', ''),
                      'created_by': user['name'], 'created_at': now(), 'updated_at': now()}
                await db.production_pos.insert_one(po)
                for item in row.get('items', []):
                    await db.po_items.insert_one({
                        'id': new_id(), 'po_id': po_id, 'po_number': row['po_number'],
                        'product_name': item.get('product_name', ''),
                        'sku': item.get('sku', ''), 'size': item.get('size', ''),
                        'color': item.get('color', ''), 'serial_number': item.get('serial_number', ''),
                        'qty': int(item.get('qty', 0) or 0),
                        'selling_price_snapshot': float(item.get('selling_price', 0) or 0),
                        'cmt_price_snapshot': float(item.get('cmt_price', 0) or 0),
                        'created_at': now()})
                imported += 1
            except Exception as e: errors.append(f"Row {imported+1}: {str(e)}")
    elif import_type == 'accessories':
        for row in data_rows:
            try:
                await db.accessories.insert_one({'id': new_id(), 'name': row.get('name', ''),
                    'code': row.get('code', ''), 'category': row.get('category', ''),
                    'unit': row.get('unit', 'pcs'), 'description': row.get('description', ''),
                    'status': 'active', 'created_at': now(), 'updated_at': now()})
                imported += 1
            except Exception as e: errors.append(f"Row {imported+1}: {str(e)}")
    else:
        raise HTTPException(400, f"Unknown import type: {import_type}")
    await log_activity(user['id'], user['name'], 'Import', import_type, f"Imported {imported} records")
    return {'imported': imported, 'errors': errors, 'type': import_type}

@router.get("/import-template")
async def import_template(request: Request):
    await require_auth(request)
    ttype = request.query_params.get('type', '')
    templates = {
        'products': {'columns': ['product_code', 'product_name', 'category', 'cmt_price', 'selling_price'],
                     'variant_columns': ['sku', 'size', 'color'], 'example': {'product_code': 'PRD-001', 'product_name': 'T-Shirt Basic', 'category': 'Shirt', 'cmt_price': 5000, 'selling_price': 15000}},
        'garments': {'columns': ['garment_code', 'garment_name', 'location', 'contact_person', 'phone', 'monthly_capacity'],
                     'example': {'garment_code': 'VND-001', 'garment_name': 'PT Garmen Jaya', 'location': 'Jakarta', 'contact_person': 'Budi', 'phone': '08123456789'}},
        'production-pos': {'columns': ['po_number', 'customer_name', 'vendor_id', 'po_date', 'deadline', 'notes'],
                           'item_columns': ['product_name', 'sku', 'size', 'color', 'serial_number', 'qty', 'selling_price', 'cmt_price'],
                           'example': {'po_number': 'PO-001', 'customer_name': 'Buyer Corp'}},
        'accessories': {'columns': ['code', 'name', 'category', 'unit', 'description'],
                        'example': {'code': 'ACC-001', 'name': 'Kancing', 'category': 'Trimming', 'unit': 'pcs'}},
    }
    if ttype not in templates:
        return {'available_types': list(templates.keys())}
    return templates[ttype]


# ─── EXPORT EXCEL ────────────────────────────────────────────────────────────
@router.get("/export-excel")
async def export_excel(request: Request):
    user = await require_auth(request)
    db = get_db()
    sp = request.query_params
    export_type = sp.get('type', '')
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        if export_type == 'production-pos':
            ws.title = "Production POs"
            headers = ['No', 'PO Number', 'Customer', 'Vendor', 'PO Date', 'Deadline', 'Status', 'Serial', 'SKU', 'Product', 'Size', 'Color', 'Qty', 'Selling Price', 'CMT Price']
            ws.append(headers)
            pos = await db.production_pos.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
            row_num = 1
            for po in pos:
                items = await db.po_items.find({'po_id': po['id']}).to_list(None)
                for item in items:
                    ws.append([row_num, po.get('po_number'), po.get('customer_name'), po.get('vendor_name'),
                               str(po.get('po_date', ''))[:10], str(po.get('deadline', ''))[:10], po.get('status'),
                               item.get('serial_number', ''), item.get('sku', ''), item.get('product_name', ''),
                               item.get('size', ''), item.get('color', ''), item.get('qty', 0),
                               item.get('selling_price_snapshot', 0), item.get('cmt_price_snapshot', 0)])
                    row_num += 1
        elif export_type == 'vendor-shipments':
            ws.title = "Vendor Shipments"
            headers = ['No', 'Shipment Number', 'Vendor', 'Type', 'Date', 'Status', 'Inspection', 'SKU', 'Product', 'Size', 'Color', 'Qty Sent', 'Ordered Qty']
            ws.append(headers)
            ships = await db.vendor_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
            row_num = 1
            for s in ships:
                items = await db.vendor_shipment_items.find({'shipment_id': s['id']}).to_list(None)
                for item in items:
                    ws.append([row_num, s.get('shipment_number'), s.get('vendor_name'), s.get('shipment_type', 'NORMAL'),
                               str(s.get('shipment_date', ''))[:10], s.get('status'), s.get('inspection_status', 'Pending'),
                               item.get('sku', ''), item.get('product_name', ''), item.get('size', ''), item.get('color', ''),
                               item.get('qty_sent', 0), item.get('ordered_qty', 0)])
                    row_num += 1
        elif export_type == 'buyer-shipments':
            ws.title = "Buyer Shipments"
            headers = ['No', 'Shipment Number', 'PO Number', 'Customer', 'Vendor', 'Dispatch #', 'Dispatch Date', 'SKU', 'Product', 'Serial', 'Size', 'Color', 'Ordered Qty', 'Shipped Qty']
            ws.append(headers)
            ships = await db.buyer_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
            row_num = 1
            for s in ships:
                items = await db.buyer_shipment_items.find({'shipment_id': s['id']}).sort([('dispatch_seq', 1)]).to_list(None)
                for item in items:
                    ws.append([row_num, s.get('shipment_number'), s.get('po_number'), s.get('customer_name'),
                               s.get('vendor_name'), item.get('dispatch_seq', 1), str(item.get('dispatch_date', ''))[:10],
                               item.get('sku', ''), item.get('product_name', ''), item.get('serial_number', ''),
                               item.get('size', ''), item.get('color', ''), item.get('ordered_qty', 0), item.get('qty_shipped', 0)])
                    row_num += 1
        elif export_type == 'invoices':
            ws.title = "Invoices"
            headers = ['No', 'Invoice Number', 'Category', 'PO Number', 'Vendor/Customer', 'Total Amount', 'Total Paid', 'Remaining', 'Status', 'Created']
            ws.append(headers)
            invs = await db.invoices.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
            for idx, inv in enumerate(invs, 1):
                ws.append([idx, inv.get('invoice_number'), inv.get('invoice_category'),
                           inv.get('po_number'), inv.get('vendor_or_customer_name', inv.get('vendor_name', '')),
                           inv.get('total_amount', 0), inv.get('total_paid', 0),
                           inv.get('remaining_balance', inv.get('total_amount', 0) - inv.get('total_paid', 0)),
                           inv.get('status'), str(inv.get('created_at', ''))[:10]])
        elif export_type == 'accessories':
            ws.title = "Accessories"
            headers = ['No', 'Code', 'Name', 'Category', 'Unit', 'Status']
            ws.append(headers)
            accs = await db.accessories.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
            for idx, acc in enumerate(accs, 1):
                ws.append([idx, acc.get('code'), acc.get('name'), acc.get('category'), acc.get('unit'), acc.get('status')])
        elif export_type == 'production-report':
            ws.title = "Production Report"
            headers = ['No', 'Date', 'PO Number', 'Serial', 'Product Code', 'Product Name', 'Size', 'SKU', 'Color',
                       'Output Qty', 'Selling Price', 'CMT Price', 'Total Sales', 'Total CMT', 'Vendor', 'Notes',
                       'Qty Produced', 'Qty Not Produced', 'Qty Shipped']
            ws.append(headers)
            pos = await db.production_pos.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
            row_num = 1
            for po in pos:
                items = await db.po_items.find({'po_id': po['id']}).to_list(None)
                for item in items:
                    ji_list = await db.production_job_items.find({'po_item_id': item['id']}).to_list(None)
                    produced = sum(j.get('produced_qty', 0) for j in ji_list)
                    bi_list = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
                    shipped = sum(b.get('qty_shipped', 0) for b in bi_list)
                    qty = item.get('qty', 0)
                    sp_price = item.get('selling_price_snapshot', 0)
                    cmt = item.get('cmt_price_snapshot', 0)
                    ws.append([row_num, str(po.get('po_date', po.get('created_at', '')))[:10],
                               po.get('po_number'), item.get('serial_number', ''), item.get('sku', ''),
                               item.get('product_name', ''), item.get('size', ''), item.get('sku', ''),
                               item.get('color', ''), qty, sp_price, cmt, qty * sp_price, qty * cmt,
                               po.get('vendor_name', ''), po.get('notes', ''),
                               produced, max(0, qty - produced), shipped])
                    row_num += 1
        else:
            return JSONResponse({'error': f'Unknown export type: {export_type}', 'available_types': [
                'production-pos', 'vendor-shipments', 'buyer-shipments', 'invoices', 'accessories', 'production-report']}, status_code=400)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        filename = f"{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                 headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(500, f"Export failed: {str(e)}")


# ─── EXPORT PDF ──────────────────────────────────────────────────────────────
# PDF helper utilities
def _pdf_styles():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SmallCell', fontSize=7, leading=9, wordWrap='LTR'))
    styles.add(ParagraphStyle(name='SmallCellBold', fontSize=7, leading=9, fontName='Helvetica-Bold', wordWrap='LTR'))
    return styles

def _pdf_table_style():
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ])

def _pdf_total_row_style():
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ])

def _build_pdf(buf, elements, page=None):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    ps = landscape(A4) if page == 'landscape' else A4
    doc = SimpleDocTemplate(buf, pagesize=ps, leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    doc.build(elements)
    buf.seek(0)
    return buf

def _pdf_header(elements, company_name, title, subtitle=None, info_pairs=None):
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import mm
    styles = _pdf_styles()
    elements.append(Paragraph(f"<b>{company_name}</b>", styles['Title']))
    elements.append(Paragraph(title, styles['Heading2']))
    if subtitle:
        elements.append(Paragraph(subtitle, styles['Normal']))
    elements.append(Spacer(1, 4*mm))
    if info_pairs:
        info_data = []
        row = []
        for i, (k, v) in enumerate(info_pairs):
            row.extend([f"{k}:", str(v or '-')])
            if len(row) >= 4 or i == len(info_pairs) - 1:
                while len(row) < 4: row.append('')
                info_data.append(row)
                row = []
        if info_data:
            it = Table(info_data, colWidths=[85, 180, 85, 180])
            it.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 9), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold')]))
            elements.append(it)
            elements.append(Spacer(1, 5*mm))
    return elements

def _pdf_footer(elements):
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.units import mm
    styles = _pdf_styles()
    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph(f"<i>Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}</i>", styles['Normal']))
    return elements

def _safe_str(v, max_len=40):
    s = str(v or '')
    return s[:max_len] if len(s) > max_len else s

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

def _fmt_date(v):
    if not v: return '-'
    s = str(v)[:10]
    return s if s != 'None' else '-'

def _fmt_num(v):
    try:
        return f"{int(v):,}".replace(',', '.')
    except (ValueError, TypeError):
        return str(v or 0)

def _fmt_money(v):
    try:
        return f"Rp {int(v):,}".replace(',', '.')
    except (ValueError, TypeError):
        return 'Rp 0'


# ─── PDF Export Config helpers ─────────────────────────────────────────────
async def _get_pdf_config(db, pdf_type, config_id=None):
    """Get PDF export config (custom columns) if exists."""
    if config_id:
        cfg = await db.pdf_export_configs.find_one({'id': config_id})
        if cfg:
            return cfg
    # Try default for this type
    cfg = await db.pdf_export_configs.find_one({'pdf_type': pdf_type, 'is_default': True})
    return cfg

def _filter_columns(headers, all_col_keys, selected_keys, data_rows):
    """Filter table columns based on selected keys from config."""
    if not selected_keys:
        return headers, data_rows
    indices = [i for i, k in enumerate(all_col_keys) if k in selected_keys]
    if not indices:
        return headers, data_rows
    new_headers = [headers[i] for i in indices]
    new_rows = [[row[i] if i < len(row) else '' for i in indices] for row in data_rows]
    return new_headers, new_rows

@router.get("/export-pdf")
async def export_pdf(request: Request):
    user = await require_auth(request)
    db = get_db()
    sp = request.query_params
    pdf_type = sp.get('type', '')
    config_id = sp.get('config_id')
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        buf = BytesIO()
        styles = _pdf_styles()
        settings = await db.company_settings.find_one({'type': 'general'}) or {}
        company_name = settings.get('company_name', 'Garment ERP')
        pdf_header_1 = settings.get('pdf_header_line1', '')
        pdf_header_2 = settings.get('pdf_header_line2', '')
        pdf_footer = settings.get('pdf_footer_text', '')

        # Get optional custom column config
        config = await _get_pdf_config(db, pdf_type, config_id)

        # ──── PRODUCTION PO (SPP - Surat Perintah Produksi) ────
        if pdf_type == 'production-po':
            po_id = sp.get('id')
            if not po_id: raise HTTPException(400, 'id required')
            po = await db.production_pos.find_one({'id': po_id}, {'_id': 0})
            if not po: raise HTTPException(404, 'PO not found')
            items = await db.po_items.find({'po_id': po_id}, {'_id': 0}).to_list(None)
            if not items: raise HTTPException(404, 'No items in this PO')
            accessories = await db.po_accessories.find({'po_id': po_id}, {'_id': 0}).to_list(None)
            elements = []
            _pdf_header(elements, company_name, 'Surat Perintah Produksi (SPP)', info_pairs=[
                ('No PO', po.get('po_number', '')), ('Customer', po.get('customer_name', '')),
                ('Vendor', po.get('vendor_name', '')), ('Status', po.get('status', '')),
                ('Tanggal PO', _fmt_date(po.get('po_date'))), ('Deadline', _fmt_date(po.get('deadline'))),
                ('Delivery Deadline', _fmt_date(po.get('delivery_deadline'))),
            ])
            # Items table
            all_col_keys = ['no', 'serial', 'product', 'sku', 'size', 'color', 'qty', 'price', 'cmt']
            headers = ['No', 'Serial No', 'Product', 'SKU', 'Size', 'Color', 'Qty', 'Price', 'CMT']
            data_rows = []
            for idx, item in enumerate(items, 1):
                data_rows.append([
                    idx, _safe_str(item.get('serial_number')), _safe_str(item.get('product_name')),
                    _safe_str(item.get('sku')), _safe_str(item.get('size')), _safe_str(item.get('color')),
                    item.get('qty', 0), _fmt_money(item.get('selling_price_snapshot', 0)),
                    _fmt_money(item.get('cmt_price_snapshot', 0))
                ])
            if config and config.get('columns'):
                headers, data_rows = _filter_columns(headers, all_col_keys, config['columns'], data_rows)
            td = [headers] + data_rows
            total_qty = sum(i.get('qty', 0) for i in items)
            total_row = [''] * len(headers)
            total_row[-3] = 'TOTAL'
            total_row[-2] = total_qty if 'qty' in (config or {}).get('columns', all_col_keys) else ''
            td.append(total_row)
            cw = [max(25, int(530 / len(headers)))] * len(headers)
            t = Table(td, colWidths=cw, repeatRows=1)
            t.setStyle(_pdf_table_style())
            t.setStyle(_pdf_total_row_style())
            elements.append(t)
            # Accessories section
            if accessories:
                elements.append(Spacer(1, 6*mm))
                elements.append(Paragraph("<b>Accessories Required:</b>", styles['Heading3']))
                acc_td = [['No', 'Accessory', 'Code', 'Qty Needed', 'Unit', 'Notes']]
                for idx, acc in enumerate(accessories, 1):
                    acc_td.append([idx, acc.get('accessory_name', ''), acc.get('accessory_code', ''),
                                   acc.get('qty_needed', 0), acc.get('unit', 'pcs'), _safe_str(acc.get('notes', ''))])
                at = Table(acc_td, colWidths=[25, 120, 80, 70, 50, 120])
                at.setStyle(_pdf_table_style())
                elements.append(at)
            if po.get('notes'):
                elements.append(Spacer(1, 4*mm))
                elements.append(Paragraph(f"<b>Notes:</b> {po.get('notes', '')}", styles['Normal']))
            _pdf_footer(elements)
            _build_pdf(buf, elements, page='landscape')
            fname = f"SPP-{po.get('po_number', 'unknown')}.pdf"
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename={fname}"})

        # ──── VENDOR SHIPMENT (Surat Jalan Material) ────
        elif pdf_type == 'vendor-shipment':
            sid = sp.get('id')
            if not sid: raise HTTPException(400, 'id required')
            ship = await db.vendor_shipments.find_one({'id': sid}, {'_id': 0})
            if not ship: raise HTTPException(404, 'Shipment not found')
            items = await db.vendor_shipment_items.find({'shipment_id': sid}, {'_id': 0}).to_list(None)
            elements = []
            _pdf_header(elements, company_name, 'Surat Jalan Material (Vendor Shipment)', info_pairs=[
                ('Shipment No', ship.get('shipment_number', '')), ('Vendor', ship.get('vendor_name', '')),
                ('Type', ship.get('shipment_type', 'NORMAL')), ('Status', ship.get('status', '')),
                ('Date', _fmt_date(ship.get('shipment_date'))),
                ('Inspection', ship.get('inspection_status', 'Pending')),
            ])
            all_col_keys = ['no', 'po', 'serial', 'product', 'sku', 'size', 'color', 'qty_sent']
            headers = ['No', 'PO', 'Serial', 'Product', 'SKU', 'Size', 'Color', 'Qty Sent']
            data_rows = []
            for idx, i in enumerate(items, 1):
                data_rows.append([idx, _safe_str(i.get('po_number')), _safe_str(i.get('serial_number')),
                    _safe_str(i.get('product_name')), _safe_str(i.get('sku')),
                    _safe_str(i.get('size')), _safe_str(i.get('color')), i.get('qty_sent', 0)])
            if config and config.get('columns'):
                headers, data_rows = _filter_columns(headers, all_col_keys, config['columns'], data_rows)
            td = [headers] + data_rows
            total_row = [''] * len(headers)
            total_row[-2] = 'TOTAL'
            total_row[-1] = sum(i.get('qty_sent', 0) for i in items)
            td.append(total_row)
            cw = [max(25, int(445 / len(headers)))] * len(headers)
            t = Table(td, colWidths=cw, repeatRows=1)
            t.setStyle(_pdf_table_style())
            t.setStyle(_pdf_total_row_style())
            elements.append(t)
            # Signature area
            elements.append(Spacer(1, 15*mm))
            sig_data = [['Pengirim (Vendor)', '', 'Penerima'], ['', '', ''], ['_________________', '', '_________________']]
            st = Table(sig_data, colWidths=[180, 100, 180])
            st.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTSIZE', (0, 0), (-1, -1), 9)]))
            elements.append(st)
            _pdf_footer(elements)
            _build_pdf(buf, elements)
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename=SJ-Material-{ship.get('shipment_number','')}.pdf"})

        # ──── VENDOR INSPECTION PDF ────
        elif pdf_type == 'vendor-inspection':
            insp_id = sp.get('id')
            if not insp_id: raise HTTPException(400, 'id required')
            insp = await db.vendor_material_inspections.find_one({'id': insp_id}, {'_id': 0})
            if not insp: raise HTTPException(404, 'Inspection not found')
            shipment = await db.vendor_shipments.find_one({'id': insp.get('shipment_id')}, {'_id': 0})
            # Get PO info
            po_id = (shipment or {}).get('po_id', '')
            if not po_id:
                first_si = await db.vendor_shipment_items.find_one({'shipment_id': insp.get('shipment_id')})
                if first_si: po_id = first_si.get('po_id', '')
            po = await db.production_pos.find_one({'id': po_id}, {'_id': 0}) if po_id else None
            # Get invoice if linked
            invoice = await db.invoices.find_one({'po_id': po_id, 'invoice_category': 'AP'}, {'_id': 0}) if po_id else None
            # Get all inspection items
            all_insp_items = await db.vendor_material_inspection_items.find({'inspection_id': insp_id}, {'_id': 0}).to_list(None)
            material_items = [i for i in all_insp_items if i.get('item_type') != 'accessory']
            accessory_items = [i for i in all_insp_items if i.get('item_type') == 'accessory']
            elements = []
            info_pairs = [
                ('No PO', (po or {}).get('po_number', '-')),
                ('No Invoice', (invoice or {}).get('invoice_number', '-')),
                ('Vendor', insp.get('vendor_name', '')),
                ('Tanggal Inspeksi', _fmt_date(insp.get('inspection_date'))),
                ('No Shipment', insp.get('shipment_number', '')),
                ('Status', insp.get('status', '')),
            ]
            _pdf_header(elements, company_name, 'Laporan Inspeksi Material (Vendor)', info_pairs=info_pairs)
            # Material items table
            if material_items:
                elements.append(Paragraph("<b>Material Items:</b>", styles['Heading3']))
                headers = ['No', 'Produk', 'SKU', 'Size', 'Warna', 'Qty Dikirim', 'Qty Diterima', 'Qty Missing', 'Catatan']
                data_rows = []
                for idx, item in enumerate(material_items, 1):
                    # Get product info for category
                    prod = await db.products.find_one({'product_name': item.get('product_name')}, {'_id': 0})
                    category = (prod or {}).get('category', '-')
                    data_rows.append([
                        idx, f"{item.get('product_name', '')}\n({category})",
                        item.get('sku', ''), item.get('size', ''), item.get('color', ''),
                        item.get('ordered_qty', 0), item.get('received_qty', 0),
                        item.get('missing_qty', 0), _safe_str(item.get('condition_notes', ''))
                    ])
                td = [headers] + data_rows
                total_row = ['', '', '', '', 'TOTAL',
                    sum(i.get('ordered_qty', 0) for i in material_items),
                    sum(i.get('received_qty', 0) for i in material_items),
                    sum(i.get('missing_qty', 0) for i in material_items), '']
                td.append(total_row)
                cw = [25, 90, 60, 40, 50, 55, 55, 55, 90]
                t = Table(td, colWidths=cw, repeatRows=1)
                t.setStyle(_pdf_table_style())
                t.setStyle(_pdf_total_row_style())
                elements.append(t)
            # Accessory items table
            if accessory_items:
                elements.append(Spacer(1, 6*mm))
                elements.append(Paragraph("<b>Aksesoris Items:</b>", styles['Heading3']))
                acc_headers = ['No', 'Aksesoris', 'Kode', 'Satuan', 'Qty Dikirim', 'Qty Diterima', 'Qty Missing', 'Catatan']
                acc_rows = []
                for idx, acc in enumerate(accessory_items, 1):
                    acc_rows.append([
                        idx, acc.get('accessory_name', ''), acc.get('accessory_code', ''),
                        acc.get('unit', 'pcs'), acc.get('ordered_qty', 0),
                        acc.get('received_qty', 0), acc.get('missing_qty', 0),
                        _safe_str(acc.get('condition_notes', ''))
                    ])
                acc_td = [acc_headers] + acc_rows
                acc_total = ['', '', '', 'TOTAL',
                    sum(a.get('ordered_qty', 0) for a in accessory_items),
                    sum(a.get('received_qty', 0) for a in accessory_items),
                    sum(a.get('missing_qty', 0) for a in accessory_items), '']
                acc_td.append(acc_total)
                acc_cw = [25, 100, 70, 45, 60, 60, 60, 90]
                at = Table(acc_td, colWidths=acc_cw, repeatRows=1)
                at.setStyle(_pdf_table_style())
                at.setStyle(_pdf_total_row_style())
                elements.append(at)
            if insp.get('overall_notes'):
                elements.append(Spacer(1, 4*mm))
                elements.append(Paragraph(f"<b>Catatan Umum:</b> {insp.get('overall_notes', '')}", styles['Normal']))
            # Signature
            elements.append(Spacer(1, 12*mm))
            sig_data = [['Inspektor', '', 'Pengirim (Vendor)'], ['', '', ''], ['_________________', '', '_________________']]
            st = Table(sig_data, colWidths=[180, 100, 180])
            st.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTSIZE', (0, 0), (-1, -1), 9)]))
            elements.append(st)
            _pdf_footer(elements)
            _build_pdf(buf, elements, page='landscape')
            fname = f"Inspeksi-{insp.get('shipment_number', 'unknown')}.pdf"
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename={fname}"})

        # ──── BUYER SHIPMENT DISPATCH ────
        elif pdf_type == 'buyer-shipment-dispatch':
            shipment_id = sp.get('shipment_id')
            dispatch_seq = int(sp.get('dispatch_seq', 0))
            if not shipment_id or not dispatch_seq:
                raise HTTPException(400, 'shipment_id and dispatch_seq required')
            bs = await db.buyer_shipments.find_one({'id': shipment_id}, {'_id': 0})
            if not bs: raise HTTPException(404, 'Buyer shipment not found')
            items = await db.buyer_shipment_items.find({
                'shipment_id': shipment_id, 'dispatch_seq': dispatch_seq
            }, {'_id': 0}).to_list(None)
            if not items: raise HTTPException(404, f'No items for dispatch #{dispatch_seq}')
            all_items = await db.buyer_shipment_items.find({'shipment_id': shipment_id}).to_list(None)
            cumulative_by_poi = {}
            for ai in all_items:
                key = ai.get('po_item_id') or ai['id']
                if key not in cumulative_by_poi:
                    cumulative_by_poi[key] = {'ordered': ai.get('ordered_qty', 0), 'shipped': 0}
                if ai.get('dispatch_seq', 1) <= dispatch_seq:
                    cumulative_by_poi[key]['shipped'] += ai.get('qty_shipped', 0)
            elements = []
            _pdf_header(elements, company_name, f'Surat Jalan Buyer — Dispatch #{dispatch_seq}', info_pairs=[
                ('Shipment No', bs.get('shipment_number', '')), ('PO Number', bs.get('po_number', '')),
                ('Customer', bs.get('customer_name', '')), ('Vendor', bs.get('vendor_name', '')),
                ('Dispatch Date', _fmt_date(items[0].get('dispatch_date', ''))), ('Dispatch #', str(dispatch_seq)),
            ])
            all_col_keys = ['no', 'serial', 'product', 'sku', 'size', 'color', 'ordered', 'this_dispatch', 'cumul_shipped', 'remaining']
            headers = ['No', 'Serial', 'Product', 'SKU', 'Size', 'Color', 'Ordered', 'This Dispatch', 'Cumul. Shipped', 'Remaining']
            data_rows = []
            for idx, item in enumerate(items, 1):
                key = item.get('po_item_id') or item['id']
                cum = cumulative_by_poi.get(key, {'ordered': 0, 'shipped': 0})
                data_rows.append([
                    idx, _safe_str(item.get('serial_number')), _safe_str(item.get('product_name')),
                    _safe_str(item.get('sku')), _safe_str(item.get('size')), _safe_str(item.get('color')),
                    item.get('ordered_qty', 0), item.get('qty_shipped', 0), cum['shipped'],
                    max(0, cum['ordered'] - cum['shipped'])
                ])
            if config and config.get('columns'):
                headers, data_rows = _filter_columns(headers, all_col_keys, config['columns'], data_rows)
            td = [headers] + data_rows
            total_this = sum(i.get('qty_shipped', 0) for i in items)
            total_cum = sum(v['shipped'] for v in cumulative_by_poi.values())
            total_ord = sum(v['ordered'] for v in cumulative_by_poi.values())
            total_row = [''] * len(headers)
            if len(total_row) >= 4:
                total_row[-4] = total_ord
                total_row[-3] = total_this
                total_row[-2] = total_cum
                total_row[-1] = max(0, total_ord - total_cum)
                total_row[-5] = 'TOTAL' if len(total_row) > 5 else ''
            td.append(total_row)
            cw = [max(25, int(680 / len(headers)))] * len(headers)
            t = Table(td, colWidths=cw, repeatRows=1)
            t.setStyle(_pdf_table_style())
            t.setStyle(_pdf_total_row_style())
            t.setStyle(TableStyle([('ALIGN', (6, 0), (-1, -1), 'RIGHT')]))
            elements.append(t)
            _pdf_footer(elements)
            _build_pdf(buf, elements, page='landscape')
            fname = f"buyer_dispatch_{bs.get('shipment_number','')}_D{dispatch_seq}.pdf"
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename={fname}"})

        # ──── BUYER SHIPMENT (Cumulative Summary - all dispatches combined) ────
        elif pdf_type == 'buyer-shipment':
            sid = sp.get('id')
            if not sid: raise HTTPException(400, 'id required')
            bs = await db.buyer_shipments.find_one({'id': sid}, {'_id': 0})
            if not bs: raise HTTPException(404, 'Buyer shipment not found')
            all_items = await db.buyer_shipment_items.find({'shipment_id': sid}, {'_id': 0}).to_list(None)
            elements = []
            total_dispatches = max((i.get('dispatch_seq', 1) for i in all_items), default=0)
            _pdf_header(elements, company_name, 'Surat Jalan Buyer — Total Kumulatif', info_pairs=[
                ('Shipment No', bs.get('shipment_number', '')), ('PO Number', bs.get('po_number', '')),
                ('Customer', bs.get('customer_name', '')), ('Vendor', bs.get('vendor_name', '')),
                ('Status', bs.get('status', bs.get('ship_status', ''))),
                ('Total Dispatch', str(total_dispatches)),
            ])
            # Build cumulative summary per po_item (not per dispatch)
            poi_cumulative = {}
            for item in all_items:
                key = item.get('po_item_id') or f"{item.get('serial_number','')}|{item.get('sku','')}|{item.get('size','')}|{item.get('color','')}"
                if key not in poi_cumulative:
                    poi_cumulative[key] = {
                        'serial_number': item.get('serial_number', ''),
                        'product_name': item.get('product_name', ''),
                        'sku': item.get('sku', ''),
                        'size': item.get('size', ''),
                        'color': item.get('color', ''),
                        'ordered_qty': item.get('ordered_qty', 0),
                        'total_shipped': 0,
                    }
                poi_cumulative[key]['total_shipped'] += item.get('qty_shipped', 0)
            if not poi_cumulative:
                elements.append(Paragraph("No dispatch items found for this shipment.", styles['Normal']))
            else:
                td = [['No', 'Serial', 'Product', 'SKU', 'Size', 'Color', 'Ordered', 'Total Shipped', 'Remaining']]
                for idx, (key, cum) in enumerate(poi_cumulative.items(), 1):
                    remaining = max(0, cum['ordered_qty'] - cum['total_shipped'])
                    td.append([idx, _safe_str(cum['serial_number']), _safe_str(cum['product_name']),
                               _safe_str(cum['sku']), _safe_str(cum['size']), _safe_str(cum['color']),
                               cum['ordered_qty'], cum['total_shipped'], remaining])
                total_ordered = sum(v['ordered_qty'] for v in poi_cumulative.values())
                total_shipped = sum(v['total_shipped'] for v in poi_cumulative.values())
                total_remaining = max(0, total_ordered - total_shipped)
                total_row = ['', '', '', '', '', 'TOTAL', total_ordered, total_shipped, total_remaining]
                td.append(total_row)
                cw = [25, 60, 100, 70, 40, 50, 55, 70, 65]
                t = Table(td, colWidths=cw, repeatRows=1)
                t.setStyle(_pdf_table_style())
                t.setStyle(_pdf_total_row_style())
                t.setStyle(TableStyle([('ALIGN', (6, 0), (-1, -1), 'RIGHT')]))
                elements.append(t)
            _pdf_footer(elements)
            _build_pdf(buf, elements, page='landscape')
            fname = f"Buyer-Shipment-{bs.get('shipment_number', sid)}-Kumulatif.pdf"
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename={fname}"})

        # ──── PRODUCTION RETURN ────
        elif pdf_type == 'production-return':
            rid = sp.get('id')
            if not rid: raise HTTPException(400, 'id required')
            ret = await db.production_returns.find_one({'id': rid}, {'_id': 0})
            if not ret: raise HTTPException(404, 'Production return not found')
            items = await db.production_return_items.find({'return_id': rid}, {'_id': 0}).to_list(None)
            elements = []
            _pdf_header(elements, company_name, 'Surat Retur Produksi', info_pairs=[
                ('Return No', ret.get('return_number', '')), ('PO Number', ret.get('reference_po_number', '')),
                ('Customer', ret.get('customer_name', '')), ('Status', ret.get('status', '')),
                ('Return Date', _fmt_date(ret.get('return_date'))), ('Reason', _safe_str(ret.get('return_reason', ''), 60)),
            ])
            if items:
                td = [['No', 'Serial', 'Product', 'SKU', 'Size', 'Color', 'Qty Returned', 'Notes']]
                for idx, i in enumerate(items, 1):
                    td.append([idx, _safe_str(i.get('serial_number')), _safe_str(i.get('product_name')),
                               _safe_str(i.get('sku')), _safe_str(i.get('size')), _safe_str(i.get('color')),
                               i.get('return_qty', 0), _safe_str(i.get('notes', ''), 30)])
                total_row = ['', '', '', '', '', 'TOTAL', sum(i.get('return_qty', 0) for i in items), '']
                td.append(total_row)
                cw = [25, 60, 100, 70, 40, 50, 65, 80]
                t = Table(td, colWidths=cw, repeatRows=1)
                t.setStyle(_pdf_table_style())
                t.setStyle(_pdf_total_row_style())
                elements.append(t)
            else:
                elements.append(Paragraph("No return items found.", styles['Normal']))
            if ret.get('notes'):
                elements.append(Spacer(1, 4*mm))
                elements.append(Paragraph(f"<b>Notes:</b> {ret.get('notes', '')}", styles['Normal']))
            _pdf_footer(elements)
            _build_pdf(buf, elements)
            fname = f"Retur-{ret.get('return_number', rid)}.pdf"
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename={fname}"})

        # ──── MATERIAL REQUEST ────
        elif pdf_type == 'material-request':
            req_id = sp.get('id')
            if not req_id: raise HTTPException(400, 'id required')
            req = await db.material_requests.find_one({'id': req_id}, {'_id': 0})
            if not req: raise HTTPException(404, 'Material request not found')
            elements = []
            req_type = req.get('request_type', 'ADDITIONAL')
            _pdf_header(elements, company_name, f'Surat Permohonan Material ({req_type})', info_pairs=[
                ('Request No', req.get('request_number', '')), ('PO Number', req.get('po_number', '')),
                ('Vendor', req.get('vendor_name', '')), ('Status', req.get('status', '')),
                ('Total Qty', req.get('total_requested_qty', 0)),
                ('Child Shipment', req.get('child_shipment_number', '-')),
            ])
            # Request items if available
            req_items = req.get('items', [])
            if req_items:
                td = [['No', 'Serial', 'Product', 'SKU', 'Size', 'Color', 'Qty Requested']]
                for idx, i in enumerate(req_items, 1):
                    td.append([idx, _safe_str(i.get('serial_number')), _safe_str(i.get('product_name')),
                               _safe_str(i.get('sku')), _safe_str(i.get('size')), _safe_str(i.get('color')),
                               i.get('qty_requested', i.get('requested_qty', 0))])
                cw = [25, 65, 110, 75, 45, 55, 70]
                t = Table(td, colWidths=cw, repeatRows=1)
                t.setStyle(_pdf_table_style())
                elements.append(t)
            else:
                elements.append(Paragraph(f"Total Requested Quantity: <b>{req.get('total_requested_qty', 0)}</b>", styles['Normal']))
            if req.get('reason'):
                elements.append(Spacer(1, 4*mm))
                elements.append(Paragraph(f"<b>Reason:</b> {req.get('reason', '')}", styles['Normal']))
            # Approval signatures
            elements.append(Spacer(1, 15*mm))
            sig_data = [['Diajukan oleh:', '', 'Disetujui oleh:'], ['', '', ''], ['_________________', '', '_________________']]
            st = Table(sig_data, colWidths=[180, 100, 180])
            st.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTSIZE', (0, 0), (-1, -1), 9)]))
            elements.append(st)
            _pdf_footer(elements)
            _build_pdf(buf, elements)
            fname = f"Permohonan-{req.get('request_number', req_id)}.pdf"
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename={fname}"})

        # ──── PRODUCTION REPORT (full) ────
        elif pdf_type == 'production-report':
            elements = []
            _pdf_header(elements, company_name, 'Laporan Produksi Lengkap')
            pos = await db.production_pos.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
            all_col_keys = ['no', 'date', 'po', 'serial', 'product', 'sku', 'size', 'color', 'qty', 'price', 'cmt', 'vendor', 'produced', 'shipped']
            headers = ['No', 'Date', 'PO', 'Serial', 'Product', 'SKU', 'Size', 'Color', 'Qty', 'Price', 'CMT', 'Vendor', 'Produced', 'Shipped']
            data_rows = []
            rn = 1
            for po in pos:
                items = await db.po_items.find({'po_id': po['id']}).to_list(None)
                for item in items:
                    ji = await db.production_job_items.find({'po_item_id': item['id']}).to_list(None)
                    produced = sum(j.get('produced_qty', 0) for j in ji)
                    bi = await db.buyer_shipment_items.find({'po_item_id': item['id']}).to_list(None)
                    shipped = sum(b.get('qty_shipped', 0) for b in bi)
                    data_rows.append([rn, _fmt_date(po.get('po_date')), _safe_str(po.get('po_number'), 15),
                        _safe_str(item.get('serial_number'), 15), _safe_str(item.get('product_name'), 20),
                        _safe_str(item.get('sku'), 15), _safe_str(item.get('size'), 8), _safe_str(item.get('color'), 10),
                        item.get('qty', 0), _fmt_money(item.get('selling_price_snapshot', 0)),
                        _fmt_money(item.get('cmt_price_snapshot', 0)),
                        _safe_str(po.get('vendor_name'), 15), produced, shipped])
                    rn += 1
            if config and config.get('columns'):
                headers, data_rows = _filter_columns(headers, all_col_keys, config['columns'], data_rows)
            if not data_rows:
                elements.append(Paragraph("No production data found.", styles['Normal']))
            else:
                td = [headers] + data_rows
                cw = [max(22, int(680 / len(headers)))] * len(headers)
                t = Table(td, colWidths=cw, repeatRows=1)
                t.setStyle(_pdf_table_style())
                t.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 7)]))
                elements.append(t)
            _pdf_footer(elements)
            _build_pdf(buf, elements, page='landscape')
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename=production_report_{datetime.now().strftime('%Y%m%d')}.pdf"})

        # ──── REPORT-* (Reuse /api/reports/{type} query logic) ────
        elif pdf_type.startswith('report-'):
            report_type = pdf_type[7:]  # strip 'report-' prefix
            valid_report_types = ['production', 'progress', 'financial', 'shipment', 'defect', 'return', 'missing-material', 'replacement', 'accessory']
            if report_type not in valid_report_types:
                return JSONResponse({'error': f'Unknown report type: {report_type}', 'available': valid_report_types}, status_code=400)

            # ── Get report data by reusing the same query logic as /api/reports/{type} ──
            report_data = []

            if report_type == 'production':
                po_query = {}
                if sp.get('status'): po_query['status'] = sp['status']
                pos = await db.production_pos.find(po_query, {'_id': 0}).sort('created_at', -1).to_list(None)
                for po in pos:
                    if sp.get('vendor_id') and po.get('vendor_id') != sp['vendor_id']: continue
                    items = await db.po_items.find({'po_id': po['id']}).to_list(None)
                    for item in items:
                        if sp.get('serial_number') and item.get('serial_number') != sp['serial_number']: continue
                        report_data.append({
                            'tanggal': _fmt_date(po.get('po_date', po.get('created_at'))),
                            'no_po': po.get('po_number', ''), 'no_seri': item.get('serial_number', ''),
                            'nama_produk': item.get('product_name', ''), 'sku': item.get('sku', ''),
                            'size': item.get('size', ''), 'warna': item.get('color', ''),
                            'output_qty': item.get('qty', 0),
                            'harga': item.get('selling_price_snapshot', 0), 'hpp': item.get('cmt_price_snapshot', 0),
                            'garment': po.get('vendor_name', ''), 'po_status': po.get('status', ''),
                        })
                headers = ['No', 'Tanggal', 'No PO', 'Serial', 'Produk', 'SKU', 'Size', 'Warna', 'Qty', 'Harga', 'HPP/CMT', 'Vendor', 'Status']
                all_col_keys = ['no', 'tanggal', 'no_po', 'no_seri', 'nama_produk', 'sku', 'size', 'warna', 'output_qty', 'harga', 'hpp', 'garment', 'po_status']

            elif report_type == 'progress':
                progs = await db.production_progress.find({}, {'_id': 0}).sort('progress_date', -1).to_list(None)
                for p in progs:
                    ji = await db.production_job_items.find_one({'id': p.get('job_item_id')}) if p.get('job_item_id') else None
                    job = await db.production_jobs.find_one({'id': p.get('job_id')}) if p.get('job_id') else None
                    if sp.get('vendor_id') and (job or {}).get('vendor_id') != sp['vendor_id']: continue
                    report_data.append({
                        'date': _fmt_date(p.get('progress_date')),
                        'job_number': (job or {}).get('job_number', ''),
                        'po_number': (job or {}).get('po_number', ''),
                        'vendor_name': (job or {}).get('vendor_name', ''),
                        'serial_number': (ji or {}).get('serial_number', ''),
                        'sku': (ji or {}).get('sku', p.get('sku', '')),
                        'product_name': (ji or {}).get('product_name', p.get('product_name', '')),
                        'qty_progress': p.get('completed_quantity', 0),
                        'notes': p.get('notes', ''), 'recorded_by': p.get('recorded_by', '')
                    })
                headers = ['No', 'Tanggal', 'Job', 'PO', 'Vendor', 'Serial', 'SKU', 'Produk', 'Qty', 'Catatan', 'Dicatat oleh']
                all_col_keys = ['no', 'date', 'job_number', 'po_number', 'vendor_name', 'serial_number', 'sku', 'product_name', 'qty_progress', 'notes', 'recorded_by']

            elif report_type == 'financial':
                inv_query = {}
                if sp.get('status'): inv_query['status'] = sp['status']
                invoices = await db.invoices.find(inv_query, {'_id': 0}).sort('created_at', -1).to_list(None)
                for inv in invoices:
                    report_data.append({
                        'invoice_number': inv.get('invoice_number', ''),
                        'category': inv.get('invoice_category', ''),
                        'po_number': inv.get('po_number', ''),
                        'vendor_or_buyer': inv.get('vendor_name', inv.get('customer_name', '')),
                        'amount': inv.get('amount', 0),
                        'paid': inv.get('paid_amount', 0),
                        'remaining': inv.get('remaining_amount', inv.get('amount', 0) - inv.get('paid_amount', 0)),
                        'status': inv.get('status', ''),
                        'date': _fmt_date(inv.get('invoice_date', inv.get('created_at'))),
                    })
                headers = ['No', 'Invoice No', 'Category', 'PO', 'Vendor/Buyer', 'Amount', 'Paid', 'Remaining', 'Status', 'Date']
                all_col_keys = ['no', 'invoice_number', 'category', 'po_number', 'vendor_or_buyer', 'amount', 'paid', 'remaining', 'status', 'date']

            elif report_type == 'shipment':
                vs = await db.vendor_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
                bsh = await db.buyer_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
                for v in vs:
                    if sp.get('vendor_id') and v.get('vendor_id') != sp['vendor_id']: continue
                    items = await db.vendor_shipment_items.find({'shipment_id': v['id']}).to_list(None)
                    report_data.append({
                        'direction': 'VENDOR', 'shipment_number': v.get('shipment_number', ''),
                        'shipment_type': v.get('shipment_type', 'NORMAL'), 'vendor_name': v.get('vendor_name', ''),
                        'status': v.get('status', ''), 'inspection': v.get('inspection_status', 'Pending'),
                        'date': _fmt_date(v.get('shipment_date', v.get('created_at'))),
                        'total_qty': sum(i.get('qty_sent', 0) for i in items), 'items': len(items)
                    })
                for b in bsh:
                    if sp.get('vendor_id') and b.get('vendor_id') != sp['vendor_id']: continue
                    items = await db.buyer_shipment_items.find({'shipment_id': b['id']}).to_list(None)
                    report_data.append({
                        'direction': 'BUYER', 'shipment_number': b.get('shipment_number', ''),
                        'shipment_type': 'NORMAL', 'vendor_name': b.get('vendor_name', ''),
                        'status': b.get('status', b.get('ship_status', '')), 'inspection': '-',
                        'date': _fmt_date(b.get('created_at')),
                        'total_qty': sum(i.get('qty_shipped', 0) for i in items), 'items': len(items)
                    })
                headers = ['No', 'Direction', 'Shipment No', 'Type', 'Vendor', 'Status', 'Inspection', 'Date', 'Qty', 'Items']
                all_col_keys = ['no', 'direction', 'shipment_number', 'shipment_type', 'vendor_name', 'status', 'inspection', 'date', 'total_qty', 'items']

            elif report_type == 'defect':
                defects = await db.material_defect_reports.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
                for d in defects:
                    if sp.get('vendor_id') and d.get('vendor_id') != sp['vendor_id']: continue
                    report_data.append({
                        'date': _fmt_date(d.get('report_date', d.get('created_at'))),
                        'sku': d.get('sku', ''), 'product_name': d.get('product_name', ''),
                        'size': d.get('size', ''), 'color': d.get('color', ''),
                        'defect_qty': d.get('defect_qty', 0), 'defect_type': d.get('defect_type', ''),
                        'description': d.get('description', ''), 'status': d.get('status', '')
                    })
                headers = ['No', 'Tanggal', 'SKU', 'Produk', 'Size', 'Warna', 'Qty Defect', 'Tipe', 'Deskripsi', 'Status']
                all_col_keys = ['no', 'date', 'sku', 'product_name', 'size', 'color', 'defect_qty', 'defect_type', 'description', 'status']

            elif report_type == 'return':
                returns = await db.production_returns.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
                for r in returns:
                    items = await db.production_return_items.find({'return_id': r['id']}).to_list(None)
                    report_data.append({
                        'return_number': r.get('return_number', ''), 'po_number': r.get('reference_po_number', ''),
                        'customer_name': r.get('customer_name', ''), 'return_date': _fmt_date(r.get('return_date')),
                        'total_qty': sum(i.get('return_qty', 0) for i in items), 'item_count': len(items),
                        'reason': r.get('return_reason', ''), 'status': r.get('status', ''),
                    })
                headers = ['No', 'Return No', 'PO', 'Customer', 'Date', 'Total Qty', 'Items', 'Reason', 'Status']
                all_col_keys = ['no', 'return_number', 'po_number', 'customer_name', 'return_date', 'total_qty', 'item_count', 'reason', 'status']

            elif report_type == 'missing-material':
                reqs = await db.material_requests.find({'request_type': 'ADDITIONAL'}, {'_id': 0}).sort('created_at', -1).to_list(None)
                for r in reqs:
                    if sp.get('vendor_id') and r.get('vendor_id') != sp['vendor_id']: continue
                    report_data.append({
                        'request_number': r.get('request_number', ''), 'vendor_name': r.get('vendor_name', ''),
                        'po_number': r.get('po_number', ''), 'total_qty': r.get('total_requested_qty', 0),
                        'reason': r.get('reason', ''), 'status': r.get('status', ''),
                        'child_shipment': r.get('child_shipment_number', '-'),
                        'date': _fmt_date(r.get('created_at')),
                    })
                headers = ['No', 'Request No', 'Vendor', 'PO', 'Qty', 'Reason', 'Status', 'Child Shipment', 'Date']
                all_col_keys = ['no', 'request_number', 'vendor_name', 'po_number', 'total_qty', 'reason', 'status', 'child_shipment', 'date']

            elif report_type == 'replacement':
                reqs = await db.material_requests.find({'request_type': 'REPLACEMENT'}, {'_id': 0}).sort('created_at', -1).to_list(None)
                for r in reqs:
                    if sp.get('vendor_id') and r.get('vendor_id') != sp['vendor_id']: continue
                    report_data.append({
                        'request_number': r.get('request_number', ''), 'vendor_name': r.get('vendor_name', ''),
                        'po_number': r.get('po_number', ''), 'total_qty': r.get('total_requested_qty', 0),
                        'reason': r.get('reason', ''), 'status': r.get('status', ''),
                        'child_shipment': r.get('child_shipment_number', '-'),
                        'date': _fmt_date(r.get('created_at')),
                    })
                headers = ['No', 'Request No', 'Vendor', 'PO', 'Qty', 'Reason', 'Status', 'Child Shipment', 'Date']
                all_col_keys = ['no', 'request_number', 'vendor_name', 'po_number', 'total_qty', 'reason', 'status', 'child_shipment', 'date']

            elif report_type == 'accessory':
                acc_ships = await db.accessory_shipments.find({}, {'_id': 0}).sort('created_at', -1).to_list(None)
                for s in acc_ships:
                    if sp.get('vendor_id') and s.get('vendor_id') != sp['vendor_id']: continue
                    items = await db.accessory_shipment_items.find({'shipment_id': s['id']}).to_list(None)
                    for item in items:
                        report_data.append({
                            'shipment_number': s.get('shipment_number', ''), 'vendor_name': s.get('vendor_name', ''),
                            'po_number': s.get('po_number', ''), 'date': _fmt_date(s.get('shipment_date')),
                            'accessory_name': item.get('accessory_name', ''), 'accessory_code': item.get('accessory_code', ''),
                            'qty_sent': item.get('qty_sent', 0), 'unit': item.get('unit', 'pcs'),
                            'status': s.get('status', ''),
                        })
                headers = ['No', 'Shipment', 'Vendor', 'PO', 'Date', 'Accessory', 'Code', 'Qty', 'Unit', 'Status']
                all_col_keys = ['no', 'shipment_number', 'vendor_name', 'po_number', 'date', 'accessory_name', 'accessory_code', 'qty_sent', 'unit', 'status']
            else:
                return JSONResponse({'error': f'Unhandled report type: {report_type}'}, status_code=400)

            # Build the report PDF
            report_labels = {
                'production': 'Laporan Produksi', 'progress': 'Laporan Progres Produksi',
                'financial': 'Laporan Keuangan', 'shipment': 'Laporan Pengiriman',
                'defect': 'Laporan Defect Material', 'return': 'Laporan Retur Produksi',
                'missing-material': 'Laporan Material Hilang/Tambahan', 'replacement': 'Laporan Material Pengganti',
                'accessory': 'Laporan Aksesoris',
            }
            elements = []
            title = report_labels.get(report_type, f'Report: {report_type}')
            filter_info = []
            if sp.get('vendor_id'):
                vendor = await db.garments.find_one({'id': sp['vendor_id']})
                filter_info.append(('Vendor', (vendor or {}).get('garment_name', sp['vendor_id'])))
            if sp.get('date_from'): filter_info.append(('From', sp['date_from']))
            if sp.get('date_to'): filter_info.append(('To', sp['date_to']))
            if sp.get('status'): filter_info.append(('Status', sp['status']))
            _pdf_header(elements, company_name, title, info_pairs=filter_info if filter_info else None)

            if not report_data:
                elements.append(Paragraph("Tidak ada data ditemukan untuk filter yang dipilih.", styles['Normal']))
            else:
                # Build table data
                data_rows = []
                for idx, row in enumerate(report_data, 1):
                    row_values = [idx]
                    for key in all_col_keys[1:]:  # skip 'no'
                        val = row.get(key, '')
                        if key in ('harga', 'hpp', 'amount', 'paid', 'remaining'):
                            val = _fmt_money(val)
                        elif key in ('output_qty', 'qty_progress', 'defect_qty', 'total_qty', 'item_count', 'items', 'qty_sent'):
                            val = val if val else 0
                        else:
                            val = _safe_str(val, 25)
                        row_values.append(val)
                    data_rows.append(row_values)
                if config and config.get('columns'):
                    headers, data_rows = _filter_columns(headers, all_col_keys, config['columns'], data_rows)
                td = [headers] + data_rows
                num_cols = len(headers)
                use_landscape = num_cols > 7
                page_width = 680 if use_landscape else 445
                cw = [max(22, int(page_width / num_cols))] * num_cols
                t = Table(td, colWidths=cw, repeatRows=1)
                t.setStyle(_pdf_table_style())
                t.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 7 if num_cols > 8 else 8)]))
                elements.append(t)

            elements.append(Spacer(1, 4*mm))
            elements.append(Paragraph(f"<i>Total Records: {len(report_data)}</i>", styles['Normal']))
            _pdf_footer(elements)
            _build_pdf(buf, elements, page='landscape' if len(headers) > 7 else None)
            return StreamingResponse(buf, media_type="application/pdf",
                                     headers={"Content-Disposition": f"attachment; filename=laporan_{report_type}_{datetime.now().strftime('%Y%m%d')}.pdf"})

        else:
            all_types = [
                'production-po', 'vendor-shipment', 'buyer-shipment', 'buyer-shipment-dispatch',
                'production-return', 'material-request', 'production-report',
                'report-production', 'report-progress', 'report-financial', 'report-shipment',
                'report-defect', 'report-return', 'report-missing-material', 'report-replacement', 'report-accessory'
            ]
            return JSONResponse({'error': f'Unknown PDF type: {pdf_type}', 'available_types': all_types}, status_code=400)
    except HTTPException: raise
    except Exception as e:
        logger.error(f"PDF export error: {e}", exc_info=True)
        raise HTTPException(500, f"PDF export failed: {str(e)}")


# ─── PDF EXPORT CONFIGURATION CRUD ───────────────────────────────────────────

# Available columns per PDF type (used by config UI)
PDF_COLUMN_DEFINITIONS = {
    'production-po': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'qty', 'label': 'Quantity', 'required': True},
        {'key': 'price', 'label': 'Selling Price'},
        {'key': 'cmt', 'label': 'CMT Price'},
    ],
    'vendor-shipment': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'po', 'label': 'PO Number'},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'qty_sent', 'label': 'Qty Sent', 'required': True},
    ],
    'buyer-shipment-dispatch': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'ordered', 'label': 'Ordered Qty'},
        {'key': 'this_dispatch', 'label': 'This Dispatch'},
        {'key': 'cumul_shipped', 'label': 'Cumulative Shipped'},
        {'key': 'remaining', 'label': 'Remaining'},
    ],
    'production-report': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'date', 'label': 'Date'},
        {'key': 'po', 'label': 'PO Number'},
        {'key': 'serial', 'label': 'Serial No'},
        {'key': 'product', 'label': 'Product Name'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Color'},
        {'key': 'qty', 'label': 'Quantity'},
        {'key': 'price', 'label': 'Price'},
        {'key': 'cmt', 'label': 'CMT'},
        {'key': 'vendor', 'label': 'Vendor'},
        {'key': 'produced', 'label': 'Produced'},
        {'key': 'shipped', 'label': 'Shipped'},
    ],
    'report-production': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'tanggal', 'label': 'Tanggal'},
        {'key': 'no_po', 'label': 'No PO'},
        {'key': 'no_seri', 'label': 'Serial'},
        {'key': 'nama_produk', 'label': 'Produk'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'warna', 'label': 'Warna'},
        {'key': 'output_qty', 'label': 'Qty'},
        {'key': 'harga', 'label': 'Harga'},
        {'key': 'hpp', 'label': 'HPP/CMT'},
        {'key': 'garment', 'label': 'Vendor'},
        {'key': 'po_status', 'label': 'Status'},
    ],
    'report-progress': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'date', 'label': 'Tanggal'},
        {'key': 'job_number', 'label': 'Job'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'serial_number', 'label': 'Serial'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'product_name', 'label': 'Produk'},
        {'key': 'qty_progress', 'label': 'Qty'},
        {'key': 'notes', 'label': 'Catatan'},
        {'key': 'recorded_by', 'label': 'Dicatat oleh'},
    ],
    'report-financial': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'invoice_number', 'label': 'Invoice No'},
        {'key': 'category', 'label': 'Category'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'vendor_or_buyer', 'label': 'Vendor/Buyer'},
        {'key': 'amount', 'label': 'Amount'},
        {'key': 'paid', 'label': 'Paid'},
        {'key': 'remaining', 'label': 'Remaining'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'date', 'label': 'Date'},
    ],
    'report-shipment': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'direction', 'label': 'Direction'},
        {'key': 'shipment_number', 'label': 'Shipment No'},
        {'key': 'shipment_type', 'label': 'Type'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'inspection', 'label': 'Inspection'},
        {'key': 'date', 'label': 'Date'},
        {'key': 'total_qty', 'label': 'Qty'},
        {'key': 'items', 'label': 'Items'},
    ],
    'report-defect': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'date', 'label': 'Tanggal'},
        {'key': 'sku', 'label': 'SKU'},
        {'key': 'product_name', 'label': 'Produk'},
        {'key': 'size', 'label': 'Size'},
        {'key': 'color', 'label': 'Warna'},
        {'key': 'defect_qty', 'label': 'Qty Defect'},
        {'key': 'defect_type', 'label': 'Tipe'},
        {'key': 'description', 'label': 'Deskripsi'},
        {'key': 'status', 'label': 'Status'},
    ],
    'report-return': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'return_number', 'label': 'Return No'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'customer_name', 'label': 'Customer'},
        {'key': 'return_date', 'label': 'Date'},
        {'key': 'total_qty', 'label': 'Total Qty'},
        {'key': 'item_count', 'label': 'Items'},
        {'key': 'reason', 'label': 'Reason'},
        {'key': 'status', 'label': 'Status'},
    ],
    'report-missing-material': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'request_number', 'label': 'Request No'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'total_qty', 'label': 'Qty'},
        {'key': 'reason', 'label': 'Reason'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'child_shipment', 'label': 'Child Shipment'},
        {'key': 'date', 'label': 'Date'},
    ],
    'report-replacement': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'request_number', 'label': 'Request No'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'total_qty', 'label': 'Qty'},
        {'key': 'reason', 'label': 'Reason'},
        {'key': 'status', 'label': 'Status'},
        {'key': 'child_shipment', 'label': 'Child Shipment'},
        {'key': 'date', 'label': 'Date'},
    ],
    'report-accessory': [
        {'key': 'no', 'label': 'No', 'required': True},
        {'key': 'shipment_number', 'label': 'Shipment'},
        {'key': 'vendor_name', 'label': 'Vendor'},
        {'key': 'po_number', 'label': 'PO'},
        {'key': 'date', 'label': 'Date'},
        {'key': 'accessory_name', 'label': 'Accessory'},
        {'key': 'accessory_code', 'label': 'Code'},
        {'key': 'qty_sent', 'label': 'Qty'},
        {'key': 'unit', 'label': 'Unit'},
        {'key': 'status', 'label': 'Status'},
    ],
}

@router.get("/pdf-export-columns")
async def get_pdf_export_columns(request: Request):
    """Get available columns for a PDF type."""
    await require_auth(request)
    pdf_type = request.query_params.get('type', '')
    if pdf_type in PDF_COLUMN_DEFINITIONS:
        return {'pdf_type': pdf_type, 'columns': PDF_COLUMN_DEFINITIONS[pdf_type]}
    return {'pdf_type': pdf_type, 'columns': [], 'available_types': list(PDF_COLUMN_DEFINITIONS.keys())}

@router.get("/pdf-export-configs")
async def list_pdf_export_configs(request: Request):
    """List all PDF export configurations."""
    await require_auth(request)
    db = get_db()
    pdf_type = request.query_params.get('type')
    query = {}
    if pdf_type: query['pdf_type'] = pdf_type
    configs = await db.pdf_export_configs.find(query, {'_id': 0}).sort('created_at', -1).to_list(None)
    return serialize_doc(configs)

@router.get("/pdf-export-configs/{config_id}")
async def get_pdf_export_config(config_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    cfg = await db.pdf_export_configs.find_one({'id': config_id}, {'_id': 0})
    if not cfg: raise HTTPException(404, 'Config not found')
    return serialize_doc(cfg)

@router.post("/pdf-export-configs")
async def create_pdf_export_config(request: Request):
    """Create a new PDF export config."""
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    pdf_type = body.get('pdf_type', '')
    name = body.get('name', '')
    columns = body.get('columns', [])
    is_default = body.get('is_default', False)
    if not pdf_type or not name: raise HTTPException(400, 'pdf_type and name required')
    if not columns: raise HTTPException(400, 'columns array required')
    # Ensure required columns are included
    if pdf_type in PDF_COLUMN_DEFINITIONS:
        required = [c['key'] for c in PDF_COLUMN_DEFINITIONS[pdf_type] if c.get('required')]
        for rk in required:
            if rk not in columns:
                columns.insert(0, rk)
    # If setting as default, unset other defaults for this type
    if is_default:
        await db.pdf_export_configs.update_many({'pdf_type': pdf_type, 'is_default': True}, {'$set': {'is_default': False}})
    doc = {
        'id': str(uuid.uuid4()),
        'pdf_type': pdf_type,
        'name': name,
        'columns': columns,
        'is_default': is_default,
        'created_by': user.get('name', ''),
        'created_at': datetime.now(timezone.utc),
        'updated_at': datetime.now(timezone.utc),
    }
    await db.pdf_export_configs.insert_one(doc)
    await log_activity(user['id'], user.get('name', ''), 'create', 'pdf_config', f"Created PDF config: {name} for {pdf_type}")
    return JSONResponse(serialize_doc({k: v for k, v in doc.items() if k != '_id'}), status_code=201)

@router.put("/pdf-export-configs/{config_id}")
async def update_pdf_export_config(config_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    body = await request.json()
    existing = await db.pdf_export_configs.find_one({'id': config_id})
    if not existing: raise HTTPException(404, 'Config not found')
    update = {'updated_at': datetime.now(timezone.utc)}
    if 'name' in body: update['name'] = body['name']
    if 'columns' in body:
        columns = body['columns']
        pdf_type = existing.get('pdf_type', '')
        if pdf_type in PDF_COLUMN_DEFINITIONS:
            required = [c['key'] for c in PDF_COLUMN_DEFINITIONS[pdf_type] if c.get('required')]
            for rk in required:
                if rk not in columns:
                    columns.insert(0, rk)
        update['columns'] = columns
    if 'is_default' in body:
        if body['is_default']:
            await db.pdf_export_configs.update_many({'pdf_type': existing['pdf_type'], 'is_default': True}, {'$set': {'is_default': False}})
        update['is_default'] = body['is_default']
    await db.pdf_export_configs.update_one({'id': config_id}, {'$set': update})
    updated = await db.pdf_export_configs.find_one({'id': config_id}, {'_id': 0})
    return serialize_doc(updated)

@router.delete("/pdf-export-configs/{config_id}")
async def delete_pdf_export_config(config_id: str, request: Request):
    user = await require_auth(request)
    db = get_db()
    existing = await db.pdf_export_configs.find_one({'id': config_id})
    if not existing: raise HTTPException(404, 'Config not found')
    await db.pdf_export_configs.delete_one({'id': config_id})
    await log_activity(user['id'], user.get('name', ''), 'delete', 'pdf_config', f"Deleted PDF config: {existing.get('name', config_id)}")
    return {'success': True}

