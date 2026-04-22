import MasterDataCRUD from './MasterDataCRUD';

export default function RahazaModelsModule({ token }) {
  return (
    <MasterDataCRUD
      title="Model Produk"
      description="Master model produk (Sweater V-Neck, Round-Neck, Cardigan, dsb). yarn_kg_per_pcs digunakan untuk perhitungan BOM (Phase 5)."
      endpoint="/api/rahaza/models"
      token={token}
      testIdPrefix="rahaza-model"
      columns={[
        { key: 'code', label: 'Kode' },
        { key: 'name', label: 'Nama Model' },
        { key: 'category', label: 'Kategori' },
        { key: 'yarn_kg_per_pcs', label: 'Benang / pcs (Kg)', render: v => v ? Number(v).toFixed(3) : '-' },
        { key: 'bundle_size', label: 'Bundle Size', render: v => v ? `${v} pcs` : '30 pcs (default)' },
        { key: 'description', label: 'Deskripsi' },
      ]}
      fields={[
        { key: 'code', label: 'Kode', required: true, placeholder: 'Contoh: SW-VN-A' },
        { key: 'name', label: 'Nama Model', required: true, placeholder: 'Contoh: Sweater V-Neck Classic' },
        { key: 'category', label: 'Kategori', type: 'select',
          options: [
            { value: 'Sweater', label: 'Sweater' },
            { value: 'Cardigan', label: 'Cardigan' },
            { value: 'Vest', label: 'Vest' },
            { value: 'Polo', label: 'Polo Rajut' },
            { value: 'Other', label: 'Lainnya' },
          ] },
        { key: 'yarn_kg_per_pcs', label: 'Benang per pcs (Kg)', type: 'number',
          help: 'Estimasi konsumsi benang per 1 pcs jadi (untuk BOM & HPP).' },
        { key: 'bundle_size', label: 'Ukuran Bundle (pcs)', type: 'number',
          help: 'Jumlah pcs per bundle saat digenerate dari WO. Default 30. Contoh: 20–50 pcs per bundle umumnya untuk knit garment.' },
        { key: 'description', label: 'Deskripsi', placeholder: 'Opsional' },
      ]}
      defaultItem={{ code: '', name: '', category: 'Sweater', yarn_kg_per_pcs: 0, bundle_size: 30, description: '' }}
    />
  );
}
