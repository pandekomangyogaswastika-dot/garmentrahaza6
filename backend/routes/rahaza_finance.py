"""
PT Rahaza — Finance Enhancement (Fase 8.5)

Scope (MVP):
  - Cost Centers: CRUD (dipakai tagging expense/HPP)
  - AR Invoices: draft -> sent -> partial_paid -> paid | overdue (manual check)
  - AP Invoices: draft -> sent -> partial_paid -> paid
  - Payments: record payment -> update AR/AP status otomatis
  - Cash Accounts: CRUD rekening kas/bank + saldo via movements ledger
  - Cash Movements: in/out, dilink ke AR payment, AP payment, expense
  - Expenses: entry biaya operasional (manual)
  - Aging Report AR: bucket 0-30, 31-60, 61-90, 90+
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
from datetime import datetime, timezone, date
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-finance"])

AR_STATUS = ["draft", "sent", "partial_paid", "paid", "overdue", "cancelled"]
AP_STATUS = ["draft", "sent", "partial_paid", "paid", "cancelled"]


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)
def _today_iso(): return date.today().isoformat()


async def _require_fin(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin", "owner", "accounting", "finance", "manager"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "finance.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission finance.")


async def _gen_number(db, coll, prefix):
    today = date.today().strftime("%Y%m%d")
    p = f"{prefix}-{today}-"
    cnt = await db[coll].count_documents({"invoice_number": {"$regex": f"^{p}"}}) if "invoice" in coll else await db[coll].count_documents({"number": {"$regex": f"^{p}"}})
    return f"{p}{cnt+1:03d}"


# ── COST CENTERS ─────────────────────────────────────────────────────────────
@router.get("/cost-centers")
async def list_cost_centers(request: Request, active_only: bool = True):
    await require_auth(request)
    db = get_db()
    q = {"active": True} if active_only else {}
    rows = await db.rahaza_cost_centers.find(q, {"_id": 0}).sort("code", 1).to_list(None)
    return serialize_doc(rows)


@router.post("/cost-centers")
async def create_cost_center(request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(400, "code & name wajib.")
    if await db.rahaza_cost_centers.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah dipakai.")
    doc = {
        "id": _uid(), "code": code, "name": name,
        "category": body.get("category") or "umum",
        "overhead_rate_per_pcs": float(body.get("overhead_rate_per_pcs") or 0),
        "notes": body.get("notes") or "",
        "active": True,
        "created_at": _now(), "updated_at": _now(),
        "created_by": user["id"], "created_by_name": user.get("name", ""),
    }
    await db.rahaza_cost_centers.insert_one(doc)
    return serialize_doc(doc)


@router.put("/cost-centers/{cid}")
async def update_cost_center(cid: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None)
    body["updated_at"] = _now()
    res = await db.rahaza_cost_centers.update_one({"id": cid}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(404, "Cost center tidak ditemukan.")
    out = await db.rahaza_cost_centers.find_one({"id": cid}, {"_id": 0})
    return serialize_doc(out)


@router.delete("/cost-centers/{cid}")
async def delete_cost_center(cid: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    res = await db.rahaza_cost_centers.update_one({"id": cid, "active": True}, {"$set": {"active": False, "updated_at": _now()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Cost center tidak ditemukan.")
    return {"status": "deleted"}


# ── AR INVOICES ──────────────────────────────────────────────────────────────
@router.get("/ar-invoices")
async def list_ar(request: Request, status: Optional[str] = None, customer_id: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if status: q["status"] = status
    if customer_id: q["customer_id"] = customer_id
    rows = await db.rahaza_ar_invoices.find(q, {"_id": 0}).sort("issue_date", -1).to_list(None)
    # enrich customer
    cids = list({r.get("customer_id") for r in rows if r.get("customer_id")})
    cs = await db.rahaza_customers.find({"id": {"$in": cids}}, {"_id": 0}).to_list(None) if cids else []
    cmap = {c["id"]: c for c in cs}
    for r in rows:
        c = cmap.get(r.get("customer_id")) or {}
        r["customer_name"] = c.get("name")
    return serialize_doc(rows)


@router.post("/ar-invoices")
async def create_ar(request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    customer_id = body.get("customer_id")
    if not customer_id:
        raise HTTPException(400, "customer_id wajib.")
    customer = await db.rahaza_customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer tidak ditemukan.")
    items = body.get("items") or []
    subtotal = 0
    norm_items = []
    for it in items:
        qty = float(it.get("qty") or 0)
        price = float(it.get("price") or 0)
        amount = qty * price
        subtotal += amount
        norm_items.append({"description": it.get("description") or "", "qty": qty, "unit": it.get("unit") or "pcs", "price": price, "amount": round(amount)})
    tax_pct = float(body.get("tax_pct") or 0)
    tax = round(subtotal * tax_pct / 100)
    total = round(subtotal + tax)
    invoice_number = await _gen_number(db, "rahaza_ar_invoices", "AR")
    doc = {
        "id": _uid(), "invoice_number": invoice_number,
        "customer_id": customer_id,
        "order_id": body.get("order_id") or None,
        "issue_date": body.get("issue_date") or _today_iso(),
        "due_date": body.get("due_date") or _today_iso(),
        "items": norm_items, "subtotal": round(subtotal), "tax_pct": tax_pct, "tax_amount": tax,
        "total": total, "paid_amount": 0, "balance": total,
        "status": "draft", "notes": body.get("notes") or "",
        "created_at": _now(), "updated_at": _now(),
        "created_by": user["id"], "created_by_name": user.get("name", ""),
    }
    await db.rahaza_ar_invoices.insert_one(doc)
    return serialize_doc(doc)


@router.post("/ar-invoices/{iid}/status")
async def change_ar_status(iid: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    new_status = (body.get("status") or "").lower()
    if new_status not in AR_STATUS:
        raise HTTPException(400, f"status invalid: {AR_STATUS}")
    inv = await db.rahaza_ar_invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan.")
    await db.rahaza_ar_invoices.update_one({"id": iid}, {"$set": {"status": new_status, "updated_at": _now()}})
    out = await db.rahaza_ar_invoices.find_one({"id": iid}, {"_id": 0})
    return serialize_doc(out)


@router.post("/ar-invoices/{iid}/payment")
async def record_ar_payment(iid: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    amount = float(body.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(400, "amount harus > 0")
    inv = await db.rahaza_ar_invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan.")
    paid = float(inv.get("paid_amount") or 0) + amount
    total = float(inv.get("total") or 0)
    if paid > total + 0.01:
        raise HTTPException(400, f"Pembayaran melebihi total invoice (balance: {total - (paid - amount):.0f})")
    new_status = "paid" if paid >= total - 0.01 else "partial_paid"
    balance = max(0, total - paid)
    await db.rahaza_ar_invoices.update_one({"id": iid}, {"$set": {
        "paid_amount": round(paid), "balance": round(balance), "status": new_status, "updated_at": _now()
    }})
    # Record cash movement
    account_id = body.get("account_id")
    if account_id:
        acc = await db.rahaza_cash_accounts.find_one({"id": account_id}, {"_id": 0})
        if acc:
            await db.rahaza_cash_movements.insert_one({
                "id": _uid(), "account_id": account_id, "account_name": acc.get("name"),
                "direction": "in", "amount": round(amount),
                "category": "ar_payment", "ref_id": iid, "ref_label": inv.get("invoice_number"),
                "date": body.get("date") or _today_iso(), "notes": body.get("notes") or "",
                "timestamp": _now(), "created_by": user["id"], "created_by_name": user.get("name", ""),
            })
            await db.rahaza_cash_accounts.update_one({"id": account_id}, {"$inc": {"balance": round(amount)}})
    out = await db.rahaza_ar_invoices.find_one({"id": iid}, {"_id": 0})
    return serialize_doc(out)


@router.get("/ar-aging")
async def ar_aging(request: Request):
    await require_auth(request)
    db = get_db()
    today = date.today()
    rows = await db.rahaza_ar_invoices.find({"status": {"$in": ["sent", "partial_paid", "overdue"]}}, {"_id": 0}).to_list(None)
    buckets = {"current": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
    details = []
    for r in rows:
        try:
            due = datetime.strptime(r["due_date"], "%Y-%m-%d").date()
            days_overdue = (today - due).days
        except Exception:
            days_overdue = 0
        balance = float(r.get("balance") or 0)
        if days_overdue <= 0: buckets["current"] += balance
        elif days_overdue <= 30: buckets["1_30"] += balance
        elif days_overdue <= 60: buckets["31_60"] += balance
        elif days_overdue <= 90: buckets["61_90"] += balance
        else: buckets["90_plus"] += balance
        details.append({**r, "days_overdue": days_overdue})
    return {"buckets": {k: round(v) for k, v in buckets.items()}, "total": round(sum(buckets.values())), "details": serialize_doc(details)}


# ── AP INVOICES ──────────────────────────────────────────────────────────────
@router.get("/ap-invoices")
async def list_ap(request: Request, status: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if status: q["status"] = status
    rows = await db.rahaza_ap_invoices.find(q, {"_id": 0}).sort("issue_date", -1).to_list(None)
    return serialize_doc(rows)


@router.post("/ap-invoices")
async def create_ap(request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    vendor_name = (body.get("vendor_name") or "").strip()
    if not vendor_name:
        raise HTTPException(400, "vendor_name wajib.")
    items = body.get("items") or []
    subtotal = 0
    norm = []
    for it in items:
        qty = float(it.get("qty") or 0); price = float(it.get("price") or 0)
        amt = qty * price; subtotal += amt
        norm.append({"description": it.get("description") or "", "qty": qty, "unit": it.get("unit") or "", "price": price, "amount": round(amt)})
    tax_pct = float(body.get("tax_pct") or 0)
    tax = round(subtotal * tax_pct / 100)
    total = round(subtotal + tax)
    invoice_number = await _gen_number(db, "rahaza_ap_invoices", "AP")
    doc = {
        "id": _uid(), "invoice_number": invoice_number,
        "vendor_name": vendor_name, "vendor_code": body.get("vendor_code") or "",
        "issue_date": body.get("issue_date") or _today_iso(),
        "due_date": body.get("due_date") or _today_iso(),
        "items": norm, "subtotal": round(subtotal), "tax_pct": tax_pct, "tax_amount": tax,
        "total": total, "paid_amount": 0, "balance": total,
        "status": "draft", "notes": body.get("notes") or "",
        "cost_center_id": body.get("cost_center_id") or None,
        "created_at": _now(), "updated_at": _now(),
        "created_by": user["id"], "created_by_name": user.get("name", ""),
    }
    await db.rahaza_ap_invoices.insert_one(doc)
    return serialize_doc(doc)


@router.post("/ap-invoices/{iid}/payment")
async def record_ap_payment(iid: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    amount = float(body.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(400, "amount harus > 0")
    inv = await db.rahaza_ap_invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice tidak ditemukan.")
    paid = float(inv.get("paid_amount") or 0) + amount
    total = float(inv.get("total") or 0)
    if paid > total + 0.01:
        raise HTTPException(400, "Pembayaran melebihi total invoice.")
    new_status = "paid" if paid >= total - 0.01 else "partial_paid"
    balance = max(0, total - paid)
    await db.rahaza_ap_invoices.update_one({"id": iid}, {"$set": {
        "paid_amount": round(paid), "balance": round(balance), "status": new_status, "updated_at": _now()
    }})
    account_id = body.get("account_id")
    if account_id:
        acc = await db.rahaza_cash_accounts.find_one({"id": account_id}, {"_id": 0})
        if acc:
            await db.rahaza_cash_movements.insert_one({
                "id": _uid(), "account_id": account_id, "account_name": acc.get("name"),
                "direction": "out", "amount": round(amount),
                "category": "ap_payment", "ref_id": iid, "ref_label": inv.get("invoice_number"),
                "date": body.get("date") or _today_iso(), "notes": body.get("notes") or "",
                "timestamp": _now(), "created_by": user["id"], "created_by_name": user.get("name", ""),
            })
            await db.rahaza_cash_accounts.update_one({"id": account_id}, {"$inc": {"balance": -round(amount)}})
    out = await db.rahaza_ap_invoices.find_one({"id": iid}, {"_id": 0})
    return serialize_doc(out)


# ── CASH ACCOUNTS & MOVEMENTS ────────────────────────────────────────────────
@router.get("/cash-accounts")
async def list_cash_accounts(request: Request, active_only: bool = True):
    await require_auth(request)
    db = get_db()
    q = {"active": True} if active_only else {}
    rows = await db.rahaza_cash_accounts.find(q, {"_id": 0}).sort("code", 1).to_list(None)
    return serialize_doc(rows)


@router.post("/cash-accounts")
async def create_cash_account(request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    code = (body.get("code") or "").strip().upper()
    name = (body.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(400, "code & name wajib.")
    if await db.rahaza_cash_accounts.find_one({"code": code, "active": True}):
        raise HTTPException(409, f"Kode '{code}' sudah terpakai.")
    doc = {
        "id": _uid(), "code": code, "name": name,
        "type": body.get("type") or "cash",  # cash | bank
        "bank_name": body.get("bank_name") or "",
        "account_number": body.get("account_number") or "",
        "balance": float(body.get("opening_balance") or 0),
        "opening_balance": float(body.get("opening_balance") or 0),
        "notes": body.get("notes") or "",
        "active": True,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.rahaza_cash_accounts.insert_one(doc)
    return serialize_doc(doc)


@router.put("/cash-accounts/{aid}")
async def update_cash_account(aid: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    body.pop("_id", None); body.pop("id", None); body.pop("created_at", None); body.pop("balance", None)
    body["updated_at"] = _now()
    await db.rahaza_cash_accounts.update_one({"id": aid}, {"$set": body})
    return {"status": "ok"}


@router.delete("/cash-accounts/{aid}")
async def delete_cash_account(aid: str, request: Request):
    user = await _require_fin(request)
    db = get_db()
    await db.rahaza_cash_accounts.update_one({"id": aid, "active": True}, {"$set": {"active": False}})
    return {"status": "deleted"}


@router.get("/cash-movements")
async def list_movements(request: Request, account_id: Optional[str] = None, from_: Optional[str] = None, to: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if account_id: q["account_id"] = account_id
    if from_ or to:
        rg = {}
        if from_: rg["$gte"] = from_
        if to: rg["$lte"] = to
        q["date"] = rg
    rows = await db.rahaza_cash_movements.find(q, {"_id": 0}).sort("timestamp", -1).to_list(None)
    return serialize_doc(rows)


# ── EXPENSES ─────────────────────────────────────────────────────────────────
@router.get("/expenses")
async def list_expenses(request: Request, from_: Optional[str] = None, to: Optional[str] = None, cost_center_id: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    q = {}
    if cost_center_id: q["cost_center_id"] = cost_center_id
    if from_ or to:
        rg = {}
        if from_: rg["$gte"] = from_
        if to: rg["$lte"] = to
        q["date"] = rg
    rows = await db.rahaza_expenses.find(q, {"_id": 0}).sort("date", -1).to_list(None)
    # enrich cost center
    ccids = list({r.get("cost_center_id") for r in rows if r.get("cost_center_id")})
    ccs = await db.rahaza_cost_centers.find({"id": {"$in": ccids}}, {"_id": 0}).to_list(None) if ccids else []
    ccmap = {c["id"]: c for c in ccs}
    for r in rows:
        cc = ccmap.get(r.get("cost_center_id")) or {}
        r["cost_center_code"] = cc.get("code"); r["cost_center_name"] = cc.get("name")
    return serialize_doc(rows)


@router.post("/expenses")
async def create_expense(request: Request):
    user = await _require_fin(request)
    db = get_db()
    body = await request.json()
    amount = float(body.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(400, "amount harus > 0")
    doc = {
        "id": _uid(),
        "date": body.get("date") or _today_iso(),
        "category": body.get("category") or "operasional",
        "description": body.get("description") or "",
        "amount": round(amount),
        "cost_center_id": body.get("cost_center_id") or None,
        "account_id": body.get("account_id") or None,
        "notes": body.get("notes") or "",
        "created_at": _now(), "created_by": user["id"], "created_by_name": user.get("name", ""),
    }
    await db.rahaza_expenses.insert_one(doc)
    # If account_id provided, record cash movement
    if doc["account_id"]:
        acc = await db.rahaza_cash_accounts.find_one({"id": doc["account_id"]}, {"_id": 0})
        if acc:
            await db.rahaza_cash_movements.insert_one({
                "id": _uid(), "account_id": doc["account_id"], "account_name": acc.get("name"),
                "direction": "out", "amount": doc["amount"],
                "category": "expense", "ref_id": doc["id"], "ref_label": doc["description"][:40],
                "date": doc["date"], "notes": doc["notes"],
                "timestamp": _now(), "created_by": user["id"], "created_by_name": user.get("name", ""),
            })
            await db.rahaza_cash_accounts.update_one({"id": doc["account_id"]}, {"$inc": {"balance": -doc["amount"]}})
    return serialize_doc(doc)


@router.get("/finance-summary")
async def finance_summary(request: Request):
    """Ringkasan Finance utk dashboard."""
    await require_auth(request)
    db = get_db()
    # AR outstanding
    ar = await db.rahaza_ar_invoices.aggregate([
        {"$match": {"status": {"$in": ["sent", "partial_paid", "overdue"]}}},
        {"$group": {"_id": None, "outstanding": {"$sum": "$balance"}, "count": {"$sum": 1}}},
    ]).to_list(None)
    ap = await db.rahaza_ap_invoices.aggregate([
        {"$match": {"status": {"$in": ["sent", "partial_paid"]}}},
        {"$group": {"_id": None, "outstanding": {"$sum": "$balance"}, "count": {"$sum": 1}}},
    ]).to_list(None)
    cash_total = await db.rahaza_cash_accounts.aggregate([
        {"$match": {"active": True}},
        {"$group": {"_id": None, "balance": {"$sum": "$balance"}, "count": {"$sum": 1}}},
    ]).to_list(None)
    return {
        "ar_outstanding": round((ar[0] if ar else {}).get("outstanding", 0) or 0),
        "ar_count": (ar[0] if ar else {}).get("count", 0),
        "ap_outstanding": round((ap[0] if ap else {}).get("outstanding", 0) or 0),
        "ap_count": (ap[0] if ap else {}).get("count", 0),
        "cash_balance": round((cash_total[0] if cash_total else {}).get("balance", 0) or 0),
        "cash_accounts_count": (cash_total[0] if cash_total else {}).get("count", 0),
    }
