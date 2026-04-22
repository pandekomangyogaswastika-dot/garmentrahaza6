"""
PT Rahaza — Production Execution (Fase 6)

Endpoints (prefix /api/rahaza):
  - GET  /execution/process/{code}/board?date=YYYY-MM-DD
      Board khusus 1 proses: stats, lines, output per line, recent events.
  - POST /execution/quick-output
      Input output cepat (validasi line.process == process_id).
  - POST /execution/qc-event
      Entry QC: pass & fail dalam 1 call → 2 event (qc_pass / qc_fail).
  - GET  /execution/my-work?operator_id=X
      Daftar assignment operator hari ini + output terkini.
  - GET  /execution/flow-summary
      Ringkasan alur main + rework (WIP + throughput per proses).
  - GET  /execution/recent-events?process_id=X
      20 event terakhir (untuk log board).

Event type contract (tersimpan di rahaza_wip_events.event_type):
  - 'output'    : umum (Rajut/Linking/Sewing/Steam/Packing/Washer/Sontek)
  - 'qc_pass'   : keluaran QC ke Steam (lolos)
  - 'qc_fail'   : keluaran QC ke Washer (rework)
Semua event simpan qty positif; arah ditentukan oleh event_type + process.
"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from auth import require_auth, serialize_doc, log_activity
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import Optional

router = APIRouter(prefix="/api/rahaza", tags=["rahaza-execution"])


def _uid(): return str(uuid.uuid4())
def _now(): return datetime.now(timezone.utc)


async def _require_input(request: Request):
    user = await require_auth(request)
    role = (user.get("role") or "").lower()
    if role in ("superadmin", "admin", "owner", "supervisor", "operator"):
        return user
    perms = user.get("_permissions") or []
    if "*" in perms or "prod.process.input" in perms or "prod.line.manage" in perms:
        return user
    raise HTTPException(403, "Forbidden: butuh permission input produksi.")


async def _day_range(day_iso: Optional[str]):
    d = date.fromisoformat(day_iso) if day_iso else date.today()
    start = datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
    end   = datetime.combine(d, datetime.max.time()).replace(tzinfo=timezone.utc)
    return d.isoformat(), start, end


# ─── Process Board ─────────────────────────────────────────────────────
@router.get("/execution/process/{code}/board")
async def process_board(code: str, request: Request, date: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    code_up = (code or "").strip().upper()
    proc = await db.rahaza_processes.find_one({"code": code_up, "active": True}, {"_id": 0})
    if not proc:
        raise HTTPException(404, f"Proses '{code_up}' tidak ditemukan atau non-aktif.")
    today_iso, start, end = await _day_range(date)

    lines = await db.rahaza_lines.find({"process_id": proc["id"], "active": True}, {"_id": 0}).sort("code", 1).to_list(None)
    line_ids = [l["id"] for l in lines]

    # Assignments for today
    assignments = await db.rahaza_line_assignments.find(
        {"line_id": {"$in": line_ids}, "assign_date": today_iso, "active": True}, {"_id": 0}
    ).to_list(None) if line_ids else []

    # Maps
    async def _name_map(col, ids, id_field="id"):
        if not ids: return {}
        docs = await db[col].find({id_field: {"$in": list(ids)}}, {"_id": 0}).to_list(None)
        return {d[id_field]: d for d in docs}
    emp_map = await _name_map("rahaza_employees", {a.get("operator_id") for a in assignments if a.get("operator_id")})
    sh_map  = await _name_map("rahaza_shifts",    {a.get("shift_id") for a in assignments if a.get("shift_id")})
    mod_map = await _name_map("rahaza_models",    {a.get("model_id") for a in assignments if a.get("model_id")})
    sz_map  = await _name_map("rahaza_sizes",     {a.get("size_id") for a in assignments if a.get("size_id")})
    loc_map = await _name_map("rahaza_locations", {l.get("location_id") for l in lines if l.get("location_id")})

    assign_by_line = {}
    for a in assignments:
        assign_by_line.setdefault(a["line_id"], []).append(a)

    # Output today at this process
    pipe = [
        {"$match": {"process_id": proc["id"], "timestamp": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": {"line_id": "$line_id", "event_type": "$event_type"}, "total": {"$sum": "$qty"}}},
    ]
    out_agg = await db.rahaza_wip_events.aggregate(pipe).to_list(None)
    out_by_line = {}
    for r in out_agg:
        lid = r["_id"].get("line_id"); et = r["_id"].get("event_type") or "output"
        out_by_line.setdefault(lid, {}).setdefault(et, 0)
        out_by_line[lid][et] += r["total"]

    # Build lines output
    line_rows = []
    for ln in lines:
        loc = loc_map.get(ln.get("location_id"))
        agg = out_by_line.get(ln["id"], {})
        output_today = sum(agg.values())
        a_list = []
        for a in assign_by_line.get(ln["id"], []):
            op = emp_map.get(a.get("operator_id"))
            sh = sh_map.get(a.get("shift_id"))
            mod= mod_map.get(a.get("model_id"))
            sz = sz_map.get(a.get("size_id"))
            a_list.append({
                "id": a["id"], "shift_id": a.get("shift_id"), "shift_name": sh.get("name") if sh else None,
                "operator_id": a.get("operator_id"), "operator_name": op.get("name") if op else None,
                "model_id": a.get("model_id"), "model_code": mod.get("code") if mod else None, "model_name": mod.get("name") if mod else None,
                "size_id": a.get("size_id"), "size_code": sz.get("code") if sz else None,
                "target_qty": a.get("target_qty") or 0,
                "work_order_id": a.get("work_order_id") or None,
            })
        target = sum((x["target_qty"] for x in a_list), 0)
        line_rows.append({
            "line_id": ln["id"], "line_code": ln["code"], "line_name": ln["name"],
            "location_name": loc.get("name") if loc else None,
            "capacity_per_hour": ln.get("capacity_per_hour") or 0,
            "output_today": output_today, "output_breakdown": agg, "target_today": target,
            "assignments": a_list,
        })

    # Stats totals
    totals = {"output_today": sum(r["output_today"] for r in line_rows),
              "target_today": sum(r["target_today"] for r in line_rows),
              "active_lines": len(line_rows),
              "active_assignments": sum(len(r["assignments"]) for r in line_rows)}

    # Recent events (20)
    evs = await db.rahaza_wip_events.find({"process_id": proc["id"]}, {"_id": 0}).sort("timestamp", -1).limit(20).to_list(None)

    return {
        "date": today_iso,
        "process": {"id": proc["id"], "code": proc["code"], "name": proc["name"], "order_seq": proc.get("order_seq", 0), "is_rework": bool(proc.get("is_rework"))},
        "totals": totals,
        "lines": line_rows,
        "recent_events": serialize_doc(evs),
    }


# ─── Quick output (generic) ─────────────────────────────────────────────────
@router.post("/execution/quick-output")
async def quick_output(request: Request):
    user = await _require_input(request)
    db = get_db()
    body = await request.json()
    line_id = body.get("line_id")
    process_id = body.get("process_id")
    qty = int(body.get("qty") or 0)
    if not (line_id and process_id and qty > 0):
        raise HTTPException(400, "line_id, process_id, dan qty(>0) wajib diisi.")
    line = await db.rahaza_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(404, "Line tidak ditemukan.")
    if line.get("process_id") != process_id:
        raise HTTPException(400, "Line tidak cocok dengan proses yang dipilih.")
    # Disallow QC via generic quick-output (use /qc-event instead)
    proc = await db.rahaza_processes.find_one({"id": process_id}, {"_id": 0})
    if proc and (proc.get("code") == "QC"):
        raise HTTPException(400, "Gunakan /execution/qc-event untuk input QC (pass/fail).")
    # Auto-fill context from assignment if not provided
    assignment_id = body.get("line_assignment_id") or None
    model_id = body.get("model_id") or None
    size_id  = body.get("size_id") or None
    work_order_id = body.get("work_order_id") or None
    if assignment_id:
        a = await db.rahaza_line_assignments.find_one({"id": assignment_id}, {"_id": 0})
        if a:
            model_id = model_id or a.get("model_id")
            size_id  = size_id  or a.get("size_id")
            work_order_id = work_order_id or a.get("work_order_id")
    event = {
        "id": _uid(), "timestamp": _now(),
        "line_id": line_id, "process_id": process_id,
        "location_id": line.get("location_id"),
        "model_id": model_id, "size_id": size_id,
        "line_assignment_id": assignment_id,
        "work_order_id": work_order_id,
        "event_type": "output",
        "qty": qty, "notes": body.get("notes") or "",
        "created_by": user["id"], "created_by_name": user.get("name", ""),
    }
    await db.rahaza_wip_events.insert_one(event)
    await log_activity(user["id"], user.get("name", ""), f"output:{qty}", "rahaza.process", proc["code"] if proc else process_id)
    return serialize_doc(event)


# ─── QC event (pass/fail) ─────────────────────────────────────────────────────
@router.post("/execution/qc-event")
async def qc_event(request: Request):
    user = await _require_input(request)
    db = get_db()
    body = await request.json()
    line_id = body.get("line_id")
    qty_pass = int(body.get("qty_pass") or 0)
    qty_fail = int(body.get("qty_fail") or 0)
    if not line_id or (qty_pass <= 0 and qty_fail <= 0):
        raise HTTPException(400, "line_id dan minimal salah satu qty_pass/qty_fail > 0 wajib diisi.")
    line = await db.rahaza_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(404, "Line tidak ditemukan.")
    qc_proc = await db.rahaza_processes.find_one({"code": "QC", "active": True}, {"_id": 0})
    if not qc_proc:
        raise HTTPException(500, "Proses QC tidak ditemukan di master data.")
    if line.get("process_id") != qc_proc["id"]:
        raise HTTPException(400, "Line yang dipilih bukan line QC.")

    assignment_id = body.get("line_assignment_id") or None
    model_id = body.get("model_id"); size_id = body.get("size_id"); work_order_id = body.get("work_order_id")
    if assignment_id:
        a = await db.rahaza_line_assignments.find_one({"id": assignment_id}, {"_id": 0})
        if a:
            model_id = model_id or a.get("model_id")
            size_id  = size_id  or a.get("size_id")
            work_order_id = work_order_id or a.get("work_order_id")

    created = []
    for (q, et) in ((qty_pass, "qc_pass"), (qty_fail, "qc_fail")):
        if q <= 0: continue
        ev = {
            "id": _uid(), "timestamp": _now(),
            "line_id": line_id, "process_id": qc_proc["id"],
            "location_id": line.get("location_id"),
            "model_id": model_id, "size_id": size_id,
            "line_assignment_id": assignment_id,
            "work_order_id": work_order_id,
            "event_type": et,
            "qty": q, "notes": body.get("notes") or "",
            "created_by": user["id"], "created_by_name": user.get("name", ""),
        }
        await db.rahaza_wip_events.insert_one(ev)
        created.append(serialize_doc(ev))
    await log_activity(user["id"], user.get("name", ""), f"qc:{qty_pass}/{qty_fail}", "rahaza.process", "QC")

    # Phase 12.2 — QC fail rate alert (check only when there was fail)
    if qty_fail > 0:
        try:
            await _check_qc_fail_rate_alert(db, line_id, line.get("code", ""))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"QC fail-rate alert failed: {e}")

    return {"created": created, "qty_pass": qty_pass, "qty_fail": qty_fail}


async def _check_qc_fail_rate_alert(db, line_id: str, line_code: str):
    """
    Cek fail rate di line QC pada 30 menit terakhir.
    Jika total events ≥ 10 dan fail_rate > 10 %, publish alert.
    """
    since = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    events = await db.rahaza_wip_events.find(
        {"line_id": line_id, "event_type": {"$in": ["qc_pass", "qc_fail"]},
         "timestamp": {"$gte": since}},
        {"_id": 0, "event_type": 1, "qty": 1}
    ).to_list(None)
    total = sum(int(e.get("qty") or 0) for e in events)
    fail = sum(int(e.get("qty") or 0) for e in events if e.get("event_type") == "qc_fail")
    if total < 10:
        return  # sample terlalu kecil
    fail_rate = (fail / total) * 100 if total else 0
    if fail_rate > 10:
        from routes.rahaza_notifications import publish_notification
        await publish_notification(
            db,
            type_="qc_fail_spike",
            severity="error" if fail_rate > 20 else "warning",
            title=f"Fail rate tinggi di {line_code}",
            message=f"Fail rate {fail_rate:.1f}% ({fail}/{total}) dalam 30 menit terakhir. Perlu investigasi operator/mesin/model.",
            link_module="prod-line-board",
            link_id=line_id,
            target_roles=["supervisor", "production_manager", "qc_lead", "superadmin"],
            dedup_key=f"qc_fail::{line_id}::{int(datetime.now(timezone.utc).timestamp() // 1800)}",  # 30-min window
        )


# ─── Operator "my work" ──────────────────────────────────────────────────────
@router.get("/execution/my-work")
async def my_work(request: Request, operator_id: Optional[str] = None, date: Optional[str] = None):
    await require_auth(request)
    db = get_db()
    if not operator_id:
        raise HTTPException(400, "operator_id wajib dipilih.")
    today_iso, start, end = await _day_range(date)
    assignments = await db.rahaza_line_assignments.find(
        {"operator_id": operator_id, "assign_date": today_iso, "active": True}, {"_id": 0}
    ).to_list(None)
    if not assignments:
        return {"date": today_iso, "operator_id": operator_id, "assignments": [], "recent_events": []}

    line_ids = list({a["line_id"] for a in assignments if a.get("line_id")})
    lines = await db.rahaza_lines.find({"id": {"$in": line_ids}}, {"_id": 0}).to_list(None)
    ln_map = {l["id"]: l for l in lines}
    proc_ids = list({l.get("process_id") for l in lines if l.get("process_id")})
    procs = await db.rahaza_processes.find({"id": {"$in": proc_ids}}, {"_id": 0}).to_list(None)
    p_map = {p["id"]: p for p in procs}
    mod_ids = list({a.get("model_id") for a in assignments if a.get("model_id")})
    sz_ids  = list({a.get("size_id") for a in assignments if a.get("size_id")})
    mods = await db.rahaza_models.find({"id": {"$in": mod_ids}}, {"_id": 0}).to_list(None) if mod_ids else []
    szs  = await db.rahaza_sizes.find({"id":  {"$in": sz_ids}},  {"_id": 0}).to_list(None) if sz_ids else []
    m_map = {m["id"]: m for m in mods}; s_map = {s["id"]: s for s in szs}
    sh_ids = list({a.get("shift_id") for a in assignments if a.get("shift_id")})
    shs = await db.rahaza_shifts.find({"id": {"$in": sh_ids}}, {"_id": 0}).to_list(None) if sh_ids else []
    sh_map = {s["id"]: s for s in shs}

    # Output today per line_assignment for this operator
    asg_ids = [a["id"] for a in assignments]
    pipe = [
        {"$match": {"line_assignment_id": {"$in": asg_ids}, "timestamp": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": {"aid": "$line_assignment_id", "et": "$event_type"}, "total": {"$sum": "$qty"}}},
    ]
    agg = await db.rahaza_wip_events.aggregate(pipe).to_list(None)
    out_by_asg = {}
    for r in agg:
        aid = r["_id"].get("aid"); et = r["_id"].get("et") or "output"
        out_by_asg.setdefault(aid, {}).setdefault(et, 0)
        out_by_asg[aid][et] += r["total"]

    rows = []
    for a in assignments:
        ln = ln_map.get(a["line_id"]) or {}
        pr = p_map.get(ln.get("process_id")) or {}
        mod = m_map.get(a.get("model_id"))
        sz  = s_map.get(a.get("size_id"))
        sh  = sh_map.get(a.get("shift_id"))
        agg_a = out_by_asg.get(a["id"], {})
        out_today = sum(agg_a.values())
        rows.append({
            "assignment_id": a["id"],
            "line_id": ln.get("id"), "line_code": ln.get("code"), "line_name": ln.get("name"),
            "process_id": pr.get("id"), "process_code": pr.get("code"), "process_name": pr.get("name"), "is_qc": pr.get("code") == "QC",
            "shift_id": a.get("shift_id"), "shift_name": sh.get("name") if sh else None,
            "model_id": a.get("model_id"), "model_code": mod.get("code") if mod else None, "model_name": mod.get("name") if mod else None,
            "size_id": a.get("size_id"), "size_code": sz.get("code") if sz else None,
            "target_qty": a.get("target_qty") or 0,
            "output_today": out_today,
            "output_breakdown": agg_a,
            "progress_pct": round((out_today / a["target_qty"]) * 100, 1) if a.get("target_qty") else 0,
        })

    # Recent events for this operator today
    recent = await db.rahaza_wip_events.find(
        {"line_assignment_id": {"$in": asg_ids}, "timestamp": {"$gte": start, "$lte": end}}, {"_id": 0}
    ).sort("timestamp", -1).limit(15).to_list(None)

    return {
        "date": today_iso, "operator_id": operator_id,
        "assignments": rows,
        "recent_events": serialize_doc(recent),
    }


# ─── Flow summary (enhanced) ───────────────────────────────────────────────────
@router.get("/execution/flow-summary")
async def flow_summary(request: Request):
    """
    WIP per proses dengan awareness rework:
      Main : Rajut → Linking → Sewing → QC → Steam → Packing
      Rework: QC(fail) → Washer → Sontek → kembali ke QC

    WIP di setiap proses P = incoming(P) − outgoing(P).
    Untuk QC, outgoing = qc_pass + qc_fail.
    """
    await require_auth(request)
    db = get_db()
    procs = await db.rahaza_processes.find({"active": True}, {"_id": 0}).sort("order_seq", 1).to_list(None)
    p_by_code = {p["code"]: p for p in procs}

    pipe = [
        {"$group": {"_id": {"pid": "$process_id", "et": "$event_type"}, "total": {"$sum": "$qty"}}}
    ]
    raw = await db.rahaza_wip_events.aggregate(pipe).to_list(None)
    totals = {}  # totals[process_id][event_type] = qty
    for r in raw:
        pid = r["_id"].get("pid"); et = r["_id"].get("et") or "output"
        totals.setdefault(pid, {}).setdefault(et, 0)
        totals[pid][et] += r["total"]

    def out(pcode, et="output"):
        p = p_by_code.get(pcode)
        if not p: return 0
        return int(totals.get(p["id"], {}).get(et, 0))

    # Outputs
    rajut    = out("RAJUT")
    linking  = out("LINKING")
    sewing   = out("SEWING")
    qc_pass  = out("QC", "qc_pass")
    qc_fail  = out("QC", "qc_fail")
    steam    = out("STEAM")
    packing  = out("PACKING")
    washer   = out("WASHER")
    sontek   = out("SONTEK")

    # WIP per proses
    def wip(incoming, outgoing):
        return max(0, incoming - outgoing)

    wip_rajut   = wip(0,         rajut)      # Rajut tidak punya feeder in-system (anggap incoming=rajut output)
    # Alternatif: WIP Rajut = rajut - linking (barang rajut yang belum diambil linking)
    wip_rajut   = max(0, rajut - linking)
    wip_linking = max(0, linking - sewing)
    wip_sewing  = max(0, sewing - (qc_pass + qc_fail))
    # QC queue = input(QC) - (qc_pass+qc_fail); input = sewing + sontek
    wip_qc      = max(0, (sewing + sontek) - (qc_pass + qc_fail))
    wip_steam   = max(0, qc_pass - packing)
    wip_packing = max(0, packing - 0)  # packing adalah proses terakhir, tidak ada consumer
    wip_washer  = max(0, qc_fail - washer)
    wip_sontek  = max(0, washer - sontek)

    def pack(code, throughput, wip_qty, is_rework=False, extra=None):
        p = p_by_code.get(code) or {}
        item = {
            "code": code, "name": p.get("name", code),
            "order_seq": p.get("order_seq", 0), "is_rework": bool(is_rework),
            "throughput": throughput, "wip": wip_qty,
        }
        if extra: item.update(extra)
        return item

    main = [
        pack("RAJUT",   rajut,   wip_rajut),
        pack("LINKING", linking, wip_linking),
        pack("SEWING",  sewing,  wip_sewing),
        pack("QC",      qc_pass + qc_fail, wip_qc, extra={"qc_pass": qc_pass, "qc_fail": qc_fail}),
        pack("STEAM",   steam,   wip_steam),
        pack("PACKING", packing, wip_packing),
    ]
    rework = [
        pack("WASHER",  washer,  wip_washer, is_rework=True),
        pack("SONTEK",  sontek,  wip_sontek, is_rework=True),
    ]
    # Bottleneck: proses non-rework dengan WIP tertinggi
    btl = max(main, key=lambda r: r["wip"], default=None)
    return {
        "main_flow": main,
        "rework_flow": rework,
        "bottleneck": btl["code"] if btl and btl["wip"] > 0 else None,
        "bottleneck_wip": btl["wip"] if btl else 0,
        "qc_pass": qc_pass, "qc_fail": qc_fail,
        "updated_at": _now().isoformat(),
    }


# ─── Recent events per proses ──────────────────────────────────────────────────
@router.get("/execution/recent-events")
async def recent_events(request: Request, process_id: Optional[str] = None, limit: int = 30):
    await require_auth(request)
    db = get_db()
    q = {}
    if process_id: q["process_id"] = process_id
    evs = await db.rahaza_wip_events.find(q, {"_id": 0}).sort("timestamp", -1).limit(int(limit)).to_list(None)
    return serialize_doc(evs)
