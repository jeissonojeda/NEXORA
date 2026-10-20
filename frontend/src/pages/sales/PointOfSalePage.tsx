import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { extractErrorCode, extractErrorMessage, useAsync } from '../../hooks/useAsync';
import { listCustomers } from '../../services/customers';
import { listProducts, getProductByBarcode } from '../../services/products';
import { createSale, confirmSale, getSale } from '../../services/sales';
import type { ApiProduct } from '../../types/catalog';
import type { ApiSaleDetail, SalePaymentMethod } from '../../types/sale';
import ErrorAlert from '../../components/ui/ErrorAlert';
import EmptyState from '../../components/ui/EmptyState';
import Badge from '../../components/ui/Badge';
import Icon from '../../components/ui/Icon';
import LoadingState from '../../components/ui/LoadingState';
import PageHeader from '../../components/ui/PageHeader';
import Modal from '../../components/ui/Modal';
import { formatCurrency } from '../../utils/format';

interface CartLine {
  product: ApiProduct;
  quantity: number;
}

interface ScanFeedback {
  kind: 'success' | 'not-found' | 'no-stock' | 'max-stock' | 'idle';
  message: string;
}

const PAYMENT_OPTIONS: { value: SalePaymentMethod; label: string; icon: Parameters<typeof Icon>[0]['name'] }[] = [
  { value: 'CASH', label: 'Efectivo', icon: 'banknote' },
  { value: 'CARD', label: 'Tarjeta', icon: 'credit-card' },
  { value: 'TRANSFER', label: 'Transferencia', icon: 'refresh' },
  { value: 'CREDIT', label: 'Crédito', icon: 'wallet' },
];

export default function PointOfSalePage() {
  const navigate = useNavigate();

  // Búsqueda de productos
  const [query, setQuery] = useState('');
  const [barcodeError, setBarcodeError] = useState<string | null>(null);
  const scanInputRef = useRef<HTMLInputElement>(null);

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
  const [notes, setNotes] = useState('');

  const [busy, setBusy] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [saleSuccess, setSaleSuccess] = useState<ApiSaleDetail | null>(null);
  const [pendingDraft, setPendingDraft] = useState<{
    id: string;
    saleNumber: string;
  } | null>(null);
  // Evita duplicar la creación/confirmación ante dobles clics.
  const submitRef = useRef(false);
  // Borrador creado en un intento fallido: se reutiliza en el reintento.
  const draftRef = useRef<{ id: string; signature: string } | null>(null);
  const [feedback, setFeedback] = useState<ScanFeedback>({
    kind: 'idle',
    message: '',
  });
  const feedbackTimer = useRef<number | null>(null);

  const showFeedback = useCallback(
    (kind: ScanFeedback['kind'], message: string) => {
      setFeedback({ kind, message });
      if (feedbackTimer.current) window.clearTimeout(feedbackTimer.current);
      feedbackTimer.current = window.setTimeout(
        () => setFeedback((current) => (current.kind === kind ? { kind: 'idle', message: '' } : current)),
        2200,
      );
    },
    [],
  );

  // Mantener el foco en el escáner cuando se cierra el modal
  useEffect(() => {
    if (confirmOpen) return;
    const t = window.setTimeout(() => scanInputRef.current?.focus(), 50);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmOpen]);

  useEffect(() => {
    return () => {
      if (feedbackTimer.current) window.clearTimeout(feedbackTimer.current);
    };
  }, []);

  // Si cambia cualquier dato de la venta, el borrador creado ya no la
  // representa: el próximo cobro creará uno nuevo.
  useEffect(() => {
    if (!draftRef.current) return;
    draftRef.current = null;
    setPendingDraft(null);
    setCheckoutError(null);
  }, [cart, customerId, paymentMethod, discount, cashReceived, notes]);

  const totals = useMemo(() => {
    const subtotal = cart.reduce(
      (sum, line) => sum + Number(line.product.sale_price) * line.quantity,
      0,
    );
    const discountValue = Math.min(Math.max(Number(discount) || 0, 0), subtotal);
    // Impuesto calculado automáticamente por producto/categoría.
    const taxValue = cart.reduce((sum, line) => {
      const rate = Number(line.product.effective_tax?.rate ?? 0);
      const base = Number(line.product.sale_price) * line.quantity;
      return sum + (base * rate) / 100;
    }, 0);
    const total = subtotal - discountValue + taxValue;
    return { subtotal, discountValue, taxValue, total };
  }, [cart, discount]);

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
  const creditMissingCustomer = paymentMethod === 'CREDIT' && !customerId;

  const cashChange =
    paymentMethod === 'CASH' && cashReceived.trim() !== ''
      ? Number(cashReceived) - totals.total
      : 0;
  const cashShort = paymentMethod === 'CASH' && cashChange < 0;

  // Agrega o consolida un producto en el carrito.
  const addToCart = useCallback(
    (product: ApiProduct) => {
      const currentQuantity =
        cart.find((line) => line.product.id === product.id)?.quantity ?? 0;
      if (currentQuantity >= product.stock) {
        showFeedback('max-stock', `Stock máximo alcanzado (${product.stock})`);
        return;
      }
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
    },
    [cart, showFeedback],
  );

  function changeQuantity(productId: string, delta: number) {
    setCart((current) =>
      current
        .map((line) => {
          if (line.product.id !== productId) return line;
          const next = line.quantity + delta;
          if (next > line.product.stock) {
            showFeedback('max-stock', `Stock máximo alcanzado (${line.product.stock})`);
            return line;
          }
          return { ...line, quantity: next };
        })
        .filter((line) => line.quantity > 0),
    );
  }

  function setExactQuantity(productId: string, raw: string) {
    const parsed = parseInt(raw, 10);
    if (Number.isNaN(parsed)) return;
    setCart((current) =>
      current
        .map((line) => {
          if (line.product.id !== productId) return line;
          const clamped = Math.max(1, Math.min(parsed, line.product.stock));
          if (parsed > line.product.stock) {
            showFeedback('max-stock', `Stock máximo ${line.product.stock}`);
          }
          return { ...line, quantity: clamped };
        })
        .filter((line) => line.quantity > 0 || parsed > 0),
    );
  }

  function removeFromCart(productId: string) {
    setCart((current) =>
      current.filter((item) => item.product.id !== productId),
    );
    window.setTimeout(() => scanInputRef.current?.focus(), 0);
  }

  // Escaneo de código de barras: busca por código exacto.
  async function handleBarcode(raw: string) {
    const barcode = raw.trim();
    if (!barcode) return;
    setBarcodeError(null);
    try {
      const product = await getProductByBarcode(barcode);
      if (product.stock <= 0) {
        showFeedback('no-stock', 'Producto sin stock');
        setQuery('');
        return;
      }
      addToCart(product);
      showFeedback('success', `${product.name} añadido`);
      setQuery('');
      window.setTimeout(() => scanInputRef.current?.focus(), 0);
    } catch (err) {
      const message = extractErrorMessage(err);
      setBarcodeError(
        message.toLowerCase().includes('no encontrado')
          ? `Producto no encontrado para el código "${barcode}"`
          : message,
      );
      showFeedback('not-found', 'Producto no encontrado');
      setQuery('');
      window.setTimeout(() => scanInputRef.current?.focus(), 0);
    }
  }

  function onSearchSubmit(event: React.FormEvent) {
    event.preventDefault();
    void handleBarcode(query);
  }

  function onSearchKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setQuery('');
      setBarcodeError(null);
      scanInputRef.current?.focus();
    }
  }

  async function handleCheckout() {
    if (cart.length === 0) {
      setCheckoutError('Agregue al menos un producto');
      return;
    }
    if (creditMissingCustomer) {
      setCheckoutError('Seleccione un cliente para la venta a crédito');
      return;
    }
    if (submitRef.current) return;
    submitRef.current = true;
    setBusy(true);
    setCheckoutError(null);
    try {
      const payload = {
        customer_id: customerId || null,
        payment_method: paymentMethod,
        amount_paid:
          paymentMethod === 'CASH' && cashReceived.trim()
            ? Number(cashReceived)
            : undefined,
        discount: Number(discount) || 0,
        // El backend deriva el impuesto de cabecera a partir de los ítems.
        tax: 0,
        notes: notes.trim() || null,
        items: cart.map((line) => ({
          product_id: line.product.id,
          quantity: line.quantity,
          tax_rate: line.product.effective_tax
            ? Number(line.product.effective_tax.rate)
            : undefined,
          tax_name: line.product.effective_tax?.name,
        })),
      };

      // Reutiliza el borrador de un intento fallido con los mismos datos.
      const signature = JSON.stringify(payload);
      if (draftRef.current && draftRef.current.signature !== signature) {
        draftRef.current = null;
        setPendingDraft(null);
      }
      let saleId = draftRef.current?.id;
      if (!saleId) {
        const created = await createSale(payload);
        saleId = created.id;
        draftRef.current = { id: created.id, signature };
        setPendingDraft({
          id: created.id,
          saleNumber: created.sale_number,
        });
      }

      let confirmed: ApiSaleDetail;
      try {
        confirmed = await confirmSale(saleId);
      } catch (err) {
        // Un reintento puede encontrar la venta ya confirmada por el intento
        // anterior (la respuesta se perdió): se recupera, no se duplica.
        if (extractErrorCode(err) === 'SALE_ALREADY_CONFIRMED') {
          confirmed = await getSale(saleId);
        } else {
          throw err;
        }
      }

      draftRef.current = null;
      setPendingDraft(null);
      setConfirmOpen(false);
      setSaleSuccess(confirmed);
    } catch (err) {
      setCheckoutError(extractErrorMessage(err));
      setConfirmOpen(false);
    } finally {
      submitRef.current = false;
      setBusy(false);
    }
  }

  function startNewSale() {
    setSaleSuccess(null);
    setCart([]);
    setCustomerId('');
    setPaymentMethod('CASH');
    setCashReceived('');
    setDiscount('0');
    setNotes('');
    setCheckoutError(null);
    setBarcodeError(null);
    setQuery('');
    setConfirmOpen(false);
    setFeedback({ kind: 'idle', message: '' });
    draftRef.current = null;
    setPendingDraft(null);
    void productsState.reload();
    window.setTimeout(() => scanInputRef.current?.focus(), 50);
  }

  const canCheckout =
    !busy &&
    cart.length > 0 &&
    !creditMissingCustomer &&
    !creditInsufficient &&
    !(paymentMethod === 'CASH' && cashReceived !== '' && Number(cashReceived) < totals.total);

  return (
    <div className="animate-fade-in space-y-4">
      <PageHeader
        title="Punto de venta"
        subtitle="Escanea códigos de barras con el lector o agrega productos por nombre."
      />

      {/* Feedback visual del escáner */}
      {feedback.kind !== 'idle' && (
        <div
          className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium animate-fade-in ${
            feedback.kind === 'success'
              ? 'border-green-300 bg-green-50 text-green-800 dark:border-green-400/30 dark:bg-green-500/10 dark:text-green-200'
              : feedback.kind === 'not-found' || feedback.kind === 'no-stock'
                ? 'border-red-300 bg-red-50 text-red-800 dark:border-red-400/30 dark:bg-red-500/10 dark:text-red-200'
                : 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-200'
          }`}
        >
          <Icon
            name={
              feedback.kind === 'success'
                ? 'check-circle'
                : feedback.kind === 'not-found'
                  ? 'x-circle'
                  : 'triangle-alert'
            }
            size={18}
          />
          {feedback.message}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        {/* Columna izquierda: buscador + productos */}
        <div className="space-y-4 xl:col-span-3">
          {/* Buscador / código de barras */}
          <div className="nx-card p-4">
            <form onSubmit={onSearchSubmit} className="flex gap-2">
              <div className="relative flex-1">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-faint">
                  <Icon name="scan" size={18} />
                </span>
                <input
                  ref={scanInputRef}
                  type="text"
                  autoFocus
                  autoComplete="off"
                  enterKeyHint="done"
                  placeholder="Escanea código de barras o busca por nombre…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={onSearchKeyDown}
                  className="nx-input pl-10 text-base"
                />
              </div>
              <button
                type="submit"
                className="nx-btn nx-btn-primary"
                title="Procesar código de barras (Enter)"
              >
                <Icon name="scan" size={16} />
                Buscar
              </button>
            </form>
            <p className="mt-2 text-xs text-faint">
              Con el lector USB: escanea y presiona Enter (o escanea directamente) para agregar al carrito. Luego podrás seguir escaneando.
            </p>            {barcodeError && (
              <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200">
                {barcodeError}
              </p>
            )}
            {productsState.error && <ErrorAlert message={productsState.error} />}
          </div>

          {/* Productos encontrados */}
          <div className="nx-card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-bold uppercase tracking-wide text-muted">
                Resultados
              </h3>
              {query && (
                <button
                  type="button"
                  onClick={() => {
                    setBarcodeError(null);
                    void productsState.reload();
                  }}
                  className="nx-btn nx-btn-sm nx-btn-secondary"
                >
                  <Icon name="search" size={14} />
                  Buscar
                </button>
              )}
            </div>
            <div className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
              {productsState.loading ? (
                <div className="py-2">
                  <LoadingState rows={5} />
                </div>
              ) : (productsState.data?.items.length ?? 0) === 0 ? (
                <EmptyState
                  title="Sin resultados"
                  hint="Escanea el código de barras o escribe el nombre del producto."
                  icon="search"
                />
              ) : (
                productsState.data?.items.map((product) => (
                  <div
                    key={product.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-line px-3 py-2 transition-colors hover:bg-surface-2"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-medium text-foreground">
                          {product.name}
                        </p>
                        {product.stock <= 0 && <Badge tone="red">Sin stock</Badge>}
                        {product.stock > 0 && product.stock <= product.minimum_stock && (
                          <Badge tone="amber">Stock bajo</Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted">
                        Stock: {product.stock}
                        {product.barcode ? ` · ${product.barcode}` : ''}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold tabular-nums text-foreground">
                        {formatCurrency(product.sale_price)}
                      </span>
                      <button
                        type="button"
                        onClick={() => addToCart(product)}
                        disabled={product.stock <= 0}
                        className="nx-btn nx-btn-sm nx-btn-success"
                      >
                        <Icon name="plus" size={14} />
                        Agregar
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Columna derecha: carrito + cliente + resumen + cobro */}
        <div className="space-y-4 xl:col-span-2 xl:sticky xl:top-4 xl:self-start">
          {/* Carrito */}
          <div className="nx-card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-muted">
                <Icon name="cart" size={16} />
                Carrito
                {cart.length > 0 && (
                  <Badge tone="blue">
                    {cart.reduce((sum, line) => sum + line.quantity, 0)} art.
                  </Badge>
                )}
              </h3>
            </div>

            {cart.length === 0 ? (
              <EmptyState
                title="Carrito vacío"
                hint="Escanea o agrega productos para comenzar la venta."
                icon="cart"
              />
            ) : (
              <ul className="max-h-[24rem] space-y-2 overflow-y-auto pr-1">
                {cart.map((line) => (
                  <CartLineRow
                    key={line.product.id}
                    line={line}
                    onChangeQuantity={(delta) =>
                      changeQuantity(line.product.id, delta)
                    }
                    onSetQuantity={(raw) =>
                      setExactQuantity(line.product.id, raw)
                    }
                    onRemove={() => removeFromCart(line.product.id)}
                  />
                ))}
              </ul>
            )}
          </div>

          {/* Cliente */}
          <div className="nx-card p-4">
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

          {/* Resumen de compra + método de pago */}
          <div className="nx-card p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-muted">
              <Icon name="receipt" size={16} />
              Cobro
            </h3>

            <div className="space-y-3">
              <div>
                <span className="nx-label">Método de pago</span>
                <div className="mt-1 grid grid-cols-4 gap-1">
                  {PAYMENT_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setPaymentMethod(option.value)}
                      className={`flex flex-col items-center gap-1 rounded-lg border px-1 py-1.5 text-[11px] font-medium transition-colors ${
                        paymentMethod === option.value
                          ? 'border-primary bg-primary-soft text-primary'
                          : 'border-line-strong text-muted hover:bg-surface-2'
                      }`}
                    >
                      <Icon name={option.icon} size={16} />
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              {paymentMethod === 'CASH' && (
                <div>
                  <label htmlFor="pos-cash" className="nx-label">
                    Efectivo recibido
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
                  {cashReceived !== '' && (
                    <p
                      className={`mt-1 text-xs font-medium ${
                        cashShort
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-green-600 dark:text-green-400'
                      }`}
                    >
                      {cashShort
                        ? `Faltan ${formatCurrency(-cashChange)}`
                        : `Vuelto: ${formatCurrency(cashChange)}`}
                    </p>
                  )}
                </div>
              )}

              {paymentMethod === 'CREDIT' && (
                <p
                  className={`rounded-lg border px-3 py-2 text-xs ${
                    creditInsufficient
                      ? 'border-red-300 bg-red-100/60 text-red-800 dark:border-red-400/30 dark:bg-red-500/10 dark:text-red-300'
                      : 'border-line bg-surface text-muted'
                  }`}
                >
                  {selectedCustomer
                    ? `Crédito disponible: ${formatCurrency(creditAvailable)}${
                        creditInsufficient ? ' — cupo insuficiente' : ''
                      }`
                    : 'Selecciona un cliente con crédito habilitado.'}
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
                  <label className="nx-label">Impuesto (automático)</label>
                  <input
                    type="text"
                    value={formatCurrency(totals.taxValue)}
                    readOnly
                    className="nx-input"
                    aria-label="Impuesto calculado automáticamente"
                  />
                  <p className="mt-1 text-xs text-faint">
                    Se calcula según el impuesto del producto o su categoría.
                  </p>
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
            </div>
          </div>

          {/* Totales + botón COBRAR */}
          <div className="nx-card space-y-3 p-4">
            <div className="space-y-1 text-sm">
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
              <div className="flex items-center justify-between border-t border-line pt-2">
                <span className="text-base font-bold text-foreground">Total</span>
                <span className="text-2xl font-extrabold tabular-nums text-primary">
                  {formatCurrency(totals.total)}
                </span>
              </div>
            </div>

            {checkoutError && <ErrorAlert message={checkoutError} />}

            {pendingDraft && (
              <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-200">
                Borrador {pendingDraft.saleNumber} pendiente de confirmar. Al
                reintentar el cobro se confirma ese borrador, sin duplicar la
                venta.
              </p>
            )}

            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              disabled={!canCheckout}
              className="nx-btn nx-btn-success w-full py-4 text-lg font-extrabold shadow-lg"
            >
              <Icon name="check-circle" size={20} />
              {busy ? 'Procesando…' : `Cobrar ${formatCurrency(totals.total)}`}
            </button>
          </div>
        </div>
      </div>

      {/* Modal de confirmación de cobro */}
      <Modal
        open={confirmOpen}
        title="Confirmar cobro"
        onClose={() => {
          if (!busy) setConfirmOpen(false);
        }}
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-line bg-surface-2 p-4 text-center">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Total a cobrar
            </p>
            <p className="mt-1 text-4xl font-extrabold tabular-nums text-primary">
              {formatCurrency(totals.total)}
            </p>
          </div>

          <dl className="space-y-2 rounded-xl border border-line p-4 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted">Método de pago</dt>
              <dd className="font-semibold text-foreground">
                {PAYMENT_OPTIONS.find((o) => o.value === paymentMethod)?.label}
              </dd>
            </div>
            {paymentMethod === 'CASH' && (
              <>
                <div className="flex justify-between">
                  <dt className="text-muted">Efectivo recibido</dt>
                  <dd className="tabular-nums text-foreground">
                    {cashReceived.trim() ? formatCurrency(Number(cashReceived)) : formatCurrency(totals.total)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted">Vuelto</dt>
                  <dd
                    className={`tabular-nums font-semibold ${
                      cashShort ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'
                    }`}
                  >
                    {formatCurrency(cashShort ? -cashChange : cashChange)}
                  </dd>
                </div>
              </>
            )}
            {paymentMethod === 'CARD' && (
              <p className="text-muted">Pago con tarjeta.</p>
            )}
            {paymentMethod === 'TRANSFER' && (
              <p className="text-muted">Pago por transferencia.</p>
            )}
            {paymentMethod === 'CREDIT' && (
              <div className="flex justify-between">
                <dt className="text-muted">Crédito disponible</dt>
                <dd className="tabular-nums text-foreground">
                  {formatCurrency(creditAvailable)}
                </dd>
              </div>
            )}
            <div className="flex justify-between border-t border-line pt-2">
              <dt className="text-muted">Artículos</dt>
              <dd className="tabular-nums text-foreground">
                {cart.reduce((sum, line) => sum + line.quantity, 0)}
              </dd>
            </div>
          </dl>

          {confirmOpen && paymentMethod === 'CASH' && cashReceived.trim() === '' && (
            <p className="rounded-lg border border-line bg-surface px-3 py-2 text-xs text-muted">
              No se registró efectivo recibido; se asumirá el monto exacto del total.
            </p>
          )}
          {confirmOpen && paymentMethod === 'CREDIT' && !customerId && (
            <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-200">
              La venta a crédito requiere seleccionar un cliente.
            </p>
          )}

          {confirmOpen && paymentMethod === 'CREDIT' && selectedCustomer && !creditInsufficient && (
            <p className="rounded-lg border border-green-300 bg-green-50 px-3 py-2 text-xs text-green-800 dark:border-green-400/30 dark:bg-green-500/10 dark:text-green-200">
              Se cargará a la cuenta por cobrar del cliente. El cobro se registra al abonar.
            </p>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setConfirmOpen(false)}
              disabled={busy}
              className="nx-btn nx-btn-secondary flex-1"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void handleCheckout()}
              disabled={busy || !canCheckout}
              className="nx-btn nx-btn-success flex-[2] py-3 text-base font-bold"
            >
              {busy ? 'Cobrando…' : 'Confirmar cobro'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Modal de éxito: la venta ya fue confirmada por el backend */}
      <Modal
        open={saleSuccess !== null}
        title="Venta completada"
        onClose={startNewSale}
      >
        {saleSuccess && (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-2 rounded-xl border border-green-300 bg-green-50 px-4 py-5 text-center dark:border-green-400/30 dark:bg-green-500/10">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-green-500/20 text-green-700 dark:text-green-300">
                <Icon name="check-circle" size={28} />
              </span>
              <p className="text-sm font-semibold text-green-900 dark:text-green-200">
                Venta {saleSuccess.sale_number} registrada y confirmada.
              </p>
              <p className="text-3xl font-extrabold tabular-nums text-green-900 dark:text-green-200">
                {formatCurrency(saleSuccess.total)}
              </p>
            </div>

            <dl className="space-y-2 rounded-xl border border-line p-4 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted">Método de pago</dt>
                <dd className="font-semibold text-foreground">
                  {
                    PAYMENT_OPTIONS.find(
                      (option) => option.value === saleSuccess.payment_method,
                    )?.label
                  }
                </dd>
              </div>
              {saleSuccess.payment_method === 'CASH' && (
                <>
                  <div className="flex justify-between">
                    <dt className="text-muted">Efectivo recibido</dt>
                    <dd className="tabular-nums text-foreground">
                      {formatCurrency(saleSuccess.amount_paid)}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted">Vuelto</dt>
                    <dd className="tabular-nums font-semibold text-green-700 dark:text-green-300">
                      {formatCurrency(saleSuccess.change_due)}
                    </dd>
                  </div>
                </>
              )}
              {saleSuccess.payment_method === 'CREDIT' && (
                <p className="text-xs text-muted">
                  El total quedó cargado a la cuenta por cobrar del cliente.
                </p>
              )}
            </dl>

            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={() =>
                  navigate(`/ventas/${saleSuccess.id}`, {
                    state: { autoPrint: true },
                  })
                }
                className="nx-btn nx-btn-secondary flex-1"
              >
                <Icon name="printer" size={16} />
                Ver / imprimir comprobante
              </button>
              <button
                type="button"
                onClick={startNewSale}
                className="nx-btn nx-btn-success flex-1"
              >
                <Icon name="plus" size={16} />
                Nueva venta
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

interface CartLineRowProps {
  line: CartLine;
  onChangeQuantity: (delta: number) => void;
  onSetQuantity: (raw: string) => void;
  onRemove: () => void;
}

function CartLineRow({
  line,
  onChangeQuantity,
  onSetQuantity,
  onRemove,
}: CartLineRowProps) {
  const stock = line.product.stock;
  const atMax = line.quantity >= stock;

  return (
    <li
      className={`rounded-xl border px-3 py-2 transition-colors ${
        atMax ? 'border-amber-300 bg-amber-50/50 dark:border-amber-400/30 dark:bg-amber-500/5' : 'border-line bg-surface'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">
            {line.product.name}
          </p>
          {line.product.barcode && (
            <p className="text-xs text-faint">Código: {line.product.barcode}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onRemove}
          title="Eliminar"
          aria-label="Eliminar producto"
          className="rounded-lg p-1 text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
        >
          <Icon name="trash" size={16} />
        </button>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-muted">
          {formatCurrency(line.product.sale_price)} c/u
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onChangeQuantity(-1)}
            disabled={line.quantity <= 1}
            aria-label="Disminuir cantidad"
            className="flex h-7 w-7 items-center justify-center rounded-md border border-line-strong text-base text-muted transition-colors hover:bg-surface-2 hover:text-foreground disabled:opacity-40"
          >
            −
          </button>
          <QuantityInput value={line.quantity} max={stock} onCommit={onSetQuantity} />
          <button
            type="button"
            onClick={() => onChangeQuantity(1)}
            disabled={atMax}
            aria-label="Aumentar cantidad"
            className="flex h-7 w-7 items-center justify-center rounded-md border border-line-strong text-base text-muted transition-colors hover:bg-surface-2 hover:text-foreground disabled:opacity-40"
          >
            +
          </button>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between border-t border-line pt-2">
        <span
          className={`text-xs ${
            atMax
              ? 'font-medium text-amber-700 dark:text-amber-300'
              : 'text-faint'
          }`}
        >
          {atMax ? `Máximo alcanzado · ` : ''}Stock: {stock}
        </span>
        <span className="text-sm font-bold tabular-nums text-foreground">
          {formatCurrency(Number(line.product.sale_price) * line.quantity)}
        </span>
      </div>
    </li>
  );
}

interface QuantityInputProps {
  value: number;
  max: number;
  onCommit: (raw: string) => void;
}

function QuantityInput({ value, max, onCommit }: QuantityInputProps) {
  const [draft, setDraft] = useState(String(value));
  const focused = useRef(false);

  useEffect(() => {
    if (!focused.current) setDraft(String(value));
  }, [value]);

  return (
    <input
      type="number"
      inputMode="numeric"
      min={1}
      max={max}
      value={draft}
      onFocus={(event) => {
        focused.current = true;
        event.target.select();
      }}
      onBlur={() => {
        focused.current = false;
        onCommit(draft);
        setDraft(String(value));
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          (event.target as HTMLInputElement).blur();
        }
      }}
      onChange={(event) => {
        const raw = event.target.value;
        setDraft(raw);
        if (raw !== '' && !Number.isNaN(parseInt(raw, 10))) {
          onCommit(raw);
        }
      }}
      className="h-7 w-14 rounded-md border border-line-strong bg-surface text-center text-sm tabular-nums text-foreground focus:border-primary focus:outline-none"
      aria-label="Cantidad"
    />
  );
}
