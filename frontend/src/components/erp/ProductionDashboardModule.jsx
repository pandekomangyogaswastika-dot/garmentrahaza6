/**
 * Dashboard Produksi (WIP) — Tahap 2 Modernized.
 * WIP per proses real-time dengan heatmap intensity + bottleneck detection.
 * Phase 16: integrasi NextActionWidget & SetupWizard (guided operations).
 */
import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Factory, Activity, AlertTriangle, Layers, LayoutGrid } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  StatCard, ChartCard, HeroCrystalCard,
} from './dashboardAtoms';
import NextActionWidget from './NextActionWidget';
import SetupWizard from './SetupWizard';

const fmtNum = (v) => Number(v || 0).toLocaleString('id-ID');

export default function ProductionDashboardModule({ token, onNavigate }) {
  const [summary, setSummary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState('');
  const [wizardOpen, setWizardOpen] = useState(false);
  const [naeNonce, setNaeNonce] = useState(0);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/rahaza/wip/summary', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setSummary(data.processes || []);
        setUpdatedAt(new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }));
      }
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchSummary(); }, [fetchSummary]);
  useEffect(() => { const t = setInterval(fetchSummary, 15000); return () => clearInterval(t); }, [fetchSummary]);

  // Auto-detect wizard needed on first mount
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await fetch('/api/rahaza/setup/status', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (mounted && data.needs_wizard) setWizardOpen(true);
      } catch (e) { /* silent */ }
    })();
    return () => { mounted = false; };
  }, [token]);

  const wipValues = summary.map(s => s.wip_qty);
  const maxWip = Math.max(0, ...wipValues);
  const bottleneck = maxWip > 0 ? summary.find(s => s.wip_qty === maxWip) : null;
  const totalOutput = summary.reduce((a, s) => a + s.total_output, 0);
  const totalWip = summary.reduce((a, s) => a + s.wip_qty, 0);
  const totalFlow = totalOutput + totalWip;
  const efficiency = totalFlow > 0 ? Math.round((totalOutput / totalFlow) * 100) : 0;

  return (
    <div className="space-y-5" data-testid="production-dashboard">
      <HeroCrystalCard
        testId="prod-hero"
        eyebrow="Portal Produksi"
        title="Dashboard WIP Real-time"
        description="Monitoring Work-In-Progress per proses (Rajut → Linking → Sewing → QC → Steam → Packing). Auto-refresh 15 detik."
      >
        <div className="flex items-center gap-3">
          <Button onClick={fetchSummary} className="h-9 bg-[hsl(var(--primary))] hover:brightness-110" data-testid="prod-dash-refresh">
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            {loading ? 'Memuat...' : 'Refresh'}
          </Button>
          {updatedAt && <span className="text-xs text-foreground/50">Diperbarui: {updatedAt}</span>}
        </div>
      </HeroCrystalCard>

      {/* Phase 16: Next-Action Widget (guided operations) */}
      <NextActionWidget
        key={naeNonce}
        token={token}
        portal="production"
        onNavigate={(moduleId) => onNavigate && onNavigate(moduleId)}
        onOpenSetupWizard={() => setWizardOpen(true)}
        maxCards={5}
      />

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard testId="kpi-total-output" icon={Factory} label="Total Output"
          value={fmtNum(totalOutput)} sub="pcs tercatat semua proses" accent="success" />
        <StatCard testId="kpi-total-wip" icon={Layers} label="Total WIP"
          value={fmtNum(totalWip)} sub="pcs masih dalam proses" accent="primary" />
        <StatCard testId="kpi-efficiency" icon={Activity} label="Flow Efficiency"
          value={`${efficiency}%`} sub={`${fmtNum(totalOutput)} / ${fmtNum(totalFlow)}`}
          accent={efficiency >= 70 ? 'success' : 'warning'} />
        <StatCard testId="kpi-bottleneck" icon={AlertTriangle} label="Bottleneck"
          value={bottleneck ? bottleneck.process_code : 'Tidak ada'}
          sub={bottleneck ? `WIP ${fmtNum(bottleneck.wip_qty)} pcs` : 'WIP seimbang'}
          accent={bottleneck ? 'warning' : 'success'}
          onClick={onNavigate ? () => onNavigate('production-line-board') : undefined}
        />
      </div>

      {/* WIP Flow Diagram */}
      <ChartCard
        title="WIP per Proses (alur Rajut → Packing)"
        subtitle="Bar-strip menunjukkan proporsi WIP vs total per proses. Warna lebih terang = WIP lebih tinggi (bottleneck indicator)."
        actions={
          <Button
            variant="ghost"
            onClick={() => onNavigate && onNavigate('production-line-board')}
            className="h-8 text-xs border border-[var(--glass-border)]"
            data-testid="prod-line-board-cta"
          >
            <LayoutGrid className="w-3.5 h-3.5 mr-1.5" />
            Buka Line Board
          </Button>
        }
      >
        {summary.length === 0 ? (
          <div className="text-center py-10 text-foreground/40 text-sm">
            {loading ? 'Memuat data...' : 'Belum ada event produksi yang tercatat.'}
          </div>
        ) : (
          <div className="space-y-3">
            {summary.map((p, i) => {
              const total = p.total_output + p.wip_qty;
              const outPct = total > 0 ? (p.total_output / total) * 100 : 0;
              const wipPct = total > 0 ? (p.wip_qty / total) * 100 : 0;
              const isBottleneck = bottleneck && bottleneck.process_code === p.process_code && p.wip_qty > 0;
              const intensity = maxWip > 0 ? (p.wip_qty / maxWip) : 0;
              return (
                <div key={p.process_code || i} data-testid={`wip-row-${p.process_code}`}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-foreground/40 font-mono w-5">#{i + 1}</span>
                      <span className="font-semibold text-foreground">{p.process_code}</span>
                      {isBottleneck && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-[hsl(var(--warning)/0.15)] text-[hsl(var(--warning))] border border-[hsl(var(--warning)/0.25)]">
                          <AlertTriangle className="w-2.5 h-2.5" /> Bottleneck
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 tabular-nums">
                      <span className="text-foreground/60">WIP <span className="font-bold text-foreground">{fmtNum(p.wip_qty)}</span></span>
                      <span className="text-foreground/60">Output <span className="font-bold text-foreground">{fmtNum(p.total_output)}</span></span>
                    </div>
                  </div>
                  {/* Stacked bar: output (success) + wip (primary w/ intensity) */}
                  <div className="h-2.5 rounded-full overflow-hidden bg-[var(--glass-bg)] flex">
                    <div
                      className="h-full bg-[hsl(var(--success))] transition-[width] duration-500"
                      style={{ width: `${outPct}%` }}
                      title={`Output: ${p.total_output}`}
                    />
                    <div
                      className="h-full transition-[width,background-color] duration-500"
                      style={{
                        width: `${wipPct}%`,
                        background: isBottleneck
                          ? `hsl(var(--warning))`
                          : `hsl(var(--primary) / ${0.4 + intensity * 0.6})`,
                      }}
                      title={`WIP: ${p.wip_qty}`}
                    />
                  </div>
                </div>
              );
            })}
            {/* Legend */}
            <div className="flex items-center gap-4 pt-2 mt-2 border-t border-[var(--glass-border)] text-[10px] text-foreground/50">
              <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[hsl(var(--success))]" />Output selesai</div>
              <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[hsl(var(--primary))]" />WIP normal</div>
              <div className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[hsl(var(--warning))]" />WIP bottleneck</div>
            </div>
          </div>
        )}
      </ChartCard>

      {/* Phase 16: Setup Wizard modal */}
      <SetupWizard
        open={wizardOpen}
        token={token}
        onClose={() => setWizardOpen(false)}
        onNavigate={(moduleId) => onNavigate && onNavigate(moduleId)}
        onComplete={() => { setNaeNonce((n) => n + 1); fetchSummary(); }}
      />
    </div>
  );
}
