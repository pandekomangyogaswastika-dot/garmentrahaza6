# 🗺️ Roadmap: Guided Production System — PT Rahaza ERP

> **Versi:** 1.0  
> **Tanggal:** 22 April 2026  
> **Basis audit:** `PRODUCTION_FLOW_AUDIT.md` (baca dulu!)  
> **Visi:** Transformasi ERP dari **System-of-Record** → **System-of-Guidance** yang **memandu**, **memperingatkan**, dan **mempermudah** operasional harian pabrik rajut PT Rahaza.

---

## 🎯 Tujuan Strategis

1. **Operator tidak lagi "terima perintah" — mereka *dipandu* bekerja** (SOP inline, scan QR, defect code, andon).
2. **Supervisor tidak lagi "kejar-kejar" — sistem *memberi tahu* mana line yang perlu perhatian**.
3. **PPIC tidak lagi "rekam data di Excel terpisah" — sistem *merencanakan* & *simulasikan*** .
4. **Manager tidak lagi "tanya laporan" — sistem *kirim insight* setiap pagi**.
5. **Admin tidak lagi "tebak urutan setup" — sistem *menuntun* onboarding.**

### North-Star Metrics (6 bulan)
- **Time-to-First-Output** (user baru → mencatat output pertama): dari ~2 jam (tebak-menebak) → **< 15 menit** (dipandu wizard).
- **Operator adoption rate**: dari 0% scan → **> 80% input via scan QR**.
- **Proactive alerts triggered per hari**: > 10 (dari ~1-2 saat ini).
- **Avg supervisor decision time** (dari masalah terdeteksi → tindakan): dari ~30 menit → **< 5 menit**.
- **On-time delivery rate**: naik **+15%** via forecast + re-planning.
- **Defect rate reduction**: **-20%** via root-cause Pareto & closed-loop rework.

---

## 🏛️ Arsitektur Solusi (Hi-level)

```
┌─────────────────────────────────────────────────────────────────┐
│              LAPISAN GUIDANCE (BARU)                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ Next-Action│ │ Alert &    │ │ Smart      │ │ AI Assist  │   │
│  │ Engine     │ │ Andon Bus  │ │ Defaults   │ │ (LLM)      │   │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Onboarding Wizard · Setup Templates · Contextual Help   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ event-bus + derived views
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│             LAPISAN OPERATIONAL (BARU + ENHANCE)                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ Bundle /   │ │ Capacity & │ │ Defect &   │ │ Downtime & │   │
│  │ Lot Tracker│ │ Scheduling │ │ FPY / OEE  │ │ Machine    │   │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│             LAPISAN RECORD (SUDAH ADA — preserve)                │
│   Orders · BOM · Work Orders · Material Issue · WIP Events ·     │
│   Line Assignments · QC Events · Shipments · AR/AP/HPP           │
└─────────────────────────────────────────────────────────────────┘
```

**Prinsip teknis:**
- **Non-breaking**: Semua modul existing tetap hidup. Guidance layer *aditif*.
- **Event-driven**: Pakai existing `wip_events`, `qc_events`, `notifications` sebagai trigger.
- **Stateless rules engine**: Next-Action engine bukan AI (belum) — rule-based deterministik agar cepat, dapat di-audit, testable.
- **Progressive enhancement**: AI (LLM) dipakai untuk *natural language* (report, chat) — bukan mission-critical decisioning.

---

## 📅 Roadmap 5 Fase · ~16 Minggu

| Fase | Durasi | Tema | Milestone Deliverable |
|---|---|---|---|
| **Phase 16 · "Foundation of Guidance"** | 3 minggu | Onboarding + Next-Action Engine + Empty-State CTA | Setup Wizard, NextActionWidget global, tooltip global |
| **Phase 17 · "Bundle Traceability & Scan"** | 3 minggu | Bundle entity + QR print/scan + Operator-scan workflow | Bundle ticket PDF, QR scanner modal, bundle detail page |
| **Phase 18 · "Proactive Floor"** | 3 minggu | Alert bus + Andon + TV mode + Contextual SOP | Live alert feed, operator andon panel, shop-floor TV route, SOP attachment |
| **Phase 19 · "Plan & Forecast"** | 4 minggu | Capacity Gantt + Line Balance + Forecast + Defect Pareto | Scheduling board, SAM-based target suggest, due-date forecast, defect dashboard |
| **Phase 20 · "Intelligent Ops"** | 3 minggu | AI-assisted reports + OEE + WhatsApp Bot + Closed-loop rework | OEE dashboard, daily LLM summary, WA bot read-only, rework enforcement |

**Total: 16 minggu kerja.** Masing-masing fase *shippable independent* — bisa di-pause/re-prioritize.

---

## 📦 PHASE 16 — Foundation of Guidance (Minggu 1–3)

### Tujuan
Merangkul pengguna baru & lama dengan *next-action everywhere*. Quick wins paling tinggi ROI.

### Scope Fitur

#### 16.1 First-Run Setup Wizard
**Lokasi:** Floating modal triggered saat login pertama atau DB kosong.  
**Langkah 7-step:**
1. Gedung & Lokasi (default: Gedung A)
2. Proses Produksi (default: Rajut→Linking→Sewing→QC→Steam→Packing)
3. Shift Kerja (default: Shift Pagi 07-15, Shift Sore 15-23)
4. Line Produksi (minimal 1 line per proses utama)
5. Karyawan/Operator (import CSV + form cepat 5 row)
6. Model + Size (contoh 1 model, size S/M/L/XL)
7. Demo Order (auto-generate 1 order + WO + MI → user lihat full flow jalan)

**Acceptance:**
- Setelah wizard selesai, user bisa buka Dashboard & ada data.
- User bisa skip kapan saja & resume.
- State tersimpan di `setup_wizard_state` collection.

#### 16.2 Next-Action Engine (NAE)
**Backend:** `GET /api/rahaza/next-actions?portal=production&user_id=...`  
Rule-based, return maksimal 5 action card sesuai role + state.

**Contoh rules:**
```
IF orders.count(status=confirmed) > 0 AND !has_wo(order) → 
  action: "Order 123 sudah confirmed tapi belum ada WO" 
  CTA: /orders/123 + generate-wo

IF today lines.where(line.active AND !has_assignment) > 0 →
  action: "2 line aktif belum di-assign operator hari ini"
  CTA: /line-assignments?date=today&quick=true

IF wo.count(status=released) > 0 AND !has_mi(wo) →
  action: "3 WO released belum punya Material Issue"
  CTA: /material-issues?bulk_draft=wo_ids

IF low_stock_materials.count > 0 →
  action: "5 material di bawah minimum stock"
  CTA: /warehouse/stock?filter=low

IF orders.count(due_in_days<=3, status!=completed) > 0 →
  action: "2 order akan due dalam 3 hari"
  CTA: /orders?filter=due_soon
```

**Frontend:** `NextActionWidget` component, tampil di atas tiap Dashboard (Production, Warehouse, Finance, HR, Management).

**Acceptance:**
- Engine return < 200ms.
- Minimal 8 rules implemented.
- Widget dismissible per-card dengan snooze 4 jam.

#### 16.3 Empty-State CTA Upgrade
**Target:** 12 modul produksi utama.

Setiap empty state harus punya:
- Icon relevan
- Heading descriptive ("Belum ada Work Order" ≠ cukup)
- **Primary CTA** dengan tindakan spesifik
- **Secondary link** ke prerequisite modul jika belum ada (cth: "Buat Order dulu")
- **Tooltip "kenapa ini penting"** dengan ikon `?`

**Acceptance:** Review checklist via screenshot comparison PR.

#### 16.4 Contextual Tooltips
**Library:** Radix Tooltip (sudah ada via shadcn).  
**Target:** 30 field paling sering salah — Due Date, Priority, Target Qty, Is Internal, Shift, Lokasi Default di MI, dll.

**Konten:** Max 2 kalimat. Format:  
> *Apa itu ini* + *Dampak bisnis*.  
Contoh: *"Due Date = target kirim ke pelanggan. Jika WO completed setelah tanggal ini, order masuk kategori delay dan kena penalty on-time-rate."*

#### 16.5 Bulk Actions
- **Bulk Generate MI** dari multi-WO terpilih.
- **Bulk Assign Line** (paste dari template kemarin).
- **Bulk Transition Status** (confirm 5 order sekaligus).

### Files yang Akan Dibuat/Diubah
| File | Aksi |
|---|---|
| `backend/routes/rahaza_next_actions.py` | **BARU** — Next-Action Engine |
| `backend/routes/rahaza_setup.py` | **BARU** — Setup Wizard state |
| `frontend/src/components/erp/SetupWizard.jsx` | **BARU** |
| `frontend/src/components/erp/NextActionWidget.jsx` | **BARU** |
| `frontend/src/components/erp/ContextualTooltip.jsx` | **BARU** helper |
| `frontend/src/components/erp/ProductionDashboardModule.jsx` | **UBAH** — mount NextActionWidget |
| 12 modul empty-state | **UBAH** — CTA upgrade |

### Test Plan
- E2E: user baru login → wizard muncul → jalankan 7 step → dashboard tampil data demo.
- Unit: NAE rules (minimal 8) dengan fixtures.
- A11y: tooltip keyboard-navigable.

### Risk & Mitigation
| Risk | Mitigation |
|---|---|
| Wizard terasa "memaksa" | Tambah "Lewati saja" di tiap step |
| NAE menampilkan alert menghilang-muncul (noisy) | Snooze 4 jam + daily rate-limit per card |
| Tooltip bloat performance | Lazy-render Radix Tooltip (default behavior) |

---

## 📦 PHASE 17 — Bundle Traceability & Scan (Minggu 4–6)

### Tujuan
Mengubah pencatatan dari *aggregate* → *granular per bundle*. Setiap 20-50 pcs = 1 bundle, punya QR, ter-track dari Rajut → Shipment.

### Scope

#### 17.1 Bundle Entity
**Collection:** `bundles`  
**Fields:**
- `id`, `bundle_number` (BDL-YYYYMMDD-NNNN)
- `wo_id`, `wo_number_snapshot`, `model_id`, `size_id`
- `qty`, `current_process_id`, `current_line_id`, `status` (created / in_process / qc / reworking / packed / shipped)
- `created_at`, `updated_at`, `history[]` (events)
- `qr_code_url` (generated PDF link)

**Creation rule:** Saat WO `released`, auto-generate bundles berdasarkan aturan (default 30 pcs/bundle, configurable per model).

#### 17.2 QR Bundle Ticket Print
Library: **`qrcode` (backend Python)** + `jspdf` (frontend sudah terpasang).  
Endpoint: `GET /api/rahaza/bundles/{id}/ticket.pdf`  
Konten PDF (A6/thermal-printer-friendly):
- QR code besar (bundle_id)
- WO Number
- Model · Size · Qty
- Bar kotak sub-proses (Rajut/Linking/Sewing/QC/Steam/Packing) untuk stempel manual kalau QR rusak

**Bulk-print:** dari daftar WO, pilih → "Print semua bundle ticket".

#### 17.3 Operator Scan Workflow
**Frontend:** Library `html5-qrcode` (install via `yarn add html5-qrcode`).  
Di `OperatorView`:
1. Tombol besar "📷 Scan Bundle"
2. Kamera HP aktif → scan QR
3. Auto-fill: bundle info, WO, model, size, qty
4. Operator cukup input: qty yang selesai (default = bundle.qty, bisa partial) + pass/fail kalau QC
5. Submit → event tercatat, bundle pindah ke next process (auto compute next_process_id dari sequence)

#### 17.4 Bundle Detail Page
**Route:** `/production/bundle/{bundle_number}`  
Tampil:
- Timeline vertical: setiap event (Rajut start → Rajut end → Linking → ...)
- Operator yang menangani
- Durasi antar-event (cycle time)
- QC result + defect code
- Current location + next step

**Search:** ketik bundle number di global search top-bar.

#### 17.5 Closed-loop Rework
Saat QC fail → bundle (atau partial) status = `reworking`, must_return_process = Sewing (setelah Washer).  
Dashboard rework card: "12 bundle masih di rework, belum kembali > 4 jam — investigate".

### Files Baru
- `backend/routes/rahaza_bundles.py`
- `backend/utils/qrcode_generator.py`
- `frontend/src/components/erp/BundleTicketPDF.jsx`
- `frontend/src/components/erp/BundleScannerModal.jsx`
- `frontend/src/components/erp/BundleDetailPage.jsx`
- `frontend/src/components/erp/BundleReworkBoard.jsx`

### Migration
Run once: untuk `wo.released` yang sudah existing, auto-create bundles retroactively.

### Acceptance
- Operator bisa scan QR & submit output dalam < 10 detik.
- Bundle detail tampil timeline lengkap.
- Cycle time per-process tercatat akurat (timestamp tiap event).

---

## 📦 PHASE 18 — Proactive Floor (Minggu 7–9)

### Tujuan
Pabrik harus bicara ke pabrik. Alert real-time, andon operator, shop-floor TV, SOP inline.

### Scope

#### 18.1 Alert Bus (WebSocket)
Backend sudah ada `websocket.py` — extend menjadi broadcast channel per-role.  
**Topik:**
- `alert:production:*` — semua alert produksi
- `alert:line:{line_id}` — alert spesifik line (andon)
- `alert:urgent` — semua severity=urgent

**Alert sources:**
1. Behind target: line output < 70% target saat 60% shift berlalu
2. QC fail rate spike: fail/pass > 10% dalam 15 menit
3. Material low: sudah ada, tinggal di-push via WS
4. WO overdue: due_date < today AND status != completed
5. Machine breakdown (dari Phase 20)
6. Andon operator (dari 18.2)

**UI:** `AlertFeedDrawer` — slide-in dari kanan, Live list.

#### 18.2 Operator Andon
Di `OperatorView`, 4 tombol besar merah:
- 🔧 Mesin Rusak
- 📦 Material Habis
- ❌ Defect Banyak
- 🙋 Minta Bantuan (general)

**Flow:** Tekan → konfirmasi (2-tap untuk avoid accident) → notif realtime ke supervisor line-nya → log ke `andon_events` collection.  
**SLA tracker:** countdown "menit sejak andon" ditampilkan, escalate ke manager setelah 10 menit.

#### 18.3 Shop-Floor TV Mode
**Route:** `/tv/line/{line_id}` atau `/tv/floor` (semua line)  
**Design:** Full-screen, high-contrast, 5-detik refresh, tidak butuh login (read-only, IP-whitelist opsional).  
**Konten:**
- Progress bar besar per line
- Operator name + foto
- Target vs output huruf raksasa
- Live alert ticker di bawah
- Jam real-time + shift info

#### 18.4 SOP / Work Instruction Inline
**Master baru:** `ModelProcessSOP` = attach file/text/video per (model_id, process_id).  
Admin upload → operator `OperatorView` tampil button "📖 SOP" saat scan bundle. Modal tampil konten (PDF inline, image gallery, atau Bahasa plain-text).

#### 18.5 Shift Handover Checklist
Saat clock-out, leader shift tampil modal:
- [x] Semua output ter-record
- [x] Mesin bersih
- [x] Material sisa disimpan
- [x] Bundle sisa diserah-terimakan
- Catatan untuk shift berikutnya (free text)

Di-inject di `OperatorView` saat detected user adalah leader (role_field).

### Files Baru
- `backend/routes/rahaza_andon.py`
- `backend/routes/rahaza_alerts.py` (enhance existing)
- `backend/routes/rahaza_sop.py`
- `frontend/src/components/erp/AlertFeedDrawer.jsx`
- `frontend/src/components/erp/AndonPanel.jsx`
- `frontend/src/components/erp/ShopFloorTV.jsx`
- `frontend/src/components/erp/SOPModal.jsx`
- `frontend/src/components/erp/ShiftHandoverModal.jsx`

### Acceptance
- Alert muncul dalam < 3 detik dari event.
- Andon tap → notif supervisor < 3 detik.
- TV mode stabil 24 jam (no memory leak).

---

## 📦 PHASE 19 — Plan & Forecast (Minggu 10–13)

### Tujuan
Memberi PPIC & Manager kemampuan *melihat ke depan* — tidak hanya ke belakang.

### Scope

#### 19.1 Capacity & Scheduling Board (Gantt)
**Route:** `/production/schedule`  
**UI:** Grid — baris = line, kolom = hari (14-30 hari). Blok = WO yang ter-schedule.  
**Features:**
- Drag WO ke line/tanggal berbeda
- Tooltip di hover: WO detail, qty, expected output per day
- Capacity bar di bawah tiap line (daily capacity pcs vs total allocated)
- Conflict detection: overlap blok atau over-capacity → merah
- Save schedule ke DB → reflect ke `work_orders.scheduled_start`, `scheduled_end`, `scheduled_line_id`

**Library:** buat custom (tidak perlu library Gantt berat). Grid CSS + absolute-position blocks.

#### 19.2 SAM / Line Balancing
**Master baru:** `ModelProcessSAM` — standard allowed minutes per (model, process, size_bucket).  
**Logic:**
```
target_pcs_per_line_per_day = (shift_minutes × operator_count × line_efficiency%) / sam_minutes
```

**UI:**
- Form input SAM saat create/edit model (atau bulk import Excel).
- Saat create/edit Line Assignment, auto-suggest `target_qty` dengan formula di atas.
- Tombol "pakai saran sistem" vs manual override.

#### 19.3 Due-Date Forecast
**Algoritma sederhana:**
```
forecast_complete_date = today + ceil(remaining_qty / avg_daily_throughput_last_7_days)
risk = (forecast_complete_date - due_date).days
```
**UI:**
- Di list Order/WO, tambah kolom **Forecast** (hijau/kuning/merah badge).
- Di detail order, timeline: Today → Forecast Complete → Due Date → Deviation bar.
- Daily digest: "5 order berisiko delay: ..."

#### 19.4 Material Reservation
**Saat WO status transition → `released`:**
- Hitung total kebutuhan material dari BOM snapshot
- Validasi stock availability
- **IF available**: reserve (flag `reserved_qty` di stock)
- **IF partial**: allow release tapi flag `material_shortage_qty`
- **IF none**: block release + saran "perlu PO material X jumlah Y"

**UI:** Modal konfirmasi saat release + status badge di WO list ("Material: Reserved" / "Short by 5kg").

#### 19.5 Defect Code & Pareto Dashboard
**Master baru:** `DefectCodes` — kode (HOLE, BROKEN_STITCH, DIRT, SIZE_OUT, COLOR_MISS, dll) + severity (minor/major/critical) + action_if (accept/rework/reject).  
**Ubah QC event:** `qty_fail` → `defects: [{code, qty, action, notes}]`

**Dashboard baru `/production/quality`:**
- Pareto chart 30 hari: bar top-10 defect code
- Heatmap: defect per line × per process
- Trend: weekly defect rate
- Drill-down: per operator, per model
- FPY (First Pass Yield) per line: `qc_pass / (qc_pass + qc_fail)`

### Files Baru
- `backend/routes/rahaza_scheduling.py`
- `backend/routes/rahaza_sam.py`
- `backend/routes/rahaza_forecast.py`
- `backend/routes/rahaza_reservation.py`
- `backend/routes/rahaza_defects.py`
- `backend/routes/rahaza_quality.py`
- `frontend/src/components/erp/SchedulingBoard.jsx`
- `frontend/src/components/erp/SAMEditor.jsx`
- `frontend/src/components/erp/QualityDashboard.jsx`
- `frontend/src/components/erp/DefectCodesModule.jsx`

### Acceptance
- Gantt drag-drop update DB & re-render < 500ms.
- SAM target suggestion bisa di-override dan tetap saved.
- Reservation block release bila stok kurang + saran PO (prep untuk Purchase module future).
- Pareto chart interactive (click bar → filter).

---

## 📦 PHASE 20 — Intelligent Ops (Minggu 14–16)

### Tujuan
Layer AI tipis & OEE — tutup loop untuk excellence.

### Scope

#### 20.1 AI Daily Summary (pakai Emergent LLM)
**Endpoint:** `POST /api/rahaza/ai/daily-summary?date=YYYY-MM-DD`  
Input: aggregate data hari (output, target, bottleneck, alerts, defect top-3).  
Prompt:
```
Sebagai manajer produksi, ringkas data hari ini dalam 3 paragraf Bahasa Indonesia
untuk executive. Fokus: (1) pencapaian vs target, (2) masalah terbesar, (3) saran
besok. Gunakan data aktual, jangan berspekulasi.

Data hari:
{json.dumps(metrics)}
```

**UI:**
- Widget di Dashboard Produksi
- Send-via-Email button (pakai existing reminder infra)
- Schedule cron 17:30 tiap hari → push notifikasi ke manager

#### 20.2 Smart Search (NL → Query)
**Endpoint:** `POST /api/rahaza/ai/smart-search`  
Input: `{ query: "WO terlambat minggu ini untuk customer Alfamart" }`  
LLM convert → filter parameters → execute query → return results + explain.

Integrated di Command Palette (Cmd+K).

#### 20.3 OEE Dashboard
**Formula:**
```
OEE = Availability × Performance × Quality
where:
  Availability = (planned_run_time - downtime) / planned_run_time
  Performance  = (actual_output × cycle_time_ideal) / actual_run_time
  Quality      = qc_pass / (qc_pass + qc_fail_scrap)   # rework bukan scrap
```

**Prerequisite:** Downtime log (18.2 andon + machine status), SAM (19.2), QC with defect action (19.5).

**UI:** OEE per line harian + weekly trend, world-class benchmark line (85%), color-coded.

#### 20.4 WhatsApp Bot (Read-only MVP)
**Integration:** Twilio WhatsApp Business (atau WA Business API native).  
**Commands:**
- `/prod` → ringkasan hari ini
- `/wo 123` → status WO 123
- `/alert` → alert aktif
- `/help` → daftar command

**Privacy:** whitelist nomor HP di master user.

#### 20.5 Closed-loop Rework Enforcement
Validasi:
- `qc.qty_fail` per WO harus = sum(washer_output + sontek_output) untuk WO sama
- Jika gap > 0 (rework hilang), show alert
- Bundle yang flagged `reworking` > 8 jam → alert "stuck rework"
- Operator tidak bisa mark WO complete kalau masih ada bundle reworking

### Files Baru
- `backend/routes/rahaza_ai.py` (pakai `emergentintegrations`)
- `backend/routes/rahaza_oee.py`
- `backend/routes/rahaza_wa_bot.py`
- `frontend/src/components/erp/DailyAISummaryWidget.jsx`
- `frontend/src/components/erp/OEEDashboard.jsx`
- `frontend/src/components/erp/SmartSearchExt.jsx` (extend CommandPalette)

### Acceptance
- AI summary streaming < 10s, bahasa natural, berbasis data real.
- OEE numbers match manual calculation test cases.
- WA bot response < 5s.
- Closed-loop blocking works in test scenarios.

---

## 🛠️ Principles Teknis Lintas-Phase

1. **Every new feature MUST preserve existing data & endpoints.** Migrasi harus idempotent.
2. **Feature flags** — setiap fase di-gate oleh flag di `settings.features.*` biar bisa rollback cepat.
3. **Testing agent mandatory** — setelah implement suatu fase, testing agent jalan untuk coverage end-to-end.
4. **Screenshot regression** — Phase 16-18 terutama (banyak UI change), simpan snapshot baseline.
5. **A11y check** — setiap PR run `yarn lint` + manual keyboard walkthrough untuk modul baru.
6. **No hardcoded colors/spacing** — pakai design tokens di CSS variables existing.
7. **Non-breaking API changes** — kalau perlu ganti schema, tambah kolom baru, deprecate old, migrate data.

---

## 📝 Template Definition-of-Done per Phase

Sebuah phase dianggap **Done** kalau:
- [ ] Semua fitur di scope terdeliver (checklist acceptance di masing-masing sub-bab).
- [ ] Backend test (unit + integration) pass, coverage ≥ 70% untuk route baru.
- [ ] Frontend lint + build clean (`esbuild` check).
- [ ] Testing agent full-flow report tidak ada issue prioritas High.
- [ ] Screenshot pre-post untuk 3 screen utama phase terlampir.
- [ ] Dokumentasi user (di `HelpGuideModule`) ter-update.
- [ ] `plan.md` di root repo di-update (phase status = COMPLETED).
- [ ] Demo 5 menit ke user, user approve.

---

## 💡 Bagaimana Mulai Eksekusi?

**Rekomendasi immediate next step:** Mulai **Phase 16.1 Setup Wizard** dan **16.2 Next-Action Engine** parallel — keduanya independen, sama-sama quick win, dan langsung terasa dampaknya.

### Minggu 1 — Checklist Konkret:
- [ ] Day 1-2: Design Setup Wizard flow (user stories + mockup)
- [ ] Day 1-2: Spec Next-Action rules (daftar 10+ rules dengan SQL/Mongo query)
- [ ] Day 3-5: Implement backend `rahaza_setup.py` + `rahaza_next_actions.py`
- [ ] Day 6-8: Implement frontend `SetupWizard.jsx` + `NextActionWidget.jsx`
- [ ] Day 9: Integrate ke `ProductionDashboardModule.jsx`
- [ ] Day 10: Testing agent + fix bugs
- [ ] Day 10: Demo ke stakeholder + approval → merge

---

## 🤝 Governance

- **Owner:** Product Owner PT Rahaza (ditentukan)
- **Execution:** Main Agent (Neo) + subagent sesuai kebutuhan (design, testing, integration)
- **Review cadence:** per phase end → demo 5 menit + user feedback → decision go/no-go phase berikutnya
- **Rollback plan:** Feature flags di `settings.features` per phase. Kalau broken → toggle off < 1 menit.
- **Backup:** Production data tidak di-alter destructive — semua phase additive.

---

*Living document. Update setiap phase selesai atau scope berubah. Cross-reference: `PRODUCTION_FLOW_AUDIT.md`, `plan.md`.*
