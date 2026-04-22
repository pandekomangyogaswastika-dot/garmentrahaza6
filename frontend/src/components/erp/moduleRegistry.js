import { lazy } from 'react';

// ─────────────────────────────────────────────────────────────────────────────
// PT Rahaza ERP — Module Registry (Stage A kerangka)
//
// Rules:
//   - Setiap moduleId UNIK (tidak duplikat antar portal).
//   - Hanya modul fungsional yang terdaftar di sini.
//   - Modul yang belum diimplementasi TIDAK di-register (placeholder ditangani
//     oleh portal-dashboard masing-masing yang menjelaskan status fase).
//
// Usage:
//   const Comp = MODULE_REGISTRY[moduleId] || DEFAULT_MODULE;
//   <Suspense fallback={<Spinner/>}><Comp {...props} /></Suspense>
// ─────────────────────────────────────────────────────────────────────────────

// Dashboards
const ManagementDashboard = lazy(() => import('./ManagementDashboard'));
const WarehouseDashboard  = lazy(() => import('./WarehouseDashboard'));
const FinanceDashboard    = lazy(() => import('./FinanceDashboard'));
const ProductionDashboardPlaceholder = lazy(() => import('./ProductionDashboardPlaceholder'));
const HRDashboardPlaceholder         = lazy(() => import('./HRDashboardPlaceholder'));

// Management — master data + administrasi
const ProductsModule        = lazy(() => import('./ProductsModule'));
const BuyersModule          = lazy(() => import('./BuyersModule'));
const ReportsModule         = lazy(() => import('./ReportsModule'));
const UserManagementModule  = lazy(() => import('./UserManagementModule'));
const RoleManagementModule  = lazy(() => import('./RoleManagementModule'));
const RoleMatrixModule      = lazy(() => import('./RoleMatrixModule'));
const ActivityLogModule     = lazy(() => import('./ActivityLogModule'));
const CompanySettingsModule = lazy(() => import('./CompanySettingsModule'));
const PDFConfigModule       = lazy(() => import('./PDFConfigModule'));
const HelpGuideModule       = lazy(() => import('./HelpGuideModule'));

// Warehouse
const ReceivingModule = lazy(() => import('./ReceivingModule'));
const PutAwayModule   = lazy(() => import('./PutAwayModule'));
const OpnameModule    = lazy(() => import('./OpnameModule'));
const LocationsModule = lazy(() => import('./LocationsModule'));
const AccessoryModule = lazy(() => import('./AccessoryModule'));

// Finance
const InvoiceModule            = lazy(() => import('./InvoiceModule'));
const PaymentModule            = lazy(() => import('./PaymentModule'));
const FinancialRecapModule     = lazy(() => import('./FinancialRecapModule'));
const AccountsPayableModule    = lazy(() => import('./AccountsPayableModule'));
const AccountsReceivableModule = lazy(() => import('./AccountsReceivableModule'));
const ManualInvoiceModule      = lazy(() => import('./ManualInvoiceModule'));
const ApprovalModule           = lazy(() => import('./ApprovalModule'));

// Produksi · Master Data Rajut (PT Rahaza)
const RahazaLocationsModule = lazy(() => import('./RahazaLocationsModule'));
const RahazaProcessesModule = lazy(() => import('./RahazaProcessesModule'));
const RahazaShiftsModule    = lazy(() => import('./RahazaShiftsModule'));
const RahazaMachinesModule  = lazy(() => import('./RahazaMachinesModule'));
const RahazaLinesModule     = lazy(() => import('./RahazaLinesModule'));
const RahazaEmployeesModule = lazy(() => import('./RahazaEmployeesModule'));
const RahazaModelsModule    = lazy(() => import('./RahazaModelsModule'));
const RahazaSizesModule     = lazy(() => import('./RahazaSizesModule'));
const RahazaLineAssignmentsModule = lazy(() => import('./RahazaLineAssignmentsModule'));
const LineBoardModule              = lazy(() => import('./LineBoardModule'));
const ProductionDashboardModule    = lazy(() => import('./ProductionDashboardModule'));
const RahazaCustomersModule        = lazy(() => import('./RahazaCustomersModule'));
const RahazaOrdersModule           = lazy(() => import('./RahazaOrdersModule'));
const RahazaBOMModule              = lazy(() => import('./RahazaBOMModule'));
const RahazaWorkOrdersModule       = lazy(() => import('./RahazaWorkOrdersModule'));
const RahazaBundlesModule          = lazy(() => import('./RahazaBundlesModule'));
const BundleReworkBoard            = lazy(() => import('./BundleReworkBoard'));
const RahazaAlertSettingsModule    = lazy(() => import('./RahazaAlertSettingsModule'));
const ProcessExecutionModule       = lazy(() => import('./ProcessExecutionModule'));
const RahazaMaterialsModule        = lazy(() => import('./RahazaMaterialsModule'));
const RahazaStockModule            = lazy(() => import('./RahazaStockModule'));
const RahazaMaterialIssueModule    = lazy(() => import('./RahazaMaterialIssueModule'));
const RahazaAttendanceModule       = lazy(() => import('./RahazaAttendanceModule'));
const RahazaPayrollProfilesModule  = lazy(() => import('./RahazaPayrollProfilesModule'));
const RahazaPayrollRunModule       = lazy(() => import('./RahazaPayrollRunModule'));
const RahazaCostCentersModule      = lazy(() => import('./RahazaCostCentersModule'));
const RahazaARInvoicesModule       = lazy(() => import('./RahazaARInvoicesModule'));
const RahazaCashAccountsModule     = lazy(() => import('./RahazaCashAccountsModule'));
const RahazaExpensesModule         = lazy(() => import('./RahazaExpensesModule'));
const RahazaHPPModule              = lazy(() => import('./RahazaHPPModule'));
const ManagementOverviewModule     = lazy(() => import('./ManagementOverviewModule'));
const RahazaShipmentsModule        = lazy(() => import('./RahazaShipmentsModule'));
const AndonBoardModule             = lazy(() => import('./AndonBoardModule'));
const RahazaSOPModule              = lazy(() => import('./RahazaSOPModule'));
const APSGanttModule               = lazy(() => import('./APSGanttModule'));

// Module map — id → component. IDs MUST be unique.
export const MODULE_REGISTRY = {
  // Portal dashboards
  'management-dashboard': ManagementDashboard,
  'production-dashboard': ProductionDashboardModule,
  'warehouse-dashboard':  WarehouseDashboard,
  'finance-dashboard':    FinanceDashboard,
  'hr-dashboard':         HRDashboardPlaceholder,

  // Management · Master Data & Admin
  'mgmt-products':     ProductsModule,
  'mgmt-customers':    BuyersModule,
  'mgmt-reports':      ReportsModule,
  'mgmt-users':        UserManagementModule,
  'mgmt-roles':        RoleManagementModule,
  'mgmt-role-matrix':  RoleMatrixModule,
  'mgmt-activity':     ActivityLogModule,
  'mgmt-company':      CompanySettingsModule,
  'mgmt-pdf':          PDFConfigModule,
  'mgmt-help':         HelpGuideModule,

  // Warehouse
  'wh-receiving':  ReceivingModule,
  'wh-putaway':    PutAwayModule,
  'wh-opname':     OpnameModule,
  'wh-bin':        LocationsModule,
  'wh-accessory':  AccessoryModule,

  // Finance
  'fin-ar':            AccountsReceivableModule,
  'fin-ap':            AccountsPayableModule,
  'fin-invoices':      InvoiceModule,
  'fin-manual-invoice':ManualInvoiceModule,
  'fin-approval':      ApprovalModule,
  'fin-payments':      PaymentModule,
  'fin-recap':         FinancialRecapModule,

  // Produksi · Master Data (Fase 3)
  'prod-locations': RahazaLocationsModule,
  'prod-processes': RahazaProcessesModule,
  'prod-shifts':    RahazaShiftsModule,
  'prod-machines':  RahazaMachinesModule,
  'prod-lines':     RahazaLinesModule,
  'prod-employees': RahazaEmployeesModule,

  // Produksi · Eksekusi (Fase 4)
  'prod-models':       RahazaModelsModule,
  'prod-sizes':        RahazaSizesModule,
  'prod-assignments':  RahazaLineAssignmentsModule,
  'prod-line-board':   LineBoardModule,

  // Produksi · Order (Fase 5a)
  'prod-orders':       RahazaOrdersModule,

  // Produksi · BOM + WO (Fase 5b & 5c)
  'prod-bom':          RahazaBOMModule,
  'prod-work-orders':  RahazaWorkOrdersModule,

  // Produksi · Bundle Traceability (Phase 17A)
  'prod-bundles':      RahazaBundlesModule,

  // Produksi · Rework Board (Phase 17E)
  'prod-rework-board': BundleReworkBoard,

  // Produksi · Alert Settings (Phase 18A)
  'prod-alert-settings': RahazaAlertSettingsModule,

  // Produksi · Eksekusi Proses (Fase 6) — 1 komponen generik dgn moduleId sbg kode proses
  'prod-exec-rajut':   ProcessExecutionModule,
  'prod-exec-linking': ProcessExecutionModule,
  'prod-exec-sewing':  ProcessExecutionModule,
  'prod-exec-qc':      ProcessExecutionModule,
  'prod-exec-steam':   ProcessExecutionModule,
  'prod-exec-packing': ProcessExecutionModule,
  'prod-exec-washer':  ProcessExecutionModule,
  'prod-exec-sontek':  ProcessExecutionModule,

  // Warehouse · Inventory Rahaza (Fase 7)
  'wh-materials':      RahazaMaterialsModule,
  'wh-stock':          RahazaStockModule,
  'wh-material-issue': RahazaMaterialIssueModule,

  // HR · Attendance (Fase 8a)
  'hr-attendance':     RahazaAttendanceModule,

  // HR · Payroll (Fase 8b + 8c)
  'hr-payroll-profiles': RahazaPayrollProfilesModule,
  'hr-payroll-run':      RahazaPayrollRunModule,

  // Finance · Enhanced (Fase 8.5)
  'fin-cost-centers':  RahazaCostCentersModule,
  'fin-ar-invoices':   RahazaARInvoicesModule,
  'fin-cash':          RahazaCashAccountsModule,
  'fin-expenses':      RahazaExpensesModule,

  // Finance · HPP (Fase 9)
  'fin-hpp':           RahazaHPPModule,

  // Management · Overview (Fase 10)
  'mgmt-overview':     ManagementOverviewModule,

  // Produksi · Sales Closure (Fase 14)
  'prod-shipments':    RahazaShipmentsModule,

  // Management · Master Data (Fase 5a — ganti BuyersModule dengan Rahaza Customers)
  'mgmt-rahaza-customers': RahazaCustomersModule,

  // Produksi · Andon Panel (Phase 18B)
  'prod-andon-board': AndonBoardModule,

  // Produksi · SOP Inline (Phase 18D)
  'prod-sop': RahazaSOPModule,

  // Produksi · APS Gantt (Phase 19A)
  'prod-aps-gantt': APSGanttModule,
};

export const DEFAULT_MODULE = ManagementDashboard;
