import { UserCog, Wallet, CalendarClock, ClipboardList, ArrowRight } from 'lucide-react';
import { GlassCard, GlassPanel } from '@/components/ui/glass';

const SCHEMES = [
  { title: 'Borongan Hasil', desc: 'Rupiah per pcs · otomatis dari output produksi per operator/line.' },
  { title: 'Borongan Waktu', desc: 'Rupiah per jam · terhubung ke shift & absensi.' },
  { title: 'Gaji Mingguan',  desc: 'Rekap otomatis per minggu berdasar output + jam kerja.' },
  { title: 'Gaji Bulanan',   desc: 'Payroll standar bulanan dengan komponen tambahan.' },
];

export default function HRDashboardPlaceholder() {
  return (
    <div className="space-y-6" data-testid="hr-dashboard-placeholder">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[hsl(var(--primary))] uppercase tracking-wider mb-2">
            <UserCog className="w-4 h-4" /> Portal HR
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Dashboard HR</h1>
          <p className="text-foreground/60 text-sm max-w-2xl">
            Portal HR akan mengelola data karyawan, absensi/shift, dan payroll multi-skema
            yang terhubung langsung dengan output produksi dari portal Produksi.
          </p>
        </div>
        <GlassPanel className="px-4 py-3">
          <div className="text-xs text-foreground/50">Status Portal</div>
          <div className="text-sm font-semibold text-amber-300">Kerangka siap · Modul dibangun di Fase 8</div>
        </GlassPanel>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SCHEMES.map(s => (
          <GlassCard key={s.title} className="p-5">
            <div className="flex items-center gap-2 mb-2">
              <Wallet className="w-4 h-4 text-[hsl(var(--primary))]" />
              <h3 className="text-base font-semibold text-foreground">{s.title}</h3>
            </div>
            <p className="text-sm text-foreground/60 leading-relaxed">{s.desc}</p>
          </GlassCard>
        ))}
      </div>

      <GlassPanel className="p-5">
        <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-[hsl(var(--primary))]" /> Modul yang akan tersedia di portal HR
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm text-foreground/70">
          <div className="flex items-center gap-2"><UserCog className="w-4 h-4 text-foreground/40" /> Master Karyawan</div>
          <div className="flex items-center gap-2"><CalendarClock className="w-4 h-4 text-foreground/40" /> Absensi & Shift</div>
          <div className="flex items-center gap-2"><Wallet className="w-4 h-4 text-foreground/40" /> Payroll Run & Slip</div>
          <div className="flex items-center gap-2"><ArrowRight className="w-4 h-4 text-foreground/40" /> Integrasi Output Produksi</div>
          <div className="flex items-center gap-2"><ArrowRight className="w-4 h-4 text-foreground/40" /> Feeding ke HPP (Finance)</div>
          <div className="flex items-center gap-2"><ArrowRight className="w-4 h-4 text-foreground/40" /> Laporan HR per periode</div>
        </div>
      </GlassPanel>
    </div>
  );
}
