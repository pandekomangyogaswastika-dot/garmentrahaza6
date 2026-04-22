import { Factory, LayoutGrid, Wrench, Timer, Users, ListChecks, ArrowRight } from 'lucide-react';
import { GlassCard, GlassPanel } from '@/components/ui/glass';

const PHASES = [
  { id: 3, label: 'Fase 3', title: 'Master Data Rajut', items: ['Gedung & Zona', 'Proses produksi (8 proses)', 'Shift (konfigurabel)', 'Mesin Rajut', 'Line Produksi', 'Karyawan & Operator'], status: 'done' },
  { id: 4, label: 'Fase 4', title: 'Line Board + WIP Real-time', items: ['Line Board per proses & gedung', 'WIP ledger (event-based)', 'Realtime broadcast via WebSocket'], status: 'next' },
  { id: 6, label: 'Fase 6', title: 'Eksekusi Proses Produksi', items: ['Rajut · Linking · Sewing', 'QC (branching rework)', 'Washer · Sontek · Steam · Packing', 'Operator View (mobile) di /operator'], status: 'upcoming' },
];

export default function ProductionDashboardPlaceholder() {
  return (
    <div className="space-y-6" data-testid="production-dashboard-placeholder">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[hsl(var(--primary))] uppercase tracking-wider mb-2">
            <Factory className="w-4 h-4" /> Portal Produksi
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Dashboard Produksi</h1>
          <p className="text-foreground/60 text-sm max-w-2xl">
            Portal ini akan menampung seluruh alur produksi rajut PT Rahaza:
            <span className="text-foreground font-medium"> Rajut → Linking → Sewing → QC → Steam → Packing </span>
            (+ rework: QC → Washer → Sontek → QC → Steam → Packing).
          </p>
        </div>
        <GlassPanel className="px-4 py-3">
          <div className="text-xs text-foreground/50">Status Portal</div>
          <div className="text-sm font-semibold text-amber-300">Kerangka siap · Modul dibangun bertahap</div>
        </GlassPanel>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PHASES.map(p => (
          <GlassCard key={p.id} className="p-5" data-testid={`phase-card-${p.id}`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-full ${
                p.status === 'done'
                  ? 'text-emerald-300 bg-emerald-400/15'
                  : p.status === 'next'
                    ? 'text-amber-300 bg-amber-400/15'
                    : 'text-[hsl(var(--primary))] bg-[hsl(var(--primary))]/15'
              }`}>{p.label}{p.status === 'done' ? ' · SELESAI' : p.status === 'next' ? ' · BERIKUTNYA' : ''}</span>
              <ArrowRight className="w-3.5 h-3.5 text-foreground/30" />
            </div>
            <h3 className="text-base font-semibold text-foreground mb-3">{p.title}</h3>
            <ul className="space-y-1.5">
              {p.items.map(it => (
                <li key={it} className="text-sm text-foreground/70 flex items-start gap-2">
                  <span className={`w-1 h-1 rounded-full mt-2 flex-shrink-0 ${p.status === 'done' ? 'bg-emerald-400' : 'bg-[hsl(var(--primary))]'}`} />
                  <span>{it}</span>
                </li>
              ))}
            </ul>
          </GlassCard>
        ))}
      </div>

      <GlassPanel className="p-5" data-testid="production-roadmap-panel">
        <div className="flex items-center gap-2 mb-3">
          <ListChecks className="w-4 h-4 text-[hsl(var(--primary))]" />
          <h4 className="text-sm font-semibold text-foreground">Komponen yang akan tersedia di portal ini</h4>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            { icon: LayoutGrid, label: 'Line Board' },
            { icon: Wrench, label: 'Mesin Rajut' },
            { icon: Timer, label: 'Shift & Jam Kerja' },
            { icon: Users, label: 'Assign Operator' },
          ].map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-2 text-foreground/70">
              <Icon className="w-4 h-4 text-foreground/40" />
              <span>{label}</span>
            </div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
