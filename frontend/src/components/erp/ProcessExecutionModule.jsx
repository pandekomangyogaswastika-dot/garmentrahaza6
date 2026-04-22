import { useState, useEffect, useCallback } from 'react';
import { Factory, Plus, CheckCircle2, XCircle, RefreshCw, AlertTriangle, Clock, RotateCcw } from 'lucide-react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import Modal from './Modal';

/* ─── Process Execution Module (Fase 6) ─────────────────────────────────────────
   Generic UI per process (RAJUT/LINKING/SEWING/STEAM/PACKING/WASHER/SONTEK).
   Untuk QC, render mode khusus: tombol Pass + Fail (rework ke Washer).
   processCode diturunkan dari moduleId (mis. 'prod-exec-rajut' → RAJUT).
 ────────────────────────────────────────────────────────────────────────── */

const REWORK_PROCESSES = ['WASHER', 'SONTEK'];

function ProcessHeader({ board, isRework, isQC }) {
  const p = board?.process;
  const t = board?.totals || {};
  const progress = t.target_today > 0 ? Math.min(100, Math.round((t.output_today / t.target_today) * 100)) : 0;
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap" data-testid="process-header">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground">{p?.name || '—'}</h1>
          {isRework && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-400/15 border border-amber-300/25 text-amber-300">REWORK</span>}
          {isQC && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-primary/15 border border-primary/25 text-primary">QC GATE</span>}
        </div>
        <p className="text-sm text-muted-foreground mt-1">Input output cepat untuk proses {p?.code}. Auto-refresh 15 detik.</p>
      </div>
      <div className="grid grid-cols-4 gap-2">
        <GlassPanel className="px-3 py-2 min-w-[110px]">
          <div className="text-[10px] text-muted-foreground uppercase">Output Hari Ini</div>
          <div className="text-xl font-bold text-primary">{t.output_today || 0}</div>
        </GlassPanel>
        <GlassPanel className="px-3 py-2 min-w-[110px]">
          <div className="text-[10px] text-muted-foreground uppercase">Target Total</div>
          <div className="text-xl font-bold text-foreground">{t.target_today || 0}</div>
        </GlassPanel>
        <GlassPanel className="px-3 py-2 min-w-[110px]">
          <div className="text-[10px] text-muted-foreground uppercase">Pencapaian</div>
          <div className="text-xl font-bold text-foreground">{progress}%</div>
        </GlassPanel>
        <GlassPanel className="px-3 py-2 min-w-[110px]">
          <div className="text-[10px] text-muted-foreground uppercase">Line Aktif</div>
          <div className="text-xl font-bold text-foreground">{t.active_lines || 0}</div>
        </GlassPanel>
      </div>
    </div>
  );
}

export default function ProcessExecutionModule({ token, moduleId }) {
  const processCode = (moduleId || '').replace('prod-exec-', '').toUpperCase();
  const isQC     = processCode === 'QC';
  const isRework = REWORK_PROCESSES.includes(processCode);

  const [board, setBoard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [quickModal, setQuickModal] = useState(null); // { line, assignment, mode: 'output'|'qc' }
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchBoard = useCallback(async () => {
    try {
      const res = await fetch(`/api/rahaza/execution/process/${processCode}/board`, { headers });
      if (res.ok) setBoard(await res.json());
      else setBoard(null);
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processCode, token]);

  useEffect(() => { setLoading(true); fetchBoard(); }, [fetchBoard]);
  useEffect(() => {
    const id = setInterval(fetchBoard, 15000);
    return () => clearInterval(id);
  }, [fetchBoard]);

  const openQuick = (line, assignment = null) => {
    setFormError('');
    setQuickModal({
      line, assignment,
      qty: '', qty_pass: '', qty_fail: '', notes: '',
    });
  };

  const submitOutput = async () => {
    if (!quickModal) return;
    setSaving(true); setFormError('');
    try {
      const qty = Number(quickModal.qty);
      if (!(qty > 0)) throw new Error('Qty harus lebih dari 0.');
      const body = {
        line_id: quickModal.line.line_id,
        process_id: board.process.id,
        qty,
        line_assignment_id: quickModal.assignment?.id || null,
        model_id: quickModal.assignment?.model_id || null,
        size_id:  quickModal.assignment?.size_id || null,
        work_order_id: quickModal.assignment?.work_order_id || null,
        notes: quickModal.notes || '',
      };
      const r = await fetch('/api/rahaza/execution/quick-output', { method: 'POST', headers, body: JSON.stringify(body) });
      if (!r.ok) {
        const STATUS_MSG = { 400:'Input tidak valid / line tidak cocok proses.', 403:'Tidak ada akses.', 404:'Line tidak ditemukan.' };
        throw new Error(STATUS_MSG[r.status] || `Gagal simpan (HTTP ${r.status})`);
      }
      setQuickModal(null);
      fetchBoard();
    } catch (e) { setFormError(e.message); }
    finally { setSaving(false); }
  };

  const submitQC = async () => {
    if (!quickModal) return;
    setSaving(true); setFormError('');
    try {
      const qty_pass = Number(quickModal.qty_pass) || 0;
      const qty_fail = Number(quickModal.qty_fail) || 0;
      if (qty_pass <= 0 && qty_fail <= 0) throw new Error('Minimal isi salah satu: Pass atau Fail (>0).');
      const body = {
        line_id: quickModal.line.line_id, qty_pass, qty_fail,
        line_assignment_id: quickModal.assignment?.id || null,
        model_id: quickModal.assignment?.model_id || null,
        size_id:  quickModal.assignment?.size_id || null,
        work_order_id: quickModal.assignment?.work_order_id || null,
        notes: quickModal.notes || '',
      };
      const r = await fetch('/api/rahaza/execution/qc-event', { method: 'POST', headers, body: JSON.stringify(body) });
      if (!r.ok) {
        const STATUS_MSG = { 400:'Input QC tidak valid.', 403:'Tidak ada akses.', 404:'Line QC tidak ditemukan.' };
        throw new Error(STATUS_MSG[r.status] || `Gagal simpan QC (HTTP ${r.status})`);
      }
      setQuickModal(null);
      fetchBoard();
    } catch (e) { setFormError(e.message); }
    finally { setSaving(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
    </div>
  );
  if (!board) return (
    <GlassCard className="p-12 text-center text-muted-foreground">
      <AlertTriangle className="w-10 h-10 mx-auto mb-3 text-amber-400/70" />
      Proses “{processCode}” tidak ditemukan di master data.
    </GlassCard>
  );

  return (
    <div className="space-y-5" data-testid={`process-exec-${processCode.toLowerCase()}`}>
      <ProcessHeader board={board} isRework={isRework} isQC={isQC} />

      {/* Lines list */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-foreground">Line {board.process.name}</h2>
          <button onClick={fetchBoard} className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1" title="Refresh manual">
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
        {board.lines.length === 0 ? (
          <GlassCard className="p-8 text-center text-muted-foreground">
            Belum ada line yang di-assign untuk proses ini. Buat Line di menu <b>Line Produksi</b>, lalu Assign di <b>Assign Line Hari Ini</b>.
          </GlassCard>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
            {board.lines.map(ln => {
              const progress = ln.target_today > 0 ? Math.min(100, Math.round((ln.output_today / ln.target_today) * 100)) : 0;
              const breakdown = ln.output_breakdown || {};
              return (
                <GlassCard key={ln.line_id} className="p-4" data-testid={`line-card-${ln.line_code}`}>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Factory className="w-4 h-4 text-primary" />
                        <span className="font-semibold text-foreground truncate">{ln.line_code}</span>
                        <span className="text-xs text-muted-foreground truncate">{ln.line_name}</span>
                      </div>
                      {ln.location_name && <div className="text-[11px] text-muted-foreground mt-0.5">{ln.location_name}</div>}
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-xl font-bold text-primary">{ln.output_today}</div>
                      <div className="text-[10px] text-muted-foreground">{ln.target_today > 0 ? `/ ${ln.target_today} pcs` : 'pcs'}</div>
                    </div>
                  </div>

                  {/* Progress bar */}
                  {ln.target_today > 0 && (
                    <div className="mb-3">
                      <div className="h-1 bg-[var(--glass-bg)] rounded-full overflow-hidden">
                        <div className="h-full bg-[hsl(var(--primary))]" style={{ width: `${progress}%` }} />
                      </div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">{progress}%</div>
                    </div>
                  )}

                  {/* QC breakdown */}
                  {isQC && (breakdown.qc_pass > 0 || breakdown.qc_fail > 0) && (
                    <div className="flex items-center gap-2 mb-2 text-[11px]">
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-400/10 text-emerald-300"><CheckCircle2 className="w-3 h-3" /> Pass {breakdown.qc_pass || 0}</span>
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-400/10 text-red-300"><XCircle className="w-3 h-3" /> Fail {breakdown.qc_fail || 0}</span>
                    </div>
                  )}

                  {/* Assignments */}
                  {ln.assignments.length === 0 ? (
                    <div className="text-xs text-muted-foreground italic mb-2">Belum ada assignment hari ini.</div>
                  ) : (
                    <div className="space-y-1.5 mb-2">
                      {ln.assignments.map(a => (
                        <div key={a.id} className="border border-[var(--glass-border)] rounded-lg px-2.5 py-1.5 flex items-center justify-between gap-2 bg-[var(--glass-bg)]">
                          <div className="min-w-0">
                            <div className="text-xs text-foreground truncate">
                              {a.model_code ? `${a.model_code} · ${a.size_code || '—'}` : <span className="text-muted-foreground italic">Model belum dipilih</span>}
                            </div>
                            <div className="text-[10px] text-muted-foreground truncate">{a.operator_name || 'Operator?'} · {a.shift_name || 'Shift?'} · target {a.target_qty}</div>
                          </div>
                          <Button size="sm" onClick={() => openQuick(ln, a)} className="h-7 px-2 text-xs flex-shrink-0" data-testid={`quick-input-${ln.line_code}-${a.id}`}>
                            <Plus className="w-3 h-3 mr-1" /> Input
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}

                  <button onClick={() => openQuick(ln, null)} className="w-full text-xs text-muted-foreground hover:text-foreground border border-dashed border-[var(--glass-border)] rounded-lg py-1.5 hover:bg-[var(--glass-bg-hover)] transition-colors" data-testid={`quick-input-free-${ln.line_code}`}>
                    Input tanpa assignment
                  </button>
                </GlassCard>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent events log */}
      <GlassCard className="p-0 overflow-hidden">
        <div className="px-4 py-2 border-b border-[var(--glass-border)] bg-[var(--glass-bg)] flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold text-foreground">Event Terbaru</span>
          <span className="text-[10px] text-muted-foreground ml-auto">({board.recent_events?.length || 0})</span>
        </div>
        <div className="max-h-64 overflow-y-auto">
          {(board.recent_events || []).length === 0 ? (
            <div className="text-center text-xs text-muted-foreground py-6">Belum ada event.</div>
          ) : (
            <table className="w-full text-xs">
              <tbody>
                {board.recent_events.map(ev => (
                  <tr key={ev.id} className="border-t border-[var(--glass-border)]">
                    <td className="px-3 py-1.5 text-muted-foreground whitespace-nowrap">{new Date(ev.timestamp).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</td>
                    <td className="px-3 py-1.5">
                      {ev.event_type === 'qc_pass' && <span className="inline-flex items-center gap-1 text-emerald-300"><CheckCircle2 className="w-3 h-3" /> Pass</span>}
                      {ev.event_type === 'qc_fail' && <span className="inline-flex items-center gap-1 text-red-300"><XCircle className="w-3 h-3" /> Fail</span>}
                      {ev.event_type === 'output'  && <span className="inline-flex items-center gap-1 text-foreground/80"><Plus className="w-3 h-3" /> Output</span>}
                    </td>
                    <td className="px-3 py-1.5 font-semibold text-foreground">{ev.qty} pcs</td>
                    <td className="px-3 py-1.5 text-muted-foreground truncate">{ev.created_by_name || ev.created_by || '—'}</td>
                    <td className="px-3 py-1.5 text-muted-foreground truncate max-w-[160px]">{ev.notes || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </GlassCard>

      {/* Quick input modal */}
      {quickModal && (
        <Modal onClose={() => setQuickModal(null)} title={`Input ${isQC ? 'QC' : 'Output'} — ${quickModal.line.line_code}`} size="sm">
          <div className="space-y-4" data-testid="quick-input-modal">
            {formError && <div className="bg-red-400/10 border border-red-300/20 rounded-lg p-2.5 text-sm text-red-300">{formError}</div>}
            {quickModal.assignment && (
              <div className="text-xs text-muted-foreground bg-[var(--glass-bg)] border border-[var(--glass-border)] rounded-lg p-2.5">
                <div className="text-foreground font-medium">{quickModal.assignment.model_code} · {quickModal.assignment.size_code}</div>
                <div>{quickModal.assignment.operator_name} · {quickModal.assignment.shift_name} · target {quickModal.assignment.target_qty}</div>
              </div>
            )}

            {isQC ? (
              <>
                <div>
                  <label className="block text-xs font-medium text-emerald-300 mb-1"><CheckCircle2 className="w-3 h-3 inline mr-1" /> Qty Pass (lolos → Steam)</label>
                  <GlassInput type="number" value={quickModal.qty_pass} onChange={e => setQuickModal(m => ({ ...m, qty_pass: e.target.value }))} placeholder="0" data-testid="qc-qty-pass" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-red-300 mb-1"><XCircle className="w-3 h-3 inline mr-1" /> Qty Fail (rework → Washer)</label>
                  <GlassInput type="number" value={quickModal.qty_fail} onChange={e => setQuickModal(m => ({ ...m, qty_fail: e.target.value }))} placeholder="0" data-testid="qc-qty-fail" />
                </div>
              </>
            ) : (
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Qty Output (pcs) <span className="text-red-400">*</span></label>
                <GlassInput type="number" value={quickModal.qty} onChange={e => setQuickModal(m => ({ ...m, qty: e.target.value }))} placeholder="0" data-testid="quick-qty-input" autoFocus />
                <div className="flex gap-1 mt-2">
                  {[5, 10, 25, 50].map(n => (
                    <button key={n} onClick={() => setQuickModal(m => ({ ...m, qty: String((Number(m.qty) || 0) + n) }))}
                      className="flex-1 h-7 text-xs border border-[var(--glass-border)] rounded hover:bg-[var(--glass-bg-hover)] text-foreground/80"
                      data-testid={`qty-chip-${n}`}>
                      +{n}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Catatan</label>
              <GlassInput value={quickModal.notes} onChange={e => setQuickModal(m => ({ ...m, notes: e.target.value }))} placeholder="Opsional" />
            </div>

            {isRework && (
              <div className="flex items-start gap-2 bg-amber-400/10 border border-amber-300/20 rounded-lg p-2.5 text-xs text-amber-200">
                <RotateCcw className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                <span>Proses {processCode} adalah proses rework. Pastikan jumlah sesuai material yang masuk dari {processCode === 'WASHER' ? 'QC Fail' : 'Washer'}.</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-1">
              <Button variant="ghost" onClick={() => setQuickModal(null)} disabled={saving}>Batal</Button>
              <Button onClick={isQC ? submitQC : submitOutput} disabled={saving} data-testid="quick-submit-btn">
                {saving ? 'Menyimpan...' : 'Simpan'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
