
import { useState, useEffect, useCallback } from 'react';
import { Download, FileText, BarChart2, TrendingUp, CreditCard, Factory, Truck, RotateCcw, AlertTriangle, RefreshCw, Search, Filter, Calendar, ChevronDown, ChevronRight, Package } from 'lucide-react';

const REPORT_TYPES = [
  { id: 'production', label: 'Laporan Produksi', icon: Factory, description: 'Data PO & produksi lengkap', color: 'blue' },
  { id: 'progress', label: 'Laporan Progres', icon: TrendingUp, description: 'Riwayat progres produksi', color: 'emerald' },
  { id: 'financial', label: 'Laporan Keuangan', icon: CreditCard, description: 'Invoice, pembayaran & adjustment', color: 'purple' },
  { id: 'shipment', label: 'Laporan Pengiriman', icon: Truck, description: 'Vendor & Buyer shipment', color: 'amber' },
  { id: 'return', label: 'Laporan Retur', icon: RotateCcw, description: 'Retur produksi', color: 'red' },
  { id: 'missing-material', label: 'Material Hilang', icon: AlertTriangle, description: 'Permintaan material tambahan', color: 'orange' },
  { id: 'replacement', label: 'Material Pengganti', icon: Package, description: 'Permintaan penggantian material', color: 'teal' },
];

const fmt = (v) => 'Rp ' + Number(v || 0).toLocaleString('id-ID');
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('id-ID') : '-';
const fmtNum = (v) => (v || 0).toLocaleString('id-ID');

export default function ReportsModule({ token }) {
  const [activeReport, setActiveReport] = useState('production');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [vendors, setVendors] = useState([]);
  const [pos, setPos] = useState([]);

  // Filters
  const [filters, setFilters] = useState({
    date_from: '', date_to: '', vendor_id: '', po_id: '', serial_number: '', status: ''
  });
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchVendors();
    fetchPOs();
  }, []);

  useEffect(() => {
    fetchReport();
  }, [activeReport]);

  const fetchVendors = async () => {
    try {
      const res = await fetch('/api/garments', { headers: { Authorization: `Bearer ${token}` } });
      const d = await res.json();
      setVendors(Array.isArray(d) ? d : []);
    } catch (e) { setVendors([]); }
  };

  const fetchPOs = async () => {
    try {
      const res = await fetch('/api/production-pos', { headers: { Authorization: `Bearer ${token}` } });
      const d = await res.json();
      setPos(Array.isArray(d) ? d : []);
    } catch (e) { setPos([]); }
  };

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
      const res = await fetch(`/api/reports/${activeReport}?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const result = await res.json();
      setData(Array.isArray(result) ? result : []);
    } catch (e) { setData([]); }
    setLoading(false);
  }, [activeReport, filters, token]);

  const handleFilter = () => {
    fetchReport();
  };

  const resetFilters = () => {
    setFilters({ date_from: '', date_to: '', vendor_id: '', po_id: '', serial_number: '', status: '' });
  };

  // Excel export using server-side endpoint
  const exportToExcel = async () => {
    if (!data.length) return;
    try {
      const params = new URLSearchParams({ type: `report-${activeReport}` });
      Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
      const res = await fetch(`/api/export-excel?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `laporan_${activeReport}_${new Date().toISOString().split('T')[0]}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        // Fallback to client-side export
        const XLSX = (await import('xlsx')).default || (await import('xlsx'));
        const colDefs = getColumns();
        const headers = colDefs.map(c => c.label);
        const rows = data.map(row => colDefs.map(c => {
          const val = row[c.key];
          if (c.format === 'date') return fmtDate(val);
          if (c.format === 'currency') return Number(val || 0);
          if (c.format === 'number') return Number(val || 0);
          return val ?? '';
        }));
        const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);
        const colWidths = headers.map((h, i) => ({
          wch: Math.min(Math.max(h.length, ...rows.map(r => String(r[i] || '').length)) + 2, 30)
        }));
        ws['!cols'] = colWidths;
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, activeReport);
        XLSX.writeFile(wb, `laporan_${activeReport}_${new Date().toISOString().split('T')[0]}.xlsx`);
      }
    } catch (e) {
      console.error('Excel export error:', e);
      alert('Gagal export Excel: ' + e.message);
    }
  };

  // PDF export
  const exportToPDF = async () => {
    if (!data.length) return;
    try {
      const params = new URLSearchParams({ type: `report-${activeReport}` });
      Object.entries(filters).forEach(([k, v]) => { if (v) params.append(k, v); });
      const res = await fetch(`/api/export-pdf?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `laporan_${activeReport}_${new Date().toISOString().split('T')[0]}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        // Fallback: CSV download
        alert('PDF export gagal, coba export Excel/CSV sebagai alternatif');
      }
    } catch (e) {
      alert('Error: ' + e.message);
    }
  };

  const exportToCSV = () => {
    if (!data.length) return;
    const colDefs = getColumns();
    const headers = colDefs.map(c => c.label);
    const rows = data.map(row => colDefs.map(c => {
      const val = row[c.key];
      if (c.format === 'date') return fmtDate(val);
      if (c.format === 'currency') return Number(val || 0);
      return String(val ?? '').replace(/,/g, ';');
    }));
    const csv = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `laporan_${activeReport}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const getColumns = () => {
    switch (activeReport) {
      case 'production':
        return [
          { key: '_no', label: 'NO', format: 'number' },
          { key: 'tanggal', label: 'TANGGAL', format: 'date' },
          { key: 'no_po', label: 'NO-PO' },
          { key: 'no_seri', label: 'NO-SERI' },
          { key: 'kode_produk', label: 'KODE-PRODUK' },
          { key: 'nama_produk', label: 'NAMA-PRODUK' },
          { key: 'kategori', label: 'KATEGORI' },
          { key: 'size', label: 'SIZE' },
          { key: 'sku', label: 'SKU' },
          { key: 'warna', label: 'WARNA' },
          { key: 'output_qty', label: 'OUTPUT(QTY)', format: 'number' },
          { key: 'harga', label: 'HARGA', format: 'currency' },
          { key: 'hpp', label: 'HPP', format: 'currency' },
          { key: 'hasil_po', label: 'HASIL-PO', format: 'currency' },
          { key: 'total_hpp', label: 'TOTAL-HPP', format: 'currency' },
          { key: 'garment', label: 'GARMENT' },
          { key: 'note', label: 'NOTE' },
          { key: 'qty_sudah_diproduksi', label: 'QTY SUDAH DIPRODUKSI', format: 'number' },
          { key: 'qty_belum_diproduksi', label: 'QTY BELUM DIPRODUKSI', format: 'number' },
          { key: 'qty_sudah_dikirim', label: 'QTY SUDAH DIKIRIM', format: 'number' },
        ];
      case 'progress':
        return [
          { key: 'date', label: 'Tanggal', format: 'date' },
          { key: 'po_number', label: 'No. PO' },
          { key: 'serial_number', label: 'No. Seri' },
          { key: 'vendor', label: 'Vendor' },
          { key: 'sku', label: 'SKU' },
          { key: 'product_name', label: 'Produk' },
          { key: 'qty_progress', label: 'Qty Progres', format: 'number' },
          { key: 'cumulative_produced', label: 'Kumulatif Produksi', format: 'number' },
          { key: 'cumulative_shipped', label: 'Kumulatif Kirim', format: 'number' },
          { key: 'status', label: 'Status' },
          { key: 'notes', label: 'Catatan' },
          { key: 'operator', label: 'Operator' },
        ];
      case 'financial':
        return [
          { key: 'invoice_number', label: 'No. Invoice' },
          { key: 'invoice_category', label: 'Kategori' },
          { key: 'po_number', label: 'No. PO' },
          { key: 'vendor_or_customer', label: 'Vendor / Customer' },
          { key: 'base_amount', label: 'Nilai Dasar', format: 'currency' },
          { key: 'adjustment_add', label: 'Adjustment (+)', format: 'currency' },
          { key: 'adjustment_deduct', label: 'Adjustment (-)', format: 'currency' },
          { key: 'adjusted_total', label: 'Total Final', format: 'currency' },
          { key: 'total_paid', label: 'Dibayar', format: 'currency' },
          { key: 'remaining', label: 'Sisa', format: 'currency' },
          { key: 'status', label: 'Status' },
          { key: 'created_at', label: 'Tanggal', format: 'date' },
        ];
      case 'shipment':
        return [
          { key: 'direction', label: 'Arah' },
          { key: 'shipment_number', label: 'No. Shipment' },
          { key: 'shipment_type', label: 'Tipe' },
          { key: 'vendor_name', label: 'Vendor' },
          { key: 'date', label: 'Tanggal', format: 'date' },
          { key: 'total_qty', label: 'Total Qty', format: 'number' },
          { key: 'item_count', label: 'Jumlah Item', format: 'number' },
          { key: 'status', label: 'Status' },
          { key: 'inspection_status', label: 'Inspeksi' },
          { key: 'notes', label: 'Catatan' },
        ];
      case 'return':
        return [
          { key: 'return_number', label: 'No. Retur' },
          { key: 'vendor_name', label: 'Vendor' },
          { key: 'po_number', label: 'No. PO' },
          { key: 'return_date', label: 'Tanggal', format: 'date' },
          { key: 'total_qty', label: 'Total Qty', format: 'number' },
          { key: 'reason', label: 'Alasan' },
          { key: 'status', label: 'Status' },
          { key: 'notes', label: 'Catatan' },
        ];
      case 'missing-material':
      case 'replacement':
        return [
          { key: 'request_number', label: 'No. Permintaan' },
          { key: 'vendor_name', label: 'Vendor' },
          { key: 'po_number', label: 'No. PO' },
          { key: 'serial_number', label: 'No. Seri' },
          { key: 'sku', label: 'SKU' },
          { key: 'requested_qty', label: 'Qty Diminta', format: 'number' },
          { key: 'reason', label: 'Alasan' },
          { key: 'status', label: 'Status' },
          { key: 'child_shipment_number', label: 'Shipment Anak' },
          { key: 'created_at', label: 'Tanggal', format: 'date' },
        ];
      default: return [];
    }
  };

  const renderValue = (val, format) => {
    if (format === 'date') return fmtDate(val);
    if (format === 'currency') return fmt(val);
    if (format === 'number') return fmtNum(val);
    return val ?? '-';
  };

  const STATUS_COLORS = {
    'Paid': 'bg-emerald-100 text-emerald-700',
    'Unpaid': 'bg-red-100 text-red-700',
    'Partial': 'bg-amber-100 text-amber-700',
    'Completed': 'bg-emerald-100 text-emerald-700',
    'In Progress': 'bg-primary/15 text-primary',
    'In Production': 'bg-primary/15 text-primary',
    'Pending': 'bg-amber-100 text-amber-700',
    'Approved': 'bg-emerald-100 text-emerald-700',
    'Rejected': 'bg-red-100 text-red-700',
    'Sent': 'bg-primary/15 text-primary',
    'Received': 'bg-emerald-100 text-emerald-700',
    'Draft': 'bg-secondary text-muted-foreground',
    'Closed': 'bg-secondary text-muted-foreground',
  };

  // Summary stats
  const getSummary = () => {
    if (!data.length) return null;
    switch (activeReport) {
      case 'production': {
        const totalQty = data.reduce((s, r) => s + (r.output_qty || 0), 0);
        const totalProd = data.reduce((s, r) => s + (r.qty_sudah_diproduksi || 0), 0);
        const totalShipped = data.reduce((s, r) => s + (r.qty_sudah_dikirim || 0), 0);
        const totalHasil = data.reduce((s, r) => s + (r.hasil_po || 0), 0);
        const totalHPP = data.reduce((s, r) => s + (r.total_hpp || 0), 0);
        return [
          { label: 'Total Order', value: fmtNum(totalQty) + ' pcs' },
          { label: 'Sudah Produksi', value: fmtNum(totalProd) + ' pcs' },
          { label: 'Sudah Kirim', value: fmtNum(totalShipped) + ' pcs' },
          { label: 'Total Hasil PO', value: fmt(totalHasil) },
          { label: 'Total HPP', value: fmt(totalHPP) },
          { label: 'Margin', value: fmt(totalHasil - totalHPP) },
        ];
      }
      case 'financial': {
        const totalBase = data.reduce((s, r) => s + (r.base_amount || 0), 0);
        const totalAdj = data.reduce((s, r) => s + (r.adjusted_total || 0), 0);
        const totalPaid = data.reduce((s, r) => s + (r.total_paid || 0), 0);
        const totalRemaining = data.reduce((s, r) => s + (r.remaining || 0), 0);
        return [
          { label: 'Total Invoice', value: data.length },
          { label: 'Nilai Dasar', value: fmt(totalBase) },
          { label: 'Total Setelah Adj', value: fmt(totalAdj) },
          { label: 'Total Dibayar', value: fmt(totalPaid) },
          { label: 'Sisa', value: fmt(totalRemaining) },
        ];
      }
      case 'shipment': {
        const vendorShips = data.filter(r => r.direction?.includes('VENDOR'));
        const buyerShips = data.filter(r => r.direction?.includes('BUYER'));
        return [
          { label: 'Total Shipment', value: data.length },
          { label: 'Vendor → Produksi', value: vendorShips.length },
          { label: 'Produksi → Buyer', value: buyerShips.length },
          { label: 'Total Qty', value: fmtNum(data.reduce((s, r) => s + (r.total_qty || 0), 0)) + ' pcs' },
        ];
      }
      default: return [{ label: 'Total Records', value: data.length }];
    }
  };

  const summary = getSummary();

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Laporan</h1>
          <p className="text-muted-foreground text-sm mt-1">Laporan operasional dan finansial produksi garmen</p>
        </div>
      </div>

      {/* Report Type Selector */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
        {REPORT_TYPES.map(r => {
          const Icon = r.icon;
          const isActive = activeReport === r.id;
          return (
            <button key={r.id} onClick={() => setActiveReport(r.id)}
              className={`p-3 rounded-xl border text-left transition-all ${
                isActive ? 'bg-primary border-blue-600 text-white shadow-md' : 'bg-[var(--card-surface)] border-border text-foreground hover:border-primary/25 hover:shadow-sm'
              }`}>
              <Icon className={`w-4 h-4 mb-1 ${isActive ? 'text-white' : 'text-primary'}`} />
              <p className={`text-xs font-semibold leading-tight ${isActive ? 'text-white' : 'text-foreground'}`}>{r.label}</p>
            </button>
          );
        })}
      </div>

      {/* Filters */}
      <div className="bg-[var(--card-surface)] rounded-xl border border-border shadow-sm">
        <button onClick={() => setShowFilters(!showFilters)}
          className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-foreground hover:bg-[var(--glass-bg)]">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-primary" />
            <span>Filter & Pencarian</span>
            {Object.values(filters).filter(Boolean).length > 0 && (
              <span className="bg-primary/15 text-primary px-2 py-0.5 rounded-full text-xs font-bold">
                {Object.values(filters).filter(Boolean).length} aktif
              </span>
            )}
          </div>
          {showFilters ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
        {showFilters && (
          <div className="px-5 pb-4 border-t border-border pt-4">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Dari Tanggal</label>
                <input type="date" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={filters.date_from} onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Sampai Tanggal</label>
                <input type="date" className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={filters.date_to} onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Vendor</label>
                <select className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={filters.vendor_id} onChange={e => setFilters(f => ({ ...f, vendor_id: e.target.value }))}>
                  <option value="">Semua Vendor</option>
                  {vendors.map(v => <option key={v.id} value={v.id}>{v.garment_name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">No. PO</label>
                <select className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={filters.po_id} onChange={e => setFilters(f => ({ ...f, po_id: e.target.value }))}>
                  <option value="">Semua PO</option>
                  {pos.map(p => <option key={p.id} value={p.id}>{p.po_number} - {p.vendor_name || ''}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">No. Seri</label>
                <input type="text" placeholder="Cari serial..." className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={filters.serial_number} onChange={e => setFilters(f => ({ ...f, serial_number: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">Status</label>
                <input type="text" placeholder="Status..." className="w-full border border-border rounded-lg px-3 py-2 text-sm"
                  value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={handleFilter} className="flex items-center gap-1 px-4 py-2 bg-primary text-white rounded-lg text-sm hover:brightness-110">
                <Search className="w-3.5 h-3.5" /> Terapkan Filter
              </button>
              <button onClick={resetFilters} className="px-4 py-2 border border-border rounded-lg text-sm text-muted-foreground hover:bg-[var(--glass-bg)]">
                Reset
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Summary Cards */}
      {summary && data.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {summary.map((s, i) => (
            <div key={i} className="bg-[var(--card-surface)] rounded-xl border border-border p-3 shadow-sm">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className="text-lg font-bold text-foreground mt-0.5">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Report Table */}
      <div className="bg-[var(--card-surface)] rounded-xl border border-border shadow-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h3 className="font-semibold text-foreground">
              {REPORT_TYPES.find(r => r.id === activeReport)?.label}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">{data.length} record</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchReport} className="flex items-center gap-1 px-3 py-1.5 border border-border rounded-lg text-sm hover:bg-[var(--glass-bg)]">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </button>
            <button onClick={exportToExcel} disabled={!data.length}
              className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed">
              <Download className="w-3.5 h-3.5" /> Excel
            </button>
            <button onClick={exportToPDF} disabled={!data.length}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed">
              <FileText className="w-3.5 h-3.5" /> PDF
            </button>
            <button onClick={exportToCSV} disabled={!data.length}
              className="flex items-center gap-1 px-3 py-1.5 bg-primary text-white rounded-lg text-sm hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed">
              <Download className="w-3.5 h-3.5" /> CSV
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : !data.length ? (
          <div className="text-center py-16 text-muted-foreground">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">Tidak ada data untuk laporan ini</p>
            <p className="text-sm mt-1">Coba ubah filter atau pilih periode yang berbeda</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-[var(--glass-bg)]">
                <tr>
                  <th className="text-left px-3 py-3 text-xs font-semibold text-muted-foreground uppercase w-10 sticky left-0 bg-[var(--glass-bg)]">#</th>
                  {getColumns().filter(c => c.key !== '_no').map(c => (
                    <th key={c.key} className="text-left px-3 py-3 text-xs font-semibold text-muted-foreground uppercase whitespace-nowrap">{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.map((row, i) => (
                  <tr key={i} className="hover:bg-[var(--glass-bg)]">
                    <td className="px-3 py-2.5 text-sm text-muted-foreground sticky left-0 bg-[var(--card-surface)]">{i + 1}</td>
                    {getColumns().filter(c => c.key !== '_no').map(c => (
                      <td key={c.key} className="px-3 py-2.5 text-sm text-foreground whitespace-nowrap">
                        {c.key === 'status' || c.key === 'inspection_status' ? (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[row[c.key]] || 'bg-secondary text-muted-foreground'}`}>
                            {row[c.key] || '-'}
                          </span>
                        ) : (
                          renderValue(row[c.key], c.format)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
