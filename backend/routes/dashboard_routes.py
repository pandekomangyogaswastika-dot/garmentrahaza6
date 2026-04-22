"""
Dashboard, Global Search, Vendor Dashboard
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

router = APIRouter(prefix="/api", tags=["dashboard"])

# ─── DASHBOARD ───────────────────────────────────────────────────────────────
@router.get("/dashboard")
async def get_dashboard(request: Request):
    await require_auth(request)
    db = get_db()
    n = now()
    three_days = n + timedelta(days=3)
    # PO counts by status
    total_pos = await db.production_pos.count_documents({})
    po_status_counts = {}
    for st in ["Draft", "Confirmed", "Distributed", "In Production", "Production Complete",
               "Variance Review", "Return Review", "Ready to Close", "Closed"]:
        po_status_counts[st] = await db.production_pos.count_documents({'status': st})
    active_pos = po_status_counts.get('In Production', 0) + po_status_counts.get('Distributed', 0)
    garments_count = await db.garments.count_documents({'status': 'active'})
    products_count = await db.products.count_documents({})
    invoices = await db.invoices.find({}, {'_id': 0}).to_list(None)
    payments = await db.payments.find({}, {'_id': 0}).to_list(None)
    # Active jobs
    all_active_parent_jobs = await db.production_jobs.find({
        'status': 'In Progress',
        '$or': [{'parent_job_id': None}, {'parent_job_id': ''}, {'parent_job_id': {'$exists': False}}]
    }).to_list(None)
    active_jobs = len(all_active_parent_jobs)
    # Production stats
    all_job_items = await db.production_job_items.find({}).to_list(None)
    total_produced_global = sum(i.get('produced_qty', 0) for i in all_job_items)
    total_available_global = sum(i.get('available_qty', i.get('shipment_qty', 0)) for i in all_job_items)
    global_progress_pct = round((total_produced_global / total_available_global * 100) if total_available_global > 0 else 0)
    # Shipment & request counts
    pending_shipments = await db.vendor_shipments.count_documents({'status': {'$in': ['Sent', 'In Transit']}})
    pending_additional = await db.material_requests.count_documents({'request_type': 'ADDITIONAL', 'status': 'Pending'})
    pending_replacement = await db.material_requests.count_documents({'request_type': 'REPLACEMENT', 'status': 'Pending'})
    pending_returns = await db.production_returns.count_documents({'status': {'$nin': ['Shipped Back', 'Closed']}})
    total_buyer_shipments = await db.buyer_shipments.count_documents({})
    total_vendor_shipments = await db.vendor_shipments.count_documents({'shipment_type': 'NORMAL'})
    # Accessory stats
    total_accessories = await db.accessories.count_documents({'status': 'active'})
    total_acc_shipments = await db.accessory_shipments.count_documents({})
    pending_acc_inspections = await db.accessory_inspections.count_documents({'status': 'Pending'})
    pending_acc_requests = await db.accessory_requests.count_documents({'status': 'Pending'})
    # Financial
    all_adjustments = await db.invoice_adjustments.find({}).to_list(None)
    adj_map = {}
    for adj in all_adjustments:
        iid = adj.get('invoice_id')
        if iid not in adj_map: adj_map[iid] = {'add': 0, 'deduct': 0}
        if adj.get('adjustment_type') == 'ADD': adj_map[iid]['add'] += adj.get('amount', 0)
        else: adj_map[iid]['deduct'] += adj.get('amount', 0)
    def get_adj_total(inv):
        a = adj_map.get(inv['id'], {'add': 0, 'deduct': 0})
        return (inv.get('base_amount', inv.get('total_amount', 0))) + a['add'] - a['deduct']
    vendor_invs = [i for i in invoices if i.get('invoice_category') == 'VENDOR']
    customer_invs = [i for i in invoices if i.get('invoice_category') == 'BUYER']
    total_vendor_cost = sum(get_adj_total(i) for i in vendor_invs)
    total_revenue = sum(get_adj_total(i) for i in customer_invs)
    paid_by_inv = {}
    for p in payments:
        if p.get('invoice_id'):
            paid_by_inv[p['invoice_id']] = paid_by_inv.get(p['invoice_id'], 0) + p.get('amount', 0)
    total_invoiced_ar = sum(get_adj_total(i) for i in customer_invs)
    total_invoiced_ap = sum(get_adj_total(i) for i in vendor_invs)
    total_paid_ar = sum(paid_by_inv.get(i['id'], i.get('total_paid', 0)) for i in customer_invs)
    total_paid_ap = sum(paid_by_inv.get(i['id'], i.get('total_paid', 0)) for i in vendor_invs)
    outstanding_ar = total_invoiced_ar - total_paid_ar
    outstanding_ap = total_invoiced_ap - total_paid_ap
    # Delayed POs
    delayed_pos = await db.production_pos.count_documents({
        'status': {'$in': ['Draft', 'Distributed', 'In Production']},
        'deadline': {'$lt': n}
    })
    # Alerts
    overdue_pos = await db.production_pos.find({
        'status': {'$in': ['Draft', 'Distributed', 'In Production']}, 'deadline': {'$lt': n}
    }, {'_id': 0}).sort('deadline', 1).limit(5).to_list(None)
    near_deadline = await db.production_pos.find({
        'status': {'$in': ['Draft', 'Distributed', 'In Production']},
        'deadline': {'$gte': n, '$lt': three_days}
    }, {'_id': 0}).sort('deadline', 1).limit(5).to_list(None)
    unpaid_invs = await db.invoices.find({'status': {'$in': ['Unpaid', 'Partial']}}, {'_id': 0}).sort('created_at', 1).limit(5).to_list(None)
    # Monthly data (6 months)
    monthly_data = []
    for i in range(5, -1, -1):
        start = datetime(n.year, n.month, 1, tzinfo=timezone.utc) - timedelta(days=i * 30)
        start = start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        m_pos = await db.production_pos.count_documents({'created_at': {'$gte': start, '$lt': end}})
        m_prog_agg = await db.production_progress.aggregate([
            {'$match': {'progress_date': {'$gte': start, '$lt': end}}},
            {'$group': {'_id': None, 'total': {'$sum': '$completed_quantity'}}}
        ]).to_list(None)
        monthly_data.append({
            'month': start.strftime('%b %y'), 'pos': m_pos,
            'production': m_prog_agg[0]['total'] if m_prog_agg else 0
        })
    # Work order status distribution (use production_jobs since work_orders may be sparse)
    wo_status_agg = await db.production_jobs.aggregate([
        {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
    ]).to_list(None)
    # Top garments by production
    top_garments_agg = await db.production_job_items.aggregate([
        {'$group': {'_id': '$vendor_name', 'total_qty': {'$sum': '$produced_qty'}}},
        {'$sort': {'total_qty': -1}}, {'$limit': 5}
    ]).to_list(None)
    # If vendor_name is not on job_items, aggregate via jobs
    if not top_garments_agg or all(not g.get('_id') for g in top_garments_agg):
        top_garments_agg = []
        jobs_for_top = await db.production_jobs.find({}).to_list(None)
        vendor_prod = {}
        for j in jobs_for_top:
            vn = j.get('vendor_name', 'Unknown')
            ji = await db.production_job_items.find({'job_id': j['id']}).to_list(None)
            vendor_prod[vn] = vendor_prod.get(vn, 0) + sum(i.get('produced_qty', 0) for i in ji)
        for vn, qty in sorted(vendor_prod.items(), key=lambda x: -x[1])[:5]:
            top_garments_agg.append({'_id': vn, 'total_qty': qty})
    # PO status breakdown for drilldown
    po_status_list = []
    for st, cnt in po_status_counts.items():
        if cnt > 0:
            sample_pos = await db.production_pos.find({'status': st}, {'_id': 0}).limit(5).to_list(None)
            po_status_list.append({'status': st, 'count': cnt, 'samples': serialize_doc(sample_pos)})
    # Reminders
    pending_reminders = await db.reminders.count_documents({'status': 'pending'})
    # On-time rate
    closed_pos = await db.production_pos.find({'status': 'Closed'}).to_list(None)
    on_time = sum(1 for p in closed_pos if p.get('deadline') and p.get('updated_at') and p['updated_at'] <= p['deadline'])
    on_time_rate = round((on_time / len(closed_pos) * 100) if closed_pos else 0)
    return {
        'totalPOs': total_pos, 'activePOs': active_pos, 'garments': garments_count,
        'products': products_count,
        'poStatusCounts': po_status_counts,
        'poStatusList': po_status_list,
        'totalInvoiced': total_invoiced_ar + total_invoiced_ap,
        'totalPaid': total_paid_ar + total_paid_ap,
        'outstanding': outstanding_ar + outstanding_ap,
        'totalVendorCost': total_vendor_cost, 'totalRevenue': total_revenue,
        'grossMargin': total_revenue - total_vendor_cost,
        'totalInvoicedAR': total_invoiced_ar, 'totalInvoicedAP': total_invoiced_ap,
        'outstandingAR': outstanding_ar, 'outstandingAP': outstanding_ap,
        'totalPaidAR': total_paid_ar, 'totalPaidAP': total_paid_ap,
        'activeJobs': active_jobs,
        'pendingShipments': pending_shipments,
        'pendingAdditionalRequests': pending_additional,
        'pendingReplacementRequests': pending_replacement,
        'pendingReturns': pending_returns,
        'totalBuyerShipments': total_buyer_shipments,
        'totalVendorShipments': total_vendor_shipments,
        'totalProducedGlobal': total_produced_global,
        'totalAvailableGlobal': total_available_global,
        'globalProgressPct': global_progress_pct,
        'totalAccessories': total_accessories,
        'totalAccShipments': total_acc_shipments,
        'pendingAccInspections': pending_acc_inspections,
        'pendingAccRequests': pending_acc_requests,
        'unpaidInvoices': sum(1 for i in invoices if i.get('status') == 'Unpaid'),
        'partialInvoices': sum(1 for i in invoices if i.get('status') == 'Partial'),
        'delayedPOs': delayed_pos,
        'monthlyData': monthly_data,
        'woStatus': wo_status_agg,
        'topGarments': top_garments_agg,
        'pendingReminders': pending_reminders,
        'onTimeRate': on_time_rate,
        'alerts': {
            'overduePos': serialize_doc(overdue_pos),
            'nearDeadlinePos': serialize_doc(near_deadline),
            'unpaidInvoices': serialize_doc(unpaid_invs)
        }
    }

@router.get("/dashboard/analytics")
async def get_dashboard_analytics(request: Request):
    """Enhanced analytics with date range filter"""
    user = await require_auth(request)
    db = get_db()
    sp = request.query_params
    date_from = parse_date(sp.get('from'))
    date_to = to_end_of_day(sp.get('to'))
    date_filter = {}
    if date_from: date_filter['$gte'] = date_from
    if date_to: date_filter['$lte'] = date_to
    date_q = {'created_at': date_filter} if date_filter else {}
    # Vendor lead times (shipment sent → received)
    vendor_lead_times = []
    ships = await db.vendor_shipments.find({**date_q, 'status': 'Received', 'shipment_type': 'NORMAL'}, {'_id': 0}).to_list(None)
    vendor_lt_map = {}
    for s in ships:
        vn = s.get('vendor_name', 'Unknown')
        if s.get('shipment_date') and s.get('updated_at'):
            delta = (s['updated_at'] - s['shipment_date']).days if isinstance(s['updated_at'], datetime) and isinstance(s['shipment_date'], datetime) else 0
            if delta >= 0:
                if vn not in vendor_lt_map: vendor_lt_map[vn] = []
                vendor_lt_map[vn].append(delta)
    for vn, days_list in sorted(vendor_lt_map.items()):
        avg_lt = round(sum(days_list) / len(days_list), 1) if days_list else 0
        vendor_lead_times.append({'vendor': vn, 'avg_days': avg_lt, 'shipment_count': len(days_list)})
    # Missing/defect rates by vendor
    all_inspections = await db.vendor_material_inspections.find(date_q, {'_id': 0}).to_list(None)
    vendor_defect_map = {}
    for insp in all_inspections:
        vn = insp.get('vendor_name', 'Unknown')
        if vn not in vendor_defect_map: vendor_defect_map[vn] = {'received': 0, 'missing': 0}
        vendor_defect_map[vn]['received'] += insp.get('total_received', 0)
        vendor_defect_map[vn]['missing'] += insp.get('total_missing', 0)
    defect_rates = []
    for vn, vals in sorted(vendor_defect_map.items()):
        total = vals['received'] + vals['missing']
        rate = round((vals['missing'] / total * 100) if total > 0 else 0, 1)
        defect_rates.append({'vendor': vn, 'missing_rate': rate, 'total_received': vals['received'], 'total_missing': vals['missing']})
    # Production throughput by week
    weekly_throughput = []
    n = now()
    for w in range(7, -1, -1):
        start = n - timedelta(days=(w + 1) * 7)
        end = n - timedelta(days=w * 7)
        prog_agg = await db.production_progress.aggregate([
            {'$match': {'progress_date': {'$gte': start, '$lt': end}}},
            {'$group': {'_id': None, 'total': {'$sum': '$completed_quantity'}}}
        ]).to_list(None)
        weekly_throughput.append({
            'week': f"W{8-w}", 'label': start.strftime('%d/%m'),
            'qty': prog_agg[0]['total'] if prog_agg else 0
        })
    # Production completion rate by product
    product_completion = await db.production_job_items.aggregate([
        {'$group': {'_id': '$product_name', 'total_available': {'$sum': '$available_qty'}, 'total_produced': {'$sum': '$produced_qty'}}},
        {'$sort': {'total_available': -1}}, {'$limit': 10}
    ]).to_list(None)
    product_comp = [{'product': p['_id'] or 'Unknown',
                     'available': p.get('total_available', 0),
                     'produced': p.get('total_produced', 0),
                     'rate': round((p['total_produced'] / p['total_available'] * 100) if p.get('total_available', 0) > 0 else 0, 1)
                     } for p in product_completion]
    # Shipment status breakdown
    ship_status_agg = await db.vendor_shipments.aggregate([
        {'$group': {'_id': '$status', 'count': {'$sum': 1}}}
    ]).to_list(None)
    # PO deadline distribution
    all_pos = await db.production_pos.find({'status': {'$nin': ['Closed', 'Draft']}}, {'_id': 0, 'deadline': 1, 'po_number': 1}).to_list(None)
    overdue_count = 0
    this_week_count = 0
    next_week_count = 0
    later_count = 0
    for p in all_pos:
        dl = p.get('deadline')
        if not dl: continue
        if isinstance(dl, str):
            dl = parse_date(dl)
        if not isinstance(dl, datetime): continue
        # Ensure timezone-aware comparison
        if dl.tzinfo is None:
            dl = dl.replace(tzinfo=timezone.utc)
        if dl < n: overdue_count += 1
        elif dl < n + timedelta(days=7): this_week_count += 1
        elif dl < n + timedelta(days=14): next_week_count += 1
        else: later_count += 1
    return {
        'vendorLeadTimes': vendor_lead_times,
        'defectRates': defect_rates,
        'weeklyThroughput': weekly_throughput,
        'productCompletion': product_comp,
        'shipmentStatus': [{'status': s['_id'] or 'Unknown', 'count': s['count']} for s in ship_status_agg],
        'deadlineDistribution': {
            'overdue': overdue_count, 'thisWeek': this_week_count,
            'nextWeek': next_week_count, 'later': later_count
        }
    }


# ─── VENDOR DASHBOARD ────────────────────────────────────────────────────────
@router.get("/vendor/dashboard")
async def get_vendor_dashboard(request: Request):
    user = await require_auth(request)
    if user.get('role') != 'vendor': raise HTTPException(403, 'Forbidden')
    db = get_db()
    vendor_id = user.get('vendor_id')
    jobs = await db.production_jobs.find({'vendor_id': vendor_id}, {'_id': 0}).sort('created_at', -1).to_list(None)
    active_jobs = len([j for j in jobs if j.get('status') == 'In Progress' and not j.get('parent_job_id')])
    completed_jobs = len([j for j in jobs if j.get('status') == 'Completed'])
    incoming = await db.vendor_shipments.count_documents({'vendor_id': vendor_id, 'status': 'Sent'})
    all_job_ids = [j['id'] for j in jobs]
    all_job_items = await db.production_job_items.find({'job_id': {'$in': all_job_ids}}).to_list(None) if all_job_ids else []
    total_produced = sum(i.get('produced_qty', 0) for i in all_job_items)
    total_available = sum(i.get('available_qty', i.get('shipment_qty', 0)) for i in all_job_items)
    return {
        'activeJobs': active_jobs, 'completedJobs': completed_jobs,
        'incomingShipments': incoming,
        'totalProduced': total_produced, 'totalAvailable': total_available,
        'progressPct': round((total_produced / total_available * 100) if total_available > 0 else 0),
        'recentProgress': [], 'alerts': {'overdueJobs': [], 'nearDeadlineJobs': []}
    }


# ─── GLOBAL SEARCH ───────────────────────────────────────────────────────────
@router.get("/global-search")
async def global_search(request: Request):
    """
    Global Search v2 — Rahaza-native.
    Mencari lintas entitas bisnis utama: Order, Work Order, Customer, Material,
    Employee, AR Invoice, AP Invoice, Line.

    Response: {results: [{type, id, label, sub, module}]}
    - `module` = moduleId yang dikenali moduleRegistry.js (untuk navigasi saat klik).
    """
    await require_auth(request)
    db = get_db()
    q = request.query_params.get('q', '').strip()
    if not q or len(q) < 2:
        return {'results': []}

    regex = {'$regex': q, '$options': 'i'}
    limit_per_type = 5
    results = []

    # ── Orders ─────────────────────────────────────────────────────────────
    orders = await db.rahaza_orders.find(
        {'$or': [
            {'order_number': regex},
            {'customer_name_snapshot': regex},
            {'notes': regex},
        ]},
        {'_id': 0, 'id': 1, 'order_number': 1, 'customer_name_snapshot': 1, 'status': 1, 'order_date': 1}
    ).limit(limit_per_type).to_list(None)
    for o in orders:
        results.append({
            'type': 'Order',
            'id': o.get('id'),
            'label': o.get('order_number', ''),
            'sub': f"{o.get('customer_name_snapshot', '')} · {o.get('status', '')}",
            'module': 'prod-orders',
        })

    # ── Work Orders ────────────────────────────────────────────────────────
    wos = await db.rahaza_work_orders.find(
        {'$or': [
            {'wo_number': regex},
            {'order_number_snapshot': regex},
            {'model_code_snapshot': regex},
            {'model_name_snapshot': regex},
        ]},
        {'_id': 0, 'id': 1, 'wo_number': 1, 'order_number_snapshot': 1, 'model_code_snapshot': 1,
         'model_name_snapshot': 1, 'status': 1, 'qty': 1}
    ).limit(limit_per_type).to_list(None)
    for w in wos:
        results.append({
            'type': 'Work Order',
            'id': w.get('id'),
            'label': w.get('wo_number', ''),
            'sub': f"{w.get('model_code_snapshot', '')} · {w.get('qty', 0)} pcs · {w.get('status', '')}",
            'module': 'prod-work-orders',
        })

    # ── Customers ──────────────────────────────────────────────────────────
    customers = await db.rahaza_customers.find(
        {'$or': [{'code': regex}, {'name': regex}, {'phone': regex}, {'email': regex}]},
        {'_id': 0, 'id': 1, 'code': 1, 'name': 1, 'active': 1}
    ).limit(limit_per_type).to_list(None)
    for c in customers:
        results.append({
            'type': 'Pelanggan',
            'id': c.get('id'),
            'label': c.get('name', ''),
            'sub': c.get('code', ''),
            'module': 'mgmt-rahaza-customers',
        })

    # ── Materials ──────────────────────────────────────────────────────────
    materials = await db.rahaza_materials.find(
        {'$or': [{'code': regex}, {'name': regex}]},
        {'_id': 0, 'id': 1, 'code': 1, 'name': 1, 'type': 1, 'unit': 1}
    ).limit(limit_per_type).to_list(None)
    for m in materials:
        results.append({
            'type': 'Material',
            'id': m.get('id'),
            'label': m.get('name', ''),
            'sub': f"{m.get('code', '')} · {m.get('type', '')} ({m.get('unit', '')})",
            'module': 'wh-materials',
        })

    # ── Employees ──────────────────────────────────────────────────────────
    employees = await db.rahaza_employees.find(
        {'$or': [{'employee_code': regex}, {'name': regex}, {'phone': regex}]},
        {'_id': 0, 'id': 1, 'employee_code': 1, 'name': 1, 'role': 1, 'active': 1}
    ).limit(limit_per_type).to_list(None)
    for e in employees:
        results.append({
            'type': 'Karyawan',
            'id': e.get('id'),
            'label': e.get('name', ''),
            'sub': f"{e.get('employee_code', '')} · {e.get('role', '')}",
            'module': 'prod-employees',
        })

    # ── AR Invoices ────────────────────────────────────────────────────────
    ar = await db.rahaza_ar_invoices.find(
        {'$or': [{'invoice_number': regex}, {'customer_name': regex}]},
        {'_id': 0, 'id': 1, 'invoice_number': 1, 'customer_name': 1, 'total': 1, 'status': 1}
    ).limit(limit_per_type).to_list(None)
    for i in ar:
        results.append({
            'type': 'AR Invoice',
            'id': i.get('id'),
            'label': i.get('invoice_number', ''),
            'sub': f"{i.get('customer_name', '')} · {i.get('status', '')}",
            'module': 'fin-ar-invoices',
        })

    # ── AP Invoices ────────────────────────────────────────────────────────
    ap = await db.rahaza_ap_invoices.find(
        {'$or': [{'invoice_number': regex}, {'vendor_name': regex}]},
        {'_id': 0, 'id': 1, 'invoice_number': 1, 'vendor_name': 1, 'total': 1, 'status': 1}
    ).limit(limit_per_type).to_list(None)
    for i in ap:
        results.append({
            'type': 'AP Invoice',
            'id': i.get('id'),
            'label': i.get('invoice_number', ''),
            'sub': f"{i.get('vendor_name', '')} · {i.get('status', '')}",
            'module': 'fin-ap',  # routes to legacy AP module (Rahaza AP belum punya module dedicated)
        })

    # ── Lines ──────────────────────────────────────────────────────────────
    lines = await db.rahaza_lines.find(
        {'$or': [{'code': regex}, {'name': regex}]},
        {'_id': 0, 'id': 1, 'code': 1, 'name': 1, 'process_code': 1, 'active': 1}
    ).limit(limit_per_type).to_list(None)
    for l in lines:
        results.append({
            'type': 'Line Produksi',
            'id': l.get('id'),
            'label': l.get('code', ''),
            'sub': f"{l.get('name', '')} · {l.get('process_code', '')}",
            'module': 'prod-lines',
        })

    return {'results': results}


# ─── ATTACHMENTS ─────────────────────────────────────────────────────────────
@router.get("/attachments")
async def get_attachments(request: Request):
    await require_auth(request)
    db = get_db()
    sp = request.query_params
    entity_type = sp.get('entity_type')
    entity_id = sp.get('entity_id')
    if not entity_type or not entity_id: raise HTTPException(400, 'entity_type and entity_id required')
    return serialize_doc(await db.attachments.find({'entity_type': entity_type, 'entity_id': entity_id}, {'_id': 0}).sort('uploaded_at', -1).to_list(None))

