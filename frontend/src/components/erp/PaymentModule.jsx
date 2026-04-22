
import { useState, useEffect, useCallback } from 'react';
import { Plus, ArrowDownCircle, ArrowUpCircle, RefreshCw, Eye, CreditCard, DollarSign, CheckCircle, AlertTriangle } from 'lucide-react';
import Modal from './Modal';

const PAYMENT_METHODS = ['Transfer Bank', 'Cek/Giro', 'Cash', 'Kartu Kredit', 'Lainnya'];
const FILTER_OPTIONS = [
  { label: 'Hari Ini', value: 'today' },
  { label: '7 Hari', value: '7d' },
  { label: '28 Hari', value: '28d' },
  { label: 'Bulan Ini', value: 'month' },
  { label: 'Semua', value: 'all' },
  { label: 'Custom', value: 'custom' },
];

function getDateRange(filter) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (filter === 'today') return { date_from: today.toISOString().split('T')[0], date_to: today.toISOString().split('T')[0] };
  if (filter === '7d') { const d = new Date(today); d.setDate(d.getDate() - 7); return { date_from: d.toISOString().split('T')[0], date_to: today.toISOString().split('T')[0] }; }
  if (filter === '28d') { const d = new Date(today); d.setDate(d.getDate() - 28); return { date_from: d.toISOString().split('T')[0], date_to: today.toISOString().split('T')[0] }; }
  if (filter === 'month') { const d = new Date(now.getFullYear(), now.getMonth(), 1); return { date_from: d.toISOString().split('T')[0], date_to: today.toISOString().split('T')[0] }; }
  return {};
}

const fmt = (v) => 'Rp ' + Number(v || 0).toLocaleString('id-ID');
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('id-ID') : '-';

export default function PaymentModule({ token, userRole, prefillInvoice }) {
  const [vendorPayments, setVendorPayments] = useState([]);
  const [customerPayments, setCustomerPayments] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('vendor'); // 'vendor' | 'customer'
  const [filter, setFilter] = useState('all');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    invoice_id: '', payment_date: new Date().toISOString().split('T')[0],
    amount: '', payment_method: 'Transfer Bank', reference_number: '', notes: '', payment_type: 'VENDOR_PAYMENT'
  });
  const [amountError, setAmountError] = useState('');
  const [saving, setSaving] = useState(false);

  const canEdit = ['superadmin', 'admin', 'finance'].includes(userRole);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const range = filter === 'custom' ? { date_from: customFrom, date_to: customTo } : getDateRange(filter);
      const params = new URLSearchParams();
      if (range.date_from) params.set('date_from', range.date_from);
      if (range.date_to) params.set('date_to', range.date_to);

      const [vpRes, cpRes, invRes] = await Promise.all([
        fetch(`/api/payments?payment_type=VENDOR_PAYMENT&${params}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`/api/payments?payment_type=CUSTOMER_PAYMENT&${params}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/invoices', { headers: { Authorization: `Bearer ${token}` } })
      ]);
      const [vpData, cpData, invData] = await Promise.all([vpRes.json(), cpRes.json(), invRes.json()]);
      setVendorPayments(Array.isArray(vpData) ? vpData : []);
      setCustomerPayments(Array.isArray(cpData) ? cpData : []);
      setInvoices(Array.isArray(invData) ? invData.filter(i => i.status !== 'Paid' && i.status !== 'Superseded') : []);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, [token, filter, customFrom, customTo]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    if (prefillInvoice) {
      const pType = prefillInvoice.invoice_category === 'VENDOR' ? 'VENDOR_PAYMENT' : 'CUSTOMER_PAYMENT';
      setForm(f => ({ ...f, invoice_id: prefillInvoice.id, payment_type: pType }));
      setActiveTab(pType === 'VENDOR_PAYMENT' ? 'vendor' : 'customer');
      setShowModal(true);
    }
  }, [prefillInvoice]);

  const vendorInvoices = invoices.filter(i => i.invoice_category === 'VENDOR' || i.invoice_type === 'vendor' || (!i.invoice_category && i.invoice_type !== 'customer'));
  const customerInvoices = invoices.filter(i => i.invoice_category === 'BUYER' || i.invoice_type === 'customer');

  const activeInvoices = form.payment_type === 'VENDOR_PAYMENT' ? vendorInvoices : customerInvoices;
  const selectedInv = invoices.find(i => i.id === form.invoice_id) || null;
  const outstanding = selectedInv ? (selectedInv.total_amount || 0) - (selectedInv.total_paid || 0) : 0;

  const totalCashOut = vendorPayments.reduce((s, p) => s + (p.amount || 0), 0);
  const totalCashIn = customerPayments.reduce((s, p) => s + (p.amount || 0), 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const amount = Number(form.amount);
    if (amount <= 0) { setAmountError('Jumlah harus > 0'); return; }
    if (selectedInv && amount > outstanding) { setAmountError(`Melebihi sisa: ${fmt(outstanding)}`); return; }
    setSaving(true);
    const res = await fetch('/api/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...form, amount })
    });
    const data = await res.json();
    setSaving(false);
    if (!res.ok) { alert(data.error || 'Gagal menyimpan'); return; }
    setShowModal(false);
    setForm({ invoice_id: '', payment_date: new Date().toISOString().split('T')[0], amount: '', payment_method: 'Transfer Bank', reference_number: '', notes: '', payment_type: 'VENDOR_PAYMENT' });
    setAmountError('');
    fetchAll();
  };

  const openCreate = (type) => {
    setForm(f => ({ ...f, invoice_id: '', amount: '', payment_type: type }));
    setAmountError('');
    setShowModal(true);
  };

  const displayPayments = activeTab === 'vendor' ? vendorPayments : customerPayments;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Manajemen Pembayaran</h1>
          <p className="text-muted-foreground text-sm mt-1">Cash Out (Bayar Vendor) dan Cash In (Terima dari Customer)</p>
        </div>
      </div>

      {/* Summary KPI */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-emerald-600 font-medium">Total Cash In</p>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{fmt(totalCashIn)}</p>
              <p className="text-xs text-emerald-500 mt-0.5">{customerPayments.length} transaksi dari customer</p>
            </div>
            <ArrowDownCircle className="w-8 h-8 text-emerald-500" />
          </div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-red-600 font-medium">Total Cash Out</p>
              <p className="text-2xl font-bold text-red-700 mt-1">{fmt(totalCashOut)}</p>
              <p className="text-xs text-red-500 mt-0.5">{vendorPayments.length} transaksi ke vendor</p>
            </div>
            <ArrowUpCircle className="w-8 h-8 text-red-500" />
          </div>
        </div>
        <div className={`border rounded-xl p-4 ${(totalCashIn - totalCashOut) >= 0 ? 'bg-primary/10 border-primary/20' : 'bg-orange-50 border-orange-200'}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-xs font-medium ${(totalCashIn - totalCashOut) >= 0 ? 'text-primary' : 'text-orange-600'}`}>Net Cash Flow</p>
              <p className={`text-2xl font-bold mt-1 ${(totalCashIn - totalCashOut) >= 0 ? 'text-primary' : 'text-orange-700'}`}>{fmt(totalCashIn - totalCashOut)}</p>
              <p className="text-xs text-muted-foreground mt-0.5">Cash In − Cash Out</p>
            </div>
            <DollarSign className={`w-8 h-8 ${(totalCashIn - totalCashOut) >= 0 ? 'text-primary' : 'text-orange-500'}`} />
          </div>
        </div>
      </div>

      {/* Date Filter */}
      <div className="bg-[var(--card-surface)] rounded-xl border border-border p-3 shadow-sm">
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-muted-foreground font-semibold">Periode:</span>
          {FILTER_OPTIONS.map(opt => (
            <button key={opt.value} onClick={() => setFilter(opt.value)}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${filter === opt.value ? 'bg-primary text-white border-blue-600' : 'border-border text-muted-foreground hover:bg-[var(--glass-bg)]'}`}>
              {opt.label}
            </button>
          ))}
          {filter === 'custom' && (
            <div className="flex items-center gap-2">
              <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)} className="border border-border rounded-lg px-2 py-1.5 text-sm" />
              <span className="text-muted-foreground text-sm">—</span>
              <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)} className="border border-border rounded-lg px-2 py-1.5 text-sm" />
              <button onClick={fetchAll} className="px-3 py-1.5 bg-primary text-white rounded-lg text-sm">OK</button>
            </div>
          )}
          <button onClick={fetchAll} className="ml-auto flex items-center gap-1 px-3 py-1.5 border border-border rounded-lg text-sm hover:bg-[var(--glass-bg)]">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 bg-secondary rounded-xl p-1">
        <button onClick={() => setActiveTab('vendor')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'vendor' ? 'bg-[var(--card-surface)] text-red-700 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>
          <ArrowUpCircle className="w-4 h-4" />
          Cash Out — Vendor Payments ({vendorPayments.length})
        </button>
        <button onClick={() => setActiveTab('customer')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${activeTab === 'customer' ? 'bg-[var(--card-surface)] text-emerald-700 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>
          <ArrowDownCircle className="w-4 h-4" />
          Cash In — Customer Payments ({customerPayments.length})
        </button>
      </div>

      {/* Add Payment Button (context-aware) */}
      {canEdit && (
        <div className="flex justify-end">
          <button
            onClick={() => openCreate(activeTab === 'vendor' ? 'VENDOR_PAYMENT' : 'CUSTOMER_PAYMENT')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white ${activeTab === 'vendor' ? 'bg-red-600 hover:bg-red-700' : 'bg-emerald-600 hover:bg-emerald-700'}`}>
            <Plus className="w-4 h-4" />
            {activeTab === 'vendor' ? 'Bayar Vendor (Cash Out)' : 'Terima dari Customer (Cash In)'}
          </button>
        </div>
      )}

      {/* Payment Table */}
      {loading ? (
        <div className="text-center py-16"><RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-muted-foreground" /></div>
      ) : displayPayments.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <CreditCard className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>Belum ada {activeTab === 'vendor' ? 'pembayaran ke vendor' : 'penerimaan dari customer'}</p>
        </div>
      ) : (
        <div className="bg-[var(--card-surface)] rounded-xl border border-border overflow-hidden shadow-sm">
          <div className={`px-4 py-2 border-b font-semibold text-sm ${activeTab === 'vendor' ? 'bg-red-50 text-red-700 border-red-100' : 'bg-emerald-50 text-emerald-700 border-emerald-100'}`}>
            {activeTab === 'vendor' ? '↑ Cash Out — Pembayaran ke Vendor' : '↓ Cash In — Penerimaan dari Customer'}
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[var(--glass-bg)] border-b">
              <tr>
                {activeTab === 'vendor'
                  ? ['Vendor', 'No. Invoice', 'Jumlah Bayar', 'Sisa Hutang', 'Tanggal', 'Metode', 'Referensi'].map(h => <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase">{h}</th>)
                  : ['Customer', 'No. Invoice', 'Jumlah Terima', 'Sisa Piutang', 'Tanggal', 'Metode', 'Referensi'].map(h => <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase">{h}</th>)
                }
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {displayPayments.map(p => {
                const inv = invoices.find(i => i.id === p.invoice_id);
                const remaining = inv ? Math.max(0, (inv.total_amount || 0) - (inv.total_paid || 0)) : null;
                return (
                  <tr key={p.id} className="hover:bg-[var(--glass-bg)]">
                    <td className="px-4 py-3 font-medium text-foreground">{p.vendor_or_customer_name || p.garment_name || '-'}</td>
                    <td className="px-4 py-3 font-mono text-xs text-primary">{p.invoice_number}</td>
                    <td className={`px-4 py-3 font-bold ${activeTab === 'vendor' ? 'text-red-700' : 'text-emerald-700'}`}>{fmt(p.amount)}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{remaining !== null ? fmt(remaining) : '-'}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{fmtDate(p.payment_date)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{p.payment_method}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{p.reference_number || p.reference || '-'}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-[var(--glass-bg)] border-t-2 border-border">
              <tr>
                <td className="px-4 py-2 font-bold text-foreground" colSpan={2}>Total ({displayPayments.length} transaksi)</td>
                <td className={`px-4 py-2 font-bold ${activeTab === 'vendor' ? 'text-red-700' : 'text-emerald-700'}`}>
                  {fmt(displayPayments.reduce((s, p) => s + (p.amount || 0), 0))}
                </td>
                <td colSpan={4}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* Payment Modal */}
      {showModal && (
        <Modal
          title={form.payment_type === 'VENDOR_PAYMENT' ? '↑ Bayar Vendor (Cash Out)' : '↓ Terima dari Customer (Cash In)'}
          onClose={() => setShowModal(false)}>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Type Toggle */}
            <div className="flex gap-2">
              {[
                { value: 'VENDOR_PAYMENT', label: '↑ Cash Out (Vendor)', cls: 'border-red-400 text-red-700 bg-red-50' },
                { value: 'CUSTOMER_PAYMENT', label: '↓ Cash In (Customer)', cls: 'border-emerald-400 text-emerald-700 bg-emerald-50' },
              ].map(opt => (
                <button key={opt.value} type="button"
                  onClick={() => setForm(f => ({ ...f, payment_type: opt.value, invoice_id: '', amount: '' }))}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border-2 transition-all ${form.payment_type === opt.value ? opt.cls : 'border-border text-muted-foreground'}`}>
                  {opt.label}
                </button>
              ))}
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Pilih Invoice {form.payment_type === 'VENDOR_PAYMENT' ? 'Vendor' : 'Customer'} *
              </label>
              <select required className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                value={form.invoice_id} onChange={e => { setForm(f => ({ ...f, invoice_id: e.target.value, amount: '' })); setAmountError(''); }}>
                <option value="">— Pilih Invoice —</option>
                {activeInvoices.map(inv => {
                  const outs = (inv.total_amount || 0) - (inv.total_paid || 0);
                  return <option key={inv.id} value={inv.id}>{inv.invoice_number} — {inv.vendor_or_customer_name || inv.vendor_name || inv.customer_name} — Sisa: {fmt(outs)}</option>;
                })}
              </select>
            </div>

            {selectedInv && (
              <div className="bg-[var(--glass-bg)] rounded-xl p-3 grid grid-cols-3 gap-3 text-sm">
                <div><p className="text-xs text-muted-foreground">No. Invoice</p><p className="font-bold text-primary">{selectedInv.invoice_number}</p></div>
                <div><p className="text-xs text-muted-foreground">Total</p><p className="font-bold">{fmt(selectedInv.total_amount)}</p></div>
                <div><p className="text-xs text-muted-foreground">Sisa Belum Bayar</p><p className="font-bold text-red-600">{fmt(outstanding)}</p></div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Tanggal *</label>
                <input type="date" required className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={form.payment_date} onChange={e => setForm(f => ({ ...f, payment_date: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Jumlah (Rp) *</label>
                <input type="number" required min="1" max={outstanding || undefined}
                  className={`w-full border rounded-lg px-3 py-2 text-sm ${amountError ? 'border-red-400' : 'border-border'}`}
                  value={form.amount}
                  onChange={e => {
                    const val = e.target.value;
                    setForm(f => ({ ...f, amount: val }));
                    if (selectedInv && Number(val) > outstanding) setAmountError(`Melebihi sisa: ${fmt(outstanding)}`);
                    else setAmountError('');
                  }} />
                {amountError && <p className="text-xs text-red-500 mt-0.5">{amountError}</p>}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Metode</label>
                <select className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={form.payment_method} onChange={e => setForm(f => ({ ...f, payment_method: e.target.value }))}>
                  {PAYMENT_METHODS.map(m => <option key={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">No. Referensi</label>
                <input className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={form.reference_number} onChange={e => setForm(f => ({ ...f, reference_number: e.target.value }))} placeholder="No. BG / Transfer" />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Catatan</label>
              <textarea rows="2" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
            </div>

            <div className="flex gap-3">
              <button type="submit" disabled={saving || !!amountError}
                className={`flex-1 text-white py-2 rounded-lg text-sm font-medium disabled:opacity-50 ${form.payment_type === 'VENDOR_PAYMENT' ? 'bg-red-600 hover:bg-red-700' : 'bg-emerald-600 hover:bg-emerald-700'}`}>
                {saving ? 'Menyimpan...' : form.payment_type === 'VENDOR_PAYMENT' ? 'Bayar Vendor' : 'Konfirmasi Penerimaan'}
              </button>
              <button type="button" onClick={() => setShowModal(false)} className="flex-1 border border-border py-2 rounded-lg text-sm">Batal</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
