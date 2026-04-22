/**
 * Dashboard Eksekutif (legacy) — Tahap 2 Modernized.
 * Ringkasan performa operasional lintas departemen (data dari /api/dashboard).
 */
import { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area,
} from 'recharts';
import {
  TrendingUp, Package, Factory, DollarSign, AlertTriangle, Clock, Truck, Users,
} from 'lucide-react';
import {
  StatCard, ChartCard, GlassTooltip, HeroCrystalCard, CHART_PALETTE,
} from './dashboardAtoms';
import NextActionWidget from './NextActionWidget';

const fmtNum = (v) => Number(v || 0).toLocaleString('id-ID');
const fmtShortIDR = (n) => {
  const v = Number(n || 0);
  if (v >= 1e9) return `Rp ${(v / 1e9).toFixed(1)}M`;
  if (v >= 1e6) return `Rp ${(v / 1e6).toFixed(1)}jt`;
  if (v >= 1e3) return `Rp ${(v / 1e3).toFixed(0)}rb`;
  return `Rp ${v.toLocaleString('id-ID')}`;
};

import { PeriodPicker } from './PeriodPicker';

export default function ManagementDashboard({ token, onNavigate }) {
  const [metrics, setMetrics] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState({ preset: '30d', from: null, to: null, compare: false });
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  // Phase 12.4 — Drill-down helper: navigate ke module bila parent menyediakan onNavigate
  const drill = (moduleId) => () => { if (onNavigate) onNavigate(moduleId); };

  const fetchData = useCallback(async () => {
    try {
      const [mRes, aRes] = await Promise.all([
        fetch('/api/dashboard', { headers }),
        fetch('/api/dashboard/analytics', { headers }),
      ]);
      if (mRes.ok) setMetrics(await mRes.json());
      if (aRes.ok) setAnalytics(await aRes.json());
    } catch (e) { /* ignore */ }
    finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return (
    <div className="space-y-5">
      <div className="h-32 rounded-[var(--radius-xl)] bg-[var(--card-surface)] border border-[var(--glass-border)] animate-pulse" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => <div key={i} className="h-28 rounded-[var(--radius-lg)] bg-[var(--card-surface)] border border-[var(--glass-border)] animate-pulse" />)}
      </div>
    </div>
  );

  const weeklyTP = analytics?.weeklyThroughput || [];
  const woStatusData = (metrics?.woStatus || []).map(s => ({ name: s._id || 'Unknown', value: s.count }));

  return (
    <div className="space-y-5" data-testid="management-dashboard">
      <HeroCrystalCard
        testId="mgmt-dashboard-hero"
        eyebrow="Portal Management"
        title="Dashboard Eksekutif"
        description="Ringkasan performa operasional lintas departemen dengan data real-time dari seluruh sistem ERP."
        actions={
          <PeriodPicker
            value={period}
            onChange={setPeriod}
            compareEnabled={true}
            testId="mgmt-dashboard-period"
          />
        }
      />

      {/* Phase 16: Next-Action Widget (guided ops) */}
      <NextActionWidget
        token={token}
        portal="management"
        onNavigate={(moduleId) => onNavigate && onNavigate(moduleId)}
        onOpenSetupWizard={() => { onNavigate && onNavigate('production-dashboard'); }}
        maxCards={5}
      />

      {/* KPI Row 1 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard testId="mgmt-kpi-orders" icon={Package} label="Total Order"
          value={fmtNum(metrics?.totalPOs)} sub={`${metrics?.activePOs || 0} aktif`}
          accent="primary"
          trend={metrics?.delayedPOs > 0 ? { value: -metrics.delayedPOs, suffix: ' terlambat', label: 'dari jadwal' } : null}
          onClick={drill('prod-orders')}
        />
        <StatCard testId="mgmt-kpi-jobs" icon={Factory} label="Job Aktif"
          value={fmtNum(metrics?.activeJobs)} sub="Job produksi berjalan" accent="info"
          onClick={drill('prod-work-orders')} />
        <StatCard testId="mgmt-kpi-ontime" icon={Clock} label="On-Time Rate"
          value={`${metrics?.onTimeRate || 0}%`} sub="Order tepat waktu"
          accent={metrics?.onTimeRate >= 80 ? 'success' : 'warning'}
          trend={{ value: metrics?.onTimeRate >= 80 ? 5 : -5, label: metrics?.onTimeRate >= 80 ? 'Baik' : 'Perlu perhatian' }}
          onClick={drill('prod-orders')}
        />
        <StatCard testId="mgmt-kpi-revenue" icon={DollarSign} label="Pendapatan"
          value={fmtShortIDR(metrics?.totalRevenue)} sub={`Margin: ${fmtShortIDR(metrics?.grossMargin)}`}
          accent="mint"
          onClick={drill('fin-ar-invoices')} />
      </div>

      {/* KPI Row 2 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard testId="mgmt-kpi-shipments" icon={Truck} label="Shipment Tertunda"
          value={fmtNum(metrics?.pendingShipments)} sub="Material belum diterima"
          accent={metrics?.pendingShipments > 0 ? 'warning' : 'success'}
          onClick={drill('wh-stock')} />
        <StatCard testId="mgmt-kpi-ar" icon={TrendingUp} label="Outstanding AR"
          value={fmtShortIDR(metrics?.outstandingAR)} sub="Piutang belum bayar" accent="primary"
          onClick={drill('fin-ar-invoices')} />
        <StatCard testId="mgmt-kpi-ap" icon={AlertTriangle} label="Outstanding AP"
          value={fmtShortIDR(metrics?.outstandingAP)} sub="Hutang belum bayar"
          accent={metrics?.outstandingAP > 0 ? 'warning' : 'success'}
          onClick={drill('fin-ap')} />
        <StatCard testId="mgmt-kpi-users" icon={Users} label="Total User"
          value={fmtNum(metrics?.totalUsers) || '—'} sub="Pengguna terdaftar" accent="info"
          onClick={drill('mgmt-users')} />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="Throughput Produksi (Mingguan)" subtitle="Total output per minggu" className="lg:col-span-2">
          <div style={{ width: '100%', height: 240 }}>
            <ResponsiveContainer>
              <BarChart data={weeklyTP} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 4" stroke="var(--chart-grid)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} stroke="var(--chart-grid)" />
                <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} stroke="var(--chart-grid)" width={40} />
                <Tooltip content={<GlassTooltip formatter={(v) => `${fmtNum(v)} pcs`} />} cursor={{ fill: 'var(--glass-bg-hover)' }} />
                <Bar dataKey="qty" name="Produksi" fill={CHART_PALETTE[0]} radius={[6, 6, 0, 0]} maxBarSize={44} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title="Status Job Produksi" subtitle="Distribusi WO per status">
          {woStatusData.length > 0 ? (
            <>
              <div style={{ width: '100%', height: 160 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={woStatusData} cx="50%" cy="50%" innerRadius={44} outerRadius={68} paddingAngle={3} dataKey="value" strokeWidth={0}>
                      {woStatusData.map((_, i) => <Cell key={i} fill={CHART_PALETTE[i % CHART_PALETTE.length]} />)}
                    </Pie>
                    <Tooltip content={<GlassTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-1.5 mt-3">
                {woStatusData.map((e, i) => (
                  <div key={e.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: CHART_PALETTE[i % CHART_PALETTE.length] }} />
                      <span className="text-foreground/60 capitalize">{e.name}</span>
                    </div>
                    <span className="font-semibold text-foreground tabular-nums">{e.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-40 text-foreground/40 text-xs">Belum ada data</div>
          )}
        </ChartCard>
      </div>

      {/* Production trend 6 month */}
      <ChartCard title="Tren Produksi 6 Bulan" subtitle="Perbandingan jumlah PO dan output produksi">
        <div style={{ width: '100%', height: 240 }}>
          <ResponsiveContainer>
            <AreaChart data={metrics?.monthlyData || []} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="mgmtProd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={CHART_PALETTE[0]} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={CHART_PALETTE[0]} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 4" stroke="var(--chart-grid)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} stroke="var(--chart-grid)" />
              <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} stroke="var(--chart-grid)" width={40} />
              <Tooltip content={<GlassTooltip />} cursor={{ fill: 'var(--glass-bg-hover)' }} />
              <Bar dataKey="pos" name="PO" fill={CHART_PALETTE[1]} radius={[3, 3, 0, 0]} maxBarSize={28} />
              <Area type="monotone" dataKey="production" name="Produksi" stroke={CHART_PALETTE[0]} strokeWidth={2.5} fill="url(#mgmtProd)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>
    </div>
  );
}
