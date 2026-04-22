import { useState, useEffect, useCallback } from 'react';
import { Calculator, RefreshCw, Save, Package, Users, Layers, TrendingUp } from 'lucide-react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import { PageHeader } from './moduleAtoms';

const fmt = (n) => `Rp ${Number(n || 0).toLocaleString('id-ID')}`;

export default function RahazaHPPModule({ token }) {
  const [settings, setSettings] = useState(null);
  const [wos, setWos] = useState([]);
  const [selected, setSelected] = useState(null);
  const [hpp, setHpp] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [loading, setLoading] = useState(true);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [cs, ws] = await Promise.all([
        fetch('/api/rahaza/costing-settings', { headers }).then(r => r.json()),
        fetch('/api/rahaza/work-orders', { headers }).then(r => r.json()),
      ]);
      setSettings(cs || null);
      setWos(Array.isArray(ws) ? ws : []);
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  useEffect(() => { fetchAll(); }, [fetchAll]);

  const computeHPP = async (wo_id) => {
    const r = await fetch(`/api/rahaza/hpp/work-order/${wo_id}`, { headers });
    if (r.ok) setHpp(await r.json());
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      await fetch('/api/rahaza/costing-settings', { method: 'PUT', headers, body: JSON.stringify(settings) });
      if (selected) computeHPP(selected.id);
    } finally { setSavingSettings(false); }
  };

  const snapshot = async () => {
    if (!selected) return;
    const r = await fetch(`/api/rahaza/hpp/work-order/${selected.id}/snapshot`, { method: 'POST', headers });
    if (r.ok) alert('Snapshot HPP tersimpan.');
  };

  return (
    <div className="space-y-5" data-testid="rahaza-hpp-page">
      <PageHeader
        icon={TrendingUp}
        eyebrow="Portal Finance · Rahaza Finance"
        title="HPP / Costing"
        subtitle="Hitung Harga Pokok Produksi per Work Order: material + labor + overhead. Real-time + snapshot untuk audit."
        actions={
          <Button variant="ghost" onClick={fetchAll} className="h-9 border border-[var(--glass-border)]"><RefreshCw className="w-3.5 h-3.5 mr-1.5" />Refresh</Button>
        }
      />

      {/* Settings */}
      {settings && (
        <GlassCard className="p-4" data-testid="hpp-settings">
          <h3 className="font-semibold text-foreground mb-3"><Calculator className="w-4 h-4 inline mr-1" />Global Costing Settings</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div><label className="text-xs uppercase text-muted-foreground">Overhead/pcs</label><GlassInput type="number" min={0} value={settings.overhead_rate_per_pcs || 0} onChange={e => setSettings(s => ({...s, overhead_rate_per_pcs: Number(e.target.value)}))} data-testid="hpp-overhead-pcs" /></div>
            <div><label className="text-xs uppercase text-muted-foreground">Default Yarn/kg</label><GlassInput type="number" min={0} value={settings.default_yarn_cost_per_kg || 0} onChange={e => setSettings(s => ({...s, default_yarn_cost_per_kg: Number(e.target.value)}))} data-testid="hpp-yarn-kg" /></div>
            <div><label className="text-xs uppercase text-muted-foreground">Default Accessory/unit</label><GlassInput type="number" min={0} value={settings.default_accessory_cost_per_unit || 0} onChange={e => setSettings(s => ({...s, default_accessory_cost_per_unit: Number(e.target.value)}))} /></div>
            <div><label className="text-xs uppercase text-muted-foreground">Labor Fallback/pcs</label><GlassInput type="number" min={0} value={settings.labor_rate_fallback_per_pcs || 0} onChange={e => setSettings(s => ({...s, labor_rate_fallback_per_pcs: Number(e.target.value)}))} /></div>
          </div>
          <div className="flex justify-end mt-3"><Button onClick={saveSettings} disabled={savingSettings} data-testid="hpp-save-settings"><Save className="w-4 h-4 mr-1.5" />{savingSettings ? 'Menyimpan...' : 'Simpan Settings'}</Button></div>
        </GlassCard>
      )}

      {/* WO list */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard className="p-0 lg:col-span-1 overflow-hidden">
          <div className="p-3 border-b border-[var(--glass-border)] text-sm font-semibold text-foreground">Work Orders</div>
          <div className="max-h-[500px] overflow-y-auto">
            {wos.length === 0 ? <div className="p-6 text-center text-muted-foreground text-xs">Belum ada work order.</div> : wos.map(w => (
              <button key={w.id} onClick={() => { setSelected(w); computeHPP(w.id); }} className={`w-full text-left p-3 border-b border-[var(--glass-border)] hover:bg-[var(--glass-bg-hover)] ${selected?.id === w.id ? 'bg-[var(--glass-bg-hover)]' : ''}`} data-testid={`hpp-wo-${w.wo_number}`}>
                <div className="font-mono text-xs text-foreground">{w.wo_number}</div>
                <div className="text-xs text-muted-foreground">{w.model_code} · {w.size_code} · {w.qty} pcs · <span className="text-primary">{w.status}</span></div>
              </button>
            ))}
          </div>
        </GlassCard>

        <div className="lg:col-span-2">
          {!hpp ? (
            <GlassCard className="p-8 text-center text-muted-foreground">Pilih Work Order untuk hitung HPP</GlassCard>
          ) : (
            <div className="space-y-3" data-testid="hpp-detail">
              <GlassCard className="p-4">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-foreground">{hpp.wo_number}</h3>
                    <p className="text-xs text-muted-foreground">{hpp.model_code} · {hpp.size_code} · qty {hpp.qty} pcs</p>
                  </div>
                  <Button onClick={snapshot} className="h-9" data-testid="hpp-snapshot"><Save className="w-4 h-4 mr-1.5" />Snapshot</Button>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <GlassPanel className="px-3 py-2"><div className="text-[10px] uppercase text-muted-foreground"><Package className="w-3 h-3 inline" /> Material</div><div className="text-lg font-bold text-foreground">{fmt(hpp.material_cost)}</div></GlassPanel>
                  <GlassPanel className="px-3 py-2"><div className="text-[10px] uppercase text-muted-foreground"><Users className="w-3 h-3 inline" /> Labor</div><div className="text-lg font-bold text-foreground">{fmt(hpp.labor_cost)}</div></GlassPanel>
                  <GlassPanel className="px-3 py-2"><div className="text-[10px] uppercase text-muted-foreground"><Layers className="w-3 h-3 inline" /> Overhead</div><div className="text-lg font-bold text-foreground">{fmt(hpp.overhead_cost)}</div></GlassPanel>
                  <GlassPanel className="px-3 py-2 bg-primary/10 border-primary/30"><div className="text-[10px] uppercase text-primary">HPP / Unit</div><div className="text-lg font-bold text-primary">{fmt(hpp.hpp_unit)}</div></GlassPanel>
                </div>
                <div className="mt-3 pt-3 border-t border-[var(--glass-border)] flex justify-between items-center"><span className="text-sm font-semibold text-foreground">Total Biaya</span><span className="text-xl font-bold text-foreground font-mono">{fmt(hpp.total_cost)}</span></div>
              </GlassCard>

              <GlassCard className="p-4">
                <h4 className="font-semibold text-foreground mb-2">Breakdown Material ({hpp.material_breakdown?.length || 0})</h4>
                {(!hpp.material_breakdown || hpp.material_breakdown.length === 0) ? <div className="text-xs text-muted-foreground">Belum ada material issue untuk WO ini.</div> : (
                  <table className="w-full text-xs"><thead><tr className="text-left text-muted-foreground"><th>Material</th><th>Tipe</th><th className="text-right">Qty</th><th className="text-right">Unit Cost</th><th className="text-right">Amount</th></tr></thead><tbody>{hpp.material_breakdown.map((m, i) => (<tr key={i} className="border-t border-[var(--glass-border)]"><td className="py-1">{m.material_name}</td><td className="py-1 text-muted-foreground">{m.type}</td><td className="py-1 text-right font-mono">{m.qty} {m.unit}</td><td className="py-1 text-right font-mono">{fmt(m.unit_cost)}</td><td className="py-1 text-right font-mono">{fmt(m.amount)}</td></tr>))}</tbody></table>
                )}
              </GlassCard>

              <GlassCard className="p-4">
                <h4 className="font-semibold text-foreground mb-2">Breakdown Labor ({hpp.labor_breakdown?.length || 0})</h4>
                {(!hpp.labor_breakdown || hpp.labor_breakdown.length === 0) ? <div className="text-xs text-muted-foreground">Belum ada output produksi tagged ke WO ini.</div> : (
                  <table className="w-full text-xs"><thead><tr className="text-left text-muted-foreground"><th>Operator</th><th>Proses</th><th className="text-right">Qty</th><th className="text-right">Rate</th><th className="text-right">Amount</th></tr></thead><tbody>{hpp.labor_breakdown.map((l, i) => (<tr key={i} className="border-t border-[var(--glass-border)]"><td className="py-1">{l.operator_name}</td><td className="py-1 text-muted-foreground">{l.process_code}</td><td className="py-1 text-right font-mono">{l.qty} pcs</td><td className="py-1 text-right font-mono">{fmt(l.rate)}</td><td className="py-1 text-right font-mono">{fmt(l.amount)}</td></tr>))}</tbody></table>
                )}
              </GlassCard>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
