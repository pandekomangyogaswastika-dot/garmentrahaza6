import { GlassCard, GlassPanel } from '@/components/ui/glass';
import { motion } from 'framer-motion';
import { FileText, CreditCard, TrendingUp, DollarSign, BarChart3, Receipt, PieChart, Shield } from 'lucide-react';

// Quick links — moduleId harus selaras dengan MODULE_REGISTRY (fin-*).
const QUICK_LINKS = [
  { id: 'fin-invoices',       label: 'Semua Invoice',    desc: 'Daftar semua invoice AR dan AP',      icon: FileText },
  { id: 'fin-payments',       label: 'Pembayaran',       desc: 'Manajemen pembayaran masuk & keluar',  icon: DollarSign },
  { id: 'fin-ap',             label: 'Hutang (AP)',      desc: 'Hutang vendor yang belum terbayar',    icon: CreditCard },
  { id: 'fin-ar',             label: 'Piutang (AR)',     desc: 'Piutang pelanggan yang belum diterima',icon: TrendingUp },
  { id: 'fin-recap',          label: 'Rekap Keuangan',   desc: 'Ringkasan keuangan & analisis margin', icon: PieChart },
  { id: 'fin-manual-invoice', label: 'Invoice Manual',   desc: 'Buat invoice manual untuk kebutuhan khusus', icon: Receipt },
  { id: 'fin-approval',       label: 'Approval Invoice', desc: 'Approval permintaan perubahan invoice', icon: Shield },
];

export default function FinanceDashboard({ onNavigate }) {
  return (
    <div className="space-y-6" data-testid="finance-dashboard">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Portal Finance</h1>
        <p className="text-muted-foreground text-sm mt-1">Invoice, pembayaran, AR/AP, cost center, dan laporan keuangan.</p>
      </div>

      <GlassPanel className="p-4 flex items-center gap-3">
        <BarChart3 className="w-5 h-5 text-primary" />
        <div>
          <p className="text-sm font-medium text-foreground">Modul keuangan tersedia</p>
          <p className="text-xs text-muted-foreground">Gunakan navigasi sidebar atau quick link di bawah untuk mengakses modul.</p>
        </div>
      </GlassPanel>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {QUICK_LINKS.map((link, idx) => {
          const Icon = link.icon;
          return (
            <motion.div
              key={link.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: idx * 0.05 }}
            >
              <GlassCard
                className="p-5 h-full cursor-pointer group"
                onClick={() => onNavigate && onNavigate(link.id)}
                data-testid={`fin-link-${link.id}`}
              >
                <div className="w-10 h-10 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                  <Icon className="w-5 h-5 text-primary" />
                </div>
                <h3 className="text-sm font-semibold text-foreground mb-1">{link.label}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{link.desc}</p>
              </GlassCard>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
