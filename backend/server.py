"""
End-to-End Fashion ERP - Main Server
All route logic has been modularized into routes/ directory.
This file handles app initialization, middleware, and router registration.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from database import get_db, client
from auth import seed_initial_data
import os
import logging
from datetime import datetime, timezone
from collections import defaultdict
import time

app = FastAPI(title="PT Rahaza Global Indonesia — ERP Rajut API")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── STARTUP ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await seed_initial_data()
    await create_indexes()
    # PT Rahaza master data seed (idempotent)
    try:
        from routes.rahaza_master import seed_rahaza_master_data
        await seed_rahaza_master_data()
        from routes.rahaza_production import seed_rahaza_production_data
        await seed_rahaza_production_data()
    except Exception as e:
        logger.warning(f"Rahaza master seed: {e}")
    # Init persistent storage
    try:
        from storage import init_storage
        init_storage()
    except Exception as e:
        logger.warning(f"Storage init: {e}")
    # Start Alert Rule Engine background task (Phase 18A)
    try:
        start_alerts_bg()
        logger.info("Alert rule engine started")
    except Exception as e:
        logger.warning(f"Alert engine start failed: {e}")
    logger.info("PT Rahaza ERP API started")


async def create_indexes():
    """Create MongoDB indexes for active collections only (PT Rahaza)."""
    db = get_db()
    try:
        # Auth / RBAC
        await db.users.create_index("email", unique=True)
        await db.roles.create_index("name", unique=True)
        await db.permissions.create_index("key", unique=True)
        await db.activity_logs.create_index([("timestamp", -1)])

        # Warehouse (reused)
        await db.warehouse_locations.create_index("code", unique=True)
        await db.warehouse_locations.create_index("type")
        await db.warehouse_receiving.create_index("receipt_number", unique=True)
        await db.warehouse_receiving.create_index("status")
        await db.warehouse_receiving.create_index("created_at")
        await db.warehouse_stock.create_index([("location_id", 1), ("sku", 1)])
        await db.warehouse_stock.create_index("sku")
        await db.warehouse_movements.create_index("created_at")
        await db.warehouse_movements.create_index("sku")
        await db.warehouse_opname.create_index("opname_number", unique=True)
        await db.warehouse_opname.create_index("status")

        # Accessories (retained as master)
        await db.accessories.create_index("status")

        # PT Rahaza master data — unique code on active records only
        # (use partial index so deactivated codes can be reused)
        pfe_active = {"partialFilterExpression": {"active": True}}
        # Drop old non-partial unique indexes if they exist
        for col in ["rahaza_locations", "rahaza_processes", "rahaza_shifts", "rahaza_machines", "rahaza_lines"]:
            try:
                await db[col].drop_index("code_1")
            except Exception:
                pass
        try:
            await db["rahaza_employees"].drop_index("employee_code_1")
        except Exception:
            pass

        await db.rahaza_locations.create_index("code", unique=True, **pfe_active)
        await db.rahaza_processes.create_index("code", unique=True)  # process seeded, no soft-delete reuse
        await db.rahaza_shifts.create_index("code", unique=True, **pfe_active)
        await db.rahaza_machines.create_index("code", unique=True, **pfe_active)
        await db.rahaza_lines.create_index("code", unique=True, **pfe_active)
        await db.rahaza_employees.create_index("employee_code", unique=True, **pfe_active)

        # Rahaza production execution (Fase 4)
        await db.rahaza_models.create_index("code", unique=True, **pfe_active)
        await db.rahaza_sizes.create_index("code", unique=True, **pfe_active)
        await db.rahaza_line_assignments.create_index([("line_id", 1), ("assign_date", 1), ("shift_id", 1)])
        await db.rahaza_line_assignments.create_index("assign_date")
        await db.rahaza_wip_events.create_index([("line_id", 1), ("timestamp", -1)])
        await db.rahaza_wip_events.create_index([("process_id", 1), ("timestamp", -1)])
        await db.rahaza_wip_events.create_index("timestamp")

        # Rahaza orders (Fase 5)
        await db.rahaza_customers.create_index("code", unique=True, **pfe_active)
        await db.rahaza_orders.create_index("order_number", unique=True)
        await db.rahaza_orders.create_index("status")
        await db.rahaza_orders.create_index("order_date")
        await db.rahaza_orders.create_index("customer_id")

        # Rahaza BOM (Fase 5b) — unique (model_id, size_id) for active BOM
        try:
            await db.rahaza_boms.drop_index("model_size_active_unique")
        except Exception:
            pass
        await db.rahaza_boms.create_index(
            [("model_id", 1), ("size_id", 1)],
            unique=True,
            name="model_size_active_unique",
            partialFilterExpression={"active": True},
        )
        await db.rahaza_boms.create_index("model_id")

        # Rahaza work orders (Fase 5c)
        await db.rahaza_work_orders.create_index("wo_number", unique=True)
        await db.rahaza_work_orders.create_index("status")
        await db.rahaza_work_orders.create_index("order_id")
        await db.rahaza_work_orders.create_index("model_id")
        await db.rahaza_wip_events.create_index("work_order_id")

        # Rahaza inventory (Fase 7)
        await db.rahaza_materials.create_index("code", unique=True, **pfe_active)
        await db.rahaza_materials.create_index("type")
        await db.rahaza_material_stock.create_index([("material_id", 1), ("location_id", 1)], unique=True)
        await db.rahaza_material_stock.create_index("location_id")
        await db.rahaza_material_movements.create_index([("timestamp", -1)])
        await db.rahaza_material_movements.create_index("material_id")
        await db.rahaza_material_issues.create_index("mi_number", unique=True)
        await db.rahaza_material_issues.create_index("work_order_id")
        await db.rahaza_material_issues.create_index("status")

        # Rahaza attendance (Fase 8a)
        await db.rahaza_attendance_events.create_index([("employee_id", 1), ("date", 1)], unique=True)
        await db.rahaza_attendance_events.create_index("date")
        await db.rahaza_attendance_events.create_index("status")

        # Rahaza payroll (Fase 8b + 8c)
        await db.rahaza_payroll_profiles.create_index([("employee_id", 1), ("active", 1)])
        await db.rahaza_payroll_profiles.create_index("pay_scheme")
        await db.rahaza_payroll_runs.create_index("run_number", unique=True)
        await db.rahaza_payroll_runs.create_index([("period_from", 1), ("period_to", 1)])
        await db.rahaza_payroll_runs.create_index("status")
        await db.rahaza_payslips.create_index([("run_id", 1), ("employee_id", 1)])
        await db.rahaza_payslips.create_index("employee_id")

        # Rahaza finance (Fase 8.5)
        await db.rahaza_cost_centers.create_index([("code", 1), ("active", 1)])
        await db.rahaza_ar_invoices.create_index("invoice_number", unique=True)
        await db.rahaza_ar_invoices.create_index("status")
        await db.rahaza_ar_invoices.create_index("customer_id")
        await db.rahaza_ap_invoices.create_index("invoice_number", unique=True)
        await db.rahaza_ap_invoices.create_index("status")
        await db.rahaza_cash_accounts.create_index([("code", 1), ("active", 1)])
        await db.rahaza_cash_movements.create_index([("timestamp", -1)])
        await db.rahaza_cash_movements.create_index("account_id")
        await db.rahaza_expenses.create_index([("date", -1)])
        await db.rahaza_expenses.create_index("cost_center_id")

        # Rahaza costing / HPP (Fase 9)
        await db.rahaza_costing_settings.create_index("id", unique=True)
        await db.rahaza_hpp_snapshots.create_index("work_order_id", unique=True)

        # Rahaza Bundles (Phase 17A)
        await db.rahaza_bundles.create_index("bundle_number", unique=True)
        await db.rahaza_bundles.create_index("work_order_id")
        await db.rahaza_bundles.create_index("status")
        await db.rahaza_bundles.create_index([("current_process_id", 1), ("status", 1)])
        await db.rahaza_bundles.create_index([("current_line_id", 1), ("status", 1)])
        await db.rahaza_bundles.create_index("parent_bundle_id")
        await db.rahaza_bundles.create_index("created_at")

        # Rahaza Andon (Phase 18B)
        await db.rahaza_andon_events.create_index("status")
        await db.rahaza_andon_events.create_index([("created_at", -1)])
        await db.rahaza_andon_events.create_index("employee_id")
        await db.rahaza_andon_events.create_index("line_id")

        # Rahaza SOP (Phase 18D)
        await db.rahaza_model_process_sop.create_index([("model_id", 1), ("process_id", 1)])
        await db.rahaza_model_process_sop.create_index("active")

        logger.info("MongoDB indexes created (PT Rahaza active schema)")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")

@app.on_event("shutdown")
async def shutdown():
    try:
        stop_alerts_bg()
    except Exception:
        pass
    client.close()

# ─── RATE LIMITING MIDDLEWARE ────────────────────────────────────────────────
_rate_limit_store = defaultdict(list)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    current = time.time()
    window = 60
    max_requests = 200
    _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if current - t < window]
    if len(_rate_limit_store[client_ip]) >= max_requests:
        return JSONResponse({"error": "Rate limit exceeded. Max 200 requests/minute."}, status_code=429)
    _rate_limit_store[client_ip].append(current)
    response = await call_next(request)
    return response

# ─── INCLUDE ALL ROUTERS ────────────────────────────────────────────────────
# Domain routers (active after PT Rahaza cleanup — Stage A Phase 1)
from routes.auth_routes import router as auth_router
from routes.master_data import router as master_data_router
from routes.production_po import router as production_po_router
from routes.production import router as production_router
from routes.finance import router as finance_router
from routes.admin import router as admin_router
from routes.dashboard_routes import router as dashboard_router
from routes.operations import router as operations_router
from routes.file_storage import router as file_router
from routes.websocket import router as ws_router
from routes.warehouse import router as warehouse_router
from routes.finishing import router as finishing_router
from routes.qc import router as qc_router
from routes.rahaza_master import router as rahaza_master_router
from routes.rahaza_production import router as rahaza_production_router
from routes.rahaza_orders import router as rahaza_orders_router
from routes.rahaza_bom import router as rahaza_bom_router
from routes.rahaza_work_orders import router as rahaza_work_orders_router
from routes.rahaza_execution import router as rahaza_execution_router
from routes.rahaza_inventory import router as rahaza_inventory_router
from routes.rahaza_attendance import router as rahaza_attendance_router
from routes.rahaza_payroll import router as rahaza_payroll_router
from routes.rahaza_finance import router as rahaza_finance_router
from routes.rahaza_hpp import router as rahaza_hpp_router
from routes.rahaza_reports import router as rahaza_reports_router
from routes.rahaza_notifications import router as rahaza_notifications_router
from routes.rahaza_audit import router as rahaza_audit_router
from routes.rahaza_shipments import router as rahaza_shipments_router
from routes.rahaza_next_actions import router as rahaza_next_actions_router
from routes.rahaza_setup import router as rahaza_setup_router
from routes.rahaza_bundles import router as rahaza_bundles_router
from routes.rahaza_alerts import (
    router as rahaza_alerts_router,
    start_background_task as start_alerts_bg,
    stop_background_task as stop_alerts_bg,
)
from routes.rahaza_andon import router as rahaza_andon_router
from routes.rahaza_tv import router as rahaza_tv_router
from routes.rahaza_sop import router as rahaza_sop_router
from routes.rahaza_aps import router as rahaza_aps_router

# NOTE: legacy routers removed for PT Rahaza rebuild:
#   buyer_portal, retail, distribution, shipments, rnd, cutting
# These flows are not relevant for in-house knit manufacturer.

# Register all active routers
app.include_router(auth_router)
app.include_router(master_data_router)
app.include_router(production_po_router)
app.include_router(production_router)
app.include_router(finance_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
app.include_router(operations_router)
app.include_router(file_router)
app.include_router(ws_router)
app.include_router(warehouse_router)
app.include_router(finishing_router)
app.include_router(qc_router)
app.include_router(rahaza_master_router)
app.include_router(rahaza_production_router)
app.include_router(rahaza_orders_router)
app.include_router(rahaza_bom_router)
app.include_router(rahaza_work_orders_router)
app.include_router(rahaza_execution_router)
app.include_router(rahaza_inventory_router)
app.include_router(rahaza_attendance_router)
app.include_router(rahaza_payroll_router)
app.include_router(rahaza_finance_router)
app.include_router(rahaza_hpp_router)
app.include_router(rahaza_reports_router)
app.include_router(rahaza_notifications_router)
app.include_router(rahaza_audit_router)
app.include_router(rahaza_shipments_router)
app.include_router(rahaza_next_actions_router)
app.include_router(rahaza_setup_router)
app.include_router(rahaza_bundles_router)
app.include_router(rahaza_alerts_router)
app.include_router(rahaza_andon_router)
app.include_router(rahaza_tv_router)
app.include_router(rahaza_sop_router)
app.include_router(rahaza_aps_router)

# ─── CORS MIDDLEWARE ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
