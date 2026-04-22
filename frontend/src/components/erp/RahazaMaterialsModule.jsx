import { useState, useEffect, useCallback } from 'react';
import { Plus, Edit2, Trash2, Package, Scale, Gem, Archive } from 'lucide-react';
import { GlassCard, GlassInput } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import Modal from './Modal';

const TYPE_META = {
  yarn:      { label: 'Benang',    icon: Scale,  color: 'text-amber-300',    bg: 'bg-amber-400/10',    border: 'border-amber-300/20' },
  accessory: { label: 'Aksesoris', icon: Gem,    color: 'text-primary',      bg: 'bg-primary/10',      border: 'border-primary/25' },
  fg:        { label: 'Barang Jadi', icon: Archive, color: 'text-emerald-300', bg: 'bg-emerald-400/10', border: 'border-emerald-300/20' },
};

export default function RahazaMaterialsModule({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [filterType, setFilterType] = useState('');
  const [form, setForm] = useState({
    code: '', name: '', type: 'yarn', unit: 'kg', yarn_type: '', color: '', notes: '', min_stock: 0, active: true,
  });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchRows = useCallback(async () => {
    setLoading(true);
    try {
      const q = filterType ? `?type=${filterType}` : '';
      const r = await fetch(`/api/rahaza/materials${q}`, { headers });
      if (r.ok) setRows(await r.json());
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, filterType]);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  const openCreate = () => {
    setEditing(null);
    setForm({ code: '', name: '', type: 'yarn', unit: 'kg', yarn_type: '', color: '', notes: '', min_stock: 0, active: true });
    setFormError(''); setModalOpen(true);
  };
  const openEdit = (r) => {
    setEditing(r); setForm({ ...r });
    setFormError(''); setModalOpen(true);
  };
  const save = async () => {
    setSaving(true); setFormError('');
    try {
      if (!form.code || !form.name) throw new Error('Kode & nama wajib diisi.');
      const url = editing ? `/api/rahaza/materials/${editing.id}` : '/api/rahaza/materials';
      const method = editing ? 'PUT' : 'POST';
      const res = await fetch(url, { method, headers, body: JSON.stringify({ ...form, min_stock: Number(form.min_stock) || 0 }) });
      if (!res.ok) {
        const STATUS_MSG = { 400: 'Data tidak valid.', 403: 'Tidak ada akses.', 409: 'Kode sudah terpakai.' };
        throw new Error(STATUS_MSG[res.status] || `Gagal simpan (HTTP ${res.status})`);
      }
      setModalOpen(false); fetchRows();
    } catch (e) { setFormError(e.message); }
    finally { setSaving(false); }
  };
  const remove = async (r) => {
    if (!window.confirm(`Nonaktifkan material ${r.code}?`)) return;
    await fetch(`/api/rahaza/materials/${r.id}`, { method: 'DELETE', headers });
    fetchRows();
  };

  if (loading) return (<div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" /></div>);

  return (
    <div className="space-y-5" data-testid="rahaza-materials-page">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Master Material</h1>
          <p className="text-muted-foreground text-sm mt-1">Benang, aksesoris, dan barang jadi. Dipakai di Stock, Material Issue, dan WO.</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={filterType} onChange={e => setFilterType(e.target.value)} className="h-9 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="mat-filter-type">
            <option value="">Semua Type</option>
            <option value="yarn">Benang</option>
            <option value="accessory">Aksesoris</option>
            <option value="fg">Barang Jadi</option>
          </select>
          <Button onClick={openCreate} data-testid="mat-add-btn"><Plus className="w-4 h-4 mr-1.5" /> Material Baru</Button>
        </div>
      </div>

      <GlassCard className="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--glass-bg)]">
              <tr className="text-left text-xs text-muted-foreground">
                <th className="px-4 py-3">Kode</th>
                <th className="px-4 py-3">Nama</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Unit</th>
                <th className="px-4 py-3">Min Stok</th>
                <th className="px-4 py-3">Warna/Jenis</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-12 text-muted-foreground">Belum ada material. Klik "Material Baru" untuk menambah.</td></tr>
              ) : rows.map(r => {
                const meta = TYPE_META[r.type] || {};
                const Icon = meta.icon || Package;
                return (
                  <tr key={r.id} className={`border-t border-[var(--glass-border)] hover:bg-[var(--glass-bg-hover)] ${!r.active ? 'opacity-50' : ''}`} data-testid={`mat-row-${r.code}`}>
                    <td className="px-4 py-3 font-mono text-xs text-foreground">{r.code}</td>
                    <td className="px-4 py-3 text-foreground">{r.name}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${meta.bg} ${meta.border} border ${meta.color}`}>
                        <Icon className="w-3 h-3" /> {meta.label || r.type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{r.unit}</td>
                    <td className="px-4 py-3 text-muted-foreground">{r.min_stock || 0}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{r.color || r.yarn_type || '—'}</td>
                    <td className="px-4 py-3">{r.active ? <span className="text-emerald-300 text-xs">Aktif</span> : <span className="text-muted-foreground text-xs">Non-aktif</span>}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1">
                        <button onClick={() => openEdit(r)} className="p-1.5 rounded hover:bg-[var(--glass-bg-hover)] text-muted-foreground hover:text-foreground" title="Edit" data-testid={`mat-edit-${r.code}`}><Edit2 className="w-3.5 h-3.5" /></button>
                        {r.active && <button onClick={() => remove(r)} className="p-1.5 rounded hover:bg-red-400/10 text-muted-foreground hover:text-red-400" title="Nonaktifkan"><Trash2 className="w-3.5 h-3.5" /></button>}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {modalOpen && (
        <Modal onClose={() => setModalOpen(false)} title={editing ? `Edit ${editing.code}` : 'Material Baru'} size="md">
          <div className="space-y-3" data-testid="mat-form">
            {formError && <div className="bg-red-400/10 border border-red-300/20 rounded-lg p-3 text-sm text-red-300">{formError}</div>}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Kode <span className="text-red-400">*</span></label>
                <GlassInput value={form.code} onChange={e => setForm({...form, code: e.target.value.toUpperCase()})} placeholder="YRN-ACR28" data-testid="mat-field-code" />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Type <span className="text-red-400">*</span></label>
                <select value={form.type} onChange={e => setForm({...form, type: e.target.value, unit: e.target.value === 'yarn' ? 'kg' : 'pcs'})} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="mat-field-type">
                  <option value="yarn">Benang</option>
                  <option value="accessory">Aksesoris</option>
                  <option value="fg">Barang Jadi</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Nama <span className="text-red-400">*</span></label>
              <GlassInput value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Benang Acrylic 2/28" data-testid="mat-field-name" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Unit</label>
                <select value={form.unit} onChange={e => setForm({...form, unit: e.target.value})} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground">
                  {['kg','pcs','m','set','pair','gram'].map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Min Stok</label>
                <GlassInput type="number" step="0.1" value={form.min_stock} onChange={e => setForm({...form, min_stock: e.target.value})} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Jenis/Komposisi</label>
                <GlassInput value={form.yarn_type} onChange={e => setForm({...form, yarn_type: e.target.value})} placeholder="Acrylic 100%" />
              </div>
              <div>
                <label className="block text-xs font-medium text-foreground/70 mb-1">Warna</label>
                <GlassInput value={form.color} onChange={e => setForm({...form, color: e.target.value})} placeholder="Navy" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-foreground/70 mb-1">Catatan</label>
              <GlassInput value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="Opsional" />
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={saving}>Batal</Button>
              <Button onClick={save} disabled={saving} data-testid="mat-save-btn">{saving ? 'Menyimpan...' : 'Simpan'}</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
