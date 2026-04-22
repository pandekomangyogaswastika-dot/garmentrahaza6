
import { useState, useEffect } from 'react';
import { Plus, FileText, RefreshCw, Eye, Edit3, ChevronRight, AlertCircle, AlertTriangle, CheckCircle, Pencil, ArrowUpCircle, ArrowDownCircle, Trash2, History, Send } from 'lucide-react';
import Modal from './Modal';
import SearchableSelect from './SearchableSelect';
import ImportExportPanel from './ImportExportPanel';

const CATEGORY_COLORS = {
  VENDOR: 'bg-amber-100 text-amber-700 border border-amber-200',
  BUYER: 'bg-primary/15 text-primary border border-primary/20',
};
const TYPE_COLORS = {
  MANUAL: 'bg-purple-100 text-purple-700 border border-purple-200',
  AUTO_GENERATED: 'bg-secondary text-muted-foreground border border-border',
};
const STATUS_COLORS = {
  Unpaid: 'bg-red-100 text-red-700', Partial: 'bg-amber-100 text-amber-700',
  Paid: 'bg-emerald-100 text-emerald-700', Draft: 'bg-secondary text-muted-foreground',
  Superseded: 'bg-pink-100 text-pink-700 line-through',
};

const fmt = (v) => 'Rp ' + Number(v || 0).toLocaleString('id-ID');
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('id-ID') : '-';

export default function ManualInvoiceModule({ token, userRole }) {
  const [invoices, setInvoices] = useState([]);
  const [pos, setPos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterCat, setFilterCat] = useState('');
  const [filterType, setFilterType] = useState('MANUAL'); // default show MANUAL
  const [filterStatus, setFilterStatus] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showDetail, setShowDetail] = useState(false);
  const [showRevise, setShowRevise] = useState(false);
  const [selectedInv, setSelectedInv] = useState(null);
  const [saving, setSaving] = useState(false);

  // Create form
  const [createForm, setCreateForm] = useState({
    source_po_id: '', invoice_category: 'BUYER', notes: '', discount: 0
  });
  const [poItems, setPoItems] = useState([]);
  const [invoiceItems, setInvoiceItems] = useState([]);
  const [variances, setVariances] = useState([]); // NEW: variance data for selected PO

  // Revise form
  const [reviseForm, setReviseForm] = useState({ change_reason: '', invoice_items: [] });

  // Adjustment form
  const [showAdjustment, setShowAdjustment] = useState(false);
  const [adjForm, setAdjForm] = useState({ adjustment_type: 'ADD', amount: '', reason: '', notes: '', reference_event: '' });
  const [adjSaving, setAdjSaving] = useState(false);

  // Request Edit form
  const [showRequestEdit, setShowRequestEdit] = useState(false);
  const [requestEditForm, setRequestEditForm] = useState({
    invoice_items: [],
    discount: 0,
    notes: '',
    change_summary: ''
  });
  const [requestEditSaving, setRequestEditSaving] = useState(false);

  // Change History
  const [showHistory, setShowHistory] = useState(false);
  const [changeHistory, setChangeHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const canEdit = ['superadmin', 'admin', 'finance'].includes(userRole);

  useEffect(() => { fetchAll(); }, [filterCat, filterType, filterStatus]);

  const fetchAll = async () => {
    setLoading(true);
    try {
      let url = '/api/invoices?';
      const params = [];
      if (filterCat) params.push(`category=${filterCat}`);
      if (filterType) params.push(`invoice_type=${filterType}`);
      if (filterStatus) params.push(`status=${filterStatus}`);
      const res = await fetch(url + params.join('&'), { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setInvoices(Array.isArray(data) ? data : []);
    } catch (e) { setInvoices([]); } finally { setLoading(false); }
  };

  const fetchPOs = async () => {
    const res = await fetch('/api/production-pos', { headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    setPos(Array.isArray(data) ? data.filter(p => p.status !== 'Closed') : []);
  };

  const loadPOItems = async (poId) => {
    if (!poId) { setPoItems([]); setInvoiceItems([]); setVariances([]); return; }
    setCreateForm(f => ({ ...f, source_po_id: poId }));
    const res = await fetch(`/api/po-items?po_id=${poId}`, { headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    const items = Array.isArray(data) ? data : [];
    setPoItems(items);
    setInvoiceItems(items.map(it => ({
      sku: it.sku, product_name: it.product_name, size: it.size, color: it.color,
      ordered_qty: it.qty, invoice_qty: it.qty,
      selling_price: it.selling_price_snapshot || 0,
      cmt_price: it.cmt_price_snapshot || 0,
      po_item_id: it.id,
    })));
    
    // Fetch variances for this PO (Acknowledged or Resolved status)
    const varRes = await fetch(`/api/production-variances?po_id=${poId}`, { headers: { Authorization: `Bearer ${token}` } });
    const varData = await varRes.json();
    const approvedVars = Array.isArray(varData) ? varData.filter(v => ['Acknowledged', 'Resolved'].includes(v.status)) : [];
    setVariances(approvedVars);
  };

  const openCreate = async () => {
    await fetchPOs();
    setCreateForm({ source_po_id: '', invoice_category: 'BUYER', notes: '', discount: 0 });
    setPoItems([]); setInvoiceItems([]);
    setShowCreate(true);
  };

  const updateItem = (idx, field, value) => {
    setInvoiceItems(items => {
      const next = [...items];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const getSubtotal = (item) => {
    const qty = Number(item.invoice_qty) || 0;
    const price = createForm.invoice_category === 'VENDOR' ? (Number(item.cmt_price) || 0) : (Number(item.selling_price) || 0);
    return qty * price;
  };

  const getReviseSubtotal = (item) => {
    const qty = Number(item.invoice_qty) || 0;
    const price = selectedInv?.invoice_category === 'VENDOR' ? (Number(item.cmt_price) || 0) : (Number(item.selling_price) || 0);
    return qty * price;
  };

  const totalBeforeDiscount = invoiceItems.reduce((s, it) => s + getSubtotal(it), 0);
  const discountAmt = Number(createForm.discount) || 0;
  const totalAfterDiscount = totalBeforeDiscount - discountAmt;


  // Request Edit functions
  const openRequestEdit = (inv) => {
    setSelectedInv(inv);
    setRequestEditForm({
      invoice_items: (inv.invoice_items || []).map(it => ({ ...it })),
      discount: inv.discount || 0,
      notes: inv.notes || '',
      change_summary: ''
    });
    setShowRequestEdit(true);
  };

  const updateRequestEditItem = (idx, field, value) => {
    setRequestEditForm(f => {
      const items = [...f.invoice_items];
      items[idx] = { ...items[idx], [field]: value };
      return { ...f, invoice_items: items };
    });
  };

  const getRequestEditSubtotal = (item) => {
    const qty = Number(item.invoice_qty) || 0;
    const price = selectedInv?.invoice_category === 'VENDOR' ? (Number(item.cmt_price) || 0) : (Number(item.selling_price) || 0);
    return qty * price;
  };

  const requestEditTotalBeforeDiscount = requestEditForm.invoice_items.reduce((s, it) => s + getRequestEditSubtotal(it), 0);
  const requestEditTotalAfterDiscount = requestEditTotalBeforeDiscount - Number(requestEditForm.discount || 0);

  const handleRequestEdit = async (e) => {
    e.preventDefault();
    if (!requestEditForm.change_summary.trim()) {
      alert('Ringkasan perubahan wajib diisi');
      return;
    }
    if (!confirm(`Submit request edit untuk invoice ${selectedInv.invoice_number}?\n\nInvoice tidak akan berubah sampai request di-approve oleh Superadmin/Admin.`)) return;
    setRequestEditSaving(true);
    try {
      const res = await fetch('/api/invoice-edit-requests', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          invoice_id: selectedInv.id,
          change_summary: requestEditForm.change_summary,
          changes_requested: {
            invoice_items: requestEditForm.invoice_items,
            discount: Number(requestEditForm.discount),
            notes: requestEditForm.notes,
            total_amount: requestEditTotalAfterDiscount
          }
        })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Gagal submit request edit');
      } else {
        alert('Request edit berhasil disubmit! Tunggu approval dari Superadmin/Admin.');
        setShowRequestEdit(false);
        fetchAll();
      }
    } catch (e) {
      alert('Error: ' + e.message);
    } finally {
      setRequestEditSaving(false);
    }
  };

  // Change History functions
  const openHistory = async (inv) => {
    setSelectedInv(inv);
    setShowHistory(true);
    setHistoryLoading(true);
    try {
      const res = await fetch(`/api/invoices/${inv.id}/change-history`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await res.json();
      setChangeHistory(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Error fetching history:', e);
      setChangeHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createForm.source_po_id) { alert('Pilih Production PO terlebih dahulu'); return; }
    if (invoiceItems.length === 0) { alert('Tidak ada item PO'); return; }
    setSaving(true);
    const res = await fetch('/api/invoices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...createForm, invoice_items: invoiceItems, total_amount: totalAfterDiscount })
    });
    const data = await res.json();
    setSaving(false);
    if (!res.ok) { alert(data.error || 'Gagal membuat invoice'); return; }
    setShowCreate(false);
    fetchAll();
  };

  const openDetail = async (inv) => {
    const res = await fetch(`/api/invoices/${inv.id}`, { headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    setSelectedInv(data);
    
    // Fetch variances for this PO (if has PO)
    if (data.source_po_id || data.po_id) {
      const poId = data.source_po_id || data.po_id;
      try {
        const varRes = await fetch(`/api/production-variances?po_id=${poId}`, { headers: { Authorization: `Bearer ${token}` } });
        const varData = await varRes.json();
        const approvedVars = Array.isArray(varData) ? varData.filter(v => ['Acknowledged', 'Resolved'].includes(v.status)) : [];
        setVariances(approvedVars);
      } catch (e) {
        console.error('Error fetching variances:', e);
        setVariances([]);
      }
    } else {
      setVariances([]);
    }
    
    setShowDetail(true);
  };

  const openRevise = (inv) => {
    setSelectedInv(inv);
    setReviseForm({
      change_reason: '',
      invoice_items: (inv.invoice_items || []).map(it => ({ ...it }))
    });
    setShowRevise(true);
  };

  const updateReviseItem = (idx, field, value) => {
    setReviseForm(f => {
      const items = [...f.invoice_items];
      items[idx] = { ...items[idx], [field]: value };
      return { ...f, invoice_items: items };
    });
  };

  const reviseTotalBeforeDiscount = reviseForm.invoice_items.reduce((s, it) => s + getReviseSubtotal(it), 0);

  const handleRevise = async (e) => {
    e.preventDefault();
    setSaving(true);
    const res = await fetch(`/api/invoices/${selectedInv.id}/revise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...reviseForm, total_amount: reviseTotalBeforeDiscount })
    });
    const data = await res.json();
    setSaving(false);
    if (!res.ok) { alert(data.error || 'Gagal merevisi invoice'); return; }
    setShowRevise(false);
    fetchAll();
  };

  const handleAddAdjustment = async (e) => {
    e.preventDefault();
    if (!adjForm.amount || Number(adjForm.amount) <= 0) { alert('Jumlah harus lebih dari 0'); return; }
    if (!adjForm.reason) { alert('Alasan wajib diisi'); return; }
    setAdjSaving(true);
    try {
      const res = await fetch('/api/invoice-adjustments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ invoice_id: selectedInv.id, ...adjForm, amount: Number(adjForm.amount) })
      });
      const data = await res.json();
      if (!res.ok) { alert(data.error || 'Gagal menambahkan adjustment'); }
      else {
        setShowAdjustment(false);
        setAdjForm({ adjustment_type: 'ADD', amount: '', reason: '', notes: '', reference_event: '' });
        // Refresh detail
        openDetail(selectedInv);
        fetchAll();
      }
    } catch (err) { alert('Error: ' + err.message); }
    setAdjSaving(false);
  };

  const handleDeleteAdjustment = async (adjId) => {
    if (!confirm('Hapus adjustment ini?')) return;
    try {
      const res = await fetch(`/api/invoice-adjustments/${adjId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        openDetail(selectedInv);
        fetchAll();
      }
    } catch (err) { alert('Error: ' + err.message); }
  };

  const filtered = invoices;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Invoice Manual</h1>
          <p className="text-muted-foreground text-sm mt-1">Buat invoice manual dengan qty/harga yang bisa disesuaikan. Invoice manual menjadi dokumen resmi menggantikan invoice otomatis.</p>
        </div>
        <div className="flex items-center gap-2">
          <ImportExportPanel token={token} importType={null} exportType="invoices" />
          {canEdit && (
            <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700">
              <Plus className="w-4 h-4" /> Buat Invoice Manual
            </button>
          )}
        </div>
      </div>

      {/* Info box */}
      <div className="bg-primary/10 border border-primary/20 rounded-xl p-4 text-sm text-primary">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-semibold">Cara Kerja Invoice Manual:</p>
            <p className="mt-1">1. Invoice <span className="font-bold">AUTO_GENERATED</span> dibuat otomatis saat PO dikonfirmasi berdasarkan qty & harga PO.</p>
            <p>2. Invoice <span className="font-bold">MANUAL</span> memungkinkan penyesuaian qty, harga, atau diskon (misal: negosiasi, variansi produksi).</p>
            <p>3. Jika invoice MANUAL dibuat, invoice tersebut menjadi <span className="font-bold">dokumen resmi</span> untuk pembayaran.</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1">
          {['', 'AUTO_GENERATED', 'MANUAL'].map(t => (
            <button key={t} onClick={() => setFilterType(t)}
              className={`px-3 py-1.5 rounded-lg text-sm border ${filterType === t ? 'bg-primary text-white border-blue-600' : 'border-border text-muted-foreground hover:bg-[var(--glass-bg)]'}`}>
              {t || 'Semua Tipe'}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {['', 'VENDOR', 'BUYER'].map(c => (
            <button key={c} onClick={() => setFilterCat(c)}
              className={`px-3 py-1.5 rounded-lg text-sm border ${filterCat === c ? 'bg-primary text-white border-blue-600' : 'border-border text-muted-foreground hover:bg-[var(--glass-bg)]'}`}>
              {c || 'Semua Kategori'}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {['', 'Unpaid', 'Partial', 'Paid'].map(s => (
            <button key={s} onClick={() => setFilterStatus(s)}
              className={`px-3 py-1.5 rounded-lg text-sm border ${filterStatus === s ? 'bg-primary text-white border-blue-600' : 'border-border text-muted-foreground hover:bg-[var(--glass-bg)]'}`}>
              {s || 'Semua Status'}
            </button>
          ))}
        </div>
        <button onClick={fetchAll} className="ml-auto flex items-center gap-1 px-3 py-1.5 border border-border rounded-lg text-sm hover:bg-[var(--glass-bg)]">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Invoice Table */}
      {loading ? (
        <div className="text-center py-16"><RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-muted-foreground" /><p className="text-muted-foreground">Memuat...</p></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Tidak ada invoice ditemukan</p>
        </div>
      ) : (
        <div className="bg-[var(--card-surface)] rounded-xl border border-border overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-[var(--glass-bg)] border-b">
              <tr>
                {['No. Invoice', 'Kategori', 'Tipe', 'No. PO', 'Vendor / Customer', 'Total', 'Dibayar', 'Sisa', 'Status', 'Aksi'].map(h => (
                  <th key={h} className="text-left px-3 py-3 text-xs font-semibold text-muted-foreground uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map(inv => {
                const outstanding = (inv.total_amount || 0) - (inv.total_paid || 0);
                return (
                  <tr key={inv.id} className={`hover:bg-[var(--glass-bg)] ${inv.status === 'Superseded' ? 'opacity-50' : ''}`}>
                    <td className="px-3 py-3 font-bold text-primary">{inv.invoice_number}</td>
                    <td className="px-3 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${CATEGORY_COLORS[inv.invoice_category] || 'bg-secondary text-muted-foreground'}`}>
                        {inv.invoice_category || 'N/A'}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[inv.invoice_type] || 'bg-secondary text-muted-foreground'}`}>
                        {inv.invoice_type === 'AUTO_GENERATED' ? 'AUTO' : inv.invoice_type || 'N/A'}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-muted-foreground">{inv.po_number || '-'}</td>
                    <td className="px-3 py-3 text-foreground">{inv.vendor_or_customer_name || inv.vendor_name || inv.customer_name || '-'}</td>
                    <td className="px-3 py-3 font-bold">{fmt(inv.total_amount)}</td>
                    <td className="px-3 py-3 text-emerald-700">{fmt(inv.total_paid)}</td>
                    <td className={`px-3 py-3 font-bold ${outstanding > 0 ? 'text-red-600' : 'text-emerald-700'}`}>{fmt(outstanding)}</td>
                    <td className="px-3 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[inv.status] || 'bg-secondary'}`}>{inv.status}</span>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-1">
                        <button onClick={() => openDetail(inv)} className="p-1.5 rounded hover:bg-primary/10 text-primary" title="Detail">
                          <Eye className="w-4 h-4" />
                        </button>
                        {canEdit && inv.status !== 'Paid' && inv.status !== 'Superseded' && (
                          <button onClick={() => openRevise(inv)} className="p-1.5 rounded hover:bg-purple-50 text-purple-600" title="Revisi">
                            <Edit3 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* CREATE Modal */}
      {showCreate && (
        <Modal title="Buat Invoice Manual" onClose={() => setShowCreate(false)} size="xl">
          <form onSubmit={handleCreate} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Pilih Production PO *</label>
                <SearchableSelect
                  options={pos.map(p => ({
                    value: p.id,
                    label: `${p.po_number} – ${p.vendor_name || 'No Vendor'} – ${fmtDate(p.po_date)}`,
                    sub: `${p.customer_name || ''} • Status: ${p.status}`
                  }))}
                  value={createForm.source_po_id}
                  onChange={val => loadPOItems(val)}
                  placeholder="— Pilih PO —"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Kategori Invoice *</label>
                <select required className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={createForm.invoice_category} onChange={e => setCreateForm(f => ({ ...f, invoice_category: e.target.value }))}>
                  <option value="BUYER">BUYER (Piutang Customer)</option>
                  <option value="VENDOR">VENDOR (Hutang Vendor)</option>
                </select>
              </div>
            </div>

            {createForm.invoice_category === 'VENDOR' && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
                <strong>Mode VENDOR:</strong> Total dihitung dari <strong>CMT Price × Invoice Qty</strong>
              </div>
            )}
            {createForm.invoice_category === 'BUYER' && (
              <div className="bg-primary/10 border border-primary/20 rounded-lg p-3 text-sm text-primary">
                <strong>Mode BUYER:</strong> Total dihitung dari <strong>Selling Price × Invoice Qty</strong>
              </div>
            )}

            {invoiceItems.length > 0 && (
              <div>
                <label className="block text-sm font-semibold text-foreground mb-2">Item Invoice (edit qty & harga)</label>
                <div className="overflow-x-auto rounded-xl border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-[var(--glass-bg)]">
                      <tr>
                        <th className="text-left px-3 py-2 text-xs text-muted-foreground">SKU / Produk</th>
                        <th className="text-right px-3 py-2 text-xs text-muted-foreground">Ordered Qty</th>
                        <th className="text-right px-3 py-2 text-xs text-muted-foreground bg-primary/10">Invoice Qty *</th>
                        <th className="text-right px-3 py-2 text-xs text-muted-foreground bg-emerald-50">Selling Price *</th>
                        <th className="text-right px-3 py-2 text-xs text-muted-foreground bg-amber-50">CMT Price *</th>
                        <th className="text-right px-3 py-2 text-xs text-foreground font-bold">Subtotal</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoiceItems.map((item, idx) => (
                        <tr key={idx} className="border-t border-border">
                          <td className="px-3 py-2">
                            <p className="font-medium">{item.product_name}</p>
                            <p className="text-xs font-mono text-primary">{item.sku} · {item.size}/{item.color}</p>
                          </td>
                          <td className="px-3 py-2 text-right text-muted-foreground">{item.ordered_qty?.toLocaleString('id-ID')}</td>
                          <td className="px-3 py-2 bg-primary/10">
                            <input type="number" min="0" max={item.ordered_qty}
                              className="w-20 border border-primary/20 rounded px-2 py-1 text-sm text-right ml-auto block"
                              value={item.invoice_qty} onChange={e => updateItem(idx, 'invoice_qty', e.target.value)} />
                          </td>
                          <td className="px-3 py-2 bg-emerald-50">
                            <input type="number" min="0"
                              className="w-28 border border-emerald-200 rounded px-2 py-1 text-sm text-right ml-auto block"
                              value={item.selling_price} onChange={e => updateItem(idx, 'selling_price', e.target.value)} />
                          </td>
                          <td className="px-3 py-2 bg-amber-50">
                            <input type="number" min="0"
                              className="w-28 border border-amber-200 rounded px-2 py-1 text-sm text-right ml-auto block"
                              value={item.cmt_price} onChange={e => updateItem(idx, 'cmt_price', e.target.value)} />
                          </td>
                          <td className="px-3 py-2 text-right font-bold">{fmt(getSubtotal(item))}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-[var(--glass-bg)] border-t-2 border-border">
                      <tr>
                        <td className="px-3 py-2 font-bold" colSpan={5}>Subtotal</td>
                        <td className="px-3 py-2 text-right font-bold">{fmt(totalBeforeDiscount)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            )}

            {/* Variance Warning - Show if PO has approved variances */}
            {variances.length > 0 && (
              <div className="mt-4 p-4 bg-amber-50 border-2 border-amber-300 rounded-lg">
                <div className="flex items-start gap-2 mb-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-amber-900 text-sm">Production Variance Terdeteksi</h4>
                    <p className="text-xs text-amber-700 mt-1">
                      PO ini memiliki {variances.length} variance produksi yang sudah di-acknowledge. 
                      Silakan sesuaikan qty invoice secara manual jika diperlukan berdasarkan informasi di bawah.
                    </p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-amber-100 border-b border-amber-300">
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Job Number</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Type</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold text-amber-900">Total Variance</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Alasan</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-amber-200">
                      {variances.map(v => (
                        <tr key={v.id} className="hover:bg-amber-100/50">
                          <td className="px-3 py-2 text-xs font-medium text-foreground">{v.job_number}</td>
                          <td className="px-3 py-2">
                            {v.variance_type === 'OVERPRODUCTION' ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700">
                                <ArrowUpCircle className="w-3 h-3" /> Over (+)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-primary/15 text-primary">
                                <ArrowDownCircle className="w-3 h-3" /> Under (-)
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <span className="font-bold text-foreground">{v.total_variance_qty.toLocaleString('id-ID')}</span>
                            <span className="text-xs text-muted-foreground ml-1">pcs</span>
                          </td>
                          <td className="px-3 py-2 text-xs text-muted-foreground max-w-xs">
                            <div className="truncate" title={v.reason}>{v.reason}</div>
                          </td>
                          <td className="px-3 py-2">
                            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary/15 text-primary">
                              {v.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Diskon (Rp)</label>
                <input type="number" min="0" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={createForm.discount} onChange={e => setCreateForm(f => ({ ...f, discount: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Total Setelah Diskon</label>
                <div className="w-full border border-emerald-300 bg-emerald-50 rounded-lg px-3 py-2 text-sm font-bold text-emerald-700">
                  {fmt(totalAfterDiscount)}
                </div>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Catatan</label>
              <textarea rows="2" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                value={createForm.notes} onChange={e => setCreateForm(f => ({ ...f, notes: e.target.value }))} />
            </div>
            <div className="flex gap-3">
              <button type="submit" disabled={saving} className="flex-1 bg-purple-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50">
                {saving ? 'Menyimpan...' : 'Buat Invoice Manual'}
              </button>
              <button type="button" onClick={() => setShowCreate(false)} className="flex-1 border border-border py-2 rounded-lg text-sm">Batal</button>
            </div>
          </form>
        </Modal>
      )}

      {/* DETAIL Modal */}
      {showDetail && selectedInv && (
        <Modal title={`Detail: ${selectedInv.invoice_number}`} onClose={() => { setShowDetail(false); setShowAdjustment(false); }} size="xl">
          <div className="space-y-4">
            {/* Action Buttons */}
            {canEdit && selectedInv.status !== 'Superseded' && (
              <div className="flex gap-2 pb-3 border-b border-border">
                <button
                  onClick={() => openRequestEdit(selectedInv)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700"
                  data-testid="request-edit-button"
                >
                  <Send className="w-3.5 h-3.5" /> Request Edit
                </button>
                <button
                  onClick={() => openHistory(selectedInv)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white rounded-lg text-sm hover:brightness-110"
                  data-testid="view-history-button"
                >
                  <History className="w-3.5 h-3.5" /> Histori Perubahan
                </button>
              </div>
            )}

            <div className="grid grid-cols-3 gap-3">
              {[
                { l: 'No. Invoice', v: <span className="font-bold text-primary">{selectedInv.invoice_number}</span> },
                { l: 'Tipe', v: <span className={`px-2 py-0.5 rounded-full text-xs ${TYPE_COLORS[selectedInv.invoice_type]}`}>{selectedInv.invoice_type}</span> },
                { l: 'Kategori', v: <span className={`px-2 py-0.5 rounded-full text-xs ${CATEGORY_COLORS[selectedInv.invoice_category]}`}>{selectedInv.invoice_category}</span> },
                { l: 'No. PO', v: selectedInv.po_number },
                { l: 'Nilai Dasar', v: <span className="font-bold">{fmt(selectedInv.base_amount || selectedInv.total_amount)}</span> },
                { l: 'Status', v: <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[selectedInv.status]}`}>{selectedInv.status}</span> },
                { l: 'Total Saat Ini', v: <span className="font-bold text-primary">{fmt(selectedInv.adjusted_total || selectedInv.total_amount)}</span> },
                { l: 'Dibayar', v: <span className="text-emerald-700 font-bold">{fmt(selectedInv.total_paid)}</span> },
                { l: 'Sisa', v: <span className={`font-bold ${((selectedInv.adjusted_total || selectedInv.total_amount) - (selectedInv.total_paid || 0)) > 0 ? 'text-red-600' : 'text-emerald-700'}`}>{fmt((selectedInv.adjusted_total || selectedInv.total_amount) - (selectedInv.total_paid || 0))}</span> },
              ].map(it => (
                <div key={it.l} className="bg-[var(--glass-bg)] rounded-lg p-3">
                  <p className="text-xs text-muted-foreground">{it.l}</p>
                  <div className="font-medium text-sm mt-0.5">{it.v}</div>
                </div>
              ))}
            </div>

            {selectedInv.parent_invoice_number && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-sm text-purple-700">
                Revisi dari: <strong>{selectedInv.parent_invoice_number}</strong>
                {selectedInv.change_reason && <> · Alasan: <em>{selectedInv.change_reason}</em></>}
              </div>
            )}

            {/* Invoice Items */}
            {(selectedInv.invoice_items || []).length > 0 && (
              <div>
                <h4 className="font-semibold text-foreground mb-2">Item Invoice</h4>
                <table className="w-full text-sm border border-border rounded-xl overflow-hidden">
                  <thead className="bg-[var(--glass-bg)]">
                    <tr>
                      {['SKU', 'Produk', 'Ordered', 'Invoice Qty', 'Selling', 'CMT', 'Subtotal'].map(h => (
                        <th key={h} className="text-right px-3 py-2 text-xs text-muted-foreground first:text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {selectedInv.invoice_items.map((it, i) => (
                      <tr key={i} className="border-t border-border">
                        <td className="px-3 py-2 font-mono text-xs text-primary">{it.sku}</td>
                        <td className="px-3 py-2">{it.product_name} <span className="text-xs text-muted-foreground">{it.size}/{it.color}</span></td>
                        <td className="px-3 py-2 text-right text-muted-foreground">{(it.ordered_qty||0).toLocaleString('id-ID')}</td>
                        <td className="px-3 py-2 text-right font-bold">{(it.invoice_qty||0).toLocaleString('id-ID')}</td>
                        <td className="px-3 py-2 text-right text-emerald-700">{fmt(it.selling_price)}</td>
                        <td className="px-3 py-2 text-right text-amber-700">{fmt(it.cmt_price)}</td>
                        <td className="px-3 py-2 text-right font-bold">{fmt(it.subtotal || ((it.invoice_qty||0) * (selectedInv.invoice_category === 'VENDOR' ? it.cmt_price : it.selling_price)))}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-[var(--glass-bg)] border-t-2 border-border font-bold">
                    <tr>
                      <td colSpan={6} className="px-3 py-2">Subtotal Item</td>
                      <td className="px-3 py-2 text-right">{fmt(selectedInv.base_amount || selectedInv.total_amount)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}

            {/* Production Variance Info (if exists) */}
            {variances.length > 0 && (
              <div className="mt-4 p-4 bg-amber-50 border-2 border-amber-300 rounded-lg">
                <div className="flex items-start gap-2 mb-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-amber-900 text-sm">Production Variance untuk PO ini</h4>
                    <p className="text-xs text-amber-700 mt-1">
                      PO ini memiliki {variances.length} variance produksi yang sudah di-acknowledge/resolved.
                    </p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-amber-100 border-b border-amber-300">
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Job Number</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Type</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold text-amber-900">Total Variance</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Alasan</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-amber-900">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-amber-200">
                      {variances.map(v => (
                        <tr key={v.id} className="hover:bg-amber-100/50">
                          <td className="px-3 py-2 text-xs font-medium text-foreground">{v.job_number}</td>
                          <td className="px-3 py-2">
                            {v.variance_type === 'OVERPRODUCTION' ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-700">
                                <ArrowUpCircle className="w-3 h-3" /> Over (+)
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-primary/15 text-primary">
                                <ArrowDownCircle className="w-3 h-3" /> Under (-)
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <span className="font-bold text-foreground">{v.total_variance_qty.toLocaleString('id-ID')}</span>
                            <span className="text-xs text-muted-foreground ml-1">pcs</span>
                          </td>
                          <td className="px-3 py-2 text-xs text-muted-foreground max-w-xs">
                            <div className="truncate" title={v.reason}>{v.reason}</div>
                          </td>
                          <td className="px-3 py-2">
                            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary/15 text-primary">
                              {v.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}


            {/* Invoice Adjustments Section */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-foreground">Riwayat Adjustment</h4>
                {canEdit && selectedInv.status !== 'Paid' && selectedInv.status !== 'Superseded' && (
                  <button onClick={() => setShowAdjustment(!showAdjustment)}
                    className="flex items-center gap-1 px-3 py-1.5 bg-amber-500 text-white rounded-lg text-xs font-medium hover:bg-amber-600">
                    <Plus className="w-3.5 h-3.5" /> Tambah Adjustment
                  </button>
                )}
              </div>

              {/* Add Adjustment Form */}
              {showAdjustment && (
                <form onSubmit={handleAddAdjustment} className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-3 space-y-3">
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-foreground mb-1">Tipe *</label>
                      <select required className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                        value={adjForm.adjustment_type} onChange={e => setAdjForm(f => ({ ...f, adjustment_type: e.target.value }))}>
                        <option value="ADD">TAMBAH (+)</option>
                        <option value="DEDUCT">KURANGI (-)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-foreground mb-1">Jumlah (Rp) *</label>
                      <input type="number" min="1" required className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                        value={adjForm.amount} onChange={e => setAdjForm(f => ({ ...f, amount: e.target.value }))}
                        placeholder="100000" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-foreground mb-1">Referensi</label>
                      <input type="text" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                        value={adjForm.reference_event} onChange={e => setAdjForm(f => ({ ...f, reference_event: e.target.value }))}
                        placeholder="Contoh: Negosiasi ulang" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1">Alasan *</label>
                    <input type="text" required className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                      value={adjForm.reason} onChange={e => setAdjForm(f => ({ ...f, reason: e.target.value }))}
                      placeholder="Contoh: Tambahan barang, kasbon, potongan defect..." />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1">Catatan</label>
                    <input type="text" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                      value={adjForm.notes} onChange={e => setAdjForm(f => ({ ...f, notes: e.target.value }))} />
                  </div>
                  <div className="flex gap-2">
                    <button type="submit" disabled={adjSaving}
                      className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm hover:bg-amber-700 disabled:opacity-50">
                      {adjSaving ? 'Menyimpan...' : 'Simpan Adjustment'}
                    </button>
                    <button type="button" onClick={() => setShowAdjustment(false)}
                      className="px-4 py-2 border border-border rounded-lg text-sm">Batal</button>
                  </div>
                </form>
              )}

              {/* Adjustment History */}
              {(selectedInv.adjustments || []).length > 0 ? (
                <div className="space-y-1.5">
                  {selectedInv.adjustments.map(adj => (
                    <div key={adj.id} className={`rounded-lg p-3 flex items-center justify-between ${
                      adj.adjustment_type === 'ADD' ? 'bg-emerald-50 border border-emerald-200' : 'bg-red-50 border border-red-200'
                    }`}>
                      <div className="flex items-center gap-3">
                        {adj.adjustment_type === 'ADD' ? (
                          <ArrowUpCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                        ) : (
                          <ArrowDownCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                        )}
                        <div>
                          <p className="text-sm font-medium">
                            <span className={adj.adjustment_type === 'ADD' ? 'text-emerald-700' : 'text-red-700'}>
                              {adj.adjustment_type === 'ADD' ? '+' : '-'} {fmt(adj.amount)}
                            </span>
                          </p>
                          <p className="text-xs text-muted-foreground">{adj.reason}</p>
                          {adj.reference_event && <p className="text-xs text-muted-foreground">Ref: {adj.reference_event}</p>}
                          <p className="text-xs text-muted-foreground">{adj.created_by} · {fmtDate(adj.created_at)}</p>
                        </div>
                      </div>
                      {canEdit && (
                        <button onClick={() => handleDeleteAdjustment(adj.id)} className="p-1.5 rounded hover:bg-red-100 text-red-500" title="Hapus">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                  {/* Summary */}
                  <div className="bg-primary/10 border border-primary/20 rounded-lg p-3 mt-2">
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <p className="text-xs text-muted-foreground">Nilai Dasar</p>
                        <p className="font-bold">{fmt(selectedInv.base_amount || selectedInv.total_amount)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Total Adjustment</p>
                        <p className="font-bold">
                          {(() => {
                            const adds = (selectedInv.adjustments || []).filter(a => a.adjustment_type === 'ADD').reduce((s, a) => s + (a.amount || 0), 0);
                            const deducts = (selectedInv.adjustments || []).filter(a => a.adjustment_type === 'DEDUCT').reduce((s, a) => s + (a.amount || 0), 0);
                            const net = adds - deducts;
                            return <span className={net >= 0 ? 'text-emerald-700' : 'text-red-700'}>{net >= 0 ? '+' : ''}{fmt(net)}</span>;
                          })()}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Total Saat Ini</p>
                        <p className="font-bold text-primary">{fmt(selectedInv.adjusted_total || selectedInv.total_amount)}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4 text-muted-foreground text-sm bg-[var(--glass-bg)] rounded-lg">
                  Belum ada adjustment pada invoice ini
                </div>
              )}
            </div>

            {/* Payments */}
            {(selectedInv.payments || []).length > 0 && (
              <div>
                <h4 className="font-semibold text-foreground mb-2">Riwayat Pembayaran</h4>
                <div className="space-y-1">
                  {selectedInv.payments.map((p, i) => (
                    <div key={p.id} className="bg-emerald-50 rounded-lg p-3 flex justify-between">
                      <div>
                        <p className="text-sm font-medium">{p.payment_method} · {fmtDate(p.payment_date)}</p>
                        <p className="text-xs text-muted-foreground">{p.reference_number || p.reference || ''}</p>
                      </div>
                      <span className="font-bold text-emerald-700">{fmt(p.amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* REVISE Modal */}
      {showRevise && selectedInv && (
        <Modal title={`Revisi Invoice: ${selectedInv.invoice_number}`} onClose={() => setShowRevise(false)} size="xl">
          <form onSubmit={handleRevise} className="space-y-4">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
              <strong>Perhatian:</strong> Revisi akan membuat invoice baru ({selectedInv.invoice_number}-R{(selectedInv.revision_number || 0) + 1}) dan menandai invoice lama sebagai "Superseded".
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Alasan Revisi *</label>
              <input required className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                value={reviseForm.change_reason} onChange={e => setReviseForm(f => ({ ...f, change_reason: e.target.value }))}
                placeholder="Contoh: Negosiasi harga, penyesuaian qty produksi..." />
            </div>
            {reviseForm.invoice_items.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-[var(--glass-bg)]">
                    <tr>
                      <th className="text-left px-3 py-2 text-xs text-muted-foreground">SKU / Produk</th>
                      <th className="text-right px-3 py-2 text-xs text-muted-foreground">Invoice Qty *</th>
                      <th className="text-right px-3 py-2 text-xs text-muted-foreground">Selling Price *</th>
                      <th className="text-right px-3 py-2 text-xs text-muted-foreground">CMT Price *</th>
                      <th className="text-right px-3 py-2 text-xs font-bold text-foreground">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reviseForm.invoice_items.map((item, idx) => (
                      <tr key={idx} className="border-t border-border">
                        <td className="px-3 py-2">
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-xs font-mono text-primary">{item.sku} · {item.size}/{item.color}</p>
                        </td>
                        <td className="px-3 py-2">
                          <input type="number" min="0" className="w-20 border border-primary/20 rounded px-2 py-1 text-sm text-right ml-auto block"
                            value={item.invoice_qty} onChange={e => updateReviseItem(idx, 'invoice_qty', e.target.value)} />
                        </td>
                        <td className="px-3 py-2">
                          <input type="number" min="0" className="w-28 border border-emerald-200 rounded px-2 py-1 text-sm text-right ml-auto block"
                            value={item.selling_price} onChange={e => updateReviseItem(idx, 'selling_price', e.target.value)} />
                        </td>
                        <td className="px-3 py-2">
                          <input type="number" min="0" className="w-28 border border-amber-200 rounded px-2 py-1 text-sm text-right ml-auto block"
                            value={item.cmt_price} onChange={e => updateReviseItem(idx, 'cmt_price', e.target.value)} />
                        </td>
                        <td className="px-3 py-2 text-right font-bold">{fmt(getReviseSubtotal(item))}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-[var(--glass-bg)] border-t-2 border-border">
                    <tr>
                      <td colSpan={4} className="px-3 py-2 font-bold">Total Revisi</td>
                      <td className="px-3 py-2 text-right font-bold text-primary">{fmt(reviseTotalBeforeDiscount)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
            <div className="flex gap-3">
              <button type="submit" disabled={saving} className="flex-1 bg-purple-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50">
                {saving ? 'Menyimpan...' : 'Simpan Revisi'}
              </button>
              <button type="button" onClick={() => setShowRevise(false)} className="flex-1 border border-border py-2 rounded-lg text-sm">Batal</button>
            </div>
          </form>
        </Modal>
      )}

      {/* REQUEST EDIT Modal */}
      {showRequestEdit && selectedInv && (
        <Modal title={`Request Edit: ${selectedInv.invoice_number}`} onClose={() => setShowRequestEdit(false)} size="xl">
          <form onSubmit={handleRequestEdit} className="space-y-4">
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 text-sm text-purple-700">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-semibold">Perhatian: Request Edit (Approval System)</p>
                  <p className="mt-1">• Request ini <strong>TIDAK</strong> langsung mengubah invoice.</p>
                  <p>• Superadmin/Admin akan me-review request Anda di <strong>Invoice Edit Approval</strong> module.</p>
                  <p>• Jika di-approve, invoice akan diupdate otomatis + histori perubahan tersimpan.</p>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Ringkasan Perubahan *</label>
              <input
                required
                className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                value={requestEditForm.change_summary}
                onChange={e => setRequestEditForm(f => ({ ...f, change_summary: e.target.value }))}
                placeholder="Contoh: Penyesuaian qty sesuai kesepakatan customer, perubahan harga negosiasi..."
              />
            </div>

            {requestEditForm.invoice_items.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-[var(--glass-bg)]">
                    <tr>
                      <th className="text-left px-3 py-2 text-xs text-muted-foreground">SKU / Produk</th>
                      <th className="text-right px-3 py-2 text-xs text-muted-foreground">Invoice Qty</th>
                      <th className="text-right px-3 py-2 text-xs text-muted-foreground">Selling Price</th>
                      <th className="text-right px-3 py-2 text-xs text-muted-foreground">CMT Price</th>
                      <th className="text-right px-3 py-2 text-xs font-bold text-foreground">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requestEditForm.invoice_items.map((item, idx) => (
                      <tr key={idx} className="border-t border-border">
                        <td className="px-3 py-2">
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-xs font-mono text-primary">{item.sku} · {item.size}/{item.color}</p>
                        </td>
                        <td className="px-3 py-2">
                          <input type="number" min="0" className="w-20 border border-primary/20 rounded px-2 py-1 text-sm text-right ml-auto block"
                            value={item.invoice_qty} onChange={e => updateRequestEditItem(idx, 'invoice_qty', e.target.value)} />
                        </td>
                        <td className="px-3 py-2">
                          <input type="number" min="0" className="w-28 border border-emerald-200 rounded px-2 py-1 text-sm text-right ml-auto block"
                            value={item.selling_price} onChange={e => updateRequestEditItem(idx, 'selling_price', e.target.value)} />
                        </td>
                        <td className="px-3 py-2">
                          <input type="number" min="0" className="w-28 border border-amber-200 rounded px-2 py-1 text-sm text-right ml-auto block"
                            value={item.cmt_price} onChange={e => updateRequestEditItem(idx, 'cmt_price', e.target.value)} />
                        </td>
                        <td className="px-3 py-2 text-right font-bold">{fmt(getRequestEditSubtotal(item))}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-[var(--glass-bg)] border-t-2 border-border">
                    <tr>
                      <td colSpan={4} className="px-3 py-2 font-bold">Subtotal</td>
                      <td className="px-3 py-2 text-right font-bold">{fmt(requestEditTotalBeforeDiscount)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Diskon (Rp)</label>
                <input type="number" min="0" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={requestEditForm.discount} onChange={e => setRequestEditForm(f => ({ ...f, discount: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Total Setelah Diskon</label>
                <div className="w-full border border-purple-300 bg-purple-50 rounded-lg px-3 py-2 text-sm font-bold text-purple-700">
                  {fmt(requestEditTotalAfterDiscount)}
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Catatan</label>
              <textarea rows="2" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                value={requestEditForm.notes} onChange={e => setRequestEditForm(f => ({ ...f, notes: e.target.value }))} />
            </div>

            <div className="flex gap-3">
              <button type="submit" disabled={requestEditSaving} className="flex-1 bg-purple-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-purple-700 disabled:opacity-50">
                {requestEditSaving ? 'Mengirim...' : 'Submit Request Edit'}
              </button>
              <button type="button" onClick={() => setShowRequestEdit(false)} className="flex-1 border border-border py-2 rounded-lg text-sm">Batal</button>
            </div>
          </form>
        </Modal>
      )}

      {/* CHANGE HISTORY Modal */}
      {showHistory && selectedInv && (
        <Modal title={`Histori Perubahan: ${selectedInv.invoice_number}`} onClose={() => setShowHistory(false)} size="lg">
          <div className="space-y-4">
            {historyLoading ? (
              <div className="text-center py-8">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-muted-foreground" />
                <p className="text-muted-foreground text-sm">Memuat histori...</p>
              </div>
            ) : changeHistory.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <History className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="font-medium">Belum ada histori perubahan</p>
                <p className="text-xs mt-1">Histori akan tercatat saat ada approval request edit</p>
              </div>
            ) : (
              <div className="space-y-3">
                {changeHistory.map((history, idx) => (
                  <div key={history.id || idx} className="bg-[var(--glass-bg)] border border-border rounded-lg p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <p className="font-semibold text-foreground">{history.change_type}</p>
                        <p className="text-xs text-muted-foreground">
                          {history.changed_by_name} ({history.changed_by}) • {fmtDate(history.changed_at)}
                        </p>
                      </div>
                      <span className="px-2 py-0.5 rounded-full text-xs bg-primary/15 text-primary">
                        {history.change_type}
                      </span>
                    </div>
                    {history.notes && (
                      <div className="bg-[var(--card-surface)] rounded p-2 text-sm text-muted-foreground mb-2">
                        <strong>Catatan:</strong> {history.notes}
                      </div>
                    )}
                    {history.approval_request_id && (
                      <p className="text-xs text-muted-foreground">
                        Request ID: {history.approval_request_id}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}

    </div>
  );
}
