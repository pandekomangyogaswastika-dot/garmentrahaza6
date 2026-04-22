import { useState, useEffect, useCallback } from 'react';
import { Calendar, Save, RefreshCw, Clock as ClockIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GlassCard, GlassInput } from '@/components/ui/glass';
import { PageHeader, StatTile, StatusBadge, EmptyState } from './moduleAtoms';

const STATUS_OPTS = [
  { code: 'hadir', label: 'Hadir' },
  { code: 'izin',  label: 'Izin'  },
  { code: 'sakit', label: 'Sakit' },
  { code: 'alfa',  label: 'Alfa'  },
  { code: 'cuti',  label: 'Cuti'  },
  { code: 'libur', label: 'Libur' },
];

export default function RahazaAttendanceModule({ token }) {
  const today = new Date().toISOString().split('T')[0];
  const [date, setDate] = useState(today);
  const [rows, setRows] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchGrid = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`/api/rahaza/attendance/grid?date=${date}`, { headers });
      if (r.ok) {
        const data = await r.json();
        setRows(data.rows || []);
        setShifts(data.shifts || []);
      }
    } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date, token]);

  useEffect(() => { fetchGrid(); }, [fetchGrid]);

  const update = (empId, patch) => setRows(prev => prev.map(r => r.employee_id === empId ? { ...r, ...patch } : r));
  const setAll = (status) => setRows(prev => prev.map(r => ({ ...r, status })));

  const saveAll = async () => {
    setSaving(true); setMsg('');
    try {
      const entries = rows.map(r => ({
        employee_id: r.employee_id,
        status: r.status || 'hadir',
        shift_id: r.shift_id || null,
        hours_worked: Number(r.hours_worked) || 0,
        overtime_hours: Number(r.overtime_hours) || 0,
        notes: r.notes || '',
      }));
      const res = await fetch('/api/rahaza/attendance/bulk', {
        method: 'POST', headers, body: JSON.stringify({ date, entries }),
      });
      if (res.ok) { setMsg('Berhasil disimpan'); fetchGrid(); setTimeout(() => setMsg(''), 2500); }
      else setMsg('Gagal menyimpan');
    } finally { setSaving(false); }
  };

  const counts = rows.reduce((a, r) => { a[r.status] = (a[r.status] || 0) + 1; return a; }, {});
  const totalHours = rows.reduce((s, r) => s + (Number(r.hours_worked) || 0), 0);
  const totalOT = rows.reduce((s, r) => s + (Number(r.overtime_hours) || 0), 0);

  return (
    <div className="space-y-5" data-testid="rahaza-attendance-page">
      <PageHeader
        testId="attendance-header"
        icon={ClockIcon}
        eyebrow="Portal HR"
        title="Absensi Harian"
        subtitle="Input cepat kehadiran semua pegawai aktif. Mendukung bulk set & feeding ke payroll."
        actions={
          <>
            <GlassInput type="date" value={date} onChange={e => setDate(e.target.value)} className="h-9 w-40" data-testid="att-date" />
            <Button variant="ghost" className="h-9 border border-[var(--glass-border)]" onClick={fetchGrid} data-testid="att-refresh"><RefreshCw className="w-3.5 h-3.5 mr-1.5" />Refresh</Button>
            <Button onClick={saveAll} disabled={saving || rows.length === 0} className="h-9" data-testid="attendance-save"><Save className="w-3.5 h-3.5 mr-1.5" />{saving ? 'Menyimpan...' : 'Simpan Semua'}</Button>
          </>
        }
      />

      {msg && <div className="bg-[hsl(var(--success)/0.12)] border border-[hsl(var(--success)/0.22)] rounded-lg p-3 text-sm text-[hsl(var(--success))]">{msg}</div>}

      {/* Status counters */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        {STATUS_OPTS.map(s => (
          <StatTile key={s.code} label={s.label} value={counts[s.code] || 0} accent={
            s.code === 'hadir' ? 'success' : s.code === 'alfa' ? 'danger' : s.code === 'libur' ? 'muted' : 'primary'
          } testId={`att-count-${s.code}`} />
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <StatTile label="Total Karyawan" value={rows.length} accent="primary" />
        <StatTile label="Total Jam Kerja" value={totalHours.toFixed(1)} suffix="jam" accent="default" />
        <StatTile label="Total Lembur" value={totalOT.toFixed(1)} suffix="jam" accent="warning" />
        <StatTile label="Tanggal" value={date} accent="muted" />
      </div>

      {/* Quick-set chips */}
      <GlassCard className="p-3" hover={false}>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-foreground/60">Set cepat semua:</span>
          {STATUS_OPTS.map(s => (
            <button key={s.code}
              onClick={() => setAll(s.code)}
              className="px-2.5 py-1 rounded-full text-[11px] font-medium border border-[var(--glass-border)] bg-[var(--glass-bg)] hover:bg-[var(--glass-bg-hover)] text-foreground/70 hover:text-foreground transition-colors duration-150"
              data-testid={`att-setall-${s.code}`}
            >{s.label}</button>
          ))}
        </div>
      </GlassCard>

      {loading ? (
        <div className="flex items-center justify-center h-48"><div className="animate-spin rounded-full h-9 w-9 border-b-2 border-[hsl(var(--primary))]" /></div>
      ) : rows.length === 0 ? (
        <GlassCard hover={false} className="p-0"><EmptyState icon={ClockIcon} title="Belum ada karyawan aktif" description="Tambahkan master karyawan terlebih dahulu untuk input absensi." /></GlassCard>
      ) : (
        <GlassCard className="p-0 overflow-hidden" hover={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--glass-bg)]">
                <tr className="text-left text-[10px] uppercase tracking-wider text-foreground/50">
                  <th className="px-4 py-3">Karyawan</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Shift</th>
                  <th className="px-3 py-3 text-right">Jam Kerja</th>
                  <th className="px-3 py-3 text-right">Lembur</th>
                  <th className="px-3 py-3">Catatan</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.employee_id} className="border-t border-[var(--glass-border)] hover:bg-[var(--glass-bg-hover)] transition-colors" data-testid={`att-row-${r.employee_code}`}>
                    <td className="px-4 py-2">
                      <div className="font-mono text-xs text-foreground">{r.employee_code}</div>
                      <div className="text-xs text-foreground/60">{r.employee_name}</div>
                    </td>
                    <td className="px-3 py-2">
                      <select value={r.status || 'hadir'} onChange={e => update(r.employee_id, { status: e.target.value })} className="h-8 px-2 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-xs text-foreground">
                        {STATUS_OPTS.map(s => <option key={s.code} value={s.code}>{s.label}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <select value={r.shift_id || ''} onChange={e => update(r.employee_id, { shift_id: e.target.value })} className="h-8 px-2 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-xs text-foreground">
                        <option value="">—</option>
                        {shifts.map(s => <option key={s.id} value={s.id}>{s.code}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <input type="number" min={0} step="0.5" value={r.hours_worked || 0} onChange={e => update(r.employee_id, { hours_worked: e.target.value })} className="w-20 h-8 px-2 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-xs text-foreground text-right font-mono" />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <input type="number" min={0} step="0.5" value={r.overtime_hours || 0} onChange={e => update(r.employee_id, { overtime_hours: e.target.value })} className="w-20 h-8 px-2 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-xs text-foreground text-right font-mono" />
                    </td>
                    <td className="px-3 py-2">
                      <input value={r.notes || ''} onChange={e => update(r.employee_id, { notes: e.target.value })} placeholder="—" className="w-full h-8 px-2 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-xs text-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}
    </div>
  );
}
