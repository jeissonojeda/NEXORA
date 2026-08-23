import { useState } from 'react';
import { useAsync } from '../../hooks/useAsync';
import { listSupplierProducts } from '../../services/suppliers';
import type { ApiSupplierDetail } from '../../types/catalog';
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
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">{label}</p>
      <p className="text-sm text-gray-800">{value || '—'}</p>
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
          <span className="text-xs text-gray-500">
            {supplier.products_count} producto(s) asociado(s)
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3 rounded-md bg-gray-50 p-4 sm:grid-cols-2">
          <InfoRow label="Identificación" value={supplier.identification} />
          <InfoRow label="Contacto" value={supplier.contact_name} />
          <InfoRow label="Teléfono" value={supplier.phone} />
          <InfoRow label="Email" value={supplier.email} />
          <InfoRow label="Dirección" value={supplier.address} />
          <InfoRow label="Ciudad" value={supplier.city} />
        </div>

        {supplier.notes && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <span className="font-semibold">Notas:</span> {supplier.notes}
          </div>
        )}

        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">Productos asociados</h4>
          <ErrorAlert
            message={productsState.error}
            onRetry={
              productsState.loading ? undefined : () => void productsState.reload()
            }
          />
          {productsState.loading ? (
            <p className="py-6 text-center text-sm text-gray-500">Cargando…</p>
          ) : (productsState.data?.total ?? 0) === 0 ? (
            <p className="rounded-md bg-gray-50 py-6 text-center text-sm text-gray-500">
              Este proveedor no tiene productos asociados.
            </p>
          ) : (
            <div className="overflow-hidden rounded-md border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-gray-600">
                      Producto
                    </th>
                    <th className="px-3 py-2 text-left font-semibold text-gray-600">
                      Código
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-gray-600">
                      Compra
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-gray-600">
                      Venta
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-gray-600">
                      Stock
                    </th>
                    <th className="px-3 py-2 text-left font-semibold text-gray-600">
                      Estado
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {productsState.data?.items.map((product) => (
                    <tr key={product.id}>
                      <td className="px-3 py-2 font-medium text-gray-900">
                        {product.name}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-gray-500">
                        {product.barcode || '—'}
                      </td>
                      <td className="px-3 py-2 text-right">
                        ₡{Number(product.purchase_price).toLocaleString('es-CR', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-3 py-2 text-right">
                        ₡{Number(product.sale_price).toLocaleString('es-CR', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-3 py-2 text-right">{product.stock}</td>
                      <td className="px-3 py-2">
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
