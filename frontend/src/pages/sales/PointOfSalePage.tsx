import { useEffect, useMemo, useState } from 'react';
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
import EmptyState from '../../components/ui/EmptyState';
import Icon from '../../components/ui/Icon';
import LoadingState from '../../components/ui/LoadingState';
import PageHeader from '../../components/ui/PageHeader';
import { formatCurrency } from '../../utils/format';

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

  useEffect(() => {
    const timer = setTimeout(() => {
      void productsState.reload();
    }, 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

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
    <div className="animate-fade-in space-y-4">
      <PageHeader
        title="Punto de venta"
        subtitle="Escanea el código de barras o busca productos para armar la venta."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {/* Búsqueda de productos */}
        <div className="nx-card space-y-3 p-4 lg:col-span-3">
          <form onSubmit={(event) => { event.preventDefault(); void handleBarcode(); }} className="flex gap-2">
            <input
              type="text"
              placeholder="Busca por nombre o escanea código de barras…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="nx-input"
              autoFocus
            />
            <button
              type="submit"
              className="nx-btn nx-btn-secondary"
            >
              <Icon name="scan" size={16} />
              Código
            </button>
            <button
              type="button"
              onClick={async () => {
                setBarcodeError(null);
                await productsState.reload();
              }}
              className="nx-btn nx-btn-primary"
            >
              <Icon name="search" size={16} />
              Buscar
            </button>
          </form>
          {barcodeError && (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200">
              {barcodeError}
            </p>
          )}

          {productsState.error && <ErrorAlert message={productsState.error} />}

          <div className="max-h-[28rem] space-y-2 overflow-y-auto">
            {productsState.loading ? (
              <div className="py-2">
                <LoadingState rows={5} />
              </div>
            ) : (productsState.data?.items.length ?? 0) === 0 ? (
              <EmptyState
                title="Sin resultados"
                hint="Escribe el nombre del producto y presiona Buscar, o escanea el código."
                icon="search"
              />
            ) : (
              productsState.data?.items.map((product) => (
                <div
                  key={product.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2 transition-colors hover:bg-surface-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {product.name}
                    </p>
                    <p className="text-xs text-muted">
                      Stock: {product.stock}
                      {product.barcode ? ` · ${product.barcode}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-foreground">
                      {formatCurrency(product.sale_price)}
                    </span>
                    <button
                      type="button"
                      onClick={() => addToCart(product)}
                      disabled={product.stock <= 0}
                      className="nx-btn nx-btn-sm nx-btn-success"
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
        <div className="nx-card space-y-4 p-4 lg:col-span-2">
          <h3 className="text-sm font-bold uppercase tracking-wide text-muted">
            Carrito
          </h3>

          {cart.length === 0 ? (
            <EmptyState
              title="Carrito vacío"
              hint="Agrega productos para comenzar la venta."
              icon="cart"
            />
          ) : (
            <ul className="divide-y divide-line">
              {cart.map((line) => (
                <li key={line.product.id} className="flex items-center justify-between gap-2 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {line.product.name}
                    </p>
                    <p className="text-xs text-muted">
                      {formatCurrency(line.product.sale_price)} × {line.quantity}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => changeQuantity(line.product.id, -1)}
                      className="rounded-lg border border-line-strong px-2 py-1 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
                    >
                      −
                    </button>
                    <span className="w-8 text-center text-sm tabular-nums">{line.quantity}</span>
                    <button
                      type="button"
                      onClick={() => changeQuantity(line.product.id, 1)}
                      className="rounded-lg border border-line-strong px-2 py-1 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-foreground"
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
                      className="ml-1 rounded-lg px-1.5 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                    >
                      Quitar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <div>
            <label htmlFor="pos-customer" className="nx-label">
              Cliente (opcional)
            </label>
            <select
              id="pos-customer"
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
              className="nx-select"
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
            {customersState.error && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                No se pudieron cargar los clientes.
              </p>
            )}
          </div>

          <div>
            <span className="nx-label">Método de pago</span>
            <div className="mt-1 grid grid-cols-4 gap-1">
              {PAYMENT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPaymentMethod(option.value)}
                  className={`rounded-lg border px-1 py-1.5 text-xs font-medium transition-colors ${
                    paymentMethod === option.value
                      ? 'border-primary bg-primary-soft text-primary'
                      : 'border-line-strong text-muted hover:bg-surface-2'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {paymentMethod === 'CASH' && (
            <div>
              <label htmlFor="pos-cash" className="nx-label">
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
                className="nx-input"
              />
              {Number(cashReceived) >= totals.total && cashReceived !== '' && (
                <p className="mt-1 text-xs font-medium text-green-600 dark:text-green-400">
                  Vuelto: {formatCurrency(Number(cashReceived) - totals.total)}
                </p>
              )}
            </div>
          )}

          {paymentMethod === 'CREDIT' && customerId && (
            <p
              className={`rounded-lg border px-3 py-2 text-xs ${
                creditInsufficient
                  ? 'border-red-300 bg-red-100/60 text-red-800 dark:border-red-400/30 dark:bg-red-500/10 dark:text-red-300'
                  : 'border-line bg-surface text-muted'
              }`}
            >
              Crédito disponible: {formatCurrency(creditAvailable)}
              {creditInsufficient && ' — cupo insuficiente para esta venta'}
            </p>
          )}

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="pos-discount" className="nx-label">
                Descuento
              </label>
              <input
                id="pos-discount"
                type="number"
                min="0"
                step="0.01"
                value={discount}
                onChange={(event) => setDiscount(event.target.value)}
                className="nx-input"
              />
            </div>
            <div>
              <label htmlFor="pos-tax" className="nx-label">
                Impuesto
              </label>
              <input
                id="pos-tax"
                type="number"
                min="0"
                step="0.01"
                value={tax}
                onChange={(event) => setTax(event.target.value)}
                className="nx-input"
              />
            </div>
          </div>

          <div>
            <label htmlFor="pos-notes" className="nx-label">
              Notas (opcional)
            </label>
            <input
              id="pos-notes"
              type="text"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="nx-input"
            />
          </div>

          <div className="space-y-1 border-t border-line pt-3 text-sm">
            <div className="flex justify-between text-muted">
              <span>Subtotal</span>
              <span className="tabular-nums">{formatCurrency(totals.subtotal)}</span>
            </div>
            <div className="flex justify-between text-red-600 dark:text-red-400">
              <span>Descuento</span>
              <span className="tabular-nums">−{formatCurrency(totals.discountValue)}</span>
            </div>
            <div className="flex justify-between text-muted">
              <span>Impuesto</span>
              <span className="tabular-nums">+{formatCurrency(totals.taxValue)}</span>
            </div>
            <div className="flex justify-between text-lg font-bold text-foreground">
              <span>Total</span>
              <span className="tabular-nums">{formatCurrency(totals.total)}</span>
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
            className="nx-btn nx-btn-success w-full py-3 text-base font-bold"
          >
            {busy ? 'Procesando…' : `Cobrar ${formatCurrency(totals.total)}`}
          </button>
        </div>
      </div>
    </div>
  );
}