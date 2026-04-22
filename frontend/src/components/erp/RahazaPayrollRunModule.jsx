import { useState, useEffect, useCallback } from 'react';
import { Plus, RefreshCw, Download, CheckCircle2, Trash2, FileText, Eye, Lock, Calendar, DollarSign } from 'lucide-react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import { PageHeader, StatusBadge, EmptyState } from './moduleAtoms';

const fmtIDR = (n) => `Rp ${Number(n || 0).toLocaleString('id-ID')}`;
const fmtDate = (s) => s || '—';

export default function RahazaPayrollRunModule({ token }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState(null);
  const [error, setError] = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/rahaza/payroll-runs', { headers });
      if (r.ok) setRuns(await r.json());
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { fetchRuns(); }, [fetchRuns]);

  const createRun = async (payload) => {
    setError('');
    const r = await fetch('/api/rahaza/payroll-runs', { method: 'POST', headers, body: JSON.stringify(payload) });
    if (!r.ok) {
      const STATUS_MSG = { 400: 'Data tidak valid atau tidak ada profile aktif.', 403: 'Tidak ada akses.' };
      setError(STATUS_MSG[r.status] || `Gagal buat run (HTTP ${r.status})`);
      return;
    }
    setCreating(false); fetchRuns();
  };

  const finalizeRun = async (id) => {
    if (!window.confirm('Finalize run? Setelah finalize, deductions tidak bisa diubah lagi.')) return;
    const r = await fetch(`/api/rahaza/payroll-runs/${id}/finalize`, { method: 'POST', headers });
    if (r.ok) { fetchRuns(); if (viewing?.run?.id === id) openRun(id); } else setError(`Gagal finalize (HTTP ${r.status})`);
  };

  const delRun = async (id) => {
    if (!window.confirm('Hapus run ini? (hanya bisa jika masih draft)')) return;
    const r = await fetch(`/api/rahaza/payroll-runs/${id}`, { method: 'DELETE', headers });
    if (r.ok) fetchRuns(); else setError(`Gagal hapus (HTTP ${r.status})`);
  };

  const exportCsv = (id) => {
    window.open(`/api/rahaza/payroll-runs/${id}/export`, '_blank');
  };

  const openRun = async (id) => {
    const r = await fetch(`/api/rahaza/payroll-runs/${id}`, { headers });
    if (r.ok) setViewing(await r.json());
  };

  const statusMeta = null; // replaced by StatusBadge atom

  return (
    <div className="space-y-5" data-testid="rahaza-payroll-run-page">
      <PageHeader
        icon={DollarSign}
        eyebrow="Portal HR · Payroll"
        title="Payroll Run"
        subtitle="Jalankan payroll per periode. Engine otomatis hitung slip dari output produksi + attendance sesuai profile pegawai."
        actions={
          <>
            <Button variant="ghost" onClick={fetchRuns} className="h-9 border border-[var(--glass-border)]" data-testid="pr-refresh"><RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh</Button>
            <Button onClick={() => setCreating(true)} className="h-9" data-testid="pr-create"><Plus className="w-3.5 h-3.5 mr-1.5" /> Run Baru</Button>
          </>
        }
      />

      {error && <div className="bg-[hsl(var(--destructive)/0.12)] border border-[hsl(var(--destructive)/0.22)] rounded-lg p-3 text-sm text-[hsl(var(--destructive))]">{error}</div>}

      {loading ? (
        <div className="flex items-center justify-center h-48"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" /></div>
      ) : (
        <GlassCard className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--glass-bg)]">
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="px-4 py-3">Run #</th>
                  <th className="px-3 py-3">Periode</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3 text-right">Karyawan</th>
                  <th className="px-3 py-3 text-right">Gross</th>
                  <th className="px-3 py-3 text-right">Deductions</th>
                  <th className="px-3 py-3 text-right">Net</th>
                  <th className="px-3 py-3 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {runs.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-12 text-muted-foreground">Belum ada payroll run. Tekan “Run Baru” untuk membuat.</td></tr>
                ) : runs.map(r => {
                  return (
                    <tr key={r.id} className="border-t border-[var(--glass-border)] hover:bg-[var(--glass-bg-hover)] transition-colors" data-testid={`pr-row-${r.run_number}`}>
                      <td className="px-4 py-2 font-mono text-xs text-foreground">{r.run_number}</td>
                      <td className="px-3 py-2 text-xs text-foreground">{fmtDate(r.period_from)} → {fmtDate(r.period_to)}</td>
                      <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                      <td className="px-3 py-2 text-right text-foreground">{r.total_employees}</td>
                      <td className="px-3 py-2 text-right font-mono text-foreground">{fmtIDR(r.total_gross)}</td>
                      <td className="px-3 py-2 text-right font-mono text-red-300">{fmtIDR(r.total_deductions)}</td>
                      <td className="px-3 py-2 text-right font-mono text-emerald-300 font-semibold">{fmtIDR(r.total_net)}</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button onClick={() => openRun(r.id)} className="text-xs text-primary hover:underline mr-2" data-testid={`pr-view-${r.run_number}`}><Eye className="w-3 h-3 inline" /></button>
                        <button onClick={() => exportCsv(r.id)} className="text-xs text-primary hover:underline mr-2"><Download className="w-3 h-3 inline" /></button>
                        {r.status === 'draft' && <>
                          <button onClick={() => finalizeRun(r.id)} className="text-xs text-emerald-300 hover:underline mr-2" data-testid={`pr-finalize-${r.run_number}`}><Lock className="w-3 h-3 inline" /></button>
                          <button onClick={() => delRun(r.id)} className="text-xs text-red-300 hover:underline"><Trash2 className="w-3 h-3 inline" /></button>
                        </>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {creating && <CreateRunModal onClose={() => setCreating(false)} onCreate={createRun} />}
      {viewing && <RunDetailModal data={viewing} token={token} onClose={() => setViewing(null)} onRefresh={() => openRun(viewing.run.id)} />}
    </div>
  );
}

function CreateRunModal({ onClose, onCreate }) {
  const today = new Date().toISOString().split('T')[0];
  const firstDay = today.slice(0, 7) + '-01';
  const [from, setFrom] = useState(firstDay);
  const [to, setTo] = useState(today);
  const [notes, setNotes] = useState('');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <GlassCard className="p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-foreground mb-4">Buat Payroll Run Baru</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground uppercase block mb-1">Periode Dari</label>
            <GlassInput type="date" value={from} onChange={e => setFrom(e.target.value)} data-testid="pr-create-from" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground uppercase block mb-1">Periode Sampai</label>
            <GlassInput type="date" value={to} onChange={e => setTo(e.target.value)} data-testid="pr-create-to" />
          </div>
          <div>
            <label className="text-xs text-muted-foreground uppercase block mb-1">Catatan</label>
            <GlassInput value={notes} onChange={e => setNotes(e.target.value)} placeholder="Opsional" />
          </div>
          <div className="bg-primary/10 border border-primary/20 rounded-lg p-3 text-xs text-foreground/80">
            <Calendar className="w-3.5 h-3.5 inline-block mr-1" />
            Run akan otomatis hitung slip untuk semua karyawan dengan profile payroll aktif.
          </div>
        </div>
        <div className="flex gap-2 mt-6 justify-end">
          <Button variant="ghost" onClick={onClose} className="border border-[var(--glass-border)]">Batal</Button>
          <Button onClick={() => onCreate({ period_from: from, period_to: to, notes })} data-testid="pr-create-submit">Buat Run</Button>
        </div>
      </GlassCard>
    </div>
  );
}

function RunDetailModal({ data, token, onClose, onRefresh }) {
  const [editing, setEditing] = useState(null);
  const run = data.run; const payslips = data.payslips || [];
  const locked = run.status !== 'draft';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <GlassCard className="p-6 max-w-5xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-xl font-bold text-foreground">{run.run_number}</h2>
            <p className="text-xs text-muted-foreground">{run.period_from} → {run.period_to} · Status: <span className={run.status === 'finalized' ? 'text-emerald-300' : 'text-amber-300'}>{run.status}</span></p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-2xl leading-none">×</button>
        </div>

        <div className="grid grid-cols-3 gap-2 mb-4">
          <GlassPanel className="px-3 py-2"><div className="text-[10px] uppercase text-muted-foreground">Total Gross</div><div className="text-lg font-bold text-foreground">{fmtIDR(run.total_gross)}</div></GlassPanel>
          <GlassPanel className="px-3 py-2"><div className="text-[10px] uppercase text-muted-foreground">Potongan</div><div className="text-lg font-bold text-red-300">{fmtIDR(run.total_deductions)}</div></GlassPanel>
          <GlassPanel className="px-3 py-2"><div className="text-[10px] uppercase text-muted-foreground">Net</div><div className="text-lg font-bold text-emerald-300">{fmtIDR(run.total_net)}</div></GlassPanel>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-[var(--glass-bg)]">
            <tr className="text-left text-xs text-muted-foreground">
              <th className="px-3 py-2">Karyawan</th>
              <th className="px-3 py-2">Skema</th>
              <th className="px-3 py-2 text-right">Earnings</th>
              <th className="px-3 py-2 text-right">Overtime</th>
              <th className="px-3 py-2 text-right">Gross</th>
              <th className="px-3 py-2 text-right">Potongan</th>
              <th className="px-3 py-2 text-right">Net</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {payslips.map(s => (
              <tr key={s.id} className="border-t border-[var(--glass-border)]" data-testid={`ps-row-${s.employee_code}`}>
                <td className="px-3 py-2">
                  <div className="font-mono text-xs">{s.employee_code}</div>
                  <div className="text-xs text-muted-foreground">{s.employee_name}</div>
                </td>
                <td className="px-3 py-2 text-xs">{s.pay_scheme}</td>
                <td className="px-3 py-2 text-right font-mono text-xs">{fmtIDR(s.earnings_total)}</td>
                <td className="px-3 py-2 text-right font-mono text-xs">{fmtIDR(s.overtime_amount)}</td>
                <td className="px-3 py-2 text-right font-mono text-xs text-foreground">{fmtIDR(s.gross_pay)}</td>
                <td className="px-3 py-2 text-right font-mono text-xs text-red-300">{fmtIDR(s.deductions_total)}</td>
                <td className="px-3 py-2 text-right font-mono text-xs text-emerald-300 font-semibold">{fmtIDR(s.net_pay)}</td>
                <td className="px-3 py-2 text-right">
                  <button onClick={() => setEditing(s)} className="text-xs text-primary hover:underline" data-testid={`ps-view-${s.employee_code}`}><FileText className="w-3 h-3 inline" /> Detail</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {editing && <PayslipEditor slip={editing} token={token} locked={locked} onClose={() => { setEditing(null); onRefresh(); }} />}
      </GlassCard>
    </div>
  );
}

function PayslipEditor({ slip, token, locked, onClose }) {
  const [deductions, setDeductions] = useState(slip.deductions || []);
  const [notes, setNotes] = useState(slip.notes || '');
  const [saving, setSaving] = useState(false);

  const addDed = () => setDeductions(d => [...d, { label: '', amount: 0 }]);
  const updDed = (i, k, v) => setDeductions(d => d.map((r, idx) => idx === i ? { ...r, [k]: v } : r));
  const rmDed = (i) => setDeductions(d => d.filter((_, idx) => idx !== i));

  const save = async () => {
    setSaving(true);
    try {
      const r = await fetch(`/api/rahaza/payslips/${slip.id}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ deductions: deductions.filter(d => d.label && Number(d.amount) > 0), notes }),
      });
      if (r.ok) onClose();
    } finally { setSaving(false); }
  };

  const dedTotal = deductions.reduce((s, d) => s + (Number(d.amount) || 0), 0);
  const net = Math.max(0, (slip.gross_pay || 0) - dedTotal);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={onClose}>
      <GlassCard className="p-6 max-w-2xl w-full max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="mb-4">
          <h3 className="text-lg font-bold text-foreground">Slip: {slip.employee_code} · {slip.employee_name}</h3>
          <p className="text-xs text-muted-foreground">{slip.pay_scheme} · {slip.period_from} → {slip.period_to}</p>
        </div>

        <div className="space-y-3">
          <div>
            <div className="text-xs uppercase text-muted-foreground mb-1">Earnings</div>
            <div className="bg-[var(--glass-bg)] border border-[var(--glass-border)] rounded-lg p-3 space-y-1">
              {(slip.earnings || []).map((e, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-foreground">{e.label} · {e.qty} {e.unit} × {fmtIDR(e.rate)}</span>
                  <span className="font-mono text-foreground">{fmtIDR(e.amount)}</span>
                </div>
              ))}
              <div className="flex items-center justify-between text-xs font-semibold border-t border-[var(--glass-border)] pt-1 mt-1">
                <span className="text-muted-foreground">Subtotal earnings</span>
                <span className="font-mono text-foreground">{fmtIDR(slip.earnings_total)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Overtime {slip.overtime_hours} jam × {fmtIDR(slip.overtime_rate)}</span>
                <span className="font-mono text-foreground">{fmtIDR(slip.overtime_amount)}</span>
              </div>
              <div className="flex items-center justify-between text-sm font-semibold border-t border-[var(--glass-border)] pt-2 mt-1">
                <span className="text-foreground">Gross Pay</span>
                <span className="font-mono text-foreground">{fmtIDR(slip.gross_pay)}</span>
              </div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="text-xs uppercase text-muted-foreground">Deductions {locked && <span className="text-amber-300">(locked — finalized)</span>}</div>
              {!locked && <Button variant="ghost" className="h-7 px-2 text-xs border border-[var(--glass-border)]" onClick={addDed}><Plus className="w-3 h-3 mr-1" />Tambah</Button>}
            </div>
            <div className="space-y-2">
              {deductions.length === 0 && <div className="text-xs text-muted-foreground">Tidak ada potongan.</div>}
              {deductions.map((d, i) => (
                <div key={i} className="flex items-center gap-2">
                  <GlassInput placeholder="Label (cth: PPh21, BPJS, Kasbon)" value={d.label} onChange={e => updDed(i, 'label', e.target.value)} disabled={locked} className="flex-1 h-9 text-xs" data-testid={`ps-ded-label-${i}`} />
                  <GlassInput type="number" min={0} step="1000" placeholder="Amount" value={d.amount} onChange={e => updDed(i, 'amount', e.target.value)} disabled={locked} className="w-32 h-9 text-xs text-right" data-testid={`ps-ded-amount-${i}`} />
                  {!locked && <button onClick={() => rmDed(i)} className="h-9 w-9 text-red-300 hover:bg-red-400/10 rounded border border-[var(--glass-border)]"><Trash2 className="w-3.5 h-3.5 mx-auto" /></button>}
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs text-muted-foreground uppercase block mb-1">Catatan</label>
            <GlassInput value={notes} onChange={e => setNotes(e.target.value)} disabled={locked} placeholder="Opsional" />
          </div>

          <div className="bg-primary/10 border border-primary/20 rounded-lg p-3 flex items-center justify-between">
            <span className="text-sm font-semibold text-foreground">Net Pay</span>
            <span className="text-lg font-bold text-emerald-300 font-mono">{fmtIDR(net)}</span>
          </div>
        </div>

        <div className="flex gap-2 mt-6 justify-end">
          <Button variant="ghost" onClick={onClose} className="border border-[var(--glass-border)]">Tutup</Button>
          {!locked && <Button onClick={save} disabled={saving} data-testid="ps-save"><CheckCircle2 className="w-4 h-4 mr-1.5" />{saving ? 'Menyimpan...' : 'Simpan Potongan'}</Button>}
        </div>
      </GlassCard>
    </div>
  );
}
