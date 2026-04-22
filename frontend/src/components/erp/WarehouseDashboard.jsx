import { useState, useEffect, useCallback } from 'react';
import { GlassCard, GlassPanel, GlassInput } from '@/components/ui/glass';
import { motion } from 'framer-motion';
import {
  Warehouse, Boxes, ArrowDownToLine, TrendingUp, Package,
  MapPin, Activity, RefreshCw, Clock
} from 'lucide-react';

const fmtNum = (v) => (v || 0).toLocaleString('id-ID');
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-';

function KPITile({ title, value, icon: Icon, subtitle }) {
  return (
    <GlassCard className="p-4" data-testid={`wh-kpi-${title.replace(/\s+/g, '-').toLowerCase()}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold text-foreground mt-1 font-['Space_Grotesk']">{value}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
        <div className="w-10 h-10 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center">
          <Icon className="w-5 h-5 text-primary" />
        </div>
      </div>
    </GlassCard>
  );
}

export default function WarehouseDashboard({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const headers = { Authorization: `Bearer ${token}` };

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch('/api/warehouse/dashboard', { headers });
      if (res.ok) setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchDashboard(); }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
    </div>
  );

  return (
    <div className="space-y-6" data-testid="warehouse-dashboard">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard Gudang</h1>
          <p className="text-muted-foreground text-sm mt-1">Ringkasan stok, penerimaan, dan pergerakan barang</p>
        </div>
        <button onClick={fetchDashboard} className="p-2 rounded-xl hover:bg-[var(--glass-bg-hover)] transition-colors" title="Muat Ulang">
          <RefreshCw className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KPITile title="Lokasi" value={fmtNum(data?.total_locations)} icon={MapPin} subtitle="Lokasi aktif" />
        <KPITile title="Total SKU" value={fmtNum(data?.total_skus)} icon={Package} subtitle="Produk unik di stok" />
        <KPITile title="Total Stok" value={fmtNum(data?.total_stock_qty)} icon={Boxes} subtitle="Total kuantitas tersedia" />
        <KPITile title="Penerimaan Tertunda" value={fmtNum(data?.pending_receipts)} icon={ArrowDownToLine} subtitle={`${data?.total_receipts || 0} total penerimaan`} />
      </div>

      {/* Recent Movements */}
      <GlassCard hover={false} className="p-5">
        <h3 className="font-semibold text-foreground text-sm mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" /> Pergerakan Stok Terbaru
        </h3>
        {(data?.recent_movements || []).length > 0 ? (
          <div className="space-y-2">
            {data.recent_movements.map((m, i) => (
              <div key={m.id || i} className="flex items-center justify-between p-3 rounded-xl bg-[var(--glass-bg)] border border-[var(--glass-border)]">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    m.type === 'receive' ? 'bg-emerald-400/15 text-emerald-400' : 'bg-sky-400/15 text-sky-400'
                  }`}>
                    <ArrowDownToLine className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{m.product_name}</p>
                    <p className="text-xs text-muted-foreground">{m.receipt_number} • {m.location_name}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-emerald-400">+{fmtNum(m.quantity)} {m.unit}</p>
                  <p className="text-xs text-muted-foreground">{fmtDate(m.created_at)}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <Boxes className="w-10 h-10 text-muted-foreground/30 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Belum ada pergerakan stok</p>
            <p className="text-xs text-muted-foreground mt-1">Mulai dengan membuat penerimaan barang di menu Penerimaan</p>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
