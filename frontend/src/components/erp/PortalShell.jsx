import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { GlassPanel, PillButton, IconBadge } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/theme/ThemeToggle';
import { CommandPalette } from './CommandPalette';
import { NotificationBell } from './NotificationBell';
import {
  Search, X, ChevronLeft, Menu, LogOut, Command as CommandIcon,
  LayoutDashboard, Package, BarChart3, Users, Activity,
  DollarSign, BookOpen, Pencil, Shield, ShieldCheck, Gem, FileDown, Settings,
  ArrowDownToLine, MapPin, ClipboardCheck, PackageOpen,
  FileText, CreditCard, TrendingUp, PieChart, UserCog,
  Factory, Wrench, Timer, ListChecks, LayoutGrid, ClipboardList,
  Archive, Clock, Warehouse, Truck, Hammer, Siren, AlertTriangle, Tv,
} from 'lucide-react';

// Portal labels shown as badge next to brand (top-left). Click brand to go back to selector.
const PORTAL_LABEL = {
  management: 'Management',
  production:  'Produksi',
  warehouse:   'Gudang',
  finance:     'Finance',
  hr:          'HR',
};

// ── PT Rahaza ERP · Portal-specific navigation (single source of truth) ──
// Rules:
//   - Bahasa Indonesia untuk label menu.
//   - Tidak ada moduleId duplikat antar portal (enforced by registry).
//   - Hanya menu yang fungsional di fase saat ini. Modul fase berikutnya
//     akan ditambah sesuai roadmap di plan.md.
const PORTAL_NAV = {
  management: {
    title: 'Management',
    sections: [
      {
        label: 'RINGKASAN',
        items: [
          { id: 'management-dashboard', label: 'Dashboard Eksekutif', icon: BarChart3 },
          { id: 'mgmt-overview',        label: 'Overview Bisnis',     icon: TrendingUp },
          { id: 'mgmt-reports',         label: 'Laporan',             icon: FileText },
        ]
      },
      {
        label: 'MASTER DATA',
        items: [
          { id: 'mgmt-products',          label: 'Data Produk',    icon: Package },
          { id: 'mgmt-rahaza-customers',  label: 'Data Pelanggan', icon: Users },
        ]
      },
      {
        label: 'SISTEM',
        items: [
          { id: 'mgmt-users',       label: 'Manajemen User', icon: Users },
          { id: 'mgmt-roles',       label: 'Manajemen Role', icon: Shield },
          { id: 'mgmt-role-matrix', label: 'Matriks Permission', icon: ShieldCheck },
          { id: 'mgmt-activity',    label: 'Log Aktivitas', icon: Activity },
          { id: 'mgmt-company',  label: 'Pengaturan Perusahaan', icon: Settings },
          { id: 'mgmt-pdf',      label: 'Konfigurasi PDF', icon: FileDown },
          { id: 'mgmt-help',     label: 'Panduan Penggunaan', icon: BookOpen },
        ]
      },
    ]
  },

  production: {
    title: 'Produksi',
    sections: [
      {
        label: 'RINGKASAN',
        items: [
          { id: 'production-dashboard', label: 'Dashboard Produksi (WIP)', icon: LayoutDashboard },
          { id: 'prod-line-board',      label: 'Line Board',               icon: LayoutGrid },
        ]
      },
      {
        label: 'EKSEKUSI',
        items: [
          { id: 'prod-orders',       label: 'Order Produksi',       icon: ClipboardList },
          { id: 'prod-work-orders',  label: 'Work Order',           icon: ClipboardList },
          { id: 'prod-bundles',      label: 'Bundle Traceability',  icon: Package },
          { id: 'prod-rework-board', label: 'Papan Rework',         icon: Hammer },
          { id: 'prod-assignments',  label: 'Assign Line Hari Ini', icon: ClipboardList },
        ]
      },
      {
        label: 'MONITORING',
        items: [
          { id: 'prod-alert-settings', label: 'Alert Engine',  icon: Siren },
          { id: 'prod-andon-board',    label: 'Papan Andon',   icon: AlertTriangle },
        ]
      },
      {
        label: 'SALES CLOSURE',
        items: [
          { id: 'prod-shipments',    label: 'Pengiriman (Surat Jalan)', icon: Truck },
        ]
      },
      {
        label: 'SHOP FLOOR TV',
        items: [
          { id: '__tv_mode__', label: 'TV Mode (Lantai)', icon: Tv, external: true, href: '/tv' },
        ]
      },
      {
        label: 'EKSEKUSI PROSES',
        items: [
          { id: 'prod-exec-rajut',   label: '1 · Rajut',    icon: Factory },
          { id: 'prod-exec-linking', label: '2 · Linking',  icon: Factory },
          { id: 'prod-exec-sewing',  label: '3 · Sewing',   icon: Factory },
          { id: 'prod-exec-qc',      label: '4 · QC',       icon: ClipboardCheck },
          { id: 'prod-exec-steam',   label: '5 · Steam',    icon: Factory },
          { id: 'prod-exec-packing', label: '6 · Packing',  icon: PackageOpen },
          { id: 'prod-exec-washer',  label: 'R · Washer',   icon: Factory },
          { id: 'prod-exec-sontek',  label: 'R · Sontek',   icon: Factory },
        ]
      },
      {
        label: 'MASTER DATA',
        items: [
          { id: 'prod-locations', label: 'Gedung & Zona',    icon: MapPin },
          { id: 'prod-processes', label: 'Proses Produksi',  icon: ListChecks },
          { id: 'prod-shifts',    label: 'Shift Kerja',      icon: Timer },
          { id: 'prod-machines',  label: 'Mesin Rajut',      icon: Wrench },
          { id: 'prod-lines',     label: 'Line Produksi',    icon: Factory },
          { id: 'prod-employees', label: 'Karyawan & Operator', icon: Users },
          { id: 'prod-models',    label: 'Model Produk',     icon: Package },
          { id: 'prod-sizes',     label: 'Ukuran (Size)',    icon: Gem },
          { id: 'prod-bom',       label: 'BOM Produk',       icon: ListChecks },
          { id: 'prod-sop',       label: 'SOP Produksi',     icon: BookOpen },
        ]
      },
    ]
  },

  warehouse: {
    title: 'Gudang',
    sections: [
      {
        label: 'RINGKASAN',
        items: [
          { id: 'warehouse-dashboard', label: 'Dashboard Gudang', icon: LayoutDashboard },
        ]
      },
      {
        label: 'INVENTORY',
        items: [
          { id: 'wh-materials',      label: 'Master Material',      icon: Package },
          { id: 'wh-stock',          label: 'Stok & Movement',      icon: Archive },
          { id: 'wh-material-issue', label: 'Material Issue (WO)',  icon: ClipboardList },
        ]
      },
      {
        label: 'GUDANG UMUM (LEGACY)',
        items: [
          { id: 'wh-receiving', label: 'Penerimaan Barang', icon: ArrowDownToLine },
          { id: 'wh-putaway',   label: 'Put-Away', icon: MapPin },
          { id: 'wh-opname',    label: 'Stock Opname', icon: ClipboardCheck },
          { id: 'wh-bin',       label: 'Lokasi / Bin', icon: PackageOpen },
          { id: 'wh-accessory', label: 'Aksesoris', icon: Gem },
        ]
      },
    ]
  },

  finance: {
    title: 'Finance',
    sections: [
      {
        label: 'RINGKASAN',
        items: [
          { id: 'finance-dashboard', label: 'Dashboard Finance', icon: LayoutDashboard },
        ]
      },
      {
        label: 'RAHAZA FINANCE',
        items: [
          { id: 'fin-ar-invoices',  label: 'AR Invoices',     icon: FileText },
          { id: 'fin-cash',         label: 'Cash & Bank',     icon: DollarSign },
          { id: 'fin-expenses',     label: 'Expenses',        icon: CreditCard },
          { id: 'fin-cost-centers', label: 'Cost Centers',    icon: PieChart },
          { id: 'fin-hpp',          label: 'HPP / Costing',   icon: TrendingUp },
        ]
      },
      {
        label: 'LEGACY PIUTANG',
        items: [
          { id: 'fin-ar',       label: 'Piutang (AR)', icon: TrendingUp },
          { id: 'fin-invoices', label: 'Semua Invoice', icon: FileText },
        ]
      },
      {
        label: 'LEGACY HUTANG',
        items: [
          { id: 'fin-ap',             label: 'Hutang (AP)', icon: CreditCard },
          { id: 'fin-manual-invoice', label: 'Invoice Manual', icon: Pencil },
          { id: 'fin-approval',       label: 'Approval Invoice', icon: Shield },
        ]
      },
      {
        label: 'LEGACY PEMBAYARAN & LAPORAN',
        items: [
          { id: 'fin-payments', label: 'Pembayaran', icon: DollarSign },
          { id: 'fin-recap',    label: 'Rekap Keuangan', icon: PieChart },
        ]
      },
    ]
  },

  hr: {
    title: 'HR',
    sections: [
      {
        label: 'RINGKASAN',
        items: [
          { id: 'hr-dashboard', label: 'Dashboard HR', icon: UserCog },
        ]
      },
      {
        label: 'KEHADIRAN',
        items: [
          { id: 'hr-attendance', label: 'Absensi Harian', icon: Clock },
        ]
      },
      {
        label: 'PAYROLL',
        items: [
          { id: 'hr-payroll-profiles', label: 'Profile Payroll', icon: UserCog },
          { id: 'hr-payroll-run',      label: 'Payroll Run & Slip', icon: DollarSign },
        ]
      },
    ]
  },
};

// Helper: cari label menu berdasarkan currentModule (untuk topbar title)
export function findModuleLabel(portal, moduleId) {
  const nav = PORTAL_NAV[portal];
  if (!nav) return moduleId;
  for (const sec of nav.sections) {
    const found = sec.items.find(it => it.id === moduleId);
    if (found) return found.label;
  }
  return moduleId;
}

export default function PortalShell({ portal, user, token, onBack, onLogout, onPortalChange, children, currentModule, onModuleChange }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [cmdkOpen, setCmdkOpen] = useState(false);
  const searchRef = useRef(null);
  const searchTimeout = useRef(null);

  const nav = PORTAL_NAV[portal] || PORTAL_NAV.management;

  // ── Global module suggestions (semua portal) untuk Command Palette ──
  const moduleSuggestions = useMemo(() => {
    const out = [];
    Object.entries(PORTAL_NAV).forEach(([pid, p]) => {
      p.sections.forEach(sec => {
        sec.items.forEach(it => {
          out.push({
            id: it.id,
            label: it.label,
            portal: PORTAL_LABEL[pid] || pid,
            portalId: pid,
            section: sec.label,
            icon: it.icon,
          });
        });
      });
    });
    return out;
  }, []);

  // ── Section-based nav (user's model): top pills = sections, left sidebar = items of active section ──
  const activeSectionIndex = Math.max(
    0,
    nav.sections.findIndex(s => s.items.some(i => i.id === currentModule))
  );
  const activeSection = nav.sections[activeSectionIndex] || nav.sections[0];

  const handleSectionPillClick = (sectionLabel) => {
    const target = nav.sections.find(s => s.label === sectionLabel);
    if (!target || !target.items?.length) return;
    // On section change, jump to the first item in that section
    onModuleChange(target.items[0].id);
    setMobileOpen(false);
  };

  // Close search on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleSearchInput = useCallback((q) => {
    setSearchQuery(q);
    if (!q.trim()) { setSearchResults([]); setSearchOpen(false); return; }
    setSearchOpen(true);
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await fetch(`/api/global-search?q=${encodeURIComponent(q)}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = await res.json();
        setSearchResults(data.results || []);
      } catch (e) {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);
  }, [token]);

  const handleSearchSelect = (result) => {
    onModuleChange(result.module);
    setSearchQuery('');
    setSearchResults([]);
    setSearchOpen(false);
  };

  const handlePortalPillClick = (pid) => { /* legacy — top pills now show sections, brand click handles portal-back */ };

  return (
    <div className="flex flex-col h-screen" data-testid={`portal-shell-${portal}`}>
      {/* ╔═══════════════════════════════════════════════════════════════════╗
          ║  TOP BAR — Brand + Portal Badge + SECTION pills + Search + Theme   ║
          ╚═══════════════════════════════════════════════════════════════════╝ */}
      <header className="sticky top-0 z-40 border-b border-[var(--glass-border)] bg-[var(--card-surface)] backdrop-blur-[var(--glass-blur-strong)]">
        <div className="flex items-center gap-3 px-3 sm:px-5 py-2.5">
          {/* Mobile menu toggle */}
          <button
            className="md:hidden p-1.5 rounded-lg text-foreground/60 hover:text-foreground hover:bg-[var(--nav-pill-active)] transition-colors duration-150"
            onClick={() => setMobileOpen(true)}
            data-testid="mobile-menu-btn"
            aria-label="Buka menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* Brand + Portal badge (click brand → back to portal selector) */}
          <button
            onClick={onBack}
            className="flex items-center gap-2 shrink-0 group transition-opacity duration-150 hover:opacity-80"
            data-testid="portal-back-btn"
            aria-label="Kembali ke pilih portal"
            title="Klik untuk ganti portal"
          >
            <div className="w-9 h-9 rounded-[12px] bg-[hsl(var(--primary)/0.15)] border border-[hsl(var(--primary)/0.25)] grid place-items-center text-[hsl(var(--primary))] font-bold text-sm group-hover:scale-105 transition-transform duration-150">
              R
            </div>
            <div className="hidden md:flex flex-col leading-tight text-left">
              <span className="text-[10px] uppercase tracking-wider text-foreground/40 font-semibold">Portal</span>
              <span className="text-sm font-semibold text-foreground -mt-0.5">{PORTAL_LABEL[portal] || portal}</span>
            </div>
            <ChevronLeft className="hidden md:block w-3.5 h-3.5 text-foreground/30 ml-0.5 group-hover:text-foreground/60 transition-colors duration-150" />
          </button>

          {/* Section pill nav — THE MENU (sections of current portal) */}
          <nav
            className="hidden md:inline-flex items-center gap-1 rounded-full border border-[var(--glass-border)] bg-[var(--nav-pill-bg)] backdrop-blur-xl p-1 overflow-x-auto max-w-[55vw]"
            data-testid="section-pill-nav"
            aria-label="Menu portal"
          >
            {nav.sections.map((s, idx) => {
              const active = idx === activeSectionIndex;
              return (
                <button
                  key={s.label}
                  onClick={() => handleSectionPillClick(s.label)}
                  className={`relative inline-flex items-center gap-2 rounded-full px-3 lg:px-4 py-1.5 text-xs lg:text-sm font-medium whitespace-nowrap
                    transition-[background-color,color,box-shadow] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)]
                    ${active
                      ? 'bg-[var(--nav-pill-active)] text-foreground shadow-[var(--shadow-glow-blue)]'
                      : 'text-foreground/60 hover:text-foreground hover:bg-[var(--nav-pill-active)]/60'
                    }`}
                  data-testid={`section-pill-${idx}`}
                  aria-pressed={active}
                  aria-label={`Menu ${s.label}`}
                >
                  <span className={active ? 'text-[hsl(var(--primary))]' : ''}>
                    {formatSectionLabel(s.label)}
                  </span>
                </button>
              );
            })}
          </nav>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Global Search */}
          <div ref={searchRef} className="relative hidden sm:block w-56 lg:w-72">
            <div className="flex items-center gap-2 border border-[var(--glass-border)] rounded-full px-3 py-1.5 bg-[var(--nav-pill-bg)] backdrop-blur-xl focus-within:border-[hsl(var(--primary)/0.4)] transition-colors duration-150">
              <Search className="w-3.5 h-3.5 text-foreground/40 shrink-0" />
              <input
                type="text"
                placeholder="Cari order, WO, SKU..."
                className="flex-1 bg-transparent text-xs text-foreground placeholder:text-foreground/40 focus:outline-none"
                value={searchQuery}
                onChange={e => handleSearchInput(e.target.value)}
                onFocus={() => searchQuery && setSearchOpen(true)}
                data-testid="topbar-global-search-input"
              />
              {searchQuery && (
                <button onClick={() => { setSearchQuery(''); setSearchResults([]); setSearchOpen(false); }} data-testid="search-clear-btn" aria-label="Bersihkan pencarian">
                  <X className="w-3.5 h-3.5 text-foreground/40 hover:text-foreground/70" />
                </button>
              )}
            </div>

            {searchOpen && (
              <div className="absolute top-full mt-1.5 left-0 right-0 rounded-[var(--radius-md)] border border-[var(--glass-border)] bg-[var(--popover-surface)] backdrop-blur-[var(--glass-blur-strong)] shadow-[var(--shadow-soft)] z-50 overflow-hidden">
                {searchLoading ? (
                  <div className="px-4 py-3 text-xs text-foreground/50 text-center">Mencari...</div>
                ) : searchResults.length === 0 ? (
                  <div className="px-4 py-3 text-xs text-foreground/40 text-center">Tidak ada hasil untuk "{searchQuery}"</div>
                ) : (
                  <div className="max-h-80 overflow-y-auto">
                    {searchResults.map((r, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleSearchSelect(r)}
                        className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-[var(--glass-bg-hover)] text-left transition-colors duration-150 border-b border-[var(--glass-border)] last:border-0"
                        data-testid={`search-result-${idx}`}
                      >
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold shrink-0 bg-[var(--nav-pill-active)] text-foreground/70 uppercase">{r.type}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium text-foreground truncate">{r.label}</p>
                          {r.sub && <p className="text-[10px] text-foreground/50 truncate">{r.sub}</p>}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Theme + user + logout */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Command Palette trigger (Cmd+K) */}
            <button
              onClick={() => setCmdkOpen(true)}
              className="hidden sm:inline-flex items-center gap-1.5 h-9 px-2.5 rounded-full border border-[var(--glass-border)] bg-[var(--nav-pill-bg)] text-foreground/60 hover:text-foreground hover:bg-[var(--nav-pill-active)] transition-colors duration-150"
              data-testid="topbar-cmdk-trigger"
              title="Buka Command Palette (Ctrl/Cmd + K)"
              aria-label="Buka Command Palette"
            >
              <CommandIcon className="w-3.5 h-3.5" />
              <span className="hidden lg:inline text-[10px] font-semibold tracking-wider uppercase">⌘ K</span>
            </button>
            <ThemeToggle />
            <NotificationBell
              token={token}
              onNavigateModule={(moduleId) => { if (moduleId) onModuleChange(moduleId); }}
            />
            <div className="hidden md:flex items-center gap-2 pl-2 ml-1 border-l border-[var(--glass-border)]" data-testid="topbar-user-info">
              <div className="w-8 h-8 rounded-full bg-[hsl(var(--primary)/0.15)] border border-[hsl(var(--primary)/0.25)] grid place-items-center text-[hsl(var(--primary))] text-xs font-bold">
                {user?.name?.[0]?.toUpperCase() || '?'}
              </div>
              <div className="hidden lg:block leading-tight">
                <p className="text-xs font-medium text-foreground truncate max-w-[140px]">{user?.name || 'User'}</p>
                <p className="text-[10px] text-foreground/50 capitalize">{user?.role || ''}</p>
              </div>
            </div>
            <button
              onClick={onLogout}
              className="h-9 w-9 rounded-full border border-[var(--glass-border)] bg-[var(--nav-pill-bg)] text-foreground/60 hover:text-foreground hover:bg-[var(--nav-pill-active)] transition-colors duration-150 grid place-items-center"
              data-testid="topbar-logout-btn"
              title="Keluar"
              aria-label="Keluar"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* ╔═══════════════════════════════════════════════════════════════════╗
          ║  BODY — Side Nav (items of active section) + Main Content         ║
          ╚═══════════════════════════════════════════════════════════════════╝ */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Sidebar — flat list of items belonging to ACTIVE section */}
        <aside
          className={`${collapsed ? 'md:w-[72px]' : 'md:w-[240px]'}
            fixed md:static inset-y-0 left-0 z-30 w-[260px]
            transition-[width,transform] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]
            ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
          data-testid="portal-sidebar"
        >
          <div className="h-full flex flex-col bg-[var(--card-surface)] backdrop-blur-[var(--glass-blur-strong)] border-r border-[var(--glass-border)]">
            {/* Sidebar header: active section name + collapse toggle */}
            <div className="px-3 py-3 flex items-center justify-between border-b border-[var(--glass-border)]">
              {!collapsed && (
                <div className="flex items-center gap-2 min-w-0 px-1">
                  <div className="w-1 h-4 rounded-full bg-[hsl(var(--primary))] shrink-0" />
                  <span className="text-[11px] font-semibold tracking-wider text-foreground/70 uppercase truncate" data-testid="sidebar-active-section">
                    {formatSectionLabel(activeSection?.label || '')}
                  </span>
                </div>
              )}
              <button
                onClick={() => setCollapsed(!collapsed)}
                className="hidden md:grid place-items-center h-7 w-7 rounded-lg text-foreground/50 hover:text-foreground hover:bg-[var(--nav-pill-active)] transition-colors duration-150"
                data-testid="sidebar-toggle-btn"
                aria-label={collapsed ? 'Perluas menu' : 'Ciutkan menu'}
              >
                <Menu className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setMobileOpen(false)}
                className="md:hidden grid place-items-center h-7 w-7 rounded-lg text-foreground/50 hover:text-foreground hover:bg-[var(--nav-pill-active)]"
                aria-label="Tutup menu"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Mobile: show section dropdown at top of sidebar */}
            {mobileOpen && (
              <div className="md:hidden p-2 border-b border-[var(--glass-border)]">
                <select
                  value={activeSection?.label || ''}
                  onChange={e => handleSectionPillClick(e.target.value)}
                  className="w-full h-9 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-xs text-foreground"
                  data-testid="mobile-section-select"
                >
                  {nav.sections.map(s => (
                    <option key={s.label} value={s.label}>{formatSectionLabel(s.label)}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Items (flat list) of active section */}
            <nav className="flex-1 overflow-y-auto py-2 px-2" data-testid="sidebar-items">
              <div className="space-y-0.5">
                {(activeSection?.items || []).map(item => {
                  const Icon = item.icon;
                  const isActive = currentModule === item.id;
                  // External link (e.g. TV Mode)
                  if (item.external && item.href) {
                    if (collapsed) {
                      return (
                        <a
                          key={item.id}
                          href={item.href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="relative w-full grid place-items-center h-10 rounded-xl transition-colors duration-150 text-foreground/60 hover:bg-[var(--glass-bg-hover)] hover:text-foreground"
                          title={item.label}
                          data-testid={`nav-item-${item.id}`}
                        >
                          <Icon className="w-4 h-4" />
                        </a>
                      );
                    }
                    return (
                      <a
                        key={item.id}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="relative w-full flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-[background-color,color] duration-150 text-foreground/60 hover:bg-[var(--glass-bg-hover)] hover:text-foreground/85"
                        data-testid={`nav-item-${item.id}`}
                      >
                        <Icon className="w-4 h-4 shrink-0" strokeWidth={2} />
                        <span className="truncate">{item.label}</span>
                      </a>
                    );
                  }
                  if (collapsed) {
                    return (
                      <button
                        key={item.id}
                        onClick={() => { onModuleChange(item.id); setMobileOpen(false); }}
                        className={`relative w-full grid place-items-center h-10 rounded-xl transition-colors duration-150
                          ${isActive ? 'bg-[var(--nav-pill-active)] text-[hsl(var(--primary))]' : 'text-foreground/60 hover:bg-[var(--glass-bg-hover)] hover:text-foreground'}`}
                        title={item.label}
                        data-testid={`nav-item-${item.id}`}
                      >
                        {isActive && <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-[hsl(var(--primary))]" />}
                        <Icon className="w-4 h-4" />
                      </button>
                    );
                  }
                  return (
                    <button
                      key={item.id}
                      onClick={() => { onModuleChange(item.id); setMobileOpen(false); }}
                      className={`relative w-full flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm
                        transition-[background-color,color] duration-150 ease-[cubic-bezier(0.16,1,0.3,1)]
                        ${isActive
                          ? 'bg-[var(--nav-pill-active)] text-foreground'
                          : 'text-foreground/60 hover:bg-[var(--glass-bg-hover)] hover:text-foreground/85'
                        }`}
                      data-testid={`nav-item-${item.id}`}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-[hsl(var(--primary))]" aria-hidden="true" />
                      )}
                      <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[hsl(var(--primary))]' : ''}`} strokeWidth={2} />
                      <span className="truncate">{item.label}</span>
                    </button>
                  );
                })}
                {(!activeSection?.items || activeSection.items.length === 0) && (
                  <div className="px-3 py-6 text-center text-xs text-foreground/40">Belum ada item di menu ini.</div>
                )}
              </div>
            </nav>

            {/* Sidebar footer: breadcrumb */}
            {!collapsed && (
              <div className="px-3 py-2 border-t border-[var(--glass-border)]">
                <p className="text-[10px] text-foreground/40 truncate" data-testid="topbar-module-title">
                  {findModuleLabel(portal, currentModule)}
                </p>
              </div>
            )}
          </div>
        </aside>

        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            className="fixed inset-0 bg-[var(--overlay-bg)] z-20 md:hidden"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-[1400px] mx-auto p-4 sm:p-6">
            {children}
          </div>
        </main>
      </div>

      {/* ── Command Palette (Cmd+K) ─────────────────────────────────────── */}
      <CommandPalette
        open={cmdkOpen}
        onOpenChange={setCmdkOpen}
        currentPortal={portal}
        onSelectPortal={(pid) => { onPortalChange?.(pid); }}
        onSelectModule={(mid) => { onModuleChange?.(mid); }}
        onLogout={onLogout}
        moduleSuggestions={moduleSuggestions}
      />
    </div>
  );
}

/* ── helper: tampilkan label section lebih enak dibaca (ALL CAPS → Title Case) ── */
function formatSectionLabel(label) {
  if (!label) return '';
  return label
    .toLowerCase()
    .split(' ')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}
