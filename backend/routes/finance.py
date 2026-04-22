"""
Finance: Invoices, Payments, AP/AR, Adjustments, Approval, Recap
Extracted from server.py monolith.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from database import get_db
from auth import (verify_token, require_auth, check_role, hash_password, verify_password,
                  create_token, log_activity, serialize_doc, generate_password)
from routes.shared import new_id, now, parse_date, to_end_of_day, PO_STATUSES
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["finance"])

# ─── INVOICES ────────────────────────────────────────────────────────────────
@router.get("/invoices")
async def get_invoices(request: Request):
    await require_auth(request)
    db = get_db()
    sp = request.query_params
    query = {}
    if sp.get('status'): query['status'] = sp['status']
    if sp.get('garment_id'): query['garment_id'] = sp['garment_id']
    if sp.get('type') == 'vendor': query['invoice_category'] = 'VENDOR'
    elif sp.get('type') == 'customer': query['invoice_category'] = 'BUYER'
    if sp.get('category'): query['invoice_category'] = sp['category']
    if sp.get('invoice_type'): query['invoice_type'] = sp['invoice_type']
    if sp.get('date_from') or sp.get('date_to'):
        query['created_at'] = {}
        if sp.get('date_from'): query['created_at']['$gte'] = parse_date(sp['date_from'])
        if sp.get('date_to'): query['created_at']['$lte'] = to_end_of_day(sp['date_to'])
    return serialize_doc(await db.invoices.find(query, {'_id': 0}).sort('created_at', -1).to_list(None))

@router.get("/invoices/{inv_id}")
async def get_invoice(inv_id: str, request: Request):
    await require_auth(request)
    db = get_db()
    inv = await db.invoices.find_one({'id': inv_id}, {'_id': 0})
    if not inv: raise HTTPException(404, 'Not found')
    payments = await db.payments.find({'invoice_id': inv_id}, {'_id': 0}).to_list(None)
    adjustments = await db.invoice_adjustments.find({'invoice_id': inv_id}, {'_id': 0}).sort('created_at', -1).to_list(None)
    total_add = sum(a.get('amount', 0) for a in adjustments if a.get('adjustment_type') == 'ADD')
    total_deduct = sum(a.get('amount', 0) for a in adjustments if a.get('adjustment_type') == 'DEDUCT')
    base_amount = inv.get('base_amount', inv.get('total_amount', 0))
    adjusted_total = base_amount + total_add - total_deduct
    result = serialize_doc(inv)
    result.update({'payments': serialize_doc(payments), 'adjustments': serialize_doc(adjustments),
                   'base_amount': base_amount, 'adjusted_total': adjusted_total})
    return result

@router.post("/invoices")
async def create_invoice(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin', 'finance']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    po_id = body.get('source_po_id')
    if not po_id: raise HTTPException(400, 'source_po_id wajib diisi')
    po = await db.production_pos.find_one({'id': po_id})
    if not po: raise HTTPException(404, 'PO tidak ditemukan')
    category = body.get('invoice_category')
    if category not in ['VENDOR', 'BUYER']: raise HTTPException(400, 'invoice_category harus VENDOR atau BUYER')
    
    # Generate invoice number with PO number
    po_number = po.get('po_number', 'UNKNOWN')
    revision = body.get('revision_number', 0) or 0
    prefix = 'INV-VND' if category == 'VENDOR' else 'INV-BYR'
    inv_number = f"{prefix}-{po_number}-R{revision}"
    
    # Check if invoice number already exists (should be unique)
    existing = await db.invoices.find_one({'invoice_number': inv_number})
    if existing:
        # Increment revision if duplicate
        revision += 1
        inv_number = f"{prefix}-{po_number}-R{revision}"
    
    items = body.get('invoice_items', [])
    recalc_items = []
    for it in items:
        price = it.get('cmt_price', 0) if category == 'VENDOR' else it.get('selling_price', 0)
        qty = it.get('invoice_qty', it.get('qty', 0))
        recalc_items.append({**it, 'invoice_qty': qty, 'subtotal': qty * price})
    total_amount = sum(i['subtotal'] for i in recalc_items) - float(body.get('discount', 0) or 0)
    invoice = {
        'id': new_id(), 'invoice_number': inv_number, 'invoice_type': 'MANUAL',
        'invoice_category': category, 'source_po_id': po_id, 'po_number': po.get('po_number'),
        'vendor_or_customer_id': po.get('vendor_id') if category == 'VENDOR' else None,
        'vendor_or_customer_name': po.get('vendor_name', '') if category == 'VENDOR' else po.get('customer_name', ''),
        'garment_id': po.get('vendor_id'), 'garment_name': po.get('vendor_name', ''),
        'vendor_id': po.get('vendor_id'), 'vendor_name': po.get('vendor_name', ''),
        'customer_name': po.get('customer_name', ''),
        'invoice_items': recalc_items, 'total_amount': total_amount,
        'paid_amount': 0, 'total_paid': 0, 'remaining_balance': total_amount,
        'status': 'Unpaid', 'revision_number': revision,
        'discount': float(body.get('discount', 0) or 0), 'notes': body.get('notes', ''),
        'created_by': user['name'], 'created_at': now(), 'updated_at': now()
    }
    await db.invoices.insert_one(invoice)
    await log_activity(user['id'], user['name'], 'Create Manual Invoice', 'Invoice', f"Manual {category} invoice {inv_number}")
    return JSONResponse(serialize_doc(invoice), status_code=201)

@router.put("/invoices/{inv_id}")
async def update_invoice(inv_id: str, request: Request):
    user = await require_auth(request)
    # Check permission: superadmin always allowed, or check invoice.update permission
    if user.get('role') != 'superadmin':
        if not (user.get('role') in ['admin', 'finance'] or 'invoice.update' in user.get('_permissions', [])):
            raise HTTPException(403, 'Forbidden: Tidak memiliki permission untuk edit invoice')
    db = get_db()
    body = await request.json()
    body.pop('_id', None); body.pop('id', None)
    await db.invoices.update_one({'id': inv_id}, {'$set': {**body, 'updated_at': now()}})
    await log_activity(user['id'], user['name'], 'Update', 'Invoice', f"Updated invoice {body.get('invoice_number', inv_id)}")
    return serialize_doc(await db.invoices.find_one({'id': inv_id}, {'_id': 0}))

@router.delete("/invoices/{inv_id}")
async def delete_invoice(inv_id: str, request: Request):
    user = await require_auth(request)
    if user.get('role') != 'superadmin': raise HTTPException(403, 'Forbidden')
    db = get_db()
    doc = await db.invoices.find_one({'id': inv_id})
    if not doc: raise HTTPException(404, 'Not found')
    await db.payments.delete_many({'invoice_id': inv_id})
    await db.invoice_adjustments.delete_many({'invoice_id': inv_id})
    await db.invoices.delete_one({'id': inv_id})
    return {'success': True}

@router.post("/invoices/{inv_id}/revise")
async def revise_invoice(inv_id: str, request: Request):
    """Create a revised copy of an invoice, marking the original as Superseded."""
    user = await require_auth(request)
    if not check_role(user, ['admin', 'finance']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    original = await db.invoices.find_one({'id': inv_id}, {'_id': 0})
    if not original: raise HTTPException(404, 'Invoice not found')
    body = await request.json()
    if not body.get('change_reason'): raise HTTPException(400, 'Alasan revisi wajib diisi')
    # Calculate new revision number
    old_rev = original.get('revision_number', 0) or 0
    new_rev = old_rev + 1
    # Generate new invoice number
    base_number = original.get('invoice_number', '')
    # Remove old revision suffix if present
    if f'-R{old_rev}' in base_number:
        base_number = base_number.replace(f'-R{old_rev}', '')
    new_inv_number = f"{base_number}-R{new_rev}"
    # Build revised items
    rev_items = body.get('invoice_items', original.get('invoice_items', []))
    category = original.get('invoice_category', 'BUYER')
    recalc_items = []
    for it in rev_items:
        price = it.get('cmt_price', 0) if category == 'VENDOR' else it.get('selling_price', 0)
        qty = it.get('invoice_qty', it.get('qty', 0))
        recalc_items.append({**it, 'invoice_qty': qty, 'subtotal': qty * price})
    total_amount = body.get('total_amount', sum(i['subtotal'] for i in recalc_items))
    discount = float(body.get('discount', original.get('discount', 0)) or 0)
    total_amount = total_amount - discount if total_amount > discount else total_amount
    # Create new revised invoice
    new_invoice = {
        'id': new_id(),
        'invoice_number': new_inv_number,
        'invoice_type': original.get('invoice_type', 'MANUAL'),
        'invoice_category': category,
        'source_po_id': original.get('source_po_id'),
        'po_number': original.get('po_number'),
        'vendor_or_customer_id': original.get('vendor_or_customer_id'),
        'vendor_or_customer_name': original.get('vendor_or_customer_name', ''),
        'garment_id': original.get('garment_id'),
        'garment_name': original.get('garment_name', ''),
        'vendor_id': original.get('vendor_id'),
        'vendor_name': original.get('vendor_name', ''),
        'customer_name': original.get('customer_name', ''),
        'invoice_items': recalc_items,
        'total_amount': total_amount,
        'base_amount': total_amount,
        'paid_amount': 0, 'total_paid': 0, 'remaining_balance': total_amount,
        'status': 'Unpaid',
        'revision_number': new_rev,
        'parent_invoice_id': inv_id,
        'parent_invoice_number': original.get('invoice_number'),
        'change_reason': body.get('change_reason', ''),
        'discount': discount,
        'notes': body.get('notes', original.get('notes', '')),
        'created_by': user['name'], 'created_at': now(), 'updated_at': now()
    }
    await db.invoices.insert_one(new_invoice)
    # Mark original as Superseded
    await db.invoices.update_one({'id': inv_id}, {'$set': {
        'status': 'Superseded',
        'superseded_by': new_invoice['id'],
        'superseded_by_number': new_inv_number,
        'updated_at': now()
    }})
    await log_activity(user['id'], user['name'], 'Revise Invoice', 'Invoice',
                       f"Revised {original.get('invoice_number')} → {new_inv_number}")
    return JSONResponse(serialize_doc(new_invoice), status_code=201)



# ─── INVOICE ADJUSTMENTS ─────────────────────────────────────────────────────
@router.get("/invoice-adjustments")
async def get_adjustments(request: Request):
    await require_auth(request)
    db = get_db()
    inv_id = request.query_params.get('invoice_id')
    if not inv_id: raise HTTPException(400, 'invoice_id required')
    return serialize_doc(await db.invoice_adjustments.find({'invoice_id': inv_id}, {'_id': 0}).sort('created_at', -1).to_list(None))

@router.post("/invoice-adjustments")
async def create_adjustment(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin', 'finance', 'superadmin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    if not body.get('invoice_id'): raise HTTPException(400, 'invoice_id wajib diisi')
    if body.get('adjustment_type') not in ['ADD', 'DEDUCT']: raise HTTPException(400, 'adjustment_type harus ADD atau DEDUCT')
    if not body.get('amount') or float(body['amount']) <= 0: raise HTTPException(400, 'amount harus lebih dari 0')
    if not body.get('reason'): raise HTTPException(400, 'reason wajib diisi')
    invoice = await db.invoices.find_one({'id': body['invoice_id']})
    if not invoice: raise HTTPException(404, 'Invoice not found')
    adjustment = {
        'id': new_id(), 'invoice_id': body['invoice_id'],
        'invoice_number': invoice.get('invoice_number'),
        'adjustment_type': body['adjustment_type'], 'amount': float(body['amount']),
        'reason': body.get('reason', ''), 'notes': body.get('notes', ''),
        'reference_event': body.get('reference_event', ''),
        'created_by': user['name'], 'created_at': now()
    }
    await db.invoice_adjustments.insert_one(adjustment)
    all_adj = await db.invoice_adjustments.find({'invoice_id': body['invoice_id']}).to_list(None)
    total_add = sum(a.get('amount', 0) for a in all_adj if a.get('adjustment_type') == 'ADD')
    total_deduct = sum(a.get('amount', 0) for a in all_adj if a.get('adjustment_type') == 'DEDUCT')
    base_amount = invoice.get('base_amount', invoice.get('total_amount', 0))
    new_total = base_amount + total_add - total_deduct
    new_status = 'Paid' if (invoice.get('total_paid', 0)) >= new_total else ('Partial' if (invoice.get('total_paid', 0)) > 0 else 'Unpaid')
    await db.invoices.update_one({'id': body['invoice_id']}, {'$set': {
        'base_amount': base_amount, 'total_amount': new_total,
        'remaining_balance': new_total - (invoice.get('total_paid', 0)),
        'status': new_status, 'updated_at': now()
    }})
    return JSONResponse(serialize_doc(adjustment), status_code=201)

@router.delete("/invoice-adjustments/{adj_id}")
async def delete_adjustment(adj_id: str, request: Request):
    user = await require_auth(request)
    if user.get('role') != 'superadmin': raise HTTPException(403, 'Forbidden')
    db = get_db()
    doc = await db.invoice_adjustments.find_one({'id': adj_id})
    if not doc: raise HTTPException(404, 'Not found')
    await db.invoice_adjustments.delete_one({'id': adj_id})
    invoice = await db.invoices.find_one({'id': doc.get('invoice_id')})
    if invoice:
        all_adj = await db.invoice_adjustments.find({'invoice_id': doc['invoice_id']}).to_list(None)
        total_add = sum(a.get('amount', 0) for a in all_adj if a.get('adjustment_type') == 'ADD')
        total_deduct = sum(a.get('amount', 0) for a in all_adj if a.get('adjustment_type') == 'DEDUCT')
        base_amount = invoice.get('base_amount', invoice.get('total_amount', 0))
        new_total = base_amount + total_add - total_deduct
        await db.invoices.update_one({'id': doc['invoice_id']}, {'$set': {
            'total_amount': new_total, 'remaining_balance': new_total - (invoice.get('total_paid', 0)), 'updated_at': now()
        }})
    return {'success': True}


# ─── INVOICE EDIT REQUESTS (APPROVAL SYSTEM) ─────────────────────────────────
@router.get("/invoice-edit-requests")
async def get_invoice_edit_requests(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['superadmin', 'admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    sp = request.query_params
    query = {}
    if sp.get('status'): query['status'] = sp['status']
    if sp.get('invoice_id'): query['invoice_id'] = sp['invoice_id']
    if sp.get('q'):
        q = sp['q']
        query['$or'] = [
            {'invoice_number': {'$regex': q, '$options': 'i'}},
            {'requested_by': {'$regex': q, '$options': 'i'}},
            {'change_summary': {'$regex': q, '$options': 'i'}}
        ]
    if sp.get('from') or sp.get('to'):
        query['requested_at'] = {}
        if sp.get('from'): query['requested_at']['$gte'] = parse_date(sp['from'])
        if sp.get('to'): query['requested_at']['$lte'] = to_end_of_day(sp['to'])
    return serialize_doc(await db.invoice_edit_requests.find(query, {'_id': 0}).sort('requested_at', -1).to_list(None))

@router.get("/invoice-edit-requests/{req_id}")
async def get_invoice_edit_request(req_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['superadmin', 'admin']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    req = await db.invoice_edit_requests.find_one({'id': req_id}, {'_id': 0})
    if not req: raise HTTPException(404, 'Request not found')
    return serialize_doc(req)

@router.post("/invoice-edit-requests")
async def create_invoice_edit_request(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['superadmin', 'admin']): raise HTTPException(403, 'Forbidden: Hanya Admin yang bisa mengajukan request edit')
    db = get_db()
    body = await request.json()
    invoice_id = body.get('invoice_id')
    if not invoice_id: raise HTTPException(400, 'invoice_id wajib diisi')
    
    # Get current invoice
    invoice = await db.invoices.find_one({'id': invoice_id})
    if not invoice: raise HTTPException(404, 'Invoice tidak ditemukan')
    if invoice.get('status') == 'Superseded': raise HTTPException(400, 'Tidak bisa mengedit invoice yang sudah Superseded')
    
    # Check if there's already a pending request for this invoice
    existing_pending = await db.invoice_edit_requests.find_one({
        'invoice_id': invoice_id,
        'status': 'Pending'
    })
    if existing_pending:
        raise HTTPException(400, f"Sudah ada request edit pending untuk invoice {invoice.get('invoice_number')}. Tunggu hingga di-approve/reject terlebih dahulu.")
    
    # Prepare changes (what user wants to change)
    changes_requested = body.get('changes_requested', {})
    if not changes_requested:
        raise HTTPException(400, 'changes_requested wajib diisi (object berisi field yang ingin diubah)')
    
    # Create before snapshot (current state)
    before_snapshot = {
        'invoice_items': invoice.get('invoice_items', []),
        'discount': invoice.get('discount', 0),
        'notes': invoice.get('notes', ''),
        'total_amount': invoice.get('total_amount', 0)
    }
    
    # Create after snapshot (proposed state) - merge current with changes
    after_snapshot = {**before_snapshot, **changes_requested}
    
    # Generate change summary
    change_summary = body.get('change_summary', 'Edit invoice items/fields')
    
    edit_request = {
        'id': new_id(),
        'invoice_id': invoice_id,
        'invoice_number': invoice.get('invoice_number'),
        'invoice_category': invoice.get('invoice_category'),
        'po_number': invoice.get('po_number'),
        'status': 'Pending',
        'requested_by': user['email'],
        'requested_by_name': user['name'],
        'requested_at': now(),
        'approved_by': None,
        'approved_by_name': None,
        'approved_at': None,
        'approval_notes': '',
        'changes_requested': changes_requested,
        'before_snapshot': before_snapshot,
        'after_snapshot': after_snapshot,
        'change_summary': change_summary,
        'created_at': now(),
        'updated_at': now()
    }
    
    await db.invoice_edit_requests.insert_one(edit_request)
    await log_activity(user['id'], user['name'], 'Request Invoice Edit', 'Invoice Approval', 
                      f"Request edit untuk invoice {invoice.get('invoice_number')}")
    return JSONResponse(serialize_doc(edit_request), status_code=201)

@router.put("/invoice-edit-requests/{req_id}/approve")
async def approve_invoice_edit_request(req_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['superadmin', 'admin']): raise HTTPException(403, 'Forbidden: Hanya Superadmin/Admin yang bisa approve')
    db = get_db()
    body = await request.json()
    
    # Get request
    edit_req = await db.invoice_edit_requests.find_one({'id': req_id})
    if not edit_req: raise HTTPException(404, 'Request tidak ditemukan')
    if edit_req.get('status') != 'Pending':
        raise HTTPException(400, f"Request sudah {edit_req.get('status')}. Tidak bisa approve lagi.")
    
    # Get invoice
    invoice = await db.invoices.find_one({'id': edit_req['invoice_id']})
    if not invoice: raise HTTPException(404, 'Invoice tidak ditemukan')
    
    # Prepare update payload from changes_requested
    changes = edit_req.get('changes_requested', {})
    update_payload = {**changes, 'updated_at': now()}
    
    # If invoice_items changed, recalculate total
    if 'invoice_items' in changes:
        items = changes['invoice_items']
        category = invoice.get('invoice_category')
        recalc_items = []
        for it in items:
            price = float(it.get('cmt_price', 0) or 0) if category == 'VENDOR' else float(it.get('selling_price', 0) or 0)
            qty = float(it.get('invoice_qty', it.get('qty', 0)) or 0)
            subtotal = qty * price
            recalc_items.append({**it, 'invoice_qty': qty, 'subtotal': subtotal})
        total_amount = sum(i['subtotal'] for i in recalc_items) - float(changes.get('discount', invoice.get('discount', 0)) or 0)
        update_payload['invoice_items'] = recalc_items
        update_payload['total_amount'] = total_amount
        update_payload['remaining_balance'] = total_amount - float(invoice.get('total_paid', 0) or 0)
        # Update status based on payment
        if float(invoice.get('total_paid', 0) or 0) >= total_amount:
            update_payload['status'] = 'Paid'
        elif float(invoice.get('total_paid', 0) or 0) > 0:
            update_payload['status'] = 'Partial'
        else:
            update_payload['status'] = 'Unpaid'
    
    # Update invoice
    await db.invoices.update_one({'id': edit_req['invoice_id']}, {'$set': update_payload})
    
    # Create change history record
    history = {
        'id': new_id(),
        'invoice_id': edit_req['invoice_id'],
        'invoice_number': invoice.get('invoice_number'),
        'changed_by': user['email'],
        'changed_by_name': user['name'],
        'changed_at': now(),
        'change_type': 'EDIT_APPROVAL',
        'old_values': edit_req.get('before_snapshot', {}),
        'new_values': edit_req.get('after_snapshot', {}),
        'approval_request_id': req_id,
        'notes': body.get('approval_notes', '')
    }
    await db.invoice_change_history.insert_one(history)
    
    # Update request status
    await db.invoice_edit_requests.update_one({'id': req_id}, {'$set': {
        'status': 'Approved',
        'approved_by': user['email'],
        'approved_by_name': user['name'],
        'approved_at': now(),
        'approval_notes': body.get('approval_notes', ''),
        'updated_at': now()
    }})
    
    await log_activity(user['id'], user['name'], 'Approve Invoice Edit', 'Invoice Approval',
                      f"Approved edit untuk invoice {invoice.get('invoice_number')}")
    
    return {'success': True, 'message': 'Request approved dan invoice berhasil diupdate'}

@router.put("/invoice-edit-requests/{req_id}/reject")
async def reject_invoice_edit_request(req_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['superadmin', 'admin']): raise HTTPException(403, 'Forbidden: Hanya Superadmin/Admin yang bisa reject')
    db = get_db()
    body = await request.json()
    
    # Get request
    edit_req = await db.invoice_edit_requests.find_one({'id': req_id})
    if not edit_req: raise HTTPException(404, 'Request tidak ditemukan')
    if edit_req.get('status') != 'Pending':
        raise HTTPException(400, f"Request sudah {edit_req.get('status')}. Tidak bisa reject lagi.")
    
    # Update request status
    await db.invoice_edit_requests.update_one({'id': req_id}, {'$set': {
        'status': 'Rejected',
        'approved_by': user['email'],
        'approved_by_name': user['name'],
        'approved_at': now(),
        'approval_notes': body.get('approval_notes', 'Request ditolak'),
        'updated_at': now()
    }})
    
    await log_activity(user['id'], user['name'], 'Reject Invoice Edit', 'Invoice Approval',
                      f"Rejected edit request untuk invoice {edit_req.get('invoice_number')}")
    
    return {'success': True, 'message': 'Request rejected'}


# ─── INVOICE CHANGE HISTORY ──────────────────────────────────────────────────
@router.get("/invoices/{invoice_id}/change-history")
async def get_invoice_change_history(invoice_id: str, request: Request):
    user = await require_auth(request)
    if not check_role(user, ['superadmin', 'admin', 'finance']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    history = await db.invoice_change_history.find({'invoice_id': invoice_id}, {'_id': 0}).sort('changed_at', -1).to_list(None)
    return serialize_doc(history)



# ─── PAYMENTS ────────────────────────────────────────────────────────────────
@router.get("/payments")
async def get_payments(request: Request):
    await require_auth(request)
    db = get_db()
    sp = request.query_params
    query = {}
    if sp.get('invoice_id'): query['invoice_id'] = sp['invoice_id']
    if sp.get('payment_type'): query['payment_type'] = sp['payment_type']
    return serialize_doc(await db.payments.find(query, {'_id': 0}).sort('payment_date', -1).to_list(None))

@router.post("/payments")
async def create_payment(request: Request):
    user = await require_auth(request)
    if not check_role(user, ['admin', 'finance']): raise HTTPException(403, 'Forbidden')
    db = get_db()
    body = await request.json()
    invoice = await db.invoices.find_one({'id': body.get('invoice_id')})
    if not invoice: raise HTTPException(404, 'Invoice not found')
    outstanding = (invoice.get('total_amount', 0)) - (invoice.get('total_paid', 0))
    amount = float(body.get('amount', 0) or 0)
    if amount <= 0: raise HTTPException(400, 'Jumlah pembayaran harus lebih dari 0')
    if amount > outstanding: raise HTTPException(400, f'Jumlah melebihi sisa tagihan! Maksimal: Rp {outstanding:,.0f}')
    payment_type = body.get('payment_type') or (
        'VENDOR_PAYMENT' if invoice.get('invoice_category') == 'VENDOR' else 'CUSTOMER_PAYMENT')
    payment = {
        'id': new_id(), 'invoice_id': body['invoice_id'],
        'invoice_number': invoice.get('invoice_number'),
        'payment_type': payment_type,
        'garment_id': invoice.get('garment_id'), 'garment_name': invoice.get('garment_name'),
        'vendor_or_customer_name': invoice.get('vendor_or_customer_name', invoice.get('vendor_name', invoice.get('customer_name', ''))),
        'payment_date': parse_date(body.get('payment_date')) or now(),
        'amount': amount, 'payment_method': body.get('payment_method', 'Transfer Bank'),
        'reference_number': body.get('reference_number', body.get('reference', '')),
        'notes': body.get('notes', ''), 'recorded_by': user['name'], 'created_at': now()
    }
    await db.payments.insert_one(payment)
    all_pmts = await db.payments.find({'invoice_id': body['invoice_id']}).to_list(None)
    total_paid = sum(p.get('amount', 0) for p in all_pmts)
    new_status = 'Paid' if total_paid >= invoice.get('total_amount', 0) else 'Partial'
    await db.invoices.update_one({'id': body['invoice_id']}, {'$set': {
        'status': new_status, 'total_paid': total_paid, 'paid_amount': total_paid,
        'remaining_balance': invoice.get('total_amount', 0) - total_paid, 'updated_at': now()
    }})
    return JSONResponse(serialize_doc(payment), status_code=201)

@router.delete("/payments/{pay_id}")
async def delete_payment(pay_id: str, request: Request):
    user = await require_auth(request)
    if user.get('role') != 'superadmin': raise HTTPException(403, 'Forbidden')
    db = get_db()
    doc = await db.payments.find_one({'id': pay_id})
    if not doc: raise HTTPException(404, 'Not found')
    await db.payments.delete_one({'id': pay_id})
    all_pmts = await db.payments.find({'invoice_id': doc.get('invoice_id')}).to_list(None)
    total_paid = sum(p.get('amount', 0) for p in all_pmts)
    invoice = await db.invoices.find_one({'id': doc.get('invoice_id')})
    if invoice:
        new_status = 'Unpaid' if total_paid <= 0 else ('Paid' if total_paid >= invoice.get('total_amount', 0) else 'Partial')
        await db.invoices.update_one({'id': doc['invoice_id']}, {'$set': {
            'status': new_status, 'total_paid': total_paid, 'updated_at': now()
        }})
    return {'success': True}


# ─── ACCOUNTS PAYABLE / RECEIVABLE ──────────────────────────────────────────
@router.get("/accounts-payable")
async def accounts_payable(request: Request):
    await require_auth(request)
    db = get_db()
    return serialize_doc(await db.invoices.find({'invoice_category': 'VENDOR'}, {'_id': 0}).sort('created_at', -1).to_list(None))

@router.get("/accounts-receivable")
async def accounts_receivable(request: Request):
    await require_auth(request)
    db = get_db()
    return serialize_doc(await db.invoices.find({'invoice_category': 'BUYER'}, {'_id': 0}).sort('created_at', -1).to_list(None))


# ─── FINANCIAL RECAP ─────────────────────────────────────────────────────────
@router.get("/financial-recap")
async def financial_recap(request: Request):
    await require_auth(request)
    db = get_db()
    sp = request.query_params
    inv_query = {}
    pmt_query = {}
    if sp.get('date_from') or sp.get('date_to'):
        d_range = {}
        if sp.get('date_from'): d_range['$gte'] = parse_date(sp['date_from'])
        if sp.get('date_to'): d_range['$lte'] = to_end_of_day(sp['date_to'])
        inv_query['created_at'] = d_range
        pmt_query['payment_date'] = d_range
    invoices = await db.invoices.find(inv_query, {'_id': 0}).to_list(None)
    payments = await db.payments.find(pmt_query, {'_id': 0}).to_list(None)
    all_adj = await db.invoice_adjustments.find({}).to_list(None)
    adj_map = {}
    for adj in all_adj:
        iid = adj.get('invoice_id')
        if iid not in adj_map: adj_map[iid] = {'add': 0, 'deduct': 0}
        if adj.get('adjustment_type') == 'ADD': adj_map[iid]['add'] += adj.get('amount', 0)
        else: adj_map[iid]['deduct'] += adj.get('amount', 0)
    vendor_invs = [i for i in invoices if i.get('invoice_category') == 'VENDOR']
    buyer_invs = [i for i in invoices if i.get('invoice_category') == 'BUYER']
    def adj_total(inv):
        a = adj_map.get(inv['id'], {'add': 0, 'deduct': 0})
        return (inv.get('base_amount', inv.get('total_amount', 0))) + a['add'] - a['deduct']
    total_sales = sum(adj_total(i) for i in buyer_invs)
    total_cost = sum(adj_total(i) for i in vendor_invs)
    vendor_pmts = [p for p in payments if p.get('payment_type') == 'VENDOR_PAYMENT' or any(vi['id'] == p.get('invoice_id') for vi in vendor_invs)]
    cust_pmts = [p for p in payments if p.get('payment_type') == 'CUSTOMER_PAYMENT' or any(bi['id'] == p.get('invoice_id') for bi in buyer_invs)]
    total_cash_in = sum(p.get('amount', 0) for p in cust_pmts)
    total_cash_out = sum(p.get('amount', 0) for p in vendor_pmts)
    gross_margin = total_sales - total_cost
    return {
        'total_sales_value': total_sales, 'total_vendor_cost': total_cost,
        'total_cash_in': total_cash_in, 'total_cash_out': total_cash_out,
        'gross_margin': gross_margin,
        'gross_margin_pct': round((gross_margin / total_sales * 100) if total_sales > 0 else 0),
        'total_invoiced': total_sales + total_cost, 'total_paid': total_cash_in + total_cash_out,
        'total_outstanding': (total_sales - total_cash_in) + (total_cost - total_cash_out),
        'accounts_receivable_outstanding': total_sales - total_cash_in,
        'accounts_payable_outstanding': total_cost - total_cash_out,
        'total_vendor_invoices': len(vendor_invs), 'total_buyer_invoices': len(buyer_invs),
        'garment_summary': [], 'monthly_trend': [],
        'invoices': serialize_doc(invoices), 'payments': serialize_doc(payments)
    }

