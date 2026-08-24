import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import { listCustomers } from '../../services/customers';
import { listProducts, getProductByBarcode } from '../../services/products';
import { createSale, confirmSale } from '../../services/sales';
import type {
  ApiProduct,
} from '../../types/catalog';
import type { SalePaymentMethod } from '../../types/sale';
import ErrorAlert from '../../components/ui/ErrorAlert';
import { formatCurrency } from '../../utils/format';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

interface CartLine {
  product: ApiProduct;
  quantity: number;
}

const PAYMENT_OPTIONS: { value: SalePaymentMethod; label: string }[] = [
  { value: 'CASH', label: 'Efectivo' },
  { value: 'CARD', label: 'Tarjeta' },
  { value: 'TRANSFER', label: 'Transferencia' },
  { value: 'CREDIT', label: 'Crédito' },
];

export default function PointOfSalePage() {
  const navigate = useNavigate();

  // Búsqueda de productos
  const [query, setQuery] = useState('');
  const [barcodeError, setBarcodeError] = useState<string | null>(null);

  const productsState = useAsync(
    () =>
      listProducts({
        q: query || null,
        isActive: true,
        limit: 20,
      }),
    [],
  );

  const customersState = useAsync(() => listCustomers({ limit: 200 }), []);

  // Carrito
  const [cart, setCart] = useState<CartLine[]>([]);
  const [customerId, setCustomerId] = useState('');
  const [paymentMethod, setPaymentMethod] =
    useState<SalePaymentMethod>('CASH');
  const [cashReceived, setCashReceived] = useState('');
  const [discount, setDiscount] = useState('0');
  const [tax, setTax] = useState('0');
  const [notes, setNotes] = useState('');

  const [busy, setBusy] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  const totals = useMemo(() => {
    const subtotal = cart.reduce(
      (sum, line) =>
        sum + Number(line.product.sale_price) * line.quantity,
      0,
    );
    const discountValue = Math.min(Math.max(Number(discount) || 0, 0), subtotal);
    const taxValue = Math.max(Number(tax) || 0, 0);
    const total = subtotal - discountValue + taxValue;
    return { subtotal, discountValue, taxValue, total };
  }, [cart, discount, tax]);

  const selectedCustomer = customersState.data?.items.find(
    (customer) => customer.id === customerId,
  );
  const creditAvailable = selectedCustomer?.credit_enabled
    ? Number(selectedCustomer.credit_available)
    : 0;
  const creditInsufficient =
    paymentMethod === 'CREDIT' &&
    selectedCustomer !== undefined &&
    totals.total > creditAvailable;

  function addToCart(product: ApiProduct) {
    if (product.stock <= 0) return;
    setCart((current) => {
      const existing = current.find((line) => line.product.id === product.id);
      if (existing) {
        if (existing.quantity >= product.stock) return current;
        return current.map((line) =>
          line.product.id === product.id
            ? { ...line, quantity: line.quantity + 1 }
            : line,
        );
      }
      return [...current, { product, quantity: 1 }];
    });
  }

  function changeQuantity(productId: string, delta: number) {
    setCart((current) =>
      current
        .map((line) => {
          if (line.product.id !== productId) return line;
          const next = line.quantity + delta;
          if (next > line.product.stock) return line;
          return { ...line, quantity: next };
        })
        .filter((line) => line.quantity > 0),
    );
  }

  async function handleBarcode() {
    const barcode = query.trim();
    if (!barcode) return;
    setBarcodeError(null);
    try {
      const product = await getProductByBarcode(barcode);
      addToCart(product);
      setQuery('');
    } catch {
      setBarcodeError(`Sin resultado para código "${barcode}". Presione Buscar para listar.`);
    }
  }

  async function handleCheckout() {
    if (cart.length === 0) {
      setCheckoutError('Agregue al menos un producto');
      return;
    }
    if (paymentMethod === 'CREDIT' && !customerId) {
      setCheckoutError('La venta a crédito requiere un cliente');
      return;
    }
    setBusy(true);
    setCheckoutError(null);
    try {
      const created = await createSale({
        customer_id: customerId || null,
        payment_method: paymentMethod,
        amount_paid:
          paymentMethod === 'CASH' && cashReceived.trim()
            ? Number(cashReceived)
            : undefined,
        discount: Number(discount) || 0,
        tax: Number(tax) || 0,
        notes: notes.trim() || null,
        items: cart.map((line) => ({
          product_id: line.product.id,
          quantity: line.quantity,
        })),
      });
      const confirmed = await confirmSale(created.id);
      navigate(`/ventas/${confirmed.id}`);
    } catch (err) {
      setCheckoutError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-gray-900">Punto de venta</h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {/* Búsqueda de productos */}
        <div className="space-y-3 rounded-lg bg-white p-4 shadow lg:col-span-3">
          <form onSubmit={(event) => { event.preventDefault(); void handleBarcode(); }} className="flex gap-2">
            <input
              type="text"
              placeholder="Código de barras + Enter, o nombre…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className={inputClass}
              autoFocus
            />
            <button
              type="submit"
              className="rounded-md bg-gray-800 px-3 py-2 text-sm font-semibold text-white hover:bg-gray-900"
            >
              Código
            </button>
            <button
              type="button"
              onClick={async () => {
                setBarcodeError(null);
                await productsState.reload();
              }}
              className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Buscar
            </button>
          </form>
          {barcodeError && (
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
              {barcodeError}
            </p>
          )}

          {productsState.error && <ErrorAlert message={productsState.error} />}

          <div className="max-h-[28rem] space-y-2 overflow-y-auto">
            {productsState.loading ? (
              <p className="py-8 text-center text-sm text-gray-400">
                Cargando productos…
              </p>
            ) : (productsState.data?.items.length ?? 0) === 0 ? (
              <p className="py-8 text-center text-sm text-gray-400">
                Sin resultados.
              </p>
            ) : (
              productsState.data?.items.map((product) => (
                <div
                  key={product.id}
                  className="flex items-center justify-between gap-3 rounded-md border border-gray-200 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">
                      {product.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      Stock: {product.stock}
                      {product.barcode ? ` · ${product.barcode}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-gray-900">
                      {formatCurrency(product.sale_price)}
                    </span>
                    <button
                      type="button"
                      onClick={() => addToCart(product)}
                      disabled={product.stock <= 0}
                      className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-40"
                    >
                      + Agregar
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Carrito y cobro */}
        <div className="space-y-4 rounded-lg bg-white p-4 shadow lg:col-span-2">
          <h3 className="text-sm font-bold uppercase tracking-wide text-gray-500">
            Carrito
          </h3>

          {cart.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-400">Carrito vacío.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {cart.map((line) => (
                <li key={line.product.id} className="flex items-center justify-between gap-2 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">
                      {line.product.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatCurrency(line.product.sale_price)} × {line.quantity}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => changeQuantity(line.product.id, -1)}
                      className="rounded border border-gray-300 px-2 py-1 text-sm hover:bg-gray-50"
                    >
                      −
                    </button>
                    <span className="w-8 text-center text-sm">{line.quantity}</span>
                    <button
                      type="button"
                      onClick={() => changeQuantity(line.product.id, 1)}
                      className="rounded border border-gray-300 px-2 py-1 text-sm hover:bg-gray-50"
                    >
                      +
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setCart((current) =>
                          current.filter(
                            (item) => item.product.id !== line.product.id,
                          ),
                        )
                      }
                      className="ml-1 rounded px-1.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                    >
                      Quitar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <div>
            <label htmlFor="pos-customer" className="block text-xs font-medium text-gray-500">
              Cliente (opcional)
            </label>
            <select
              id="pos-customer"
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
              className={`mt-1 ${inputClass}`}
            >
              <option value="">Consumidor final</option>
              {customersState.data?.items
                .filter((customer) => customer.is_active)
                .map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                    {customer.credit_enabled
                      ? ` · crédito disp. ${Number(customer.credit_available).toFixed(2)}`
                      : ''}
                  </option>
                ))}
            </select>
          </div>

          <div>
            <span className="block text-xs font-medium text-gray-500">Método de pago</span>
            <div className="mt-1 grid grid-cols-4 gap-1">
              {PAYMENT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPaymentMethod(option.value)}
                  className={`rounded-md border px-1 py-1.5 text-xs font-medium ${
                    paymentMethod === option.value
                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                      : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {paymentMethod === 'CASH' && (
            <div>
              <label htmlFor="pos-cash" className="block text-xs font-medium text-gray-500">
                Efectivo recibido (opcional)
              </label>
              <input
                id="pos-cash"
                type="number"
                min="0"
                step="0.01"
                placeholder={`${totals.total.toFixed(2)}`}
                value={cashReceived}
                onChange={(event) => setCashReceived(event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
              {Number(cashReceived) >= totals.total && cashReceived !== '' && (
                <p className="mt-1 text-xs font-medium text-green-700">
                  Vuelto: {(Number(cashReceived) - totals.total).toFixed(2)}
                </p>
              )}
            </div>
          )}

          {paymentMethod === 'CREDIT' && customerId && (
            <p
              className={`rounded-md border px-3 py-2 text-xs ${
                creditInsufficient
                  ? 'border-red-200 bg-red-50 text-red-700'
                  : 'border-gray-200 bg-gray-50 text-gray-600'
              }`}
            >
              Crédito disponible: {creditAvailable.toFixed(2)}
              {creditInsufficient && ' — cupo insuficiente para esta venta'}
            </p>
          )}

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="pos-discount" className="block text-xs font-medium text-gray-500">
                Descuento
              </label>
              <input
                id="pos-discount"
                type="number"
                min="0"
                step="0.01"
                value={discount}
                onChange={(event) => setDiscount(event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </div>
            <div>
              <label htmlFor="pos-tax" className="block text-xs font-medium text-gray-500">
                Impuesto
              </label>
              <input
                id="pos-tax"
                type="number"
                min="0"
                step="0.01"
                value={tax}
                onChange={(event) => setTax(event.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </div>
          </div>

          <div>
            <label htmlFor="pos-notes" className="block text-xs font-medium text-gray-500">
              Notas (opcional)
            </label>
            <input
              id="pos-notes"
              type="text"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className={`mt-1 ${inputClass}`}
            />
          </div>

          <div className="space-y-1 border-t border-gray-200 pt-3 text-sm">
            <div className="flex justify-between text-gray-600">
              <span>Subtotal</span>
              <span>{totals.subtotal.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-red-600">
              <span>Descuento</span>
              <span>−{totals.discountValue.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-gray-600">
              <span>Impuesto</span>
              <span>+{totals.taxValue.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold text-gray-900">
              <span>Total</span>
              <span>{formatCurrency(totals.total)}</span>
            </div>
          </div>

          {checkoutError && <ErrorAlert message={checkoutError} />}

          <button
            type="button"
            onClick={() => void handleCheckout()}
            disabled={
              busy ||
              cart.length === 0 ||
              creditInsufficient ||
              (paymentMethod === 'CASH' &&
                cashReceived !== '' &&
                Number(cashReceived) < totals.total)
            }
            className="w-full rounded-md bg-green-600 px-4 py-3 text-base font-bold text-white hover:bg-green-700 disabled:opacity-50"
          >
            {busy ? 'Procesando…' : `Cobrar ${formatCurrency(totals.total)}`}
          </button>
        </div>
      </div>
    </div>
  );
}
