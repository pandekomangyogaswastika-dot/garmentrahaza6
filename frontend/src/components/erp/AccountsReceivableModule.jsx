
import { useState, useEffect, useCallback } from 'react';
import { FileText, CreditCard, CheckCircle, Clock, AlertTriangle, RefreshCw, Eye, TrendingUp } from 'lucide-react';
import Modal from './Modal';

const STATUS_COLORS = {
  'Unpaid':  'bg-red-100 text-red-700 border border-red-200',
  'Partial': 'bg-amber-100 text-amber-700 border border-amber-200',
  'Paid':    'bg-emerald-100 text-emerald-700 border border-emerald-200',
  'Superseded': 'bg-pink-100 text-pink-600 border border-pink-200',
};

const PAYMENT_METHODS = ['Transfer Bank', 'Cek/Giro', 'Cash', 'Kartu Kredit', 'Lainnya'];
const STATUS_OPTS = ['', 'Unpaid', 'Partial', 'Paid'];

const FILTER_OPTIONS = [
  { label: 'Hari Ini', value: 'today' }, { label: '7 Hari', value: '7d' },
  { label: '28 Hari', value: '28d' }, { label: 'Bulan Ini', value: 'month' },
  { label: 'Semua', value: 'all' }, { label: 'Custom', value: 'custom' },
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

function ARStatusBadge({ status }) {
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status] || 'bg-secondary text-muted-foreground'}`}>{status}</span>;
}

const fmt = (v) => 'Rp ' + Number(v || 0).toLocaleString('id-ID');
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('id-ID') : '-';

export default function AccountsReceivableModule({ token, userRole }) {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [dateFilter, setDateFilter] = useState('all');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [payForm, setPayForm] = useState({ payment_date: new Date().toISOString().split('T')[0], amount: '', payment_method: 'Transfer Bank', reference_number: '', notes: '' });
  const [saving, setSaving] = useState(false);

  const canEdit = ['superadmin', 'admin', 'finance'].includes(userRole);

  useEffect(() => { fetchInvoices(); }, [filterStatus, dateFilter, customFrom, customTo]);

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const range = dateFilter === 'custom' ? { date_from: customFrom, date_to: customTo } : getDateRange(dateFilter);
      const params = new URLSearchParams({ category: 'BUYER' });
      if (filterStatus) params.set('status', filterStatus);
      if (range.date_from) params.set('date_from', range.date_from);
      if (range.date_to) params.set('date_to', range.date_to);
      const res = await fetch(`/api/invoices?${params}`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      setInvoices(Array.isArray(data) ? data : []);
    } catch (e) { setInvoices([]); } finally { setLoading(false); }
  };

  const openDetail = async (inv) => {
    const res = await fetch(`/api/invoices/${inv.id}`, { headers: { Authorization: `Bearer ${token}` } });
    const data = await res.json();
    setSelectedInvoice(data);
    setShowDetail(true);
  };

  const openPayment = (inv) => {
    setSelectedInvoice(inv);
    const outstanding = (inv.total_amount || 0) - (inv.total_paid || 0);
    setPayForm({ payment_date: new Date().toISOString().split('T')[0], amount: outstanding.toString(), payment_method: 'Transfer Bank', reference_number: '', notes: '' });
    setShowPaymentModal(true);
  };

  const handlePayment = async (e) => {
    e.preventDefault();
    setSaving(true);
    const res = await fetch('/api/payments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...payForm, invoice_id: selectedInvoice.id, amount: Number(payForm.amount), payment_type: 'CUSTOMER_PAYMENT' })
    });
    const data = await res.json();
    setSaving(false);
    if (!res.ok) { alert(data.error || 'Gagal menyimpan pembayaran'); return; }
    setShowPaymentModal(false);
    fetchInvoices();
  };

  const totalOutstanding = invoices.filter(i => i.status !== 'Paid').reduce((s, i) => s + (i.total_amount || 0) - (i.total_paid || 0), 0);
  const totalReceived = invoices.reduce((s, i) => s + (i.total_paid || 0), 0);
  const totalAll = invoices.reduce((s, i) => s + (i.total_amount || 0), 0);
  const unpaidCount = invoices.filter(i => i.status === 'Unpaid').length;
  const partialCount = invoices.filter(i => i.status === 'Partial').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Piutang (AR)</h1>
          <p className="text-muted-foreground text-sm mt-1">Kelola tagihan kepada pelanggan. Invoice dapat dibuat otomatis atau manual.</p>
        </div>
        <button onClick={fetchInvoices} className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg text-sm hover:bg-[var(--glass-bg)]">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Piutang', value: fmt(totalAll), cls: 'text-foreground', bg: 'bg-[var(--glass-bg)] border-border', icon: <FileText className="w-5 h-5 text-muted-foreground" /> },
          { label: 'Belum Diterima', value: fmt(totalOutstanding), cls: 'text-red-700', bg: 'bg-red-50 border-red-200', icon: <AlertTriangle className="w-5 h-5 text-red-500" /> },
          { label: 'Sudah Diterima', value: fmt(totalReceived), cls: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200', icon: <CheckCircle className="w-5 h-5 text-emerald-500" /> },
          { label: 'Unpaid / Partial', value: `${unpaidCount} unpaid · ${partialCount} partial`, cls: 'text-amber-700', bg: 'bg-amber-50 border-amber-200', icon: <Clock className="w-5 h-5 text-amber-500" /> },
        ].map(s => (
          <div key={s.label} className={`${s.bg} border rounded-xl p-4`}>
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              {s.icon}
            </div>
            <p className={`text-lg font-bold mt-1 ${s.cls}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Progress Bar */}
      {totalAll > 0 && (
        <div className="bg-[var(--card-surface)] rounded-xl border border-border p-4 shadow-sm">
          <div className="flex justify-between items-center mb-2">
            <h3 className="font-semibold text-foreground text-sm">Collection Progress</h3>
            <span className="text-sm font-bold text-emerald-700">{Math.round((totalReceived / totalAll) * 100)}% terkumpul</span>
          </div>
          <div className="w-full bg-secondary rounded-full h-3">
            <div
              className="h-3 rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.round((totalReceived / totalAll) * 100))}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>Terkumpul: {fmt(totalReceived)}</span>
            <span>Sisa: {fmt(totalOutstanding)}</span>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-muted-foreground font-semibold">Periode:</span>
          {FILTER_OPTIONS.map(opt => (
            <button key={opt.value} onClick={() => setDateFilter(opt.value)}
              className={`px-3 py-1.5 rounded-lg text-sm border ${dateFilter === opt.value ? 'bg-primary text-white border-blue-600' : 'border-border text-muted-foreground hover:bg-[var(--glass-bg)]'}`}>
              {opt.label}
            </button>
          ))}
          {dateFilter === 'custom' && (
            <div className="flex items-center gap-2">
              <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)} className="border border-border rounded-lg px-2 py-1.5 text-sm" />
              <span className="text-muted-foreground">—</span>
              <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)} className="border border-border rounded-lg px-2 py-1.5 text-sm" />
              <button onClick={fetchInvoices} className="px-3 py-1.5 bg-primary text-white rounded-lg text-sm">OK</button>
            </div>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          {STATUS_OPTS.map(s => (
            <button key={s} onClick={() => setFilterStatus(s)}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${filterStatus === s ? 'bg-emerald-600 text-white border-emerald-600' : 'border-border text-muted-foreground hover:bg-[var(--glass-bg)]'}`}>
              {s || 'Semua Status'}
            </button>
          ))}
          <span className="ml-auto text-xs text-muted-foreground self-center">{invoices.length} invoice</span>
        </div>
      </div>

      {/* Invoice List */}
      {loading ? (
        <div className="text-center py-16">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-muted-foreground" />
          <p className="text-muted-foreground">Memuat data...</p>
        </div>
      ) : invoices.length === 0 ? (
        <div className="text-center py-16">
          <FileText className="w-12 h-12 mx-auto mb-3 text-muted-foreground" />
          <p className="text-muted-foreground font-medium">Belum ada invoice piutang</p>
          <p className="text-muted-foreground text-sm mt-1">Invoice dapat dibuat otomatis saat terjadi pengiriman produk, atau dibuat manual.</p>
        </div>
      ) : (
        <div className="bg-[var(--card-surface)] rounded-xl border border-border overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-[var(--glass-bg)] border-b border-border">
              <tr>
                {['No. Invoice', 'Customer', 'No. PO', 'Tgl. Terbit', 'Total', 'Diterima', 'Sisa', 'Status', 'Aksi'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {invoices.map(inv => {
                const outstanding = (inv.total_amount || 0) - (inv.total_paid || 0);
                return (
                  <tr key={inv.id} className="hover:bg-[var(--glass-bg)]">
                    <td className="px-4 py-3 font-bold text-primary">{inv.invoice_number}</td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-foreground">{inv.customer_name || '-'}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{inv.po_number || '-'}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{fmtDate(inv.created_at)}</td>
                    <td className="px-4 py-3 font-bold text-foreground">{fmt(inv.total_amount)}</td>
                    <td className="px-4 py-3 text-emerald-700">{fmt(inv.total_paid)}</td>
                    <td className={`px-4 py-3 font-bold ${outstanding > 0 ? 'text-red-600' : 'text-emerald-700'}`}>{fmt(outstanding)}</td>
                    <td className="px-4 py-3"><ARStatusBadge status={inv.status} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button onClick={() => openDetail(inv)} className="p-1.5 rounded hover:bg-primary/10 text-primary" title="Detail">
                          <Eye className="w-4 h-4" />
                        </button>
                        {canEdit && inv.status !== 'Paid' && (
                          <button onClick={() => openPayment(inv)} className="p-1.5 rounded hover:bg-emerald-50 text-emerald-600" title="Terima Pembayaran">
                            <CreditCard className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="bg-[var(--glass-bg)] border-t-2 border-border">
              <tr>
                <td className="px-4 py-3 font-bold text-foreground" colSpan={4}>Total ({invoices.length} invoice)</td>
                <td className="px-4 py-3 font-bold">{fmt(totalAll)}</td>
                <td className="px-4 py-3 font-bold text-emerald-700">{fmt(totalReceived)}</td>
                <td className="px-4 py-3 font-bold text-red-600">{fmt(totalOutstanding)}</td>
                <td colSpan={2}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* Detail Modal */}
      {showDetail && selectedInvoice && (
        <Modal title={`Detail Invoice: ${selectedInvoice.invoice_number}`} onClose={() => setShowDetail(false)} size="xl">
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              {[
                { l: 'No. Invoice', v: <span className="font-bold text-primary">{selectedInvoice.invoice_number}</span> },
                { l: 'Status', v: <ARStatusBadge status={selectedInvoice.status} /> },
                { l: 'Customer', v: selectedInvoice.customer_name || '-' },
                { l: 'No. PO', v: selectedInvoice.po_number || '-' },
                { l: 'Total Tagihan', v: <span className="font-bold">{fmt(selectedInvoice.total_amount)}</span> },
                { l: 'Sisa Tagihan', v: <span className={`font-bold ${(selectedInvoice.total_amount - selectedInvoice.total_paid) > 0 ? 'text-red-600' : 'text-emerald-700'}`}>{fmt((selectedInvoice.total_amount || 0) - (selectedInvoice.total_paid || 0))}</span> },
              ].map(it => <div key={it.l} className="bg-[var(--glass-bg)] rounded-lg p-3"><p className="text-xs text-muted-foreground">{it.l}</p><div className="font-medium text-sm mt-0.5">{it.v}</div></div>)}
            </div>

            {/* Payment History */}
            {(selectedInvoice.payments || []).length > 0 && (
              <div>
                <h4 className="font-semibold text-foreground mb-2">Riwayat Penerimaan Pembayaran</h4>
                <div className="space-y-2">
                  {selectedInvoice.payments.map((p, i) => (
                    <div key={p.id} className="bg-emerald-50 rounded-lg p-3 flex justify-between items-center">
                      <div>
                        <p className="text-sm font-medium text-foreground">Pembayaran #{i + 1} — {p.payment_method}</p>
                        <p className="text-xs text-muted-foreground">{fmtDate(p.payment_date)} {p.reference ? `• Ref: ${p.reference}` : ''}</p>
                      </div>
                      <span className="font-bold text-emerald-700">{fmt(p.amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {canEdit && selectedInvoice.status !== 'Paid' && (
              <button onClick={() => { setShowDetail(false); openPayment(selectedInvoice); }}
                className="w-full flex items-center justify-center gap-2 bg-emerald-600 text-white py-2 rounded-lg text-sm hover:bg-emerald-700">
                <CreditCard className="w-4 h-4" /> Terima Pembayaran
              </button>
            )}
          </div>
        </Modal>
      )}

      {/* Payment Modal */}
      {showPaymentModal && selectedInvoice && (
        <Modal title={`Terima Pembayaran: ${selectedInvoice.invoice_number}`} onClose={() => setShowPaymentModal(false)}>
          <form onSubmit={handlePayment} className="space-y-4">
            <div className="bg-[var(--glass-bg)] rounded-xl p-4">
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div><p className="text-xs text-muted-foreground">Customer</p><p className="font-medium">{selectedInvoice.customer_name}</p></div>
                <div><p className="text-xs text-muted-foreground">Total Tagihan</p><p className="font-bold">{fmt(selectedInvoice.total_amount)}</p></div>
                <div><p className="text-xs text-muted-foreground">Sisa Belum Diterima</p><p className="font-bold text-red-600">{fmt((selectedInvoice.total_amount || 0) - (selectedInvoice.total_paid || 0))}</p></div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Tanggal Terima *</label>
                <input type="date" required className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={payForm.payment_date} onChange={e => setPayForm({ ...payForm, payment_date: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Jumlah (Rp) *</label>
                <input type="number" required min="1" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={payForm.amount} onChange={e => setPayForm({ ...payForm, amount: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Metode</label>
                <select className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={payForm.payment_method} onChange={e => setPayForm({ ...payForm, payment_method: e.target.value })}>
                  {PAYMENT_METHODS.map(m => <option key={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">No. Referensi</label>
                <input className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={payForm.reference_number} onChange={e => setPayForm({ ...payForm, reference_number: e.target.value })} placeholder="No. BG / Transfer" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Catatan</label>
              <textarea rows="2" className="w-full border border-border rounded-lg px-3 py-2 text-sm" value={payForm.notes} onChange={e => setPayForm({ ...payForm, notes: e.target.value })} />
            </div>
            <div className="flex gap-3">
              <button type="submit" disabled={saving} className="flex-1 bg-emerald-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
                {saving ? 'Menyimpan...' : 'Simpan Penerimaan'}
              </button>
              <button type="button" onClick={() => setShowPaymentModal(false)} className="flex-1 border border-border py-2 rounded-lg text-sm hover:bg-[var(--glass-bg)]">Batal</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
