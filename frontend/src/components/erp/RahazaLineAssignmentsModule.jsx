import { useEffect, useState } from 'react';
import MasterDataCRUD from './MasterDataCRUD';

export default function RahazaLineAssignmentsModule({ token }) {
  const [lines, setLines] = useState([]);
  const [emps, setEmps] = useState([]);
  const [shifts, setShifts] = useState([]);
  const [models, setModels] = useState([]);
  const [sizes, setSizes] = useState([]);

  useEffect(() => {
    const h = { Authorization: `Bearer ${token}` };
    Promise.all([
      fetch('/api/rahaza/lines', { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/employees', { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/shifts', { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/models', { headers: h }).then(r => r.ok ? r.json() : []),
      fetch('/api/rahaza/sizes', { headers: h }).then(r => r.ok ? r.json() : []),
    ]).then(([l, e, s, m, sz]) => {
      setLines(l); setEmps(e); setShifts(s); setModels(m); setSizes(sz);
    });
  }, [token]);

  const today = new Date().toISOString().slice(0, 10);

  return (
    <MasterDataCRUD
      title="Assign Line (Operator + Shift + Target)"
      description="Setiap hari/shift, setiap Line dapat di-assign dengan Operator, Model, Size, dan Target produksi."
      endpoint="/api/rahaza/line-assignments"
      token={token}
      testIdPrefix="rahaza-line-assign"
      columns={[
        { key: 'assign_date', label: 'Tanggal' },
        { key: 'line_name', label: 'Line' },
        { key: 'operator_name', label: 'Operator', render: v => v || '-' },
        { key: 'shift_name', label: 'Shift', render: v => v || '-' },
        { key: 'model_name', label: 'Model', render: v => v || '-' },
        { key: 'size_name', label: 'Size', render: v => v || '-' },
        { key: 'target_qty', label: 'Target', render: v => v ? `${v} pcs` : '-' },
      ]}
      fields={[
        { key: 'assign_date', label: 'Tanggal', type: 'text', placeholder: 'YYYY-MM-DD', required: true },
        { key: 'line_id', label: 'Line', type: 'select', required: true,
          options: lines.filter(l => l.active).map(l => ({ value: l.id, label: `${l.code} · ${l.name}` })) },
        { key: 'operator_id', label: 'Operator', type: 'select',
          options: emps.filter(e => e.active).map(e => ({ value: e.id, label: `${e.employee_code} · ${e.name}` })) },
        { key: 'shift_id', label: 'Shift', type: 'select',
          options: shifts.filter(s => s.active).map(s => ({ value: s.id, label: `${s.name} (${s.start_time}-${s.end_time})` })) },
        { key: 'model_id', label: 'Model', type: 'select',
          options: models.filter(m => m.active).map(m => ({ value: m.id, label: `${m.code} · ${m.name}` })) },
        { key: 'size_id', label: 'Size', type: 'select',
          options: sizes.filter(s => s.active).map(s => ({ value: s.id, label: s.code })) },
        { key: 'target_qty', label: 'Target pcs', type: 'number', placeholder: 'Contoh: 200' },
        { key: 'notes', label: 'Catatan' },
      ]}
      defaultItem={{ assign_date: today, line_id: '', operator_id: '', shift_id: '', model_id: '', size_id: '', target_qty: 0, notes: '' }}
    />
  );
}
