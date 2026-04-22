import { useState, useEffect, useCallback } from 'react';
import { Package, ArrowDown, ArrowRightLeft, AlertTriangle, Scale, Gem, Archive, Clock } from 'lucide-react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import Modal from './Modal';
import { DataTable } from './DataTableV2';

const TYPE_ICON = { yarn: Scale, accessory: Gem, fg: Archive };
const TYPE_LABEL = { yarn: 'Benang', accessory: 'Aksesoris', fg: 'Barang Jadi' };
const TYPE_COLOR = { yarn: 'text-amber-300', accessory: 'text-primary', fg: 'text-emerald-300' };

export default function RahazaStockModule({ token }) {
  const [stocks, setStocks] = useState([]);
  const [summary, setSummary] = useState(null);
  const [movements, setMovements] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [receiveForm, setReceiveForm] = useState({ material_id: '', location_id: '', qty: '', notes: '' });
  const [transferForm, setTransferForm] = useState({ material_id: '', from_location_id: '', to_location_id: '', qty: '', notes: '' });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [stkRes, sumRes, mvRes] = await Promise.all([
        fetch(`/api/rahaza/material-stock`, { headers }).then(r => r.ok ? r.json() : []),
        fetch('/api/rahaza/material-stock/summary', { headers }).then(r => r.ok ? r.json() : null),
        fetch('/api/rahaza/material-movements?limit=30', { headers }).then(r => r.ok ? r.json() : []),
      ]);
      setStocks(stkRes); setSummary(sumRes); setMovements(mvRes);
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    const h = { Authorization: `Bearer ${token}` };
    Promise.all([
      fetch('/api/rahaza/materials', { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/locations', { headers: h }).then(r => r.ok ? r.json() : []),
    ]).then(([m, l]) => { setMaterials((m || []).filter(x => x.active)); setLocations((l || []).filter(x => x.active)); });
  }, [token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const openReceive = () => { setReceiveForm({ material_id: '', location_id: '', qty: '', notes: '' }); setFormError(''); setReceiveOpen(true); };
  const openTransfer = () => { setTransferForm({ material_id: '', from_location_id: '', to_location_id: '', qty: '', notes: '' }); setFormError(''); setTransferOpen(true); };

  const doReceive = async () => {
    setSaving(true); setFormError('');
    try {
      if (!receiveForm.material_id || !receiveForm.location_id || !(Number(receiveForm.qty) > 0)) throw new Error('Pilih material, lokasi, dan isi qty > 0.');
      const r = await fetch('/api/rahaza/material-receive', { method: 'POST', headers, body: JSON.stringify({ ...receiveForm, qty: Number(receiveForm.qty) }) });
      if (!r.ok) {
        const STATUS_MSG = { 400: 'Data tidak valid.', 403: 'Tidak ada akses.', 404: 'Material/Lokasi tidak ditemukan.' };
        throw new Error(STATUS_MSG[r.status] || `Gagal simpan (HTTP ${r.status})`);
      }
      setReceiveOpen(false); fetchAll();
    } catch (e) { setFormError(e.message); }
    finally { setSaving(false); }
  };

  const doTransfer = async () => {
    setSaving(true); setFormError('');
    try {
      if (!transferForm.material_id || !transferForm.from_location_id || !transferForm.to_location_id) throw new Error('Lengkapi material & kedua lokasi.');
      if (transferForm.from_location_id === transferForm.to_location_id) throw new Error('Lokasi asal dan tujuan tidak boleh sama.');
      if (!(Number(transferForm.qty) > 0)) throw new Error('Qty harus > 0.');
      const r = await fetch('/api/rahaza/material-transfer', { method: 'POST', headers, body: JSON.stringify({ ...transferForm, qty: Number(transferForm.qty) }) });
      if (!r.ok) {
        const STATUS_MSG = { 400: 'Data tidak valid / stok kurang.', 403: 'Tidak ada akses.' };
        throw new Error(STATUS_MSG[r.status] || `Gagal transfer (HTTP ${r.status})`);
      }
      setTransferOpen(false); fetchAll();
    } catch (e) { setFormError(e.message); }
    finally { setSaving(false); }
  };

  if (loading) return (<div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" /></div>);

  return (
    <div className="space-y-5" data-testid="rahaza-stock-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Stok Material</h1>
          <p className="text-muted-foreground text-sm mt-1">Stok benang, aksesoris, dan barang jadi per Gedung / Zona. Transfer A↔B dan penerimaan dicatat di ledger.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={openTransfer} className="border border-[var(--glass-border)]" data-testid="stock-transfer-btn"><ArrowRightLeft className="w-4 h-4 mr-1.5" /> Transfer A↔B</Button>
          <Button onClick={openReceive} data-testid="stock-receive-btn"><ArrowDown className="w-4 h-4 mr-1.5" /> Penerimaan</Button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {['yarn', 'accessory', 'fg'].map(t => {
            const Icon = TYPE_ICON[t] || Package;
            const s = summary.by_type?.[t] || {};
            return (
              <GlassPanel key={t} className="p-3" data-testid={`stock-summary-${t}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Icon className={`w-4 h-4 ${TYPE_COLOR[t]}`} />
                  <span className="text-xs font-semibold text-muted-foreground uppercase">{TYPE_LABEL[t]}</span>
                </div>
                <div className="text-xl font-bold text-foreground">{Number(s.total_qty || 0).toFixed(t === 'yarn' ? 2 : 0)}</div>
                <div className="text-[10px] text-muted-foreground">{s.row_count || 0} baris stok</div>
              </GlassPanel>
            );
          })}
          <GlassPanel className={`p-3 ${summary.low_stock_count > 0 ? 'border-amber-300/30' : ''}`}>
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className={`w-4 h-4 ${summary.low_stock_count > 0 ? 'text-amber-300' : 'text-foreground/30'}`} />
              <span className="text-xs font-semibold text-muted-foreground uppercase">Low Stock</span>
            </div>
            <div className={`text-xl font-bold ${summary.low_stock_count > 0 ? 'text-amber-300' : 'text-foreground'}`}>{summary.low_stock_count}</div>
            <div className="text-[10px] text-muted-foreground">material di bawah min</div>
          </GlassPanel>
        </div>
      )}

      {/* Stock table — DataTable v2 */}
      <DataTable
        tableId="stock"
        loading={loading}
        rows={stocks}
        searchFields={['material_code', 'material_name', 'location_code', 'location_name']}
        filters={[
          { key: 'material_type', label: 'Type', type: 'select',
            options: [
              { value: 'yarn', label: 'Benang' },
              { value: 'accessory', label: 'Aksesoris' },
              { value: 'fg', label: 'Barang Jadi' },
            ] },
          { key: 'location_id', label: 'Lokasi', type: 'select',
            options: locations.map(l => ({ value: l.id, label: `${l.code} · ${l.name}` })) },
          { key: 'status', label: 'Status', type: 'select',
            accessor: (r) => r.below_min ? 'low' : 'ok',
            options: [
              { value: 'ok', label: 'OK' },
              { value: 'low', label: 'Low Stock' },
            ] },
        ]}
        columns={[
          { key: 'material_code', label: 'Material', sortable: true,
            render: (r) => (
              <div>
                <div className="font-mono text-xs">{r.material_code}</div>
                <div className="text-[11px] text-foreground/60">{r.material_name}</div>
              </div>
            ) },
          { key: 'material_type', label: 'Type', sortable: true,
            render: (r) => <span className={`text-xs ${TYPE_COLOR[r.material_type]}`}>{TYPE_LABEL[r.material_type]}</span> },
          { key: 'location', label: 'Lokasi', sortable: true,
            accessor: (r) => `${r.location_code} · ${r.location_name}`,
            render: (r) => <span className="text-foreground/70">{r.location_code} · {r.location_name}</span> },
          { key: 'qty', label: 'Qty', align: 'right', sortable: true,
            render: (r) => <span className="font-mono font-semibold">{Number(r.qty).toFixed(r.unit === 'kg' ? 3 : 2)} <span className="text-foreground/60 text-xs">{r.unit}</span></span> },
          { key: 'min_stock', label: 'Min Stok', align: 'right', sortable: true,
            render: (r) => <span className="text-foreground/60">{r.min_stock || '—'}</span> },
          { key: 'status', label: 'Status',
            accessor: (r) => r.below_min ? 'low' : 'ok',
            render: (r) => r.below_min
              ? <span className="text-[hsl(var(--warning))] text-xs font-medium">Low</span>
              : <span className="text-[hsl(var(--success))] text-xs font-medium">OK</span> },
        ]}
        emptyTitle="Belum ada stok"
        emptyDescription='Mulai dari "Penerimaan" untuk menambah stok ke lokasi.'
        emptyIcon={Package}
        exportFilename={`material-stock-${new Date().toISOString().slice(0,10)}.csv`}
      />

      {/* Movements ledger */}
      <GlassCard className="p-0 overflow-hidden">
        <div className="px-4 py-2 border-b border-[var(--glass-border)] bg-[var(--glass-bg)] flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold text-foreground">Movement Ledger (30 terakhir)</span>
        </div>
        <div className="overflow-x-auto max-h-80">
          <table className="w-full text-xs">
            <thead className="bg-[var(--glass-bg)] sticky top-0">
              <tr className="text-left text-[10px] text-muted-foreground">
                <th className="px-3 py-2">Waktu</th>
                <th className="px-3 py-2">Tipe</th>
                <th className="px-3 py-2">Material</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2">Dari</th>
                <th className="px-3 py-2">Ke</th>
                <th className="px-3 py-2">Ref</th>
              </tr>
            </thead>
            <tbody>
              {movements.length === 0 ? (
                <tr><td colSpan={7} className="text-center py-6 text-muted-foreground">Belum ada movement.</td></tr>
              ) : movements.map(m => (
                <tr key={m.id} className="border-t border-[var(--glass-border)]">
                  <td className="px-3 py-1.5 text-muted-foreground whitespace-nowrap">{new Date(m.timestamp).toLocaleString('id-ID', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</td>
                  <td className="px-3 py-1.5">
                    {m.type === 'receive'  && <span className="text-emerald-300">Receive</span>}
                    {m.type === 'issue'    && <span className="text-red-300">Issue</span>}
                    {m.type === 'transfer' && <span className="text-primary">Transfer</span>}
                    {m.type === 'adjust'   && <span className="text-amber-300">Adjust</span>}
                  </td>
                  <td className="px-3 py-1.5 text-foreground">{m.material_code}</td>
                  <td className="px-3 py-1.5 text-right font-mono font-semibold text-foreground">{Number(m.qty).toFixed(3)} {m.unit || ''}</td>
                  <td className="px-3 py-1.5 text-muted-foreground">{m.from_location_name || '—'}</td>
                  <td className="px-3 py-1.5 text-muted-foreground">{m.to_location_name || '—'}</td>
                  <td className="px-3 py-1.5 text-muted-foreground truncate max-w-[160px]">{m.notes || m.ref_type || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Receive modal */}
      {receiveOpen && (
        <Modal onClose={() => setReceiveOpen(false)} title="Penerimaan Material" size="md">
          <div className="space-y-3" data-testid="receive-form">
            {formError && <div className="bg-red-400/10 border border-red-300/20 rounded-lg p-3 text-sm text-red-300">{formError}</div>}
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Material <span className="text-red-400">*</span></label>
              <select value={receiveForm.material_id} onChange={e => setReceiveForm({...receiveForm, material_id: e.target.value})} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="receive-material">
                <option value="">— Pilih —</option>
                {materials.map(m => <option key={m.id} value={m.id}>{m.code} · {m.name} ({m.unit})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Lokasi Tujuan <span className="text-red-400">*</span></label>
              <select value={receiveForm.location_id} onChange={e => setReceiveForm({...receiveForm, location_id: e.target.value})} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="receive-location">
                <option value="">— Pilih —</option>
                {locations.map(l => <option key={l.id} value={l.id}>{l.code} · {l.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Qty <span className="text-red-400">*</span></label>
              <GlassInput type="number" step="0.001" value={receiveForm.qty} onChange={e => setReceiveForm({...receiveForm, qty: e.target.value})} placeholder="0" data-testid="receive-qty" />
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Catatan</label>
              <GlassInput value={receiveForm.notes} onChange={e => setReceiveForm({...receiveForm, notes: e.target.value})} placeholder="No. surat jalan, supplier, dsb" />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setReceiveOpen(false)} disabled={saving}>Batal</Button>
              <Button onClick={doReceive} disabled={saving} data-testid="receive-submit">{saving ? 'Menyimpan...' : 'Simpan Penerimaan'}</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Transfer modal */}
      {transferOpen && (
        <Modal onClose={() => setTransferOpen(false)} title="Transfer Antar Gudang" size="md">
          <div className="space-y-3" data-testid="transfer-form">
            {formError && <div className="bg-red-400/10 border border-red-300/20 rounded-lg p-3 text-sm text-red-300">{formError}</div>}
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Material <span className="text-red-400">*</span></label>
              <select value={transferForm.material_id} onChange={e => setTransferForm({...transferForm, material_id: e.target.value})} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="transfer-material">
                <option value="">— Pilih —</option>
                {materials.map(m => <option key={m.id} value={m.id}>{m.code} · {m.name} ({m.unit})</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Dari Lokasi <span className="text-red-400">*</span></label>
                <select value={transferForm.from_location_id} onChange={e => setTransferForm({...transferForm, from_location_id: e.target.value})} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="transfer-from">
                  <option value="">—</option>
                  {locations.map(l => <option key={l.id} value={l.id}>{l.code}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Ke Lokasi <span className="text-red-400">*</span></label>
                <select value={transferForm.to_location_id} onChange={e => setTransferForm({...transferForm, to_location_id: e.target.value})} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="transfer-to">
                  <option value="">—</option>
                  {locations.map(l => <option key={l.id} value={l.id}>{l.code}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Qty <span className="text-red-400">*</span></label>
              <GlassInput type="number" step="0.001" value={transferForm.qty} onChange={e => setTransferForm({...transferForm, qty: e.target.value})} placeholder="0" data-testid="transfer-qty" />
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Catatan</label>
              <GlassInput value={transferForm.notes} onChange={e => setTransferForm({...transferForm, notes: e.target.value})} placeholder="Opsional" />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setTransferOpen(false)} disabled={saving}>Batal</Button>
              <Button onClick={doTransfer} disabled={saving} data-testid="transfer-submit">{saving ? 'Menyimpan...' : 'Konfirmasi Transfer'}</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
