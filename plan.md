# plan.md — PT Rahaza ERP (garmentrahaza5)

## Objectives
- Transform modul Produksi dari **system-of-record** → **system-of-guidance** (guided workflow, proactive alerts, traceability, decision support).
- Deliver incremental, reversible improvements (additive) tanpa mematahkan modul existing.
- Prioritaskan fitur lantai produksi yang menurunkan beban kognitif user: **scan → input cepat**, **rework enforcement**, **alert proaktif**, **andon**, **TV mode**, dan **SOP inline**.
- Setelah Phase 18 selesai, fokus bergeser ke **planning & forecasting** (Phase 19) dan pengetatan operasional (Phase 20).

---

## Phase 15 — Migration & Onboarding (DONE)
### Objectives
- Repo migrated ke `/app`, dependencies terpasang, auth/portal/dashboard stabil.

### Implementation Steps
- (Done) Repository berhasil dipindahkan ke `/app` (backend + frontend) dan service berjalan via supervisor.
- (Done) Backend `.env` disesuaikan (`DB_NAME=garment_erp`) agar konsisten dengan kode.
- (Done) Frontend dependencies dikonfirmasi (fix missing deps seperti `framer-motion` dan `recharts`).
- (Done) Login dan PortalSelector terverifikasi berjalan.

### Next Actions
- None.

### Success Criteria
- App bisa login, navigasi portal jalan, modul utama render tanpa crash.

---

## Phase A — Production Flow Audit & Roadmap (DONE)
### Objectives
- Audit end-to-end flow produksi.
- Buat roadmap development bertahap (16–20) untuk guided operations.

### Implementation Steps
- (Done) Audit + gap analysis 5 persona.
- (Done) Roadmap 5 phase ditulis.

### Deliverables
- `/app/docs/PRODUCTION_FLOW_AUDIT.md`
- `/app/docs/PRODUCTION_GUIDED_SYSTEM_ROADMAP.md`

### Next Actions
- None.

### Success Criteria
- Stakeholder setuju prioritas Phase 16+ dan definisi “guided system”.

---

## Phase 16 — Foundation of Guidance (COMPLETED)
### Objectives
- Buat sistem **self-onboarding** dan **next-action everywhere**.
- Kurangi dead-ends/empty modules; user selalu tahu langkah berikutnya.

### Implementation Steps (Delivered)
1. Backend endpoint **`/api/rahaza/next-actions`** dengan deterministic rules + filter by portal.
2. Frontend **`NextActionWidget`** (dismiss + snooze + CTA) dimount di dashboard.
3. Backend Setup Wizard **`/api/rahaza/setup/*`** + frontend **`SetupWizard`**.
4. Empty-state CTA upgrades di modul utama.
5. Contextual tooltip foundation.

### Success Criteria (met)
- Dashboard menampilkan actionable cards ketika ada gap.
- Setup wizard membantu first-run tanpa menebak urutan.
- Empty-state utama punya CTA valid.

---

## Phase 17 — Bundle Traceability & Scan (COMPLETED)
### Objectives
- Tambah **bundle-level traceability** dan **QR scan** agar WIP granular dan minim salah input.

### Implementation Steps (Delivered)
- Bundle entity + generate + list + detail.
- QR ticket PDF (single + bulk) + QR PNG.
- Operator scan workflow via `html5-qrcode` + unified backend `scan-submit` endpoint.
- Bundle detail page + search.
- QC fail → rework routing + Rework Board.

### Success Criteria (met)
- Operator scan QR & submit cepat.
- Bundle state machine + history trail lengkap.
- Rework tidak “hilang” dan terlihat di Rework Board.

---

## Phase 18 — Proactive Floor (COMPLETED — sub-phased)
### Objectives
- Sistem proaktif: alert realtime + Andon + TV mode + SOP inline.
- Menurunkan response time supervisor/manager saat ada masalah.

### User-confirmed Decisions (locked)
- Execution: **incremental** — 18A → review → 18B → review → 18C → review → 18D → review.
- Alert thresholds (default, configurable):
  - Behind-target: actual/target < **70%**
  - QC spike: fail rate > **15%** in last 1 hour
  - Low stock: material qty < **20%** of min_stock
- Andon SLA: 10 min supervisor → 20 min manager escalate (configurable).
- TV Mode: per-line progress + KPI + alert ticker.
- SOP format: rich text (markdown) + attachments.

---

### Phase 18A — Alert Bus + Rule Engine (COMPLETED)
**Goal:** sistem otomatis memantau kondisi kritikal dan kirim notifikasi realtime via SSE.

**Delivered**
- Backend: `backend/routes/rahaza_alerts.py` (settings + 3 rules + background evaluator + preview/evaluate endpoints).
- Frontend: `RahazaAlertSettingsModule.jsx` + menu registration + NotificationBell icon mapping.

**Success criteria (met)**
- Threshold bisa diubah dan persist.
- Evaluate now publish notifikasi ke bell via SSE.
- Background task berjalan dan dedup mencegah spam.

---

### Phase 18B — Andon Panel (COMPLETED + tested)
**Goal:** operator bisa request bantuan tanpa meninggalkan station; supervisor/manager punya board SLA dan eskalasi otomatis.

#### 18B.1 Backend — `rahaza_andon.py`
**Location:** `/app/backend/routes/rahaza_andon.py`

**Collections**
- `rahaza_andon_events`
- `rahaza_andon_settings`

**Key Capabilities**
- Create/list/acknowledge/resolve/cancel Andon events.
- SLA settings configurable (`GET/PUT /settings`).
- SLA escalation: dijalankan dari background loop alerts (**reuse** `rahaza_alerts` loop).

**Endpoints (Delivered)**
- `POST /api/rahaza/andon` — create event (operator)
- `GET /api/rahaza/andon/active` — list active
- `GET /api/rahaza/andon/history` — list history
- `GET /api/rahaza/andon/settings` + `PUT` — configure SLA defaults
- `POST /api/rahaza/andon/{id}/ack` — acknowledge
- `POST /api/rahaza/andon/{id}/resolve` — resolve
- `POST /api/rahaza/andon/{id}/cancel` — cancel

**Notes / Fixes Applied**
- Response payload: success text returned as `success_message` (tidak menimpa field `message` operator).

#### 18B.2 Frontend — Operator Andon UI
**Delivered**
- `/app/frontend/src/components/erp/AndonPanel.jsx`
  - 4 tombol: **Mesin Rusak**, **Material Habis**, **Defect Banyak**, **Minta Bantuan**
  - 2-tap confirm + notes optional
  - Status “Andon aktif” (prevents duplicate spam for same operator; reads active events)
- Integrated into `/app/frontend/src/components/erp/OperatorView.jsx`

#### 18B.3 Frontend — Supervisor/Manager Andon Board
**Delivered**
- `/app/frontend/src/components/erp/AndonBoardModule.jsx`
  - KPI strip: active + overdue counts
  - Event cards: SLA progress bar + actions **Ack/Resolve**
  - Polling auto-refresh

#### 18B.4 Wiring
**Delivered**
- Registered moduleId `prod-andon-board` in `moduleRegistry.js`.
- Menu item added in `PortalShell.jsx` under **MONITORING**.
- `server.py` includes `rahaza_andon_router`.
- Indexes added for Andon collections.
- SLA escalation hook added into `rahaza_alerts` background loop (`check_andon_sla_escalation()`).

**Success Criteria (met)**
- Operator dapat buat Andon < 5 detik.
- Andon muncul di `/active` dan board supervisor.
- Eskalasi notifikasi siap via NotificationBell publish (dedup protected).

---

### Phase 18C — Shop-Floor TV Mode (COMPLETED + verified)
**Goal:** tampilan full-screen untuk monitor pabrik: progress per line, KPI, dan ticker alert; akses tanpa login (read-only).

#### 18C.1 Backend — `rahaza_tv.py`
**Location:** `/app/backend/routes/rahaza_tv.py`

**Endpoints (Delivered)**
- `GET /api/tv/floor` — line cards + KPI summary
- `GET /api/tv/line/{line_id}` — per-line detail
- `GET /api/tv/alerts` — latest notifications for ticker
- `GET /api/tv/clock` — server time

#### 18C.2 Frontend — `ShopFloorTV.jsx`
**Location:** `/app/frontend/src/components/erp/ShopFloorTV.jsx`

**Delivered Features**
- Route `/tv` (public; no login).
- Full-screen high-contrast layout.
- Auto-refresh 5 detik (floor + ticker).
- Empty-state handling jika belum ada line/assignment.

#### 18C.3 Wiring
**Delivered**
- `App.js` detects `/tv` and renders TV view without auth.
- PortalShell includes **TV Mode (Lantai)** link (external opens new tab).
- `server.py` includes `rahaza_tv_router`.

**Success Criteria (met)**
- TV mode bisa dibuka tanpa login.
- Stabil refresh 5 detik.
- Ticker menampilkan notifikasi terbaru (terverifikasi via screenshot).

---

### Phase 18D — SOP Inline (COMPLETED + tested)
**Goal:** operator punya instruksi kerja kontekstual per model×process yang bisa dibuka langsung saat bekerja.

#### 18D.1 Backend — `rahaza_sop.py`
**Location:** `/app/backend/routes/rahaza_sop.py`

**Collection**
- `rahaza_model_process_sop`

**Endpoints (Delivered)**
- `GET /api/rahaza/sop` (filter by model/process, active)
- `POST /api/rahaza/sop` (admin/manager)
- `PUT /api/rahaza/sop/{id}` (admin/manager)
- `DELETE /api/rahaza/sop/{id}` (soft de-activate)
- `GET /api/rahaza/sop/by-context?model_id=...&process_id=...` (operator read)

#### 18D.2 Frontend — Admin SOP Management
**Delivered**
- `/app/frontend/src/components/erp/RahazaSOPModule.jsx`
  - List + search + filter model/process
  - Create/edit SOP with markdown textarea
  - Activate/deactivate

#### 18D.3 Frontend — Operator SOP Viewer
**Delivered**
- `/app/frontend/src/components/erp/SOPModal.jsx`
  - Fetch by context model×process
  - Simple markdown rendering + attachments display
- Integrated into `OperatorView.jsx`
  - “Lihat SOP” button per assignment card

#### 18D.4 Wiring
**Delivered**
- Registered moduleId `prod-sop` in `moduleRegistry.js`.
- Menu item added in Production → **MASTER DATA**.
- `server.py` includes `rahaza_sop_router`.
- Indexes added for SOP collection.

**Success Criteria (met)**
- Admin bisa buat SOP.
- Operator bisa buka SOP dari OperatorView ≤ 2 tap.

---

## Testing / Verification (Phase 18B–18D) (COMPLETED)
### Backend (executed)
- Andon:
  - Create → Active list → Ack → Resolve flows verified.
  - Settings GET/PUT verified.
- TV:
  - `/api/tv/*` endpoints verified public.
  - Ticker reads from notifications.
- SOP:
  - Model created for test + SOP created.
  - `by-context` returns correct SOP.

### Frontend (executed)
- TV Mode `/tv` verified rendering with live clock + ticker.
- Auth login verified.

### Known Gaps / Next Hardening
- Add optional `/api/health` endpoint (currently 404) for ops monitoring.
- Add seed/demo dataset script (models/employees/assignments) to make UI demo/testing consistent.

---

## Phase 19 — Plan & Forecast (PENDING)
### Objectives
- Tambah planning layer: schedule, kapasitas, balancing, forecast due-risk.

### Proposed Scope (draft)
- Capacity model per line/shift (pcs/hour) + staffing.
- Rough-cut planning per WO: start/end estimate + risk flags.
- “What’s next” plan view for supervisor (today/tomorrow).

### Next Actions
- Confirm planning horizon (harian/mingguan) + definisi kapasitas per line.
- Confirm data entry approach (manual vs derived from historical output).

---

## Phase 20 — Intelligent Ops (PENDING)
### Objectives
- Add thin AI layer untuk report/search, dan OEE + closed-loop rework enforcement.

### Next Actions
- Approve AI scope + cost/limits.
- Define OEE KPIs required (availability/performance/quality) and data capture gaps.
