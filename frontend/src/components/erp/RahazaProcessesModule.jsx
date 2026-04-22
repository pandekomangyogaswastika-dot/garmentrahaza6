import MasterDataCRUD from './MasterDataCRUD';

export default function RahazaProcessesModule({ token }) {
  return (
    <MasterDataCRUD
      title="Proses Produksi"
      description="Daftar proses alur rajut PT Rahaza: Rajut → Linking → Sewing → QC → Steam → Packing (+ rework: Washer, Sontek)."
      endpoint="/api/rahaza/processes"
      token={token}
      testIdPrefix="rahaza-process"
      columns={[
        { key: 'order_seq', label: 'Urutan' },
        { key: 'code', label: 'Kode' },
        { key: 'name', label: 'Nama' },
        { key: 'is_rework', label: 'Alur Rework', render: v => v ? 'Ya' : 'Tidak' },
        { key: 'description', label: 'Deskripsi' },
      ]}
      fields={[
        { key: 'name', label: 'Nama' },
        { key: 'description', label: 'Deskripsi' },
      ]}
      defaultItem={{ name: '', description: '' }}
    />
  );
}
