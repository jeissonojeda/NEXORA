import { useRef, useState } from 'react';
import Icon from '../ui/Icon';
import Badge from '../ui/Badge';
import LoadingState from '../ui/LoadingState';
import ErrorAlert from '../ui/ErrorAlert';
import { extractErrorMessage } from '../../hooks/useAsync';
import { scanInvoice } from '../../services/aiOperational';
import type { AiInvoiceScanResponse } from '../../types/ai';

export default function AiInvoiceScanner() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [scan, setScan] = useState<AiInvoiceScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setScanning(true);
    setError(null);
    setScan(null);
    try {
      const res = await scanInvoice(file);
      setScan(res);
    } catch (e) {
      setError(extractErrorMessage(e));
    } finally {
      setScanning(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-dashed border-line-strong bg-surface-2 p-6 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary">
          <Icon name="scan" size={24} />
        </div>
        <p className="text-sm text-muted">
          Sube una foto o PDF de una factura de proveedor. NEXORA AI extraerá los
          datos y los comparará con tu catálogo.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept="image/*,.pdf"
          className="hidden"
          onChange={(e) => void handleFile(e.target.files?.[0])}
        />
        <button
          className="nx-btn nx-btn-secondary mt-4"
          onClick={() => fileRef.current?.click()}
          disabled={scanning}
        >
          {scanning ? 'Escaneando…' : 'Seleccionar factura'}
        </button>
      </div>

      {scanning && <LoadingState rows={2} />}
      {error && <ErrorAlert message={error} />}

      {scan && (
        <div className="space-y-4">
          {scan.duplicate && (
            <div className="flex items-center gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-200">
              <Icon name="triangle-alert" size={18} />
              Factura duplicada: coincide con un registro previo
              {scan.duplicate_of ? ` (${scan.duplicate_of.slice(0, 8)})` : ''}.
            </div>
          )}

          <div className="rounded-xl bg-surface p-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-foreground">Datos extraídos</h4>
              {scan.supplier_name && <Badge tone="green">{scan.supplier_name}</Badge>}
            </div>
            <dl className="mt-3 grid grid-cols-1 gap-y-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-muted">N° factura</dt>
                <dd className="font-medium text-foreground">{scan.invoice_number || '—'}</dd>
              </div>
              <div>
                <dt className="text-muted">Total</dt>
                <dd className="font-medium text-foreground">{scan.total ?? '—'}</dd>
              </div>
              <div>
                <dt className="text-muted">Artículos</dt>
                <dd className="font-medium text-foreground">{scan.items.length}</dd>
              </div>
            </dl>
          </div>

          {scan.items.length > 0 && (
            <div className="overflow-hidden rounded-xl border border-line">
              <table className="w-full text-sm">
                <thead className="bg-surface-2 text-left text-xs uppercase text-muted">
                  <tr>
                    <th className="px-4 py-2">Producto</th>
                    <th className="px-4 py-2">Cant.</th>
                    <th className="px-4 py-2">P. unit.</th>
                    <th className="px-4 py-2">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {scan.items.map((it, i) => (
                    <tr key={i}>
                      <td className="px-4 py-2 font-medium text-foreground">
                        {it.product_name || '—'}
                      </td>
                      <td className="px-4 py-2 text-muted">{it.quantity}</td>
                      <td className="px-4 py-2 text-muted">{it.unit_price}</td>
                      <td className="px-4 py-2 text-muted">{it.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {scan.product_matches.length > 0 && (
            <div>
              <h5 className="mb-2 text-xs font-medium uppercase text-muted">
                Coincidencias en catálogo
              </h5>
              <div className="flex flex-wrap gap-2">
                {scan.product_matches.map((pm) => (
                  <span
                    key={pm.id}
                    className="rounded-full bg-primary-soft px-3 py-1 text-xs text-primary"
                  >
                    {pm.name} ({Math.round(pm.confidence * 100)}%)
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
