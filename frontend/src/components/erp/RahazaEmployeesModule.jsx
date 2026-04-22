import { useEffect, useState } from 'react';
import MasterDataCRUD from './MasterDataCRUD';

const WAGE_SCHEMES = [
  { value: 'borongan_pcs', label: 'Borongan Hasil (per pcs)' },
  { value: 'borongan_jam', label: 'Borongan Waktu (per jam)' },
  { value: 'mingguan',     label: 'Gaji Mingguan' },
  { value: 'bulanan',      label: 'Gaji Bulanan' },
];

const JOB_TITLES = [
  'Operator Rajut', 'Operator Linking', 'Operator Sewing', 'Operator QC', 'Operator Steam', 'Operator Packing',
  'Operator Washer', 'Operator Sontek', 'Supervisor', 'Staff Gudang', 'Staff Admin', 'Lainnya',
];

export default function RahazaEmployeesModule({ token }) {
  const [locs, setLocs] = useState([]);
  useEffect(() => {
    fetch('/api/rahaza/locations', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(setLocs).catch(() => {});
  }, [token]);

  const locOptions = locs.filter(l => l.active).map(l => ({ value: l.id, label: `${l.code} · ${l.name}` }));

  return (
    <MasterDataCRUD
      title="Karyawan & Operator"
      description="Master karyawan (operator mesin, supervisor, staff). Skema gaji (borongan/mingguan/bulanan) dipakai oleh portal HR."
      endpoint="/api/rahaza/employees"
      token={token}
      testIdPrefix="rahaza-employee"
      columns={[
        { key: 'employee_code', label: 'Kode' },
        { key: 'name', label: 'Nama' },
        { key: 'job_title', label: 'Jabatan' },
        { key: 'location_name', label: 'Lokasi', render: v => v || '-' },
        { key: 'wage_scheme', label: 'Skema Gaji',
          render: v => (WAGE_SCHEMES.find(s => s.value === v)?.label) || v },
        { key: 'base_rate', label: 'Base Rate',
          render: v => v ? `Rp ${Number(v).toLocaleString('id-ID')}` : '-' },
      ]}
      fields={[
        { key: 'employee_code', label: 'Kode Karyawan', required: true, placeholder: 'Contoh: EMP-001' },
        { key: 'name', label: 'Nama Lengkap', required: true },
        { key: 'job_title', label: 'Jabatan', type: 'select', options: JOB_TITLES.map(j => ({ value: j, label: j })) },
        { key: 'location_id', label: 'Lokasi Utama', type: 'select', options: locOptions },
        { key: 'phone', label: 'No. Telepon', placeholder: 'Opsional' },
        { key: 'wage_scheme', label: 'Skema Gaji', type: 'select', options: WAGE_SCHEMES, required: true },
        { key: 'base_rate', label: 'Rate / Base (Rp)', type: 'number',
          help: 'Untuk borongan pcs = Rp/pcs, borongan jam = Rp/jam, mingguan/bulanan = total Rp.' },
      ]}
      defaultItem={{ employee_code: '', name: '', job_title: 'Operator Rajut', location_id: '', phone: '', wage_scheme: 'borongan_pcs', base_rate: 0 }}
    />
  );
}
