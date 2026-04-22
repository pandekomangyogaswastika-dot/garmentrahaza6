import { useState, useEffect, useCallback } from 'react';
import { Plus, RefreshCw, FileText, DollarSign, Calendar, Users } from 'lucide-react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import { PageHeader, StatTile, StatusBadge, EmptyState } from './moduleAtoms';
import { DataTable } from './DataTableV2';

const fmt = (n) => `Rp ${Number(n || 0).toLocaleString('id-ID')}`;

export default function RahazaARInvoicesModule({ token }) {
  const [invoices, setInvoices] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [creating, setCreating] = useState(false);
  const [paying, setPaying] = useState(null);
  const [showStatement, setShowStatement] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [inv, cs, acc] = await Promise.all([
        fetch('/api/rahaza/ar-invoices', { headers }).then(r => r.json()),
        fetch('/api/rahaza/customers', { headers }).then(r => r.json()),
        fetch('/api/rahaza/cash-accounts', { headers }).then(r => r.json()),
      ]);
      setInvoices(Array.isArray(inv) ? inv : []);
      setCustomers(Array.isArray(cs) ? cs : []);
      setAccounts(Array.isArray(acc) ? acc : []);
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  useEffect(() => { fetchAll(); }, [fetchAll]);

  const changeStatus = async (id, status) => {
    const r = await fetch(`/api/rahaza/ar-invoices/${id}/status`, { method: 'POST', headers, body: JSON.stringify({ status }) });
    if (r.ok) fetchAll();
  };

  const create = async (body) => {
    const r = await fetch('/api/rahaza/ar-invoices', { method: 'POST', headers, body: JSON.stringify(body) });
    if (!r.ok) { setError(`Gagal buat invoice (HTTP ${r.status})`); return; }
    setCreating(false); fetchAll();
  };

  const pay = async (body) => {
    const r = await fetch(`/api/rahaza/ar-invoices/${paying.id}/payment`, { method: 'POST', headers, body: JSON.stringify(body) });
    if (!r.ok) { setError(`Gagal record pembayaran (HTTP ${r.status})`); return; }
    setPaying(null); fetchAll();
  };

  const total = invoices.reduce((s, i) => s + (Number(i.total) || 0), 0);
  const outstanding = invoices.reduce((s, i) => s + (Number(i.balance) || 0), 0);

  return (
    <div className="space-y-5" data-testid="rahaza-ar-page">
      <PageHeader
        icon={FileText}
        eyebrow="Portal Finance · Rahaza Finance"
        title="AR Invoices"
        subtitle="Invoice ke pelanggan dengan dukungan partial payment, aging analysis, dan link otomatis ke cash account."
        actions={
          <>
            <Button variant="ghost" onClick={fetchAll} className="h-9 border border-[var(--glass-border)]"><RefreshCw className="w-3.5 h-3.5 mr-1.5" />Refresh</Button>
            <Button variant="ghost" onClick={() => setShowStatement(true)} className="h-9 border border-[var(--glass-border)]" data-testid="ar-statement-btn"><Users className="w-3.5 h-3.5 mr-1.5" />Statement Pelanggan</Button>
            <Button onClick={() => setCreating(true)} className="h-9" data-testid="ar-create"><Plus className="w-3.5 h-3.5 mr-1.5" />Invoice Baru</Button>
          </>
        }
      />
      {error && <div className="bg-[hsl(var(--destructive)/0.12)] border border-[hsl(var(--destructive)/0.22)] rounded-lg p-3 text-sm text-[hsl(var(--destructive))]">{error}</div>}
      <div className="grid grid-cols-3 gap-2">
        <StatTile label="Total Invoice" value={invoices.length} accent="primary" />
        <StatTile label="Total Nilai" value={fmt(total)} accent="default" />
        <StatTile label="Outstanding" value={fmt(outstanding)} accent="warning" />
      </div>
      {loading ? <div className="flex items-center justify-center h-48"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" /></div> : (
        <DataTable
          tableId="ar-invoices"
          rows={invoices}
          searchFields={['invoice_number', 'customer_name', 'status']}
          filters={[
            { key: 'status', label: 'Status', type: 'select', options: [
              { value: 'draft', label: 'Draft' },
              { value: 'sent', label: 'Terkirim' },
              { value: 'partial_paid', label: 'Paid (Partial)' },
              { value: 'paid', label: 'Paid' },
              { value: 'overdue', label: 'Overdue' },
              { value: 'cancelled', label: 'Cancelled' },
            ] },
            { key: 'issue_date', label: 'Terbit', type: 'date-range' },
          ]}
          columns={[
            { key: 'invoice_number', label: 'Invoice #', sortable: true,
              render: (r, v) => <span className="font-mono text-xs">{v}</span> },
            { key: 'customer_name', label: 'Pelanggan', sortable: true,
              render: (r, v) => <span>{v || '-'}</span> },
            { key: 'issue_date', label: 'Terbit / Due', sortable: true,
              render: (r) => <span className="text-[11px] text-foreground/60">{r.issue_date} / {r.due_date}</span> },
            { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
            { key: 'total', label: 'Total', align: 'right', sortable: true,
              render: (r) => <span className="font-mono">{fmt(r.total)}</span> },
            { key: 'balance', label: 'Balance', align: 'right', sortable: true,
              render: (r) => <span className="font-mono text-[hsl(var(--warning))]">{fmt(r.balance)}</span> },
          ]}
          emptyTitle="Belum ada invoice"
          emptyDescription='Klik "Invoice Baru" untuk membuat invoice ke pelanggan.'
          emptyIcon={FileText}
          exportFilename={`ar-invoices-${new Date().toISOString().slice(0,10)}.csv`}
          rowActions={(r) => (
            <div className="inline-flex items-center gap-2">
              {r.status === 'draft' && <button onClick={() => changeStatus(r.id, 'sent')} className="text-xs text-[hsl(var(--primary))] hover:underline">Kirim</button>}
              {['sent','partial_paid','overdue'].includes(r.status) && <button onClick={() => setPaying(r)} className="text-xs text-[hsl(var(--success))] hover:underline" data-testid={`ar-pay-${r.invoice_number}`}><DollarSign className="w-3 h-3 inline" /> Bayar</button>}
            </div>
          )}
        />
      )}
      {creating && <CreateInvoiceModal customers={customers} onClose={() => setCreating(false)} onCreate={create} />}
      {paying && <PaymentModal invoice={paying} accounts={accounts} onClose={() => setPaying(null)} onPay={pay} />}
      {showStatement && <CustomerStatementModal token={token} customers={customers} onClose={() => setShowStatement(false)} />}
    </div>
  );
}

function CreateInvoiceModal({ customers, onClose, onCreate }) {
  const today = new Date().toISOString().split('T')[0];
  const [customer_id, setCustomerId] = useState('');
  const [issue_date, setIssue] = useState(today);
  const [due_date, setDue] = useState(today);
  const [items, setItems] = useState([{ description: '', qty: 1, unit: 'pcs', price: 0 }]);
  const [tax_pct, setTax] = useState(0);
  const subtotal = items.reduce((s, i) => s + (Number(i.qty) || 0) * (Number(i.price) || 0), 0);
  const tax = subtotal * Number(tax_pct) / 100;
  const total = subtotal + tax;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <GlassCard className="p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-foreground mb-4">Buat AR Invoice</h2>
        <div className="space-y-3">
          <div><label className="text-xs uppercase text-muted-foreground">Pelanggan</label><select value={customer_id} onChange={e => setCustomerId(e.target.value)} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground" data-testid="ar-create-customer"><option value="">— Pilih —</option>{customers.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</select></div>
          <div className="grid grid-cols-2 gap-2">
            <div><label className="text-xs uppercase text-muted-foreground">Tanggal Terbit</label><GlassInput type="date" value={issue_date} onChange={e => setIssue(e.target.value)} /></div>
            <div><label className="text-xs uppercase text-muted-foreground">Jatuh Tempo</label><GlassInput type="date" value={due_date} onChange={e => setDue(e.target.value)} /></div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-2"><label className="text-xs uppercase text-muted-foreground">Items</label><Button variant="ghost" className="h-7 px-2 text-xs border border-[var(--glass-border)]" onClick={() => setItems(i => [...i, { description:'', qty:1, unit:'pcs', price:0 }])}><Plus className="w-3 h-3 mr-1" />Tambah</Button></div>
            <div className="space-y-2">
              {items.map((it, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <GlassInput className="col-span-5 h-9 text-xs" placeholder="Deskripsi" value={it.description} onChange={e => setItems(x => x.map((r,idx)=> idx===i ? {...r, description:e.target.value} : r))} />
                  <GlassInput className="col-span-2 h-9 text-xs text-right" type="number" min={0} placeholder="Qty" value={it.qty} onChange={e => setItems(x => x.map((r,idx)=> idx===i ? {...r, qty:Number(e.target.value)} : r))} />
                  <GlassInput className="col-span-2 h-9 text-xs" placeholder="Unit" value={it.unit} onChange={e => setItems(x => x.map((r,idx)=> idx===i ? {...r, unit:e.target.value} : r))} />
                  <GlassInput className="col-span-3 h-9 text-xs text-right" type="number" min={0} placeholder="Harga" value={it.price} onChange={e => setItems(x => x.map((r,idx)=> idx===i ? {...r, price:Number(e.target.value)} : r))} />
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div><label className="text-xs uppercase text-muted-foreground">Pajak (%)</label><GlassInput type="number" min={0} max={100} value={tax_pct} onChange={e => setTax(Number(e.target.value))} /></div>
            <div className="self-end bg-[var(--glass-bg)] border border-[var(--glass-border)] rounded p-2 text-right"><div className="text-xs text-muted-foreground">Total</div><div className="text-lg font-bold text-foreground font-mono">{fmt(total)}</div></div>
          </div>
        </div>
        <div className="flex gap-2 mt-6 justify-end"><Button variant="ghost" onClick={onClose} className="border border-[var(--glass-border)]">Batal</Button><Button onClick={() => onCreate({ customer_id, issue_date, due_date, items: items.filter(i => i.description), tax_pct })} data-testid="ar-create-submit">Buat Invoice</Button></div>
      </GlassCard>
    </div>
  );
}

function PaymentModal({ invoice, accounts, onClose, onPay }) {
  const [amount, setAmount] = useState(invoice.balance);
  const [account_id, setAccount] = useState(accounts[0]?.id || '');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [notes, setNotes] = useState('');
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <GlassCard className="p-6 max-w-md w-full" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-foreground mb-2">Record Pembayaran</h2>
        <p className="text-xs text-muted-foreground mb-4">{invoice.invoice_number} · Balance: {fmt(invoice.balance)}</p>
        <div className="space-y-3">
          <div><label className="text-xs uppercase text-muted-foreground">Jumlah</label><GlassInput type="number" min={0} step="1000" value={amount} onChange={e => setAmount(Number(e.target.value))} data-testid="ar-pay-amount" /></div>
          <div><label className="text-xs uppercase text-muted-foreground">Rekening</label><select value={account_id} onChange={e => setAccount(e.target.value)} className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground"><option value="">— Tidak link ke rekening —</option>{accounts.map(a => <option key={a.id} value={a.id}>{a.code} · {a.name} ({fmt(a.balance)})</option>)}</select></div>
          <div><label className="text-xs uppercase text-muted-foreground">Tanggal</label><GlassInput type="date" value={date} onChange={e => setDate(e.target.value)} /></div>
          <div><label className="text-xs uppercase text-muted-foreground">Catatan</label><GlassInput value={notes} onChange={e => setNotes(e.target.value)} /></div>
        </div>
        <div className="flex gap-2 mt-6 justify-end"><Button variant="ghost" onClick={onClose} className="border border-[var(--glass-border)]">Batal</Button><Button onClick={() => onPay({ amount, account_id, date, notes })} data-testid="ar-pay-submit"><DollarSign className="w-4 h-4 mr-1.5" />Simpan</Button></div>
      </GlassCard>
    </div>
  );
}


// ─── Customer Statement Modal (Phase 14.5) ──────────────────────────────────
function CustomerStatementModal({ token, customers, onClose }) {
  const today = new Date().toISOString().split('T')[0];
  const firstOfMonth = today.slice(0, 7) + '-01';
  const [customer_id, setCustomerId] = useState(customers[0]?.id || '');
  const [date_from, setFrom] = useState(firstOfMonth);
  const [date_to, setTo] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const load = async () => {
    if (!customer_id) { setErr('Pilih pelanggan dulu'); return; }
    setErr(''); setLoading(true); setData(null);
    try {
      const url = `/api/rahaza/shipments/customer-statement/${customer_id}?date_from=${date_from}&date_to=${date_to}`;
      const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) { setErr(`Gagal memuat (HTTP ${r.status})`); return; }
      const d = await r.json();
      setData(d);
    } finally { setLoading(false); }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <GlassCard
        className="p-6 max-w-3xl w-full max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
              <Users className="w-5 h-5 text-[hsl(var(--primary))]" /> Statement Pelanggan
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Ringkasan piutang (AR) per pelanggan untuk rentang tanggal tertentu.
            </p>
          </div>
          <button onClick={onClose} className="text-foreground/60 hover:text-foreground text-sm">✕</button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <div className="md:col-span-2">
            <label className="text-xs uppercase tracking-wider text-muted-foreground mb-1 block">Pelanggan</label>
            <select
              value={customer_id}
              onChange={(e) => setCustomerId(e.target.value)}
              className="w-full h-10 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground"
              data-testid="stmt-customer"
            >
              <option value="">— Pilih —</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.code} · {c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider text-muted-foreground mb-1 block">Dari</label>
            <GlassInput type="date" value={date_from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div>
            <label className="text-xs uppercase tracking-wider text-muted-foreground mb-1 block">Sampai</label>
            <GlassInput type="date" value={date_to} onChange={(e) => setTo(e.target.value)} />
          </div>
        </div>

        <div className="flex justify-end mb-3">
          <Button onClick={load} disabled={loading} data-testid="stmt-load">
            <Calendar className="w-4 h-4 mr-1.5" /> {loading ? 'Memuat...' : 'Tampilkan'}
          </Button>
        </div>

        {err && (
          <div className="bg-[hsl(var(--destructive)/0.12)] border border-[hsl(var(--destructive)/0.22)] rounded-lg p-3 text-sm text-[hsl(var(--destructive))] mb-3">
            {err}
          </div>
        )}

        {data && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <StatTile label="Jumlah Invoice" value={data.summary.count} accent="primary" />
              <StatTile label="Total Tagihan" value={fmt(data.summary.total_billed)} accent="default" />
              <StatTile label="Total Dibayar" value={fmt(data.summary.total_paid)} accent="success" />
              <StatTile label="Outstanding" value={fmt(data.summary.outstanding)} accent="warning" />
            </div>

            <div className="border border-[var(--glass-border)] rounded-lg overflow-hidden">
              <div className="grid grid-cols-12 gap-2 px-3 py-2 bg-[var(--glass-bg)] text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                <div className="col-span-3">Invoice</div>
                <div className="col-span-2">Terbit</div>
                <div className="col-span-2">Status</div>
                <div className="col-span-2 text-right">Total</div>
                <div className="col-span-3 text-right">Balance</div>
              </div>
              <div className="divide-y divide-[var(--glass-border)] max-h-[40vh] overflow-y-auto">
                {(data.invoices || []).length === 0 ? (
                  <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                    Tidak ada invoice pada periode ini.
                  </div>
                ) : (
                  data.invoices.map((inv) => (
                    <div key={inv.id} className="grid grid-cols-12 gap-2 px-3 py-2 items-center text-xs">
                      <div className="col-span-3 font-mono text-[11px]">{inv.invoice_number}</div>
                      <div className="col-span-2 text-foreground/70">{inv.issue_date}</div>
                      <div className="col-span-2"><StatusBadge status={inv.status} /></div>
                      <div className="col-span-2 text-right font-mono">{fmt(inv.total)}</div>
                      <div className="col-span-3 text-right font-mono text-[hsl(var(--warning))]">
                        {fmt(inv.balance)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        <div className="flex justify-end mt-6">
          <Button variant="ghost" onClick={onClose} className="border border-[var(--glass-border)]">Tutup</Button>
        </div>
      </GlassCard>
    </div>
  );
}
