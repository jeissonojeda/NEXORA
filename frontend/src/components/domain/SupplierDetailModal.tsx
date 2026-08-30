import { useState } from 'react';
import { useAsync } from '../../hooks/useAsync';
import { listSupplierProducts } from '../../services/suppliers';
import type { ApiSupplierDetail } from '../../types/catalog';
import { formatCurrency } from '../../utils/format';
import Badge from '../ui/Badge';
import ErrorAlert from '../ui/ErrorAlert';
import Modal from '../ui/Modal';
import Pagination from '../ui/Pagination';

interface SupplierDetailModalProps {
  supplier: ApiSupplierDetail | null;
  onClose: () => void;
}

const DETAIL_PAGE_SIZE = 5;

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-faint">{label}</p>
      <p className="text-sm text-foreground">{value || '—'}</p>
    </div>
  );
}

export default function SupplierDetailModal({
  supplier,
  onClose,
}: SupplierDetailModalProps) {
  const [page, setPage] = useState(1);

  const productsState = useAsync(
    () =>
      supplier
        ? listSupplierProducts(supplier.id, {
            skip: (page - 1) * DETAIL_PAGE_SIZE,
            limit: DETAIL_PAGE_SIZE,
          })
        : Promise.resolve({ items: [], total: 0 }),
    [supplier?.id, page],
  );

  if (!supplier) return null;

  return (
    <Modal open title={`Proveedor: ${supplier.name}`} onClose={onClose} wide>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          {supplier.is_active ? (
            <Badge tone="green">Activo</Badge>
          ) : (
            <Badge tone="red">Inactivo</Badge>
          )}
          <span className="text-xs text-muted">
            {supplier.products_count} producto(s) asociado(s)
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3 rounded-xl border border-line bg-surface p-4 sm:grid-cols-2">
          <InfoRow label="Identificación" value={supplier.identification} />
          <InfoRow label="Contacto" value={supplier.contact_name} />
          <InfoRow label="Teléfono" value={supplier.phone} />
          <InfoRow label="Email" value={supplier.email} />
          <InfoRow label="Dirección" value={supplier.address} />
          <InfoRow label="Ciudad" value={supplier.city} />
        </div>

        {supplier.notes && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200">
            <span className="font-semibold">Notas:</span> {supplier.notes}
          </div>
        )}

        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">Productos asociados</h4>
          <ErrorAlert
            message={productsState.error}
            onRetry={
              productsState.loading ? undefined : () => void productsState.reload()
            }
          />
          {productsState.loading ? (
            <p className="py-6 text-center text-sm text-muted">Cargando…</p>
          ) : (productsState.data?.total ?? 0) === 0 ? (
            <p className="rounded-xl bg-surface py-6 text-center text-sm text-muted">
              Este proveedor no tiene productos asociados.
            </p>
          ) : (
            <div className="overflow-hidden rounded-xl border border-line">
              <table className="nx-table">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Código</th>
                    <th className="text-right">Compra</th>
                    <th className="text-right">Venta</th>
                    <th className="text-right">Stock</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {productsState.data?.items.map((product) => (
                    <tr key={product.id}>
                      <td className="font-medium text-foreground">{product.name}</td>
                      <td className="font-mono text-xs text-muted">
                        {product.barcode || '—'}
                      </td>
                      <td className="text-right tabular-nums">
                        {formatCurrency(product.purchase_price)}
                      </td>
                      <td className="text-right tabular-nums">
                        {formatCurrency(product.sale_price)}
                      </td>
                      <td className="text-right tabular-nums">{product.stock}</td>
                      <td>
                        {product.is_active ? (
                          <Badge tone="green">Activo</Badge>
                        ) : (
                          <Badge tone="red">Inactivo</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Pagination
                page={page}
                pageSize={DETAIL_PAGE_SIZE}
                total={productsState.data?.total ?? 0}
                onChange={setPage}
              />
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}