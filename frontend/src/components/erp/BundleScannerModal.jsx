import { useEffect, useRef, useState, useCallback } from 'react';
import { Camera, Keyboard, X, AlertTriangle, Loader2 } from 'lucide-react';
import { Html5Qrcode } from 'html5-qrcode';
import { Button } from '@/components/ui/button';
import { GlassPanel, GlassInput } from '@/components/ui/glass';
import Modal from './Modal';

/**
 * BundleScannerModal — Phase 17C
 *
 * Mobile-friendly QR scanner (html5-qrcode) with a manual-input fallback.
 *
 * Props:
 *  - token: string                         bearer token for bundle lookup
 *  - onDetected: (bundle, payload) => void called with resolved bundle doc
 *  - onClose: () => void
 *
 * The scanner attempts to start the camera automatically. If the browser blocks
 * the camera or no camera is available, the operator can type the bundle number
 * directly. On successful decode OR manual submit, we resolve the bundle via
 * GET /api/rahaza/bundles/by-number/{bundle_number} and then call `onDetected`.
 */

const SCANNER_ELEMENT_ID = 'bundle-qr-reader';

export default function BundleScannerModal({ token, onDetected, onClose }) {
  const scannerRef = useRef(null);
  const [cameraState, setCameraState] = useState('idle'); // idle | starting | scanning | blocked | unsupported | stopping
  const [cameraError, setCameraError] = useState('');
  const [tab, setTab] = useState('camera'); // 'camera' | 'manual'
  const [manual, setManual] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState('');

  const stopCamera = useCallback(async () => {
    try {
      if (scannerRef.current) {
        const inst = scannerRef.current;
        scannerRef.current = null;
        if (inst.isScanning) {
          try { await inst.stop(); } catch (_) { /* noop */ }
        }
        try { await inst.clear(); } catch (_) { /* noop */ }
      }
    } catch (_) { /* noop */ }
  }, []);

  const resolveBundleByNumber = useCallback(async (bundleNumber) => {
    const cleaned = String(bundleNumber || '').trim().toUpperCase();
    if (!cleaned) throw new Error('Bundle number kosong');
    const res = await fetch(
      `/api/rahaza/bundles/by-number/${encodeURIComponent(cleaned)}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (res.status === 404) throw new Error(`Bundle "${cleaned}" tidak ditemukan`);
    if (!res.ok) {
      let detail = '';
      try { detail = (await res.json()).detail || ''; } catch (_) { /* noop */ }
      throw new Error(detail || `Gagal mengambil bundle (HTTP ${res.status})`);
    }
    return await res.json();
  }, [token]);

  const handleDetected = useCallback(async (payload, source) => {
    setLookupError('');
    setLookupLoading(true);
    try {
      const bundle = await resolveBundleByNumber(payload);
      // Stop camera before calling parent (which likely opens another UI)
      await stopCamera();
      if (onDetected) onDetected(bundle, { payload, source });
    } catch (e) {
      setLookupError(e.message || 'Gagal mengambil bundle');
    } finally {
      setLookupLoading(false);
    }
  }, [resolveBundleByNumber, onDetected, stopCamera]);

  const startCamera = useCallback(async () => {
    setCameraError('');
    setCameraState('starting');
    try {
      // Ensure target element exists before instantiating
      const el = document.getElementById(SCANNER_ELEMENT_ID);
      if (!el) {
        setCameraState('unsupported');
        setCameraError('Scanner tidak bisa diinisialisasi (element tidak ditemukan)');
        return;
      }

      if (scannerRef.current) {
        await stopCamera();
      }

      // Check camera availability
      let cameras = [];
      try {
        cameras = await Html5Qrcode.getCameras();
      } catch (err) {
        setCameraState('blocked');
        setCameraError(
          'Kamera tidak dapat diakses. Pastikan izin kamera diberikan pada browser ' +
          'atau gunakan input manual.'
        );
        return;
      }
      if (!cameras || cameras.length === 0) {
        setCameraState('unsupported');
        setCameraError('Tidak ada kamera terdeteksi di perangkat ini.');
        return;
      }

      // Prefer environment (back) camera if available
      const preferred =
        cameras.find((c) => /back|environment|rear/i.test(c.label)) ||
        cameras[cameras.length - 1] || cameras[0];

      const instance = new Html5Qrcode(SCANNER_ELEMENT_ID, { verbose: false });
      scannerRef.current = instance;

      const config = {
        fps: 10,
        qrbox: (viewfinderWidth, viewfinderHeight) => {
          const minEdge = Math.min(viewfinderWidth, viewfinderHeight);
          const box = Math.floor(minEdge * 0.7);
          return { width: box, height: box };
        },
        aspectRatio: 1.0,
      };

      let handled = false;
      await instance.start(
        preferred.id,
        config,
        async (decodedText) => {
          if (handled) return;
          handled = true;
          try { await instance.pause(true); } catch (_) { /* noop */ }
          await handleDetected(decodedText, 'camera');
        },
        () => { /* ignore per-frame errors */ },
      );
      setCameraState('scanning');
    } catch (e) {
      setCameraState('blocked');
      setCameraError(
        e?.message ||
        'Tidak bisa memulai scanner. Cek izin kamera atau gunakan input manual.'
      );
    }
  }, [handleDetected, stopCamera]);

  // Auto-start camera on mount when on camera tab
  useEffect(() => {
    if (tab !== 'camera') return;
    let cancelled = false;
    (async () => {
      if (cancelled) return;
      await startCamera();
    })();
    return () => { cancelled = true; };
  }, [tab, startCamera]);

  useEffect(() => () => { stopCamera(); }, [stopCamera]);

  const switchTab = async (next) => {
    if (next === tab) return;
    if (tab === 'camera') await stopCamera();
    setCameraError('');
    setLookupError('');
    setTab(next);
    if (next === 'camera') setCameraState('starting');
  };

  const onManualSubmit = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    const trimmed = manual.trim();
    if (!trimmed) return;
    await handleDetected(trimmed, 'manual');
  };

  return (
    <Modal
      onClose={async () => { await stopCamera(); onClose?.(); }}
      title="Scan Bundle"
      size="sm"
      data-testid="bundle-scanner-modal"
    >
      <div className="space-y-3">
        {/* Tab switcher */}
        <div className="inline-flex rounded-lg border border-[var(--glass-border)] bg-[var(--glass-bg)] p-1 w-full">
          <button
            type="button"
            onClick={() => switchTab('camera')}
            className={`flex-1 inline-flex items-center justify-center gap-1.5 py-2 rounded-md text-xs font-semibold transition-colors ${
              tab === 'camera'
                ? 'bg-[hsl(var(--primary)/0.15)] text-[hsl(var(--primary))]'
                : 'text-muted-foreground hover:text-foreground'
            }`}
            data-testid="scanner-tab-camera"
          >
            <Camera className="w-3.5 h-3.5" /> Kamera
          </button>
          <button
            type="button"
            onClick={() => switchTab('manual')}
            className={`flex-1 inline-flex items-center justify-center gap-1.5 py-2 rounded-md text-xs font-semibold transition-colors ${
              tab === 'manual'
                ? 'bg-[hsl(var(--primary)/0.15)] text-[hsl(var(--primary))]'
                : 'text-muted-foreground hover:text-foreground'
            }`}
            data-testid="scanner-tab-manual"
          >
            <Keyboard className="w-3.5 h-3.5" /> Input Manual
          </button>
        </div>

        {/* Camera tab */}
        {tab === 'camera' && (
          <div className="space-y-2">
            <GlassPanel className="p-0 overflow-hidden">
              <div
                id={SCANNER_ELEMENT_ID}
                className="w-full aspect-square bg-black/85"
                data-testid="scanner-viewport"
              />
            </GlassPanel>

            <div className="text-center text-[11px] text-muted-foreground">
              {cameraState === 'starting' && (
                <span className="inline-flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" /> Memulai kamera...
                </span>
              )}
              {cameraState === 'scanning' && 'Arahkan kamera ke QR code di bundle ticket.'}
              {lookupLoading && (
                <span className="inline-flex items-center gap-1 text-[hsl(var(--primary))]">
                  <Loader2 className="w-3 h-3 animate-spin" /> Mencocokkan bundle...
                </span>
              )}
            </div>

            {cameraError && (
              <div className="bg-red-400/10 border border-red-300/20 rounded-lg p-2.5 text-xs text-red-300 flex items-start gap-2" data-testid="scanner-camera-error">
                <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <span>
                  {cameraError}
                  <button
                    type="button"
                    onClick={() => switchTab('manual')}
                    className="ml-2 underline font-semibold"
                    data-testid="scanner-switch-manual-cta"
                  >
                    Pakai input manual
                  </button>
                </span>
              </div>
            )}
          </div>
        )}

        {/* Manual tab */}
        {tab === 'manual' && (
          <form onSubmit={onManualSubmit} className="space-y-2" data-testid="scanner-manual-form">
            <label className="block text-xs font-medium text-foreground/70">Bundle Number</label>
            <GlassInput
              autoFocus
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              placeholder="BDL-20260422-0001"
              className="uppercase"
              data-testid="scanner-manual-input"
            />
            <Button
              type="submit"
              disabled={lookupLoading || !manual.trim()}
              className="w-full h-11"
              data-testid="scanner-manual-submit"
            >
              {lookupLoading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Mencari...
                </span>
              ) : (
                'Cari Bundle'
              )}
            </Button>
          </form>
        )}

        {lookupError && (
          <div className="bg-red-400/10 border border-red-300/20 rounded-lg p-2.5 text-xs text-red-300 flex items-start gap-2" data-testid="scanner-lookup-error">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
            <span>{lookupError}</span>
          </div>
        )}

        <div className="text-[10px] text-muted-foreground text-center">
          Tips: tekan <kbd className="px-1 py-0.5 border border-[var(--glass-border)] rounded bg-[var(--glass-bg)]">Input Manual</kbd> kalau QR rusak / kamera bermasalah.
        </div>
      </div>
    </Modal>
  );
}
