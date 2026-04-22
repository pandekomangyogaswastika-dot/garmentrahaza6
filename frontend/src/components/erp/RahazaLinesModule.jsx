import { useEffect, useState } from 'react';
import MasterDataCRUD from './MasterDataCRUD';

export default function RahazaLinesModule({ token }) {
  const [locs, setLocs] = useState([]);
  const [procs, setProcs] = useState([]);
  useEffect(() => {
    const h = { Authorization: `Bearer ${token}` };
    fetch('/api/rahaza/locations', { headers: h }).then(r => r.ok ? r.json() : []).then(setLocs).catch(() => {});
    fetch('/api/rahaza/processes', { headers: h }).then(r => r.ok ? r.json() : []).then(setProcs).catch(() => {});
  }, [token]);

  const locOptions = locs.filter(l => l.active).map(l => ({ value: l.id, label: `${l.code} · ${l.name}` }));
  const procOptions = procs.filter(p => p.active).map(p => ({ value: p.id, label: p.name }));

  return (
    <MasterDataCRUD
      title="Line Produksi"
      description="Line = unit terkecil produksi (proses × lokasi). Operator, shift, model & target akan di-assign ke Line."
      endpoint="/api/rahaza/lines"
      token={token}
      testIdPrefix="rahaza-line"
      columns={[
        { key: 'code', label: 'Kode' },
        { key: 'name', label: 'Nama' },
        { key: 'process_name', label: 'Proses', render: v => v || '-' },
        { key: 'location_name', label: 'Lokasi', render: v => v || '-' },
        { key: 'capacity_per_hour', label: 'Kapasitas / jam', render: v => v ? `${v} pcs` : '-' },
      ]}
      fields={[
        { key: 'code', label: 'Kode', required: true, placeholder: 'Contoh: LN-RAJUT-01' },
        { key: 'name', label: 'Nama', placeholder: 'Contoh: Line Rajut 1' },
        { key: 'process_id', label: 'Proses', type: 'select', options: procOptions, required: true },
        { key: 'location_id', label: 'Lokasi (Zona/Gedung)', type: 'select', options: locOptions },
        { key: 'capacity_per_hour', label: 'Kapasitas per jam (pcs)', type: 'number', placeholder: 'Opsional' },
        { key: 'notes', label: 'Catatan' },
      ]}
      defaultItem={{ code: '', name: '', process_id: '', location_id: '', capacity_per_hour: 0, notes: '' }}
    />
  );
}
