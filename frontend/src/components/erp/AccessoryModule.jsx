import { useState, useEffect, useCallback } from 'react';
import { Plus, Edit2, Trash2, Package, Search, X } from 'lucide-react';

export default function AccessoryModule({ token, userRole }) {
  const [accessories, setAccessories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [form, setForm] = useState({ name: '', code: '', category: '', unit: 'pcs', description: '' });
  const [search, setSearch] = useState('');

  const fetchAccessories = useCallback(async () => {
    setLoading(true);
    try {
      const params = search ? `?search=${encodeURIComponent(search)}` : '';
      const res = await fetch(`/api/accessories${params}`, { headers: { Authorization: `Bearer ${token}` } });
      setAccessories(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [token, search]);

  useEffect(() => { fetchAccessories(); }, [fetchAccessories]);

  const handleSave = async () => {
    const method = editItem ? 'PUT' : 'POST';
    const url = editItem ? `/api/accessories/${editItem.id}` : '/api/accessories';
    try {
      const res = await fetch(url, {
        method, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(form)
      });
      if (res.ok) { fetchAccessories(); setShowForm(false); setEditItem(null); setForm({ name: '', code: '', category: '', unit: 'pcs', description: '' }); }
    } catch (e) { console.error(e); }
  };

  const handleEdit = (item) => {
    setEditItem(item);
    setForm({ name: item.name || '', code: item.code || '', category: item.category || '', unit: item.unit || 'pcs', description: item.description || '' });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Hapus aksesoris ini?')) return;
    await fetch(`/api/accessories/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } });
    fetchAccessories();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Data Aksesoris</h2>
          <p className="text-muted-foreground text-sm mt-1">Kelola master data aksesoris untuk produksi garmen</p>
        </div>
        <button onClick={() => { setShowForm(true); setEditItem(null); setForm({ name: '', code: '', category: '', unit: 'pcs', description: '' }); }}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:brightness-110 transition" data-testid="add-accessory-btn">
          <Plus className="w-4 h-4" /> Tambah Aksesoris
        </button>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2 border border-border rounded-lg px-3 py-2 bg-[var(--card-surface)] max-w-md">
        <Search className="w-4 h-4 text-muted-foreground" />
        <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari aksesoris..."
               className="flex-1 bg-transparent text-sm focus:outline-none" data-testid="accessory-search" />
        {search && <button onClick={() => setSearch('')}><X className="w-4 h-4 text-muted-foreground" /></button>}
      </div>

      {/* Table */}
      <div className="bg-[var(--card-surface)] rounded-xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--glass-bg)] border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Kode</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Nama</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Kategori</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Unit</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Aksi</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="6" className="text-center py-8 text-muted-foreground">Memuat...</td></tr>
            ) : accessories.length === 0 ? (
              <tr><td colSpan="6" className="text-center py-8 text-muted-foreground">Belum ada aksesoris</td></tr>
            ) : accessories.map(acc => (
              <tr key={acc.id} className="border-b border-border hover:bg-[var(--glass-bg)]">
                <td className="px-4 py-3 font-medium text-foreground">{acc.code || '-'}</td>
                <td className="px-4 py-3">{acc.name}</td>
                <td className="px-4 py-3">{acc.category || '-'}</td>
                <td className="px-4 py-3">{acc.unit || 'pcs'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${acc.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-secondary text-muted-foreground'}`}>
                    {acc.status || 'active'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => handleEdit(acc)} className="p-1 hover:bg-[var(--glass-bg-hover)] rounded" data-testid={`edit-acc-${acc.id}`}><Edit2 className="w-4 h-4 text-muted-foreground" /></button>
                  {userRole === 'superadmin' && (
                    <button onClick={() => handleDelete(acc.id)} className="p-1 hover:bg-red-50 rounded ml-1" data-testid={`del-acc-${acc.id}`}><Trash2 className="w-4 h-4 text-red-500" /></button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal Form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={() => setShowForm(false)}>
          <div className="bg-[var(--card-surface)] rounded-2xl shadow-xl w-full max-w-md p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-foreground mb-4">{editItem ? 'Edit Aksesoris' : 'Tambah Aksesoris'}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-muted-foreground block mb-1">Kode</label>
                <input value={form.code} onChange={e => setForm({...form, code: e.target.value})}
                       className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="ACC-001" data-testid="acc-code" />
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground block mb-1">Nama *</label>
                <input value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                       className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Kancing" data-testid="acc-name" />
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground block mb-1">Kategori</label>
                <input value={form.category} onChange={e => setForm({...form, category: e.target.value})}
                       className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="Trimming" />
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground block mb-1">Unit</label>
                <select value={form.unit} onChange={e => setForm({...form, unit: e.target.value})}
                        className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="pcs">Pcs</option>
                  <option value="meter">Meter</option>
                  <option value="roll">Roll</option>
                  <option value="yard">Yard</option>
                  <option value="kg">Kg</option>
                  <option value="set">Set</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground block mb-1">Deskripsi</label>
                <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                          className="w-full border rounded-lg px-3 py-2 text-sm" rows="2" placeholder="Deskripsi..." />
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button onClick={() => setShowForm(false)} className="flex-1 py-2 border rounded-lg text-sm text-muted-foreground hover:bg-[var(--glass-bg)]">Batal</button>
              <button onClick={handleSave} disabled={!form.name} className="flex-1 py-2 bg-primary text-white rounded-lg text-sm hover:brightness-110 disabled:opacity-50" data-testid="save-accessory-btn">Simpan</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
