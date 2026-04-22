
import { useState, useEffect } from 'react';
import { Eye, Pencil, Trash2 } from 'lucide-react';
import DataTable from './DataTable';
import Modal from './Modal';
import StatusBadge from './StatusBadge';
import ConfirmDialog from './ConfirmDialog';

export default function InvoiceModule({ token, userRole, onNavigate }) {
  const [invoices, setInvoices] = useState([]);
  const [showDetail, setShowDetail] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [filterStatus, setFilterStatus] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);

  const isSuperAdmin = userRole === 'superadmin';

  useEffect(() => { fetchInvoices(); }, []);

  const fetchInvoices = async () => {
    let url = '/api/invoices';
    if (filterStatus) url += `?status=${filterStatus}`;
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    setInvoices(Array.isArray(data) ? data : []);
  };

  const openDetail = async (row) => {
    const res = await fetch(`/api/invoices/${row.id}`, { headers: { Authorization: `Bearer ${token}` } });
    setDetailData(await res.json());
    setShowDetail(true);
  };

  const openEdit = (row) => {
    setEditForm({ ...row });
    setShowEdit(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    const res = await fetch(`/api/invoices/${editForm.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(editForm)
    });
    if (res.ok) {
      alert('✅ Invoice berhasil diupdate');
      setShowEdit(false);
      fetchInvoices();
    } else {
      const err = await res.json();
      alert(`❌ Gagal update invoice: ${err.detail || 'Unknown error'}`);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    await fetch(`/api/invoices/${confirmDelete.id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    });
    setConfirmDelete(null);
    fetchInvoices();
  };

  const fmt = (v) => 'Rp ' + (v||0).toLocaleString('id-ID');
  const fmtDate = (d) => d ? new Date(d).toLocaleDateString('id-ID') : '-';

  const totalUnpaid = invoices.filter(i=>i.status==='Unpaid').reduce((s,i)=>s+(i.total_amount||0),0);
  const totalPartial = invoices.filter(i=>i.status==='Partial').reduce((s,i)=>s+((i.total_amount||0)-(i.total_paid||0)),0);

  const columns = [
    { key: 'invoice_number', label: 'No. Invoice', render: (v) => <span className="font-bold text-primary">{v}</span> },
    { key: 'po_number', label: 'No. PO' },
    { key: 'garment_name', label: 'Garmen' },
    { key: 'produced_quantity', label: 'Qty', render: (v) => v?.toLocaleString('id-ID') },
    { key: 'cmt_price', label: 'CMT/pcs', render: (v) => fmt(v) },
    { key: 'total_amount', label: 'Total', render: (v) => <span className="font-bold">{fmt(v)}</span> },
    { key: 'total_paid', label: 'Terbayar', render: (v) => <span className="text-emerald-700 font-medium">{fmt(v)}</span> },
    { key: 'status', label: 'Status', render: (v) => <StatusBadge status={v} /> },
    { key: 'created_at', label: 'Tanggal', render: (v) => fmtDate(v) },
    {
      key: 'actions', label: 'Aksi',
      render: (_, row) => (
        <div className="flex items-center gap-1">
          <button onClick={() => openDetail(row)} className="p-1.5 rounded hover:bg-primary/10 text-primary" title="Detail">
            <Eye className="w-4 h-4" />
          </button>
          {isSuperAdmin && (
            <>
              <button onClick={() => openEdit(row)} className="p-1.5 rounded hover:bg-amber-50 text-amber-600" title="Edit">
                <Pencil className="w-4 h-4" />
              </button>
              <button onClick={() => setConfirmDelete(row)} className="p-1.5 rounded hover:bg-red-50 text-red-500" title="Hapus">
                <Trash2 className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      )
    }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Manajemen Invoice</h1>
          <p className="text-muted-foreground text-sm mt-1">Kelola semua invoice vendor dan buyer — Manual & Adjustment</p>
        </div>
        {isSuperAdmin && (
          <span className="flex items-center gap-1.5 px-2.5 py-1 bg-purple-100 text-purple-700 rounded-lg text-xs font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span>
            Mode Superadmin
          </span>
        )}
      </div>

      {(totalUnpaid > 0 || totalPartial > 0) && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-red-50 border border-red-200 rounded-xl p-4">
            <p className="text-sm text-red-600">Belum Dibayar</p>
            <p className="text-xl font-bold text-red-700 mt-1">{fmt(totalUnpaid)}</p>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-sm text-amber-600">Sebagian Dibayar</p>
            <p className="text-xl font-bold text-amber-700 mt-1">{fmt(totalPartial)}</p>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        {['','Unpaid','Partial','Paid'].map(s => (
          <button key={s} onClick={() => { setFilterStatus(s); setTimeout(fetchInvoices, 0); }}
            className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
              filterStatus===s ? 'bg-primary text-white border-blue-600' : 'border-border text-muted-foreground hover:bg-[var(--glass-bg)]'
            }`}>{s || 'Semua'}</button>
        ))}
      </div>

      <DataTable columns={columns} data={invoices} searchKeys={['invoice_number','garment_name','po_number']} />

      {showEdit && isSuperAdmin && (
        <Modal title="Edit Invoice" onClose={() => setShowEdit(false)}>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-[var(--glass-bg)] rounded-lg p-3"><p className="text-xs text-muted-foreground">No. Invoice</p><p className="font-bold">{editForm.invoice_number}</p></div>
              <div className="bg-[var(--glass-bg)] rounded-lg p-3"><p className="text-xs text-muted-foreground">Garmen</p><p className="font-medium">{editForm.garment_name}</p></div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Qty Produksi</label>
                <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={editForm.produced_quantity||''} onChange={e => setEditForm({...editForm, produced_quantity: Number(e.target.value), total_amount: Number(e.target.value)*(editForm.cmt_price||0)})} />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">CMT Price</label>
                <input type="number" className="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={editForm.cmt_price||''} onChange={e => setEditForm({...editForm, cmt_price: Number(e.target.value), total_amount: (editForm.produced_quantity||0)*Number(e.target.value)})} />
              </div>
            </div>
            <div className="bg-primary/10 rounded-lg p-3 text-sm">
              Total: <span className="font-bold">{fmt(editForm.total_amount)}</span>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Status</label>
              <select className="w-full border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                value={editForm.status} onChange={e => setEditForm({...editForm, status: e.target.value})}>
                <option value="Unpaid">Unpaid</option>
                <option value="Partial">Partial</option>
                <option value="Paid">Paid</option>
              </select>
            </div>
            <div className="flex gap-3">
              <button type="submit" className="flex-1 bg-primary text-white py-2 rounded-lg text-sm font-medium hover:brightness-110">Simpan</button>
              <button type="button" onClick={() => setShowEdit(false)} className="flex-1 border border-border py-2 rounded-lg text-sm">Batal</button>
            </div>
          </form>
        </Modal>
      )}

      {showDetail && detailData && (
        <Modal title={`Invoice: ${detailData.invoice_number}`} onClose={() => setShowDetail(false)} size="lg">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              {[{l:'No. Invoice',v:detailData.invoice_number},{l:'No. PO',v:detailData.po_number},
                {l:'Garmen',v:detailData.garment_name},{l:'Produk',v:detailData.product_name},
                {l:'Qty Diproduksi',v:`${detailData.produced_quantity?.toLocaleString('id-ID')} pcs`},
                {l:'CMT Price',v:fmt(detailData.cmt_price)}].map(item => (
                <div key={item.l} className="bg-[var(--glass-bg)] rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">{item.l}</p>
                  <p className="font-medium text-sm mt-0.5">{item.v}</p>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-primary/10 rounded-lg p-3"><p className="text-xs text-primary">Total Invoice</p><p className="font-bold text-blue-800">{fmt(detailData.total_amount)}</p></div>
              <div className="bg-emerald-50 rounded-lg p-3"><p className="text-xs text-emerald-600">Terbayar</p><p className="font-bold text-emerald-800">{fmt(detailData.total_paid)}</p></div>
              <div className="bg-orange-50 rounded-lg p-3"><p className="text-xs text-orange-600">Sisa</p><p className="font-bold text-orange-800">{fmt((detailData.total_amount||0)-(detailData.total_paid||0))}</p></div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-foreground">Status:</span>
              <StatusBadge status={detailData.status} />
            </div>
            {detailData.payments?.length > 0 && (
              <div>
                <h4 className="font-semibold text-foreground mb-2">Riwayat Pembayaran</h4>
                <div className="space-y-2">
                  {detailData.payments.map(p => (
                    <div key={p.id} className="flex justify-between items-center p-2.5 border border-border rounded-lg">
                      <div>
                        <p className="text-sm font-medium">{fmtDate(p.payment_date)}</p>
                        <p className="text-xs text-muted-foreground">{p.payment_method} {p.reference && `- ${p.reference}`}</p>
                      </div>
                      <span className="font-bold text-emerald-700">{fmt(p.amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {detailData.status !== 'Paid' && (
              <button onClick={() => { setShowDetail(false); onNavigate && onNavigate('payments', detailData); }}
                className="w-full bg-emerald-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-emerald-700">
                Catat Pembayaran
              </button>
            )}
          </div>
        </Modal>
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Hapus Invoice?"
          message={`Invoice "${confirmDelete.invoice_number}" dan semua data pembayaran terkait akan dihapus permanen.`}
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}
