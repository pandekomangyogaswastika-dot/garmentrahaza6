# plan.md — PT Rahaza ERP (garmentrahaza5)

## Objectives
- Transform modul Produksi dari **system-of-record** → **system-of-guidance** (guided workflow, proactive alerts, traceability, decision support).
- Deliver incremental, reversible improvements (additive) tanpa mematahkan modul existing.
- Prioritaskan fitur lantai produksi yang menurunkan beban kognitif user: **scan → input cepat**, **rework enforcement**, **alert proaktif**, **andon**, **TV mode**, dan **SOP inline**.

---

## Phase 15 — Migration & Onboarding (DONE)
### Objectives
- Repo migrated ke `/app`, dependencies terpasang, auth/portal/dashboard stabil.

### Implementation Steps
- (Done) Repository berhasil dipindahkan ke `/app` (backend + frontend) dan service berjalan via supervisor.
- (Done) Backend `.env` disesuaikan (`DB_NAME=garment_erp`) agar konsisten dengan kode.
- (Done) Frontend dependencies dikonfirmasi (fix missing deps seperti `framer-motion`).
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

## Phase 18 — Proactive Floor (IN PROGRESS — sub-phased)
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
- SOP format: rich text (markdown) + image/file upload via existing file_storage.

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

### Phase 18B — Andon Panel (PENDING → NEXT)
**Goal:** operator bisa request bantuan tanpa meninggalkan station; supervisor/manager punya board SLA dan eskalasi otomatis.

#### 18B.1 Backend — `rahaza_andon.py`
**Data model:** `rahaza_andon_events`
- `id`, `created_at`, `created_by_user_id`, `employee_id`, `line_id`, `process_id`
- `type` (machine_breakdown/material_shortage/quality_issue/help)
- `severity` (info/warn/urgent)
- `message`/`notes`
- `status` (active/acknowledged/resolved/cancelled)
- `acknowledged_at`, `acknowledged_by`, `resolved_at`, `resolved_by`
- `sla_supervisor_min` default 10, `sla_manager_min` default 20
- `escalation_state` (none/supervisor_notified/manager_notified)
- `dedup_key` optional (avoid spamming repeated presses)

**Endpoints**
- `POST /api/rahaza/andon` — create event (operator)
- `GET /api/rahaza/andon/active` — list active (auth; filter by line/process)
- `POST /api/rahaza/andon/{id}/ack` — acknowledge (supervisor)
- `POST /api/rahaza/andon/{id}/resolve` — resolve (supervisor/manager)
- `GET /api/rahaza/andon/history` — list history (manager/admin)
- (optional) `GET /api/rahaza/andon/settings` + `PUT` — configure SLA defaults

**SLA Escalation**
- Background task (or reuse alerts evaluator loop) checks active events:
  - if age ≥ supervisor SLA and not acked → publish notification to supervisor roles
  - if age ≥ manager SLA and still not acked/resolved → publish notification to manager roles
- Publish uses existing `publish_notification()` to NotificationBell + SSE.

#### 18B.2 Frontend — Operator Andon UI
- `AndonPanel.jsx` (atau section di `OperatorView.jsx`):
  - 4 tombol besar merah: **Mesin Rusak**, **Material Habis**, **Defect Banyak**, **Minta Bantuan**
  - 2-tap confirm (tap → confirm state 2–3 detik) untuk menghindari salah tekan.
  - Optional notes textarea singkat.
  - Feedback toast sukses + tampil countdown SLA.

#### 18B.3 Frontend — Supervisor/Manager Andon Board
- `AndonBoardModule.jsx`:
  - KPI strip: total active, oldest age, count overdue supervisor, count overdue manager.
  - Card list per event: line/process/operator, type badge, age + SLA progress bar, actions **Ack**/**Resolve**.
  - Auto-refresh 10–30s + realtime update via SSE (opsional v1: polling).

#### 18B.4 Wiring
- Register moduleId baru mis. `prod-andon-board`.
- Add sidebar item di Portal Produksi (Monitoring section) atau Eksekusi.
- Update `backend/server.py` untuk include router `rahaza_andon` + indexes.

**Success Criteria**
- Operator dapat buat Andon < 5 detik.
- Supervisor melihat event muncul (polling/SSE) < 10 detik.
- Eskalasi otomatis mengirim notif jika tidak di-acknowledge sesuai SLA.

---

### Phase 18C — Shop-Floor TV Mode (PENDING)
**Goal:** tampilan full-screen untuk monitor pabrik: progress per line, KPI, dan ticker alert; akses tanpa login (read-only).

#### 18C.1 Backend — `rahaza_tv.py`
- Public read-only endpoints (tanpa auth) dengan output yang sudah disanitasi:
  - `GET /api/tv/floor` — list line cards: target vs actual, status behind-target, qc spike, active andon count
  - `GET /api/tv/line/{line_id}` — detail line: assignments today, output per process, last events, andon active
  - `GET /api/tv/alerts` — last N notifications/alerts untuk ticker (filter type production)
- Rate-limit sederhana (optional) dan cache short TTL (5s) untuk stabilitas.

#### 18C.2 Frontend — `ShopFloorTV.jsx`
- Route `/tv` (floor) dan `/tv/line/:lineId`.
- Full-screen, high-contrast, large typography.
- Refresh interval 5 detik (setInterval) + safe cleanup.
- Layout:
  - Grid per line: output besar + % target + badge behind-target.
  - Bottom ticker: alert/andon terbaru.
  - Jam realtime + shift.

#### 18C.3 Wiring
- Update `App.js` to detect `/tv` route and render TV component without auth.
- Add minimal navigation link (optional) from production portal (admin only).
- Update `backend/server.py` to include router `rahaza_tv`.

**Success Criteria**
- TV mode bisa dibuka tanpa login.
- Tidak crash saat running lama; refresh stabil.
- Informasi line & alert update ≤ 5 detik.

---

### Phase 18D — SOP Inline (PENDING)
**Goal:** operator punya instruksi kerja kontekstual per model×process yang bisa dibuka langsung saat bekerja (terutama setelah scan bundle).

#### 18D.1 Backend — `rahaza_sop.py`
**Collection:** `rahaza_model_process_sop`
- `id`, `model_id`, `process_id`, `title`
- `content_markdown` (optional)
- `attachments[]` (file_id/url via `file_storage`)
- `version`, `active`, `created_at`, `updated_at`

**Endpoints**
- CRUD admin:
  - `GET /api/rahaza/sop` (filter by model/process)
  - `POST /api/rahaza/sop`
  - `PUT /api/rahaza/sop/{id}`
  - `DELETE /api/rahaza/sop/{id}` (soft delete recommended)
- Operator read:
  - `GET /api/rahaza/sop/by-context?model_id=...&process_id=...` (return active SOP)

#### 18D.2 Frontend — Admin SOP Management
- `RahazaSOPModule.jsx`:
  - Table list SOP, filter model/process, preview.
  - Editor markdown sederhana (textarea) + attachment upload panel (reuse `FileAttachmentPanel`).
  - Activate/deactivate + version bump.
- Register moduleId mis. `prod-sop` under Master Data or Monitoring.

#### 18D.3 Frontend — Operator SOP Viewer
- `SOPModal.jsx`:
  - Open from `OperatorView` context (assignment active / bundle scanned).
  - Fetch SOP by model+process; show markdown + attachments gallery.
  - Empty state: “Belum ada SOP untuk model/proses ini” + hint ke admin.

#### 18D.4 Wiring
- Update `OperatorView.jsx`: tombol “SOP” muncul jika ada assignment/bundle context.
- Update `backend/server.py` include `rahaza_sop` + indexes.

**Success Criteria**
- Admin bisa buat SOP + upload lampiran.
- Operator bisa buka SOP dari OperatorView dalam ≤ 2 tap.

---

## Testing / Verification (Phase 18B–18D)
### Backend
- Integration tests untuk:
  - Andon create/ack/resolve + SLA escalation publish (mock time)
  - TV endpoints return sanitized payload, no auth required
  - SOP CRUD + by-context fetch

### Frontend
- E2E manual:
  - Operator create andon → supervisor board update → notif SSE
  - `/tv` render tanpa login dan refresh berjalan
  - Operator open SOP modal from scanned bundle/assignment

### Regression
- Pastikan Phase 17 bundle scan & print tetap OK.
- Pastikan notifications stream tetap stabil.

---

## Phase 19 — Plan & Forecast (PENDING)
### Objectives
- Tambah planning layer: schedule, kapasitas, balancing, forecast due-risk.

### Next Actions
- Confirm planning horizon + definisi kapasitas per line.

---

## Phase 20 — Intelligent Ops (PENDING)
### Objectives
- Add thin AI layer untuk report/search, dan OEE + closed-loop rework enforcement.

### Next Actions
- Approve AI scope + cost/limits.
