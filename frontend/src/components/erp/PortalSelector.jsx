import { motion } from 'framer-motion';
import { GlassCard, GlassPanel } from '@/components/ui/glass';
import { ThemeToggle } from '@/components/theme/ThemeToggle';
import {
  BarChart3, Factory, Warehouse, Landmark, UserCog,
  Lock, LogOut, ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// Role → Portals mapping. Admin & Owner = full access.
// Supervisor = produksi + gudang. HR = HR portal. Accounting = Finance.
const PORTALS = [
  {
    id: 'management',
    name: 'Portal Management',
    description: 'Dashboard eksekutif, master produk/pelanggan, laporan, dan administrasi sistem.',
    icon: BarChart3,
    roles: ['admin', 'owner'],
  },
  {
    id: 'production',
    name: 'Portal Produksi',
    description: 'Line produksi rajut, WIP real-time, proses Rajut–Packing, dan rework.',
    icon: Factory,
    roles: ['admin', 'owner', 'supervisor'],
  },
  {
    id: 'warehouse',
    name: 'Portal Gudang',
    description: 'Multi-zona (Gedung A/B), receiving, put-away, stok benang/aksesoris/FG, opname.',
    icon: Warehouse,
    roles: ['admin', 'owner', 'supervisor'],
  },
  {
    id: 'finance',
    name: 'Portal Finance',
    description: 'AR/AP, invoice, pembayaran, rekap keuangan, cost center, dan HPP.',
    icon: Landmark,
    roles: ['admin', 'owner', 'accounting'],
  },
  {
    id: 'hr',
    name: 'Portal HR',
    description: 'Karyawan, shift & absensi, payroll multi-skema (borongan pcs/jam, mingguan/bulanan).',
    icon: UserCog,
    roles: ['admin', 'owner', 'hr'],
  },
];

export default function PortalSelector({ user, onSelectPortal, onLogout }) {
  const userRole = (user?.role || '').toLowerCase();

  const canAccess = (portal) => {
    if (['superadmin', 'admin', 'owner'].includes(userRole)) return true;
    return portal.roles.includes(userRole);
  };

  const accessiblePortals = PORTALS.filter(canAccess);

  return (
    <div className="min-h-screen bg-ambient noise-overlay" data-testid="portal-selector-page">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 sm:px-10 py-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[hsl(var(--primary))]/20 border border-[hsl(var(--primary))]/30 flex items-center justify-center">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="hsl(174, 70%, 55%)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20.38 3.46 16 2 12 5.5 8 2 3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/>
            </svg>
          </div>
          <div className="hidden sm:block">
            <div className="text-sm font-semibold text-foreground leading-tight">PT Rahaza Global Indonesia</div>
            <div className="text-xs text-foreground/50 leading-tight">ERP Rajut — Knit Manufacturing System</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle data-testid="portal-theme-toggle-btn" />
          <Button
            variant="ghost"
            onClick={onLogout}
            className="text-foreground/60 hover:text-foreground hover:bg-[var(--glass-bg-hover)] gap-2"
            data-testid="portal-selector-logout-btn"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Keluar</span>
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-5xl mx-auto px-6 sm:px-10 pt-8 pb-20">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground mb-2" data-testid="portal-selector-title">
            Pilih Portal
          </h1>
          <p className="text-foreground/50 text-base mb-10">
            Selamat datang, {user?.name || 'Pengguna'}. Silakan pilih portal sesuai tugas Anda.
          </p>
        </motion.div>

        {/* Portal cards grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 lg:gap-5">
          {PORTALS.map((portal, idx) => {
            const Icon = portal.icon;
            const hasAccess = canAccess(portal);

            return (
              <motion.div
                key={portal.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.05 * idx }}
              >
                <GlassCard
                  hover={hasAccess}
                  className={`p-6 cursor-${hasAccess ? 'pointer' : 'default'} group relative ${
                    !hasAccess ? 'opacity-50' : ''
                  }`}
                  onClick={() => hasAccess && onSelectPortal(portal.id)}
                  data-testid={`portal-selector-${portal.id}-card`}
                >
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                    hasAccess
                      ? 'bg-[hsl(var(--primary))]/15 border border-[hsl(var(--primary))]/25'
                      : 'bg-white/5 border border-white/10'
                  }`}>
                    {hasAccess
                      ? <Icon className="w-5 h-5 text-[hsl(var(--primary))]" />
                      : <Lock className="w-5 h-5 text-foreground/30" />
                    }
                  </div>

                  <h3 className="text-base font-semibold text-foreground mb-1">{portal.name}</h3>
                  <p className="text-sm text-foreground/50 leading-relaxed mb-3">{portal.description}</p>

                  {hasAccess ? (
                    <div className="flex items-center gap-1 text-xs text-[hsl(var(--primary))]/80 font-medium group-hover:text-[hsl(var(--primary))] transition-colors">
                      <span>Masuk</span>
                      <ChevronRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
                    </div>
                  ) : (
                    <span className="inline-flex items-center text-xs font-medium text-foreground/40 bg-white/5 border border-white/10 rounded-full px-2.5 py-0.5">
                      Tidak ada akses
                    </span>
                  )}
                </GlassCard>
              </motion.div>
            );
          })}
        </div>

        {/* Your Access */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-10"
        >
          <GlassPanel className="p-5" data-testid="portal-selector-access-panel">
            <h4 className="text-sm font-semibold text-foreground/80 mb-2">Akses Anda</h4>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-foreground/50">
              <div>
                <span className="text-foreground/40">Role: </span>
                <span className="text-foreground font-medium capitalize" data-testid="access-role">{userRole || '-'}</span>
              </div>
              <div>
                <span className="text-foreground/40">Portal dapat diakses: </span>
                <span className="text-[hsl(var(--primary))] font-medium" data-testid="access-active-count">
                  {accessiblePortals.length} dari {PORTALS.length}
                </span>
              </div>
            </div>
          </GlassPanel>
        </motion.div>
      </div>
    </div>
  );
}
