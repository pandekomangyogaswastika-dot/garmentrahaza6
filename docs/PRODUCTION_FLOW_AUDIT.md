# 📋 Audit Flow Produksi — PT Rahaza ERP

> **Versi:** 1.0  
> **Tanggal:** 22 April 2026  
> **Auditor:** Neo (Emergent AI Engineer)  
> **Scope:** End-to-end produksi — Order → BOM → Work Order → Material Issue → Rajut → Linking → Sewing → QC → Steam → Packing → Shipment  
> **Metodologi:** Static code review (28+ backend routes, 75+ frontend components), walkthrough UI sebagai 5 persona (Operator, Supervisor, PPIC, Manager, Admin), pemetaan gap vs praktik lean manufacturing knit garment.

---

## 🎯 Executive Summary

### Temuan Utama — 1 Kalimat
> **Sistem saat ini adalah *system-of-record* yang kompeten (CRUD lengkap, data model rapi, status-machine jalan), tetapi belum menjadi *system-of-guidance* yang memandu operasional, memproaktifkan keputusan, dan menurunkan beban kognitif pengguna lapangan.**

### Kesehatan Flow (skor 1–5, 5 = terbaik)

| Dimensi | Skor | Catatan |
|---|---|---|
| **Data model & API coverage** | ⭐⭐⭐⭐ 4/5 | Entitas inti lengkap (Order, WO, BOM, MI, WIP events, QC events), UUID, timezone-aware, snapshot BOM di WO. |
| **End-to-end functional completeness** | ⭐⭐⭐⭐ 4/5 | Semua stage ada, tapi link antar-stage masih manual/opsional (lihat §2). |
| **Guidance / next-action** | ⭐⭐ 2/5 | Hampir semua modul berupa tabel + modal CRUD. Empty states tanpa CTA bertenaga. Tidak ada wizard onboarding. |
| **Decision support / analytics** | ⭐⭐ 2/5 | Hanya 1 bottleneck indicator (max WIP). Tidak ada prediksi delay, line balance, kapasitas vs demand, Pareto defect. |
| **Ease of use (persona operator)** | ⭐⭐⭐ 3/5 | Mobile-friendly (+5/+10/+25 chips, clock-in/out bagus). Tapi tidak ada SOP inline, foto referensi, scan barcode, defect code. |
| **Ease of use (persona supervisor/PPIC)** | ⭐⭐ 2/5 | Tidak ada "Today's task board", tidak ada drag-drop re-assign, tidak ada kapasitas board, tidak ada alert real-time. |
| **Proactive communication** | ⭐⭐ 2/5 | Hanya low-stock alert & QC fail-rate alert (latent). Tidak ada push/toast alert di dashboard, tidak ada eskalasi otomatis. |
| **Traceability / genealogy** | ⭐⭐ 2/5 | Output tercatat per line+proses+shift, tapi **tidak ada bundle/batch tracking** (50 pcs di Sewing ini dari WO mana?). Tidak ada serial/QR per bundle. |
| **Accessibility & a11y** | ⭐⭐⭐ 3/5 | Tombol ukuran OK di Operator View, tapi banyak `<select>` native kurang aksesibel; kontras teks muted kadang rendah di light-mode. |

**Skor rata-rata: 2.7/5** — system di bawah "good", jauh dari "great".

### 3 Hal Paling Kritikal yang Harus Dibenahi Duluan
1. **🔴 Journey-first navigation & guided setup wizard** — tanpa ini, sistem tidak *onboardable* buat user baru.
2. **🔴 Proactive alerts + Next-Action engine** — system harus *berbicara*, bukan menunggu user bertanya.
3. **🔴 Bundle/Batch Traceability** — tanpa tracking "bundle X di proses Y sejak jam Z", klaim "real-time WIP" setengah kebenaran.

---

## 1️⃣ Peta Alur End-to-End & Status Implementasi

### 1.1 Ideal Knit-Garment Flow

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Customer │──▶│  Order   │──▶│   BOM    │──▶│ Work     │──▶│ Material │
│ / Buyer  │   │          │   │ (Yarn+   │   │ Order    │   │ Issue    │
│          │   │          │   │ Access.) │   │ (WO)     │   │ (MI)     │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └────┬─────┘
                                                                  │
          ┌───────────────────────────────────────────────────────┘
          ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Rajut   │──▶│ Linking  │──▶│ Sewing   │──▶│   QC     │──▶│  Steam   │
│ (knit)   │   │ (join)   │   │ (jahit)  │   │ (gate)   │   │ (press)  │
└──────────┘   └──────────┘   └──────────┘   └────┬─────┘   └────┬─────┘
                                                  │              │
                                        (fail)    │              │
                                                  ▼              ▼
                                          ┌──────────┐   ┌──────────┐
                                          │ Washer / │   │ Packing  │
                                          │ Sontek   │──▶│ + FG WH  │
                                          │ (rework) │   │          │
                                          └──────────┘   └────┬─────┘
                                                               │
                                                               ▼
                                                         ┌──────────┐
                                                         │ Shipment │──▶ AR Invoice
                                                         │ (Surat   │
                                                         │  Jalan)  │
                                                         └──────────┘
```

### 1.2 Status di Sistem Saat Ini

| Stage | Modul / Endpoint | Status | Skor UX |
|---|---|---|---|
| Customer/Buyer | `RahazaCustomersModule` | ✅ Ada | 3/5 |
| Order Produksi | `RahazaOrdersModule` · `/api/rahaza/orders` | ✅ Ada, status machine (draft→confirmed→in_production→completed→closed) | 3/5 |
| **Generate WO dari Order** | `POST /orders/{id}/generate-work-orders` | ✅ Ada, 1-click per item | 4/5 |
| BOM (yarn KG + accessory) | `RahazaBOMModule` · matrix model×size | ✅ Ada, copy-to-sizes | 3/5 |
| Work Order | `RahazaWorkOrdersModule` · BOM snapshot freeze | ✅ Ada, progress per proses | 3/5 |
| Material Issue | `RahazaMaterialIssueModule` · draft-from-WO, stock decrement | ✅ Ada | 2/5 |
| Line assignment harian | `RahazaLineAssignmentsModule` · date+line+operator+shift+model+size+target | ✅ Ada | 2/5 |
| Rajut → Linking → Sewing | `ProcessExecutionModule` (generic) · `/execution/quick-output` | ✅ Ada, auto-refresh 15s | 3/5 |
| QC gate | `ProcessExecutionModule` + `/execution/qc-event` · Pass/Fail split | ✅ Ada | 3/5 |
| Steam / Packing | `ProcessExecutionModule` | ✅ Ada | 3/5 |
| Washer / Sontek rework | `ProcessExecutionModule` (flag rework) | ⚠️ Ada tapi **tidak close-loop** (tidak ada enforcement bahwa fail qty harus kembali = rework qty) | 2/5 |
| Operator View (mobile) | `OperatorView` · chips +1/+5/+10/+25, clock-in/out | ✅ Ada | 3/5 |
| Line Board (kanban) | `LineBoardModule` · per-proses column, auto-refresh 30s | ✅ Ada | 3/5 |
| Dashboard WIP | `ProductionDashboardModule` · 4 KPI + stacked bar | ✅ Ada | 3/5 |
| Shipment + Surat Jalan | `RahazaShipmentsModule` · auto AR invoice | ✅ Ada | 3/5 |
| **Bundle/Batch tracking** | — | ❌ **TIDAK ADA** | 0/5 |
| **Barcode/QR scan operator** | — | ❌ TIDAK ADA (tercantum di FUTURE) | 0/5 |
| **Capacity planning / Gantt** | — | ❌ TIDAK ADA | 0/5 |
| **Line balancing / SAM** | — | ❌ TIDAK ADA | 0/5 |
| **Defect code & Pareto** | — | ❌ Hanya qty_pass/qty_fail, no category | 0/5 |
| **Material shortage pre-check saat WO release** | — | ❌ TIDAK ADA | 0/5 |
| **Production schedule / Gantt harian per line** | — | ❌ TIDAK ADA | 0/5 |
| **Andon (operator stop-line / help)** | — | ❌ TIDAK ADA | 0/5 |
| **SOP inline / work instruction** | — | ❌ TIDAK ADA | 0/5 |
| **Ekspor laporan produksi** | CSV export ada di DataTable | ⚠️ Basic, tidak ada PDF laporan harian/mingguan terstruktur | 2/5 |

---

## 2️⃣ Pain Points per Persona (Use-case Audit)

### 2.1 👷 Persona: Operator Lantai

**Skenario kerja ideal dalam 1 shift (7-8 jam):**
> *"Saya datang → scan ID → lihat PM (Perintah Mulai) hari ini → ambil material dari leader → kerja → setiap N menit laporkan progress → kalau ada defect saya laporkan alasannya → istirahat → resume → akhir shift close-out."*

| Kebutuhan nyata | Status di sistem | Gap |
|---|---|---|
| Lihat "apa yang harus saya kerjakan hari ini" | ✅ `OperatorView` tampilkan assignments | ⚠️ Tapi tidak ada urutan prioritas; operator tidak tahu "yang mana dikerjakan dulu" |
| Referensi visual (foto model, sample) | ❌ | Operator masih harus tanya leader atau bawa lembar kertas |
| Instruksi kerja (SOP) per proses/model | ❌ | Tidak ada; asumsinya operator sudah tahu. Nyatanya: operator baru, model baru, proses rumit → banyak error. |
| Scan barcode/QR untuk identifikasi bundle | ❌ | Operator input via typing nama model/size → rawan salah |
| Input qty cepat | ✅ Chip +1/+5/+10/+25, auto-focus | 3/5 — baik |
| Laporkan defect dengan alasan (kategori) | ❌ Hanya `qty_fail + notes text` | Tidak terstandardisasi → analitik defect lemah |
| Minta bantuan / andon (mesin rusak, material habis) | ❌ | Operator tidak punya saluran resmi di sistem |
| Lihat progress target pribadi vs realisasi | ⚠️ Ada `output_today` & `target_qty` | OK, tapi tidak ada "nilai borongan / take-home estimate" |
| Ganti operator antar-mesin / antar-line dalam shift | ❌ | Assignment 1:1 per hari, tidak fleksibel |
| Rehat / idle / istirahat (non-productive time) | ❌ | Tidak tercatat → efisiensi operator tidak akurat |
| Feedback selesai: "pekerjaan ini 100% done" | ⚠️ Implisit via target | Tidak ada tombol "tandai WO/bundle selesai" eksplisit |

**Kesimpulan persona operator:** UI mobile sudah decent, tapi **sistem belum membantu operator bekerja — hanya menerima laporan darinya**.

---

### 2.2 👨‍🔧 Persona: Supervisor / Line Leader

**Skenario kerja ideal:**
> *"Pagi datang → cek status line saya → assign operator-shift-target → pantau real-time → deteksi yang lambat → tindaklanjut (rotate, tambah bantuan) → di-escalate kalau ada masalah besar → sore laporan harian."*

| Kebutuhan nyata | Status di sistem | Gap |
|---|---|---|
| Dashboard operasional "line saya" | ⚠️ `LineBoardModule` tampilkan semua line (tidak filter per leader) | Leader harus scroll cari line-nya |
| Cepat assign/re-assign operator & target | ⚠️ `RahazaLineAssignmentsModule` — form CRUD biasa, 1 row = 1 assignment | Tidak ada bulk-assign, tidak ada drag-drop, tidak ada template "hari biasa" |
| Target dihitung otomatis dari kapasitas line + SAM model | ❌ | Leader hitung manual → banyak error, sering over/under-target |
| Alert real-time "line X behind 40%" | ❌ | Leader harus proaktif buka dashboard |
| Eskalasi ke manager jika stuck > X menit | ❌ | Manual (WA) |
| Balance / rotate operator antar-line | ❌ | Tidak ada workflow |
| Lihat kebutuhan material hari ini vs tersedia | ⚠️ Ada di MI, tapi tidak ada "mass MI generator" untuk 1 hari | Leader issue MI satu-satu per WO — buang waktu |
| Catat alasan line stop (mesin rusak, listrik, dll) | ❌ | Tidak ada log reason |
| Lihat rekap shift cepat (laporan harian) | ⚠️ Harus buka Reports & filter manual | Tidak ada "End-of-shift summary" auto-generate |

**Kesimpulan persona supervisor:** **Ini persona yang PALING kurang dilayani**. Supervisor harus *melakukan manual apa yang seharusnya sistem tawarkan*.

---

### 2.3 📋 Persona: PPIC / Planner

**Skenario kerja ideal:**
> *"Terima order baru → cek kapasitas 2-4 minggu ke depan → schedule WO ke line → pastikan material cukup → rilis WO → monitor realisasi → re-plan kalau delay."*

| Kebutuhan nyata | Status di sistem | Gap |
|---|---|---|
| Capacity view: kapasitas line/hari vs demand | ❌ | Planner harus buka Excel sendiri |
| Schedule WO ke tanggal & line (Gantt) | ❌ | WO hanya punya `target_start_date`/`target_end_date` teks, tidak ter-schedule ke line |
| Cek stok material saat mau rilis WO | ⚠️ MI baru cek saat konfirmasi (sudah telat) | Harus "what-if" pre-check sebelum rilis |
| Line balancing: hitung SAM/SMV, set target realistis | ❌ | Tidak ada SAM di master data |
| Forecast: "order X akan selesai tanggal berapa?" | ❌ | Tidak ada forecast berdasarkan kapasitas saat ini |
| Ubah prioritas WO antar-order | ⚠️ Field `priority` ada (normal/high/urgent) | Tapi tidak auto-reorder di queue line |
| Notifikasi saat material mau habis (ROP) | ⚠️ `_check_low_stock_alert` ada di backend | Tidak visible di planner dashboard |
| Kalender produksi (libur, shift khusus) | ❌ | Master data shift ada, tapi tidak ada calendar exception |
| What-if simulation ("jika saya tambah 1 line, kapan order ini selesai?") | ❌ | — |

**Kesimpulan persona PPIC:** Modul PPIC effectively **tidak ada**. Role ini di-handle manual via Excel.

---

### 2.4 📊 Persona: Manager Produksi

**Skenario kerja ideal:**
> *"Lihat health pabrik per pagi → drill ke masalah → ambil keputusan → review KPI mingguan/bulanan → comparative trend."*

| Kebutuhan nyata | Status di sistem | Gap |
|---|---|---|
| Single-screen "factory health" | ⚠️ `ProductionDashboardModule` hanya 4 KPI + stacked bar | Tidak ada trend, tidak ada anomaly detection |
| Drill-down bottleneck → detail line → detail operator | ⚠️ Bottleneck terdeteksi, tapi klik tidak drill-down lengkap | Partial |
| Compare this-week vs last-week | ❌ | Hanya snapshot hari ini |
| OEE (Availability × Performance × Quality) | ❌ | Tidak ada konsep downtime, performance rate, defect rate per line |
| First-pass-yield (FPY) per line / model | ❌ | QC events ada, tapi tidak agregasi FPY |
| Root cause analysis (Pareto defect) | ❌ | Notes text tidak bisa di-agregasi |
| Financial impact (rework cost, delay cost) | ❌ | HPP ada tapi tidak real-time link |
| Dashboard mobile / TV display | ❌ | Hanya web desktop |
| Subscribe to weekly report (email/WA) | ❌ | — |

**Kesimpulan persona manager:** Dashboard sudah layak untuk "review", tapi belum layak untuk "decide".

---

### 2.5 🛠️ Persona: Admin Sistem / Onboarding

**Skenario:** *"Pabrik baru pakai sistem. Apa langkah pertamanya?"*

| Kebutuhan | Status | Gap |
|---|---|---|
| Wizard setup (step 1: lokasi, step 2: proses, step 3: line, ...) | ❌ | User harus tebak sendiri urutan |
| Dependency checker ("BOM butuh Model + Size dulu") | ⚠️ Hanya error saat save | Tidak proaktif |
| Sample/demo data | ❌ | Database kosong → semua modul empty-state |
| Role matrix visual | ✅ `RoleMatrixModule` ada | 4/5 — good |
| Tooltip "apa itu WO? BOM? MI?" | ❌ | Tidak ada glossary inline |
| Panduan penggunaan | ✅ `HelpGuideModule` (78KB file) | Perlu dilihat apakah contextual atau hanya static docs |

**Kesimpulan persona admin:** Sistem tidak *self-explanatory*. User baru hampir pasti nyasar.

---

## 3️⃣ Audit Ease-of-Use — Temuan Per UX Principle

### 3.1 ❌ Next-Action / Guided Workflow — ABSENT

**Observasi:**
- Dashboard WIP dengan output=0 hanya tampil "Tidak ada bottleneck" + "WIP seimbang" — padahal sebenarnya "belum ada aktivitas sama sekali".
- Halaman Work Order kosong → CTA hanya "WO Manual" + empty-state text — tidak mengarahkan user untuk:
  - Buat Order dulu
  - Atau generate dari Order existing
  - Atau atur BOM dulu
- Line Board kosong 6 kolom → hanya "Belum ada line untuk proses ini" — tidak ada tombol "Buat Line" langsung.

**Rekomendasi:** Setiap empty-state **wajib punya minimal 1 primary CTA** dengan label tindakan dan tooltip "kenapa ini penting".

### 3.2 ⚠️ Proactive Alerts — PARTIAL

Backend punya:
- `_check_low_stock_alert` (inventory)
- `_check_qc_fail_rate_alert` (quality)
- `NotificationBell` di topbar

**Tapi:** Tidak ada alert di dashboard utama. Tidak ada toast saat kejadian besar. Tidak ada eskalasi (jika 15 menit tidak diklik, notif ke manager).

### 3.3 ❌ Smart Defaults — LEMAH

- Target WO: user input bebas, tidak ada saran dari kapasitas+SAM
- Tanggal due: user input bebas, tidak ada validasi "apakah feasible"
- Line target: user input bebas
- Material qty di MI: dihitung BOM × qty WO (OK), tapi tidak ada "+waste%" / safety stock

### 3.4 ❌ Visual Decision Support — LEMAH

Yang ada: 1 stacked-bar per proses. Yang TIDAK ada:
- Bottleneck heatmap (grid line × proses dengan warna)
- Gantt schedule harian
- Flow sankey dari Rajut → Packing (mana yang tersumbat)
- Operator performance leaderboard (voluntary, motivational)
- Defect Pareto chart
- Throughput trend (hourly, daily, weekly)

### 3.5 ❌ Contextual Help — ABSENT

- Tidak ada tooltip di sebelah field (contoh: "apa itu Due Date vs Target End Date?")
- Tidak ada inline SOP ("sebelum release WO, pastikan BOM sudah ada")
- `HelpGuideModule` terpisah — user harus buka tab baru

### 3.6 ❌ AI-assisted — ABSENT

Tidak ada penggunaan `EMERGENT_LLM_KEY` di flow produksi. Padahal banyak peluang:
- Saran root-cause defect dari notes history
- Prediksi delay order
- Generate laporan harian otomatis (summary bahasa natural)
- Smart search ("order terlambat minggu ini untuk customer X")
- Chatbot supervisor ("berapa output line 3 hari ini?")

### 3.7 ⚠️ Menu Architecture — Not Journey-First

Struktur sekarang:
```
Produksi
  ├ Ringkasan → Dashboard, Line Board
  ├ Eksekusi → Order, WO, Assignment
  ├ Sales Closure → Shipment
  ├ Eksekusi Proses → Rajut, Linking, ... (process-by-process)
  └ Master Data → Lokasi, Proses, Shift, ..., BOM
```

**Masalah:** User baru masuk harus tahu urutan data apa dulu. "Master Data" di bawah padahal harus di-setup duluan. "Eksekusi Proses" punya 8 submenu — 1 submenu per proses — scaling buruk kalau pabrik punya 12 proses.

**Usulan:** Tambahkan section baru **"Pekerjaan Hari Ini"** (role-aware) di paling atas, yang merefleksikan task-driven UX, bukan data-driven.

### 3.8 ⚠️ Data Traceability — LEMAH

- `wip_events` tidak link ke `bundle_id` atau `lot_id`
- Tidak bisa jawab pertanyaan: "50 pcs di Packing ini dari WO mana, keluar dari mesin Rajut mana, di-link operator siapa, di-QC hari apa?"
- Rework tidak dilacak: qty fail di QC = 10 → berapa yang kembali dari Washer → Sewing ulang → QC lagi? Tidak ada closed-loop.

### 3.9 ⚠️ Form Design — Banyak Native `<select>`

Di `RahazaOrdersModule`, `RahazaBOMModule`, `RahazaWorkOrdersModule`, dll, banyak pakai native `<select>` bukan Shadcn `Select`/`Command`. Dampak:
- Search lambat di dropdown > 50 item
- Tidak ada keyboard shortcut
- Mobile UX kurang baik
- Tidak sesuai Design Mandate sistem sendiri

---

## 4️⃣ Gap Terhadap Praktik Best-in-Class Knit Garment

Saya bandingkan dengan pola MES/APS (Manufacturing Execution / Advanced Planning) untuk knit garment:

| Fitur | Industri Standar | Rahaza ERP | Gap Score |
|---|---|---|---|
| **Style Master** (foto, tech-pack, spec sheet) | ✅ | ⚠️ Hanya code+name | 🔴 Besar |
| **Size Run Matrix** per order | ✅ | ✅ Ada via order items | 🟢 OK |
| **BOM versioning + costing** | ✅ | ⚠️ BOM ada, tapi tidak versioned; HPP ada tapi tidak realtime link | 🟡 Sedang |
| **Material reservation** saat WO release | ✅ | ❌ Hanya issue saat MI confirm | 🔴 Besar |
| **Cut Plan / Marker** | ✅ di woven; knit biasanya direct-knit | ⚠️ N/A untuk knit | 🟢 OK |
| **Bundle Ticket + barcode** | ✅ Wajib | ❌ | 🔴 Besar |
| **Line Balancing** (SMV-based) | ✅ | ❌ | 🔴 Besar |
| **Real-time WIP by bundle** | ✅ | ⚠️ Hanya aggregate | 🔴 Besar |
| **In-line QC + defect code** | ✅ | ⚠️ Hanya pass/fail | 🟡 Sedang |
| **End-line QC + AQL sampling** | ✅ | ❌ | 🔴 Besar |
| **Rework tracking (closed-loop)** | ✅ | ⚠️ Flag ada, enforcement belum | 🟡 Sedang |
| **Operator performance / piece-rate payroll link** | ✅ | ⚠️ Payroll ada, tapi borongan pcs belum link ke WIP event | 🟡 Sedang |
| **Machine maintenance / breakdown log** | ✅ | ❌ | 🔴 Besar |
| **Finished Goods put-away by carton** | ✅ | ⚠️ Hanya generic warehouse | 🟡 Sedang |
| **Shipment pack list + carton manifest** | ✅ | ⚠️ Shipment ada, carton belum | 🟡 Sedang |
| **Andon + Shop floor messaging** | ✅ | ❌ | 🔴 Besar |
| **OEE dashboard** | ✅ | ❌ | 🔴 Besar |
| **Production Order Backlog view** | ✅ | ❌ | 🔴 Besar |
| **Shift handover checklist** | ✅ | ❌ | 🔴 Besar |
| **SOP / Work Instruction inline** | ✅ | ❌ | 🔴 Besar |

---

## 5️⃣ Daftar 30 Rekomendasi Konkret (prioritized)

Masing-masing rekomendasi ditaruh dalam matriks **Impact × Effort**:

- 🚀 **Quick Wins** (High Impact, Low Effort)
- 🎯 **Strategic** (High Impact, High Effort)  
- 🔧 **Fill Gaps** (Low Impact, Low Effort)
- ❄️ **Defer** (Low Impact, High Effort)

### 🚀 Quick Wins (minggu 1–2)

1. **Empty-state CTA** — Setiap modul kosong harus punya tombol primer + tooltip "kenapa" (WO, Order, Line, BOM, MI).
2. **Setup Wizard (First-run)** — Dialog onboarding 7 langkah saat database deteksi kosong: Lokasi → Proses → Shift → Line → Karyawan → Model+Size → BOM → Demo Order.
3. **Next-Action Widget di Production Dashboard** — Deteksi: *"3 WO belum punya MI → klik untuk generate batch"*, *"Line 2 belum di-assign hari ini → klik"*, *"2 Order due dalam 3 hari → review"*.
4. **Tooltip Kontekstual di Form** — Tambahkan `?` icon kecil di setiap field penting (Due Date, Prioritas, Target Qty, dll) dengan penjelasan & dampak.
5. **Sort & Filter default yang masuk akal** — Work Orders default sort by `due_date asc`, status filter exclude `completed+cancelled` by default.
6. **Global Command Palette sudah ada (Cmd+K)** — tambah "actions" bukan hanya navigasi (contoh: "Create WO from Order 123").
7. **Bulk Material Issue** — 1 klik "Draft MI untuk semua WO released hari ini".
8. **Auto-assign template** — "Pakai assignment kemarin sebagai template hari ini" (1 tombol → salin semua, lalu edit).
9. **Toast alert on major events** — saat QC fail-rate > threshold, saat low-stock triggered, saat WO released.
10. **Defect Code dropdown** (master data kecil, 10-15 kategori: holes, broken stitch, wrong color, dirt, size-out, dll) + replace notes free-text.

### 🎯 Strategic (bulan 1–3)

11. **Bundle/Batch Tracking** — Model baru: `Bundle` (bundle_number, wo_id, model, size, qty, current_process, current_line, status). Setiap WIP event wajib link ke bundle. Operator scan bundle → auto-fill form.
12. **Barcode/QR Generator & Scanner** — Print bundle ticket (QR PDF) saat WO release. Operator pakai HP scan → replace manual select. (Library: `html5-qrcode`).
13. **Capacity & Scheduling Board (Gantt)** — 1 baris per line, kolom tanggal, draggable WO blocks. Auto-check kapasitas. Export ke PDF planning.
14. **Line Balancing Tool** — Master data `SAM` (Standard Allowed Minute) per model×proses. Hitung target line per operator otomatis.
15. **Material Reservation on WO release** — Saat WO status → `released`, auto-reserve qty material. Blocking kalau short + saran PO/transfer.
16. **Andon Panel & Operator Help Request** — Tombol merah di Operator View: "Mesin Rusak" / "Material Habis" / "Defect Banyak" → kirim notif realtime ke leader (WebSocket).
17. **Shop Floor TV Mode** — Route `/tv/line/{line_id}` → full-screen kanban untuk ditampilkan di monitor line. Auto-refresh 5 detik, high-contrast.
18. **Defect Pareto Dashboard** — Top-10 defect kategori, drill ke line/operator, trend 30 hari.
19. **First-Pass-Yield (FPY) per line/model/operator** — Metrik quality.
20. **OEE Dashboard** — A × P × Q. Butuh downtime log (rekomendasi #24).
21. **Production Backlog view** — Daftar semua WO belum selesai, sort by due-risk (pakai formula deadline - forecast complete).
22. **Forecast "Kapan order selesai?"** — Linear projection: `(qty_remaining / avg_daily_output_per_line) + today`. Alert kalau melewati due.
23. **Closed-loop Rework Enforcement** — QC fail qty harus ada jejak di Washer/Sontek kembali ke pool Sewing. Audit gap.
24. **Machine Breakdown & Downtime Log** — Master `Machine` sudah ada. Tambah event `machine_stop` dgn reason code & duration. Masuk OEE.
25. **SOP / Work Instruction attachment per Model×Proses** — Upload PDF/foto/video, tampil di Operator View saat assignment aktif.

### 🔧 Fill Gaps (2–4 minggu kumulatif)

26. **Replace native `<select>` dengan Shadcn `Select`/`Combobox`** di 10+ modul utama (accessibility + search).
27. **End-of-Shift Report** — Auto-generate PDF (line, operator, target, output, efisiensi, defect) + email/WA.
28. **Production Calendar** — Libur nasional, shift khusus, cuti massal.
29. **Mobile PWA install** — Manifest + service worker → operator bisa pasang di HP sebagai ikon.
30. **WhatsApp Bot (read-only)** — *"/prod hari ini"* → kirim ringkasan. Pakai WA Business API atau Twilio.

### 🤖 AI-Assisted (pakai EMERGENT_LLM_KEY) — *cross-cutting*

- **Natural-language report**: "Hari ini output 2.300 pcs, turun 12% dari kemarin karena mesin Rajut-03 breakdown 2 jam." (auto-summary)
- **Smart search**: bahasa natural → filter data.
- **Root-cause assistant**: "Kenapa QC fail rate tinggi hari ini di line 5?" → analisis data + saran.
- **Predictive delay warning**: model sederhana LLM-assisted (parsing historical trend) → alert "Order 4 berisiko delay 2 hari".

---

## 6️⃣ Prinsip Desain untuk Transformasi System-of-Record → System-of-Guidance

**P-1. Every screen shows a "what-next"** — Bahkan empty state.  
**P-2. The system talks first** — Proactive alerts > manual inspection.  
**P-3. Numbers have context** — "500 pcs" → "500 pcs (83% dari target 600)".  
**P-4. Actions beat forms** — 1-klik bulk action > 10-klik manual.  
**P-5. Mobile-first di lantai, desktop-first di kantor** — Kita sudah arah sini, tinggal deepen.  
**P-6. Traceability by default** — Setiap event punya parent (WO, bundle, operator).  
**P-7. No dead-ends** — Setiap detail page punya "next" atau "related" shortcut.  
**P-8. Learning system** — Semakin dipakai, semakin smart (history → suggestion).  

---

## 7️⃣ Ringkasan Eksekutif — Untuk Keputusan

| Pilihan Strategis | Biaya | Manfaat | Rekomendasi |
|---|---|---|---|
| **A. Polish saja (fix warnings, tambah tooltips, empty-state CTA)** | 1 minggu | Low — sistem terasa lebih matang tapi esensi tidak berubah | ❌ Tidak sejalan dengan visi |
| **B. Bangun Guided Operations Layer (MVP)** — Phase 1-2 roadmap: Setup Wizard + Next-Action Engine + Bundle Tracking + Barcode + Andon | 6-8 minggu | **High** — sistem benar-benar berubah jadi "assistant of operations" | ✅ **DIREKOMENDASIKAN** |
| **C. Full MES/APS** — Implement semua 30 rekomendasi + custom AI layer | 4-6 bulan | Sangat tinggi tapi risk eksekusi besar | 🟡 Phase 3-4 setelah B terbukti |

**Usulan akhir:** Jalankan **Opsi B → C** sesuai roadmap di `PRODUCTION_GUIDED_SYSTEM_ROADMAP.md`.

---

*Dokumen ini hidup — akan di-update setiap phase roadmap selesai. Untuk pertanyaan, request perubahan scope, atau validasi temuan, hubungi Main Agent Neo atau buka issue di repository.*
