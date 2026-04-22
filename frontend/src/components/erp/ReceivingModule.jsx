import { useState, useEffect, useCallback } from 'react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import Modal from '@/components/erp/Modal';
import ConfirmDialog from '@/components/erp/ConfirmDialog';
import { Button } from '@/components/ui/button';
import {
  ArrowDownToLine, Plus, Eye, CheckCircle, XCircle, Trash2,
  Package, Truck, Search, RefreshCw, FileText
} from 'lucide-react';

const fmtDate = (d) => d ? new Date(d).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';

const STATUS_STYLES = {
  draft: 'bg-secondary text-muted-foreground border border-border',
  inspecting: 'bg-amber-400/15 text-amber-400 border border-amber-300/20',
  received: 'bg-emerald-400/15 text-emerald-300 border border-emerald-300/20',
  failed: 'bg-red-400/15 text-red-400 border border-red-300/20',
};

export default function ReceivingModule({ token }) {
  const [receipts, setReceipts] = useState([]);
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showDetail, setShowDetail] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [search, setSearch] = useState('');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const [form, setForm] = useState({
    source_type: 'supplier', source_ref: '', supplier_name: '',
    location_id: '', location_name: '', notes: '',
    items: [{ product_name: '', sku: '', expected_qty: 0, received_qty: 0, rejected_qty: 0, unit: 'pcs' }]
  });

  const fetchData = useCallback(async () => {
    try {
      const [rRes, lRes] = await Promise.all([
        fetch('/api/warehouse/receiving', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/warehouse/locations', { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (rRes.ok) setReceipts(await rRes.json());
      if (lRes.ok) setLocations(await lRes.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async () => {
    try {
      const loc = locations.find(l => l.id === form.location_id);
      const payload = { ...form, location_name: loc?.name || form.location_name };
      const res = await fetch('/api/warehouse/receiving', { method: 'POST', headers, body: JSON.stringify(payload) });
      if (res.ok) { setShowCreate(false); resetForm(); fetchData(); }
    } catch (e) { alert('Error: ' + e.message); }
  };

  const handleStatusChange = async (receipt, newStatus) => {
    try {
      const res = await fetch(`/api/warehouse/receiving/${receipt.id}`, {
        method: 'PUT', headers, body: JSON.stringify({ status: newStatus, items: receipt.items })
      });
      if (res.ok) { setShowDetail(null); fetchData(); }
    } catch (e) { alert('Error: ' + e.message); }
  };

  const handleDelete = async (id) => {
    try {
      await fetch(`/api/warehouse/receiving/${id}`, { method: 'DELETE', headers });
      setConfirmDelete(null); fetchData();
    } catch (e) { alert('Error: ' + e.message); }
  };

  const resetForm = () => setForm({
    source_type: 'supplier', source_ref: '', supplier_name: '',
    location_id: '', location_name: '', notes: '',
    items: [{ product_name: '', sku: '', expected_qty: 0, received_qty: 0, rejected_qty: 0, unit: 'pcs' }]
  });

  const addItem = () => setForm(f => ({ ...f, items: [...f.items, { product_name: '', sku: '', expected_qty: 0, received_qty: 0, rejected_qty: 0, unit: 'pcs' }] }));
  const removeItem = (idx) => setForm(f => ({ ...f, items: f.items.filter((_, i) => i !== idx) }));
  const updateItem = (idx, field, val) => setForm(f => ({ ...f, items: f.items.map((it, i) => i === idx ? { ...it, [field]: val } : it) }));

  const filtered = search ? receipts.filter(r =>
    r.receipt_number?.toLowerCase().includes(search.toLowerCase()) ||
    r.supplier_name?.toLowerCase().includes(search.toLowerCase())
  ) : receipts;

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" /></div>;

  return (
    <div className="space-y-5" data-testid="wh-receiving-module">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Goods Receiving</h1>
          <p className="text-muted-foreground text-sm">Terima barang dari supplier, produksi, atau transfer</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchData} className="p-2 rounded-xl hover:bg-[var(--glass-bg-hover)] transition-colors">
            <RefreshCw className="w-4 h-4 text-muted-foreground" />
          </button>
          <Button onClick={() => setShowCreate(true)} className="bg-primary text-primary-foreground hover:brightness-110 gap-1.5" data-testid="create-receipt-btn">
            <Plus className="w-4 h-4" /> New Receipt
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <GlassInput placeholder="Search receipt..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9" />
      </div>

      {/* Receipts List */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <GlassCard hover={false} className="p-8 text-center">
            <ArrowDownToLine className="w-10 h-10 text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Belum ada goods receipt</p>
          </GlassCard>
        ) : filtered.map(r => (
          <GlassCard key={r.id} className="p-4 cursor-pointer" onClick={() => setShowDetail(r)} data-testid={`receipt-${r.receipt_number}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground font-mono">{r.receipt_number}</p>
                  <p className="text-xs text-muted-foreground">{r.supplier_name || r.source_type} • {r.items?.length || 0} items</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${STATUS_STYLES[r.status] || STATUS_STYLES.draft}`}>{r.status}</span>
                <p className="text-xs text-muted-foreground">{fmtDate(r.created_at)}</p>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <Modal title="New Goods Receipt" onClose={() => setShowCreate(false)} size="lg">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Source Type</label>
                <select value={form.source_type} onChange={e => setForm(f => ({ ...f, source_type: e.target.value }))} className="w-full border border-[var(--glass-border)] bg-[var(--input-surface)] rounded-lg px-3 py-2 text-sm text-foreground">
                  <option value="supplier">Supplier</option>
                  <option value="production">Production</option>
                  <option value="transfer">Transfer</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Reference (PO/SO)</label>
                <GlassInput value={form.source_ref} onChange={e => setForm(f => ({ ...f, source_ref: e.target.value }))} placeholder="PO-001" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Supplier / Source</label>
                <GlassInput value={form.supplier_name} onChange={e => setForm(f => ({ ...f, supplier_name: e.target.value }))} placeholder="Nama supplier" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Location</label>
                <select value={form.location_id} onChange={e => setForm(f => ({ ...f, location_id: e.target.value }))} className="w-full border border-[var(--glass-border)] bg-[var(--input-surface)] rounded-lg px-3 py-2 text-sm text-foreground">
                  <option value="">Select location...</option>
                  {locations.map(l => <option key={l.id} value={l.id}>{l.code} - {l.name}</option>)}
                </select>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-muted-foreground">Items</label>
                <button onClick={addItem} className="text-xs text-primary hover:brightness-110 font-medium">+ Add Item</button>
              </div>
              <div className="space-y-2">
                {form.items.map((item, idx) => (
                  <div key={idx} className="grid grid-cols-6 gap-2 items-end p-3 rounded-xl bg-[var(--glass-bg)] border border-[var(--glass-border)]">
                    <div className="col-span-2">
                      <label className="text-[10px] text-muted-foreground">Product</label>
                      <GlassInput value={item.product_name} onChange={e => updateItem(idx, 'product_name', e.target.value)} placeholder="Name" className="h-8 text-xs" />
                    </div>
                    <div>
                      <label className="text-[10px] text-muted-foreground">SKU</label>
                      <GlassInput value={item.sku} onChange={e => updateItem(idx, 'sku', e.target.value)} placeholder="SKU" className="h-8 text-xs" />
                    </div>
                    <div>
                      <label className="text-[10px] text-muted-foreground">Expected</label>
                      <GlassInput type="number" value={item.expected_qty} onChange={e => updateItem(idx, 'expected_qty', parseInt(e.target.value) || 0)} className="h-8 text-xs" />
                    </div>
                    <div>
                      <label className="text-[10px] text-muted-foreground">Received</label>
                      <GlassInput type="number" value={item.received_qty} onChange={e => updateItem(idx, 'received_qty', parseInt(e.target.value) || 0)} className="h-8 text-xs" />
                    </div>
                    <div className="flex gap-1">
                      <div className="flex-1">
                        <label className="text-[10px] text-muted-foreground">Rejected</label>
                        <GlassInput type="number" value={item.rejected_qty} onChange={e => updateItem(idx, 'rejected_qty', parseInt(e.target.value) || 0)} className="h-8 text-xs" />
                      </div>
                      {form.items.length > 1 && (
                        <button onClick={() => removeItem(idx)} className="text-red-400 hover:text-red-300 mt-3.5"><Trash2 className="w-3.5 h-3.5" /></button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Notes</label>
              <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} className="w-full border border-[var(--glass-border)] bg-[var(--input-surface)] rounded-lg px-3 py-2 text-sm text-foreground h-16 resize-none placeholder:text-muted-foreground" placeholder="Optional notes..." />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowCreate(false)} className="border-[var(--glass-border)] text-muted-foreground hover:bg-[var(--glass-bg-hover)]">Cancel</Button>
              <Button onClick={handleCreate} className="bg-primary text-primary-foreground hover:brightness-110" data-testid="submit-receipt-btn">Create Receipt</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Detail Modal */}
      {showDetail && (
        <Modal title={`Receipt ${showDetail.receipt_number}`} onClose={() => setShowDetail(null)} size="lg">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div><p className="text-xs text-muted-foreground">Source</p><p className="text-sm font-medium text-foreground">{showDetail.supplier_name || showDetail.source_type}</p></div>
              <div><p className="text-xs text-muted-foreground">Reference</p><p className="text-sm font-medium text-foreground">{showDetail.source_ref || '-'}</p></div>
              <div><p className="text-xs text-muted-foreground">Location</p><p className="text-sm font-medium text-foreground">{showDetail.location_name || '-'}</p></div>
              <div><p className="text-xs text-muted-foreground">Status</p><span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${STATUS_STYLES[showDetail.status]}`}>{showDetail.status}</span></div>
            </div>

            <div className="border-t border-[var(--glass-border)] pt-3">
              <p className="text-xs font-medium text-muted-foreground mb-2">Items ({showDetail.items?.length || 0})</p>
              <div className="space-y-2">
                {(showDetail.items || []).map((item, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-[var(--glass-bg)] border border-[var(--glass-border)]">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">{item.product_name}</p>
                        <p className="text-xs text-muted-foreground font-mono">{item.sku}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-foreground">Received: <strong>{item.received_qty}</strong> / {item.expected_qty} {item.unit}</p>
                        {item.rejected_qty > 0 && <p className="text-xs text-red-400">Rejected: {item.rejected_qty}</p>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {showDetail.status === 'draft' && (
              <div className="flex justify-end gap-2 pt-2 border-t border-[var(--glass-border)]">
                <Button variant="outline" onClick={() => { setConfirmDelete(showDetail.id); setShowDetail(null); }} className="border-red-300/20 text-red-400 hover:bg-red-400/10">
                  <Trash2 className="w-4 h-4 mr-1" /> Delete
                </Button>
                <Button onClick={() => handleStatusChange(showDetail, 'received')} className="bg-emerald-500 text-white hover:brightness-110" data-testid="confirm-receive-btn">
                  <CheckCircle className="w-4 h-4 mr-1" /> Confirm Received
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}

      {confirmDelete && (
        <ConfirmDialog title="Delete Receipt?" message="This action cannot be undone." onConfirm={() => handleDelete(confirmDelete)} onCancel={() => setConfirmDelete(null)} />
      )}
    </div>
  );
}
