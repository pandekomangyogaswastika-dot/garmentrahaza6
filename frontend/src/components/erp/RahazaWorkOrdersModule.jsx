import { useState, useEffect, useCallback } from 'react';
import { Plus, Edit2, Trash2, Eye, ArrowRight, X, ClipboardList, Scale, AlertTriangle, CheckCircle2, Box, Printer } from 'lucide-react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import Modal from './Modal';
import { DataTable } from './DataTableV2';
import { PageHeader } from './moduleAtoms';
import { openWorkOrderBundleTickets } from './bundleTickets';
import { toast } from 'sonner';

const WO_STATUS_COLORS = {
  draft:         { bg: 'bg-slate-400/15',   border: 'border-slate-300/25',   text: 'text-slate-300',   label: 'Draft' },
  released:      { bg: 'bg-blue-400/15',    border: 'border-blue-300/25',    text: 'text-blue-300',    label: 'Released' },
  in_production: { bg: 'bg-primary/15',     border: 'border-primary/25',     text: 'text-primary',     label: 'In Production' },
  completed:     { bg: 'bg-emerald-400/15', border: 'border-emerald-300/25', text: 'text-emerald-300', label: 'Completed' },
  cancelled:     { bg: 'bg-red-400/15',     border: 'border-red-300/25',     text: 'text-red-300',     label: 'Cancelled' },
};
const PRIORITY_COLORS = {
  normal: { bg: 'bg-foreground/5',   text: 'text-foreground/60',  label: 'Normal' },
  high:   { bg: 'bg-amber-400/15',   text: 'text-amber-300',      label: 'High' },
  urgent: { bg: 'bg-red-400/15',     text: 'text-red-300',        label: 'Urgent' },
};

function StatusBadge({ status }) {
  const s = WO_STATUS_COLORS[status] || WO_STATUS_COLORS.draft;
  return <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${s.bg} ${s.border} border ${s.text}`}>{s.label}</span>;
}
function PriorityBadge({ priority }) {
  const p = PRIORITY_COLORS[priority] || PRIORITY_COLORS.normal;
  return <span className={`inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded ${p.bg} ${p.text}`}>{p.label}</span>;
}

function ProgressBar({ percent }) {
  const pct = Math.min(100, Math.max(0, Number(percent) || 0));
  return (
    <div className="w-full">
      <div className="h-1.5 bg-[var(--glass-bg)] rounded-full overflow-hidden">
        <div className="h-full bg-[hsl(var(--primary))] transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="text-[10px] text-muted-foreground mt-0.5">{pct}%</div>
    </div>
  );
}

export default function RahazaWorkOrdersModule({ token, onNavigate }) {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statuses, setStatuses] = useState([]);
  const [models, setModels] = useState([]);
  const [sizes, setSizes] = useState([]);
  const [orders, setOrders] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState({
    order_id: '', model_id: '', size_id: '', qty: 1, priority: 'normal',
    target_start_date: '', target_end_date: '', notes: ''
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`/api/rahaza/work-orders`, { headers });
      if (r.ok) setList(await r.json());
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { fetchList(); }, [fetchList]);
  useEffect(() => {
    const h = { Authorization: `Bearer ${token}` };
    Promise.all([
      fetch('/api/rahaza/work-orders-statuses', { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/models', { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/sizes',  { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/orders', { headers: h }).then(r => r.ok ? r.json() : []),
    ]).then(([st, m, s, o]) => { setStatuses(st); setModels(m); setSizes(s); setOrders(o); });
  }, [token]);

  const openCreate = () => {
    setEditing(null);
    setForm({ order_id: '', model_id: '', size_id: '', qty: 1, priority: 'normal', target_start_date: '', target_end_date: '', notes: '' });
    setFormError('');
    setModalOpen(true);
  };
  const openEdit = async (wo) => {
    const r = await fetch(`/api/rahaza/work-orders/${wo.id}`, { headers });
    if (!r.ok) return;
    const full = await r.json();
    setEditing(full);
    setForm({
      order_id: full.order_id || '', model_id: full.model_id || '', size_id: full.size_id || '',
      qty: full.qty || 1, priority: full.priority || 'normal',
      target_start_date: full.target_start_date || '', target_end_date: full.target_end_date || '',
      notes: full.notes || '',
    });
    setFormError('');
    setModalOpen(true);
  };
  const openDetail = async (wo) => {
    const r = await fetch(`/api/rahaza/work-orders/${wo.id}`, { headers });
    if (r.ok) setDetail(await r.json());
  };

  const saveWO = async () => {
    setSaving(true); setFormError('');
    try {
      const payload = {
        order_id: form.order_id || null,
        model_id: form.model_id, size_id: form.size_id,
        qty: Number(form.qty), priority: form.priority,
        target_start_date: form.target_start_date || null,
        target_end_date:   form.target_end_date   || null,
        notes: form.notes,
      };
      if (!editing) {
        if (!payload.model_id || !payload.size_id || !(payload.qty > 0)) {
          throw new Error('Model, Size, dan Qty > 0 wajib diisi.');
        }
      }
      const url = editing ? `/api/rahaza/work-orders/${editing.id}` : '/api/rahaza/work-orders';
      const method = editing ? 'PUT' : 'POST';
      const body = editing
        ? { qty: payload.qty, priority: payload.priority, target_start_date: payload.target_start_date, target_end_date: payload.target_end_date, notes: payload.notes }
        : payload;
      const r = await fetch(url, { method, headers, body: JSON.stringify(body) });
      if (!r.ok) {
        const STATUS_MSG = { 400:'Data WO tidak valid.', 403:'Tidak ada akses.', 404:'Data tidak ditemukan.', 409:'Konflik data.' };
        throw new Error(STATUS_MSG[r.status] || `Gagal menyimpan (HTTP ${r.status})`);
      }
      setModalOpen(false);
      fetchList();
    } catch (err) { setFormError(err.message); }
    finally { setSaving(false); }
  };

  const transition = async (wo, newStatus) => {
    if (!window.confirm(`Ubah status ke ${newStatus}?`)) return;
    const r = await fetch(`/api/rahaza/work-orders/${wo.id}/status`, { method: 'POST', headers, body: JSON.stringify({ status: newStatus }) });
    if (r.ok) { fetchList(); if (detail?.id === wo.id) openDetail(wo); }
    else { alert(`Gagal transisi status (HTTP ${r.status}).`); }
  };
  const deleteWO = async (wo) => {
    if (!window.confirm(`Hapus WO ${wo.wo_number}?`)) return;
    await fetch(`/api/rahaza/work-orders/${wo.id}`, { method: 'DELETE', headers });
    fetchList();
  };

  // Phase 17A: Generate Bundles dari WO
  const [bundleGenModal, setBundleGenModal] = useState(null); // { wo, loading, result, force }
  const openBundleGen = (wo) => setBundleGenModal({ wo, loading: false, result: null, force: false });
  const submitBundleGen = async () => {
    if (!bundleGenModal) return;
    setBundleGenModal((s) => ({ ...s, loading: true }));
    try {
      const url = `/api/rahaza/work-orders/${bundleGenModal.wo.id}/generate-bundles${bundleGenModal.force ? '?force=true' : ''}`;
      const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify({}) });
      const data = await r.json();
      if (!r.ok) {
        setBundleGenModal((s) => ({ ...s, loading: false, error: data.detail || 'Gagal' }));
        return;
      }
      setBundleGenModal((s) => ({ ...s, loading: false, result: data, error: null }));
      fetchList();
    } catch (e) {
      setBundleGenModal((s) => ({ ...s, loading: false, error: e.message }));
    }
  };

  if (loading && list.length === 0) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
    </div>
  );

  return (
    <div className="space-y-5" data-testid="rahaza-work-orders-page">
      <PageHeader
        icon={ClipboardList}
        eyebrow="Portal Produksi"
        title="Work Order (WO)"
        subtitle="Perintah produksi per item. Bisa digenerate otomatis dari Order, atau dibuat manual untuk stok internal."
        actions={<Button onClick={openCreate} data-testid="wo-add-btn"><Plus className="w-4 h-4 mr-1.5" /> WO Manual</Button>}
      />

      <DataTable
        tableId="work-orders"
        loading={loading}
        rows={list}
        searchFields={['wo_number', 'order_number_snapshot', 'customer_snapshot', 'model_code', 'model_name', 'size_code', 'status']}
        filters={[
          { key: 'status', label: 'Status', type: 'select',
            options: statuses.map(s => ({ value: s.value, label: s.label })) },
          { key: 'priority', label: 'Prioritas', type: 'select',
            options: [
              { value: 'low', label: 'Rendah' },
              { value: 'normal', label: 'Normal' },
              { value: 'high', label: 'Tinggi' },
              { value: 'urgent', label: 'Urgent' },
            ] },
        ]}
        columns={[
          { key: 'wo_number', label: 'No. WO', sortable: true,
            render: (r, v) => <span className="font-mono text-xs">{v}</span> },
          { key: 'order_customer', label: 'Order / Customer', sortable: true,
            accessor: (r) => r.order_number_snapshot || r.customer_snapshot || '',
            render: (r) => (
              <div>
                {r.order_number_snapshot
                  ? <div className="font-medium text-xs">{r.order_number_snapshot}</div>
                  : <div className="text-xs text-foreground/50 italic">Manual</div>}
                <div className="text-[11px] text-foreground/60">{r.customer_snapshot || (r.is_internal ? 'Produksi Internal' : '—')}</div>
              </div>
            ) },
          { key: 'model_size', label: 'Model · Size', sortable: true,
            accessor: (r) => `${r.model_code}·${r.size_code}`,
            render: (r) => (
              <div>
                <div className="font-medium">{r.model_code}</div>
                <div className="text-[11px] text-foreground/60">{r.model_name} · {r.size_code}</div>
              </div>
            ) },
          { key: 'qty', label: 'Target', align: 'right', sortable: true,
            render: (r) => <span className="font-semibold">{r.qty} pcs</span> },
          { key: 'progress_pct', label: 'Progress', sortable: true,
            render: (r) => <div className="min-w-[100px]"><ProgressBar percent={r.progress_pct || 0} /></div> },
          { key: 'yarn', label: 'Yarn',
            render: (r) => {
              const hasBom = !!(r.bom_snapshot && r.bom_snapshot.bom_id);
              const yarnTotal = r.total_yarn_kg_required || 0;
              return hasBom
                ? <div className="flex items-center gap-1 text-xs"><Scale className="w-3 h-3 text-primary" /><span className="font-mono">{yarnTotal.toFixed(3)} kg</span></div>
                : <div className="flex items-center gap-1 text-xs text-amber-400" title="BOM belum didefinisikan"><AlertTriangle className="w-3 h-3" /> No BOM</div>;
            } },
          { key: 'priority', label: 'Prioritas',
            render: (r) => <PriorityBadge priority={r.priority} /> },
          { key: 'status', label: 'Status',
            render: (r) => <StatusBadge status={r.status} /> },
        ]}
        emptyTitle="Belum ada Work Order"
        emptyDescription="Generate dari Order Produksi (1 klik) atau buat WO manual."
        emptyIcon={ClipboardList}
        emptyAction={
          <>
            <Button
              onClick={() => onNavigate && onNavigate('prod-orders')}
              className="h-9"
              data-testid="wo-empty-cta-orders"
              disabled={!onNavigate}
            >
              <ArrowRight className="w-4 h-4 mr-1.5" /> Buka Order Produksi
            </Button>
            <Button
              variant="outline"
              onClick={openCreate}
              className="h-9"
              data-testid="wo-empty-cta-manual"
            >
              <Plus className="w-4 h-4 mr-1.5" /> WO Manual
            </Button>
          </>
        }
        emptyHelp="Cara tercepat: buka 'Order Produksi' → pilih order → klik ikon Work Order → sistem akan buat WO per item dengan BOM snapshot otomatis."
        exportFilename={`work-orders-${new Date().toISOString().slice(0,10)}.csv`}
        rowActions={(wo) => (
          <div className="inline-flex items-center gap-1">
            <button onClick={() => openDetail(wo)} className="p-1.5 rounded hover:bg-[var(--glass-bg-hover)] text-muted-foreground hover:text-foreground" title="Detail" data-testid={`wo-detail-${wo.wo_number}`}><Eye className="w-3.5 h-3.5" /></button>
            {(wo.status === 'released' || wo.status === 'in_production') && (
              <>
                <button
                  onClick={() => openBundleGen(wo)}
                  className="p-1.5 rounded hover:bg-[hsl(var(--primary)/0.12)] text-muted-foreground hover:text-[hsl(var(--primary))]"
                  title="Generate Bundles"
                  data-testid={`wo-bundles-${wo.wo_number}`}
                >
                  <Box className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => openWorkOrderBundleTickets(wo, token)}
                  className="p-1.5 rounded hover:bg-[hsl(var(--primary)/0.12)] text-muted-foreground hover:text-[hsl(var(--primary))]"
                  title="Print semua bundle ticket WO ini"
                  data-testid={`wo-print-tickets-${wo.wo_number}`}
                >
                  <Printer className="w-3.5 h-3.5" />
                </button>
              </>
            )}
            {wo.status === 'draft' && (
              <>
                <button onClick={() => openEdit(wo)} className="p-1.5 rounded hover:bg-[var(--glass-bg-hover)] text-muted-foreground hover:text-foreground" title="Edit"><Edit2 className="w-3.5 h-3.5" /></button>
                <button onClick={() => deleteWO(wo)} className="p-1.5 rounded hover:bg-red-400/10 text-muted-foreground hover:text-red-400" title="Hapus"><Trash2 className="w-3.5 h-3.5" /></button>
              </>
            )}
          </div>
        )}
      />

      {/* Create / Edit Modal */}
      {modalOpen && (
        <Modal onClose={() => setModalOpen(false)} title={editing ? `Edit WO ${editing.wo_number}` : 'Work Order Manual'} size="md">
          <div className="space-y-4" data-testid="wo-form">
            {formError && <div className="bg-red-400/10 border border-red-300/20 rounded-lg p-3 text-sm text-red-300">{formError}</div>}
            {!editing && (
              <>
                <div>
                  <label className="block text-xs font-medium text-foreground/70 mb-1">Order Terkait (opsional)</label>
                  <select value={form.order_id} onChange={e => setForm({...form, order_id: e.target.value})}
                    className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground"
                    data-testid="wo-field-order">
                    <option value="">— Tidak Terkait / Internal —</option>
                    {orders.filter(o => ['draft','confirmed','in_production'].includes(o.status)).map(o => (
                      <option key={o.id} value={o.id}>{o.order_number} · {o.customer_name || 'Internal'}</option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-foreground/70 mb-1">Model <span className="text-red-400">*</span></label>
                    <select value={form.model_id} onChange={e => setForm({...form, model_id: e.target.value})}
                      className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground"
                      data-testid="wo-field-model">
                      <option value="">— Pilih Model —</option>
                      {models.filter(m => m.active).map(m => <option key={m.id} value={m.id}>{m.code} · {m.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground/70 mb-1">Size <span className="text-red-400">*</span></label>
                    <select value={form.size_id} onChange={e => setForm({...form, size_id: e.target.value})}
                      className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground"
                      data-testid="wo-field-size">
                      <option value="">— Pilih Size —</option>
                      {sizes.filter(s => s.active).map(s => <option key={s.id} value={s.id}>{s.code}</option>)}
                    </select>
                  </div>
                </div>
              </>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Qty (pcs) <span className="text-red-400">*</span></label>
                <GlassInput type="number" value={form.qty} onChange={e => setForm({...form, qty: e.target.value})} data-testid="wo-field-qty" />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Prioritas</label>
                <select value={form.priority} onChange={e => setForm({...form, priority: e.target.value})}
                  className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground"
                  data-testid="wo-field-priority">
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Target Mulai</label>
                <GlassInput type="date" value={form.target_start_date} onChange={e => setForm({...form, target_start_date: e.target.value})} />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Target Selesai</label>
                <GlassInput type="date" value={form.target_end_date} onChange={e => setForm({...form, target_end_date: e.target.value})} />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Catatan</label>
              <GlassInput value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="Opsional" />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={saving}>Batal</Button>
              <Button onClick={saveWO} disabled={saving} data-testid="wo-save-btn">
                {saving ? 'Menyimpan...' : (editing ? 'Simpan Perubahan' : 'Buat WO')}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Detail Modal */}
      {detail && (
        <Modal onClose={() => setDetail(null)} title={`Detail ${detail.wo_number}`} size="lg">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <div><span className="text-muted-foreground">Status:</span> <StatusBadge status={detail.status} /></div>
              <div><span className="text-muted-foreground">Prioritas:</span> <PriorityBadge priority={detail.priority} /></div>
              <div><span className="text-muted-foreground">Order:</span> <b>{detail.order_number_snapshot || 'Manual'}</b></div>
              <div><span className="text-muted-foreground">Customer:</span> <b>{detail.customer_snapshot || (detail.is_internal ? 'Produksi Internal' : '—')}</b></div>
              <div><span className="text-muted-foreground">Model:</span> <b>{detail.model_code} · {detail.model_name}</b></div>
              <div><span className="text-muted-foreground">Size:</span> <b>{detail.size_code}</b></div>
              <div><span className="text-muted-foreground">Qty:</span> <b>{detail.qty} pcs</b></div>
              <div><span className="text-muted-foreground">Completed:</span> <b>{detail.completed_qty || 0} pcs ({detail.progress_pct || 0}%)</b></div>
              <div><span className="text-muted-foreground">Target mulai:</span> <b>{detail.target_start_date || '—'}</b></div>
              <div><span className="text-muted-foreground">Target selesai:</span> <b>{detail.target_end_date || '—'}</b></div>
            </div>

            {/* Progress breakdown per process */}
            {detail.progress_breakdown?.length > 0 && (
              <GlassPanel className="p-0 overflow-hidden">
                <div className="px-3 py-2 border-b border-[var(--glass-border)] bg-[var(--glass-bg)] text-xs text-muted-foreground font-semibold">Progress Per Proses</div>
                <table className="w-full text-sm">
                  <tbody>
                    {detail.progress_breakdown.map(p => (
                      <tr key={p.process_id} className="border-t border-[var(--glass-border)]">
                        <td className="px-3 py-2 w-32 font-mono text-xs text-muted-foreground">#{p.order_seq} {p.process_code}</td>
                        <td className="px-3 py-2 text-foreground">{p.process_name}</td>
                        <td className="px-3 py-2 text-right font-semibold">{p.total_output} pcs</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </GlassPanel>
            )}

            {/* BOM Snapshot */}
            {detail.bom_snapshot ? (
              <GlassPanel className="p-0 overflow-hidden">
                <div className="px-3 py-2 border-b border-[var(--glass-border)] bg-[var(--glass-bg)] flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-xs font-semibold text-foreground">BOM Snapshot</span>
                  <span className="ml-auto text-xs text-muted-foreground">{detail.bom_snapshot.total_yarn_kg_per_pcs} kg/pcs → <b className="text-primary">{detail.total_yarn_kg_required} kg total</b></span>
                </div>
                <div className="p-3 space-y-2">
                  {(detail.bom_snapshot.yarn_materials || []).length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-muted-foreground mb-1">Benang</div>
                      <div className="grid grid-cols-[1fr_auto] gap-2 text-sm">
                        {detail.bom_snapshot.yarn_materials.map((y, i) => (
                          <><span key={`yn-${i}`} className="text-foreground">{y.code} · {y.name}</span><span key={`yq-${i}`} className="font-mono text-foreground/80">{y.qty_kg} kg</span></>
                        ))}
                      </div>
                    </div>
                  )}
                  {(detail.bom_snapshot.accessory_materials || []).length > 0 && (
                    <div>
                      <div className="text-xs font-medium text-muted-foreground mb-1">Aksesoris</div>
                      <div className="grid grid-cols-[1fr_auto] gap-2 text-sm">
                        {detail.bom_snapshot.accessory_materials.map((a, i) => (
                          <><span key={`an-${i}`} className="text-foreground">{a.code} · {a.name}</span><span key={`aq-${i}`} className="font-mono text-foreground/80">{a.qty} {a.unit}</span></>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </GlassPanel>
            ) : (
              <div className="bg-amber-400/10 border border-amber-300/20 rounded-lg p-3 text-sm text-amber-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold">BOM belum didefinisikan</div>
                  <div className="text-xs text-amber-300/80 mt-0.5">WO ini tidak punya snapshot material. Isi BOM untuk model & size ini di menu “BOM Produk”, kemudian buat ulang WO.</div>
                </div>
              </div>
            )}

            {/* Status transitions */}
            <div className="border-t border-[var(--glass-border)] pt-3">
              <div className="text-xs text-muted-foreground mb-2">Transisi status:</div>
              <div className="flex flex-wrap gap-2">
                {(statuses.find(s => s.value === detail.status)?.allowed_next || []).map(ns => (
                  <Button key={ns} variant="ghost" onClick={() => transition(detail, ns)} className="gap-1.5 border border-[var(--glass-border)]" data-testid={`wo-transition-${ns}`}>
                    <ArrowRight className="w-3.5 h-3.5" /> {WO_STATUS_COLORS[ns]?.label || ns}
                  </Button>
                ))}
                {(statuses.find(s => s.value === detail.status)?.allowed_next || []).length === 0 && (
                  <div className="text-xs text-muted-foreground">Tidak ada transisi lanjutan.</div>
                )}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Phase 17A/17B: Generate Bundles Modal */}
      {bundleGenModal && (
        <Modal
          onClose={() => setBundleGenModal(null)}
          title={`Generate Bundles · ${bundleGenModal.wo.wo_number}`}
          size="md"
          data-testid="wo-bundlegen-modal"
        >
          <div className="space-y-4">
            <div className="text-sm text-foreground/80">
              WO <b className="text-foreground">{bundleGenModal.wo.wo_number}</b> — {bundleGenModal.wo.model_code} / {bundleGenModal.wo.size_code} · <b className="text-foreground">{bundleGenModal.wo.qty} pcs</b>
            </div>
            <div className="rounded-lg border border-[hsl(var(--primary)/0.25)] bg-[hsl(var(--primary)/0.04)] p-3 text-xs text-foreground/80">
              <div className="font-semibold text-foreground mb-1">Apa yang terjadi saat generate bundles?</div>
              Sistem membagi <b>{bundleGenModal.wo.qty} pcs</b> menjadi bundle (default ukuran <b>30 pcs</b>, bisa diatur di master Model).
              Tiap bundle mendapat nomor unik (mis. <span className="font-mono">BDL-YYYYMMDD-0001</span>) dan QR ticket yang bisa dicetak untuk traceability per proses.
            </div>

            {bundleGenModal.error && (
              <div className="rounded-lg border border-red-300/25 bg-red-400/10 p-3 text-xs text-red-300">
                {bundleGenModal.error}
              </div>
            )}

            {!bundleGenModal.result && (
              <label className="flex items-start gap-2 text-xs text-foreground/80">
                <input
                  type="checkbox"
                  checked={!!bundleGenModal.force}
                  onChange={(e) => setBundleGenModal((s) => ({ ...s, force: e.target.checked }))}
                  data-testid="wo-bundlegen-force"
                />
                <span>
                  <b>Regenerate</b> (admin only) — hapus bundle yang masih status <span className="font-mono">created</span> lalu buat ulang.
                  Bundle yang sudah ada event produksi tidak akan disentuh.
                </span>
              </label>
            )}

            {bundleGenModal.result ? (
              <div className="space-y-3">
                <div className="rounded-lg border border-emerald-300/25 bg-emerald-400/10 p-3 text-xs text-emerald-300 flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <div>
                    Berhasil membuat <b>{bundleGenModal.result.generated}</b> bundle (ukuran {bundleGenModal.result.bundle_size} pcs) untuk total {bundleGenModal.result.total_qty} pcs.
                  </div>
                </div>
                <div className="max-h-48 overflow-auto border border-[var(--glass-border)] rounded-lg divide-y divide-[var(--glass-border)]">
                  {(bundleGenModal.result.bundles || []).map((b) => (
                    <div key={b.id} className="flex items-center justify-between px-3 py-2 text-xs">
                      <span className="font-mono text-foreground">{b.bundle_number}</span>
                      <span className="text-muted-foreground">{b.qty} pcs</span>
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <Button
                    variant="outline"
                    onClick={() => openWorkOrderBundleTickets(bundleGenModal.wo, token)}
                    className="h-9"
                    data-testid="wo-bundlegen-print"
                  >
                    <Printer className="w-4 h-4 mr-1.5" /> Cetak Bundle Tickets
                  </Button>
                  <Button onClick={() => setBundleGenModal(null)} className="h-9">
                    Selesai
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-end gap-2 pt-1">
                <Button variant="ghost" onClick={() => setBundleGenModal(null)} disabled={bundleGenModal.loading}>Batal</Button>
                <Button
                  onClick={submitBundleGen}
                  disabled={bundleGenModal.loading}
                  data-testid="wo-bundlegen-submit"
                >
                  {bundleGenModal.loading ? 'Memproses...' : (bundleGenModal.force ? 'Regenerate Bundles' : 'Generate Bundles')}
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}

    </div>
  );
}
