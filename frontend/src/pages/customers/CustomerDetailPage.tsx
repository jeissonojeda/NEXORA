import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage, useAsync } from '../../hooks/useAsync';
import {
  cancelReceivable,
  createReceivable,
  getCustomerStatement,
  registerPayment,
} from '../../services/receivables';
import type {
  ApiReceivableAccount,
  ReceivablePaymentPayload,
} from '../../types/customer';
import {
  paymentMethodLabel,
  receivableStatusLabel,
} from '../../types/customer';
import { formatCurrency, formatDateTime } from '../../utils/format';
import { ROUTES } from '../../routes';
import PaymentModal from '../../components/domain/PaymentModal';
import Badge from '../../components/ui/Badge';
import ConfirmDialog from '../../components/ui/ConfirmDialog';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import LoadingState from '../../components/ui/LoadingState';
import Modal from '../../components/ui/Modal';

function statusTone(status: string): 'amber' | 'green' | 'red' | 'gray' {
  if (status === 'PAID') return 'green';
  if (status === 'PARTIALLY_PAID') return 'amber';
  if (status === 'OPEN') return 'red';
  if (status === 'CANCELLED') return 'gray';
  return 'gray';
}

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const roles = user?.roles.map((role) => role.name) ?? [];
  const canPay =
    roles.some((role) => ['ADMIN', 'CASHIER'].includes(role)) ?? false;
  const canCreateReceivable = roles.includes('ADMIN');
  const canCancel = roles.includes('ADMIN');

  const statementState = useAsync(
    () => getCustomerStatement(id as string),
    [id],
  );

  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Nueva cuenta por cobrar
  const [newOpen, setNewOpen] = useState(false);
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // Registro de pago
  const [payingAccount, setPayingAccount] = useState<ApiReceivableAccount | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  // Anulación
  const [cancellingAccount, setCancellingAccount] =
    useState<ApiReceivableAccount | null>(null);

  const reload = useCallback(async () => {
    await statementState.reload();
  }, [statementState]);

  async function handleCreateReceivable(event: React.FormEvent) {
    event.preventDefault();
    const errors: Record<string, string> = {};
    const value = Number(amount);
    if (!amount.trim() || Number.isNaN(value) || value <= 0) {
      errors.amount = 'Ingrese un monto mayor que cero';
    }
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;
    setBusy(true);
    setActionError(null);
    try {
      await createReceivable({
        customer_id: id as string,
        original_amount: value.toFixed(2),
        description: description.trim() || null,
        due_date: dueDate || null,
      });
      setNewOpen(false);
      setAmount('');
      setDescription('');
      setDueDate('');
      await reload();
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePayment(payload: ReceivablePaymentPayload) {
    if (!payingAccount) return;
    setBusy(true);
    setPaymentError(null);
    try {
      await registerPayment(payingAccount.id, payload);
      setPayingAccount(null);
      await reload();
    } catch (err) {
      setPaymentError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmCancel() {
    if (!cancellingAccount) return;
    setBusy(true);
    setActionError(null);
    try {
      await cancelReceivable(cancellingAccount.id);
      setCancellingAccount(null);
      await reload();
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (statementState.error && !statementState.data) {
    return (
      <div className="space-y-4">
        <Link
          to={ROUTES.CUSTOMERS}
          className="text-sm font-medium text-primary hover:underline"
        >
          ← Volver a clientes
        </Link>
        <ErrorAlert message={statementState.error} />
      </div>
    );
  }

  const statement = statementState.data;
  const customer = statement?.customer;
  const credit = statement?.credit;
  const summary = statement?.summary;

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to={ROUTES.CUSTOMERS}
            className="text-sm font-medium text-primary hover:underline"
          >
            ← Clientes
          </Link>
          <h2 className="mt-1 text-xl font-bold text-foreground">
            {customer ? customer.name : 'Cargando…'}
          </h2>
          {customer && (
            <p className="mt-0.5 text-sm text-muted">
              {customer.identification ? `${customer.identification} · ` : ''}
              {customer.phone ?? 'sin teléfono'}
              {customer.email ? ` · ${customer.email}` : ''}
            </p>
          )}
        </div>
        {canCreateReceivable && customer?.is_active && (
          <button
            type="button"
            onClick={() => {
              setAmount('');
              setDescription('');
              setDueDate('');
              setFormErrors({});
              setNewOpen(true);
            }}
            className="nx-btn nx-btn-primary"
          >
            + Nueva cuenta por cobrar
          </button>
        )}
      </div>

      {customer && !customer.is_active && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200">
          Cliente inactivo: no puede usarse en ventas futuras; su historial se
          conserva.
        </p>
      )}

      {/* Resumen de crédito */}
      {credit && summary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <div className="nx-card p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Crédito
            </p>
            <p className="mt-1 text-lg font-semibold">
              {credit.credit_enabled ? (
                <Badge tone="blue">Habilitado</Badge>
              ) : (
                <Badge tone="gray">Contado</Badge>
              )}
            </p>
          </div>
          <div className="nx-card p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Límite
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-foreground">
              {formatCurrency(credit.credit_limit)}
            </p>
          </div>
          <div className="nx-card p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Saldo actual
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-foreground">
              {formatCurrency(credit.current_balance)}
            </p>
          </div>
          <div className="nx-card p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Disponible
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-green-600 dark:text-green-400">
              {formatCurrency(credit.credit_available)}
            </p>
          </div>
          <div className="nx-card p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Deuda vigente
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-foreground">
              {formatCurrency(summary.total_balance)}
            </p>
          </div>
        </div>
      )}

      {actionError && <ErrorAlert message={actionError} />}

      {/* Cuentas por cobrar */}
      <div className="nx-card overflow-hidden">
        <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-foreground">
          Cuentas por cobrar
          {summary &&
            ` (${summary.open_count} pendientes · ${summary.partially_paid_count} abonadas · ${summary.paid_count} pagadas · ${summary.cancelled_count} anuladas)`}
        </h3>
        {statementState.loading ? (
          <div className="p-5">
            <LoadingState rows={5} />
          </div>
        ) : (statement?.accounts.total ?? 0) === 0 ? (
          <EmptyState
            title="Sin cuentas por cobrar"
            hint="Registra una cuenta por cobrar para este cliente."
            icon="banknote"
          />
        ) : (
          <div className="overflow-x-auto">
          <table className="nx-table">
            <thead>
              <tr>
                <th className="text-left">Fecha</th>
                <th className="hidden text-left md:table-cell">Descripción</th>
                <th className="hidden text-left sm:table-cell">Vencimiento</th>
                <th className="text-right">Original</th>
                <th className="hidden text-right sm:table-cell">Abonado</th>
                <th className="text-right">Saldo</th>
                <th className="text-left">Estado</th>
                <th className="text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {statement?.accounts.items.map((account) => (
                <tr key={account.id} className="hover:bg-surface-2">
                  <td className="text-muted">
                    {formatDateTime(account.created_at)}
                  </td>
                  <td className="hidden max-w-[240px] truncate text-muted md:table-cell">
                    {account.description || '—'}
                  </td>
                  <td className="hidden text-muted sm:table-cell">
                    {account.due_date ?? '—'}
                  </td>
                  <td className="text-right tabular-nums text-muted">
                    {formatCurrency(account.original_amount)}
                  </td>
                  <td className="hidden text-right tabular-nums text-muted sm:table-cell">
                    {formatCurrency(account.paid_amount)}
                  </td>
                  <td className="text-right font-semibold tabular-nums text-foreground">
                    {formatCurrency(account.balance)}
                  </td>
                  <td>
                    <Badge tone={statusTone(account.status)}>
                      {receivableStatusLabel(account.status)}
                    </Badge>
                  </td>
                  <td className="whitespace-nowrap text-right">
                    {canPay &&
                      (account.status === 'OPEN' ||
                        account.status === 'PARTIALLY_PAID') && (
                        <button
                          type="button"
                          onClick={() => {
                            setPaymentError(null);
                            setPayingAccount(account);
                          }}
                          className="mr-2 text-sm font-medium text-primary hover:underline"
                        >
                          Abonar
                        </button>
                      )}
                    {canCancel &&
                      (account.status === 'OPEN' ||
                        account.status === 'PARTIALLY_PAID') && (
                        <button
                          type="button"
                          onClick={() => setCancellingAccount(account)}
                          className="text-sm font-medium text-red-600 hover:underline dark:text-red-400"
                        >
                          Anular
                        </button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* Historial de pagos */}
      <div className="nx-card overflow-hidden">
        <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-foreground">
          Historial de pagos
        </h3>
        {(statement?.payments.total ?? 0) === 0 ? (
          <EmptyState
            title="Sin pagos registrados"
            hint="Los abonos a este cliente aparecerán aquí."
            icon="check-circle"
          />
        ) : (
          <div className="overflow-x-auto">
          <table className="nx-table">
            <thead>
              <tr>
                <th className="text-left">Fecha</th>
                <th className="text-right">Monto</th>
                <th className="text-left">Método</th>
                <th className="hidden text-left md:table-cell">Referencia</th>
                <th className="hidden text-left md:table-cell">Registrado por</th>
              </tr>
            </thead>
            <tbody>
              {statement?.payments.items.map((payment) => (
                <tr key={payment.id} className="hover:bg-surface-2">
                  <td className="text-muted">
                    {formatDateTime(payment.created_at)}
                  </td>
                  <td className="text-right font-semibold tabular-nums text-green-600 dark:text-green-400">
                    +{formatCurrency(payment.amount)}
                  </td>
                  <td className="text-muted">
                    {paymentMethodLabel(payment.payment_method)}
                  </td>
                  <td className="hidden text-muted md:table-cell">
                    {payment.reference || '—'}
                  </td>
                  <td className="hidden text-muted md:table-cell">
                    {payment.created_by_username ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* Modal nueva cuenta */}
      <Modal
        open={newOpen}
        title="Nueva cuenta por cobrar"
        onClose={() => setNewOpen(false)}
      >
        <form onSubmit={handleCreateReceivable} className="space-y-4">
          <div>
            <label htmlFor="receivable-amount" className="nx-label">
              Monto <span className="text-red-500">*</span>
            </label>
            <input
              id="receivable-amount"
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              className="nx-input"
            />
            {formErrors.amount && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">{formErrors.amount}</p>
            )}
          </div>
          <div>
            <label htmlFor="receivable-due" className="nx-label">
              Fecha de vencimiento
            </label>
            <input
              id="receivable-due"
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="nx-input"
            />
          </div>
          <div>
            <label htmlFor="receivable-desc" className="nx-label">
              Descripción
            </label>
            <textarea
              id="receivable-desc"
              rows={2}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="nx-textarea"
              placeholder="Ej. Mercadería fiada del sábado"
            />
          </div>
          {actionError && (
            <p
              role="alert"
              className="rounded-lg border border-red-300 bg-red-100/60 px-3 py-2 text-sm text-red-800 dark:bg-red-500/10 dark:text-red-300"
            >
              {actionError}
            </p>
          )}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={busy}
              className="nx-btn nx-btn-primary"
            >
              {busy ? 'Creando…' : 'Crear cuenta'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal de pago */}
      <Modal
        open={payingAccount !== null}
        title={`Registrar abono${customer ? ` — ${customer.name}` : ''}`}
        onClose={() => setPayingAccount(null)}
      >
        {payingAccount && (
          <PaymentModal
            account={payingAccount}
            busy={busy}
            error={paymentError}
            submitLabel="Registrar pago"
            onSubmit={(payload) => void handlePayment(payload)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={cancellingAccount !== null}
        title="Anular cuenta por cobrar"
        message={`¿Anular la cuenta con saldo de ${formatCurrency(
          cancellingAccount?.balance ?? '0',
        )}? El saldo saldrá del estado del cliente; los abonos ya registrados se conservan como historial y la operación no puede deshacerse.`}
        confirmLabel="Anular cuenta"
        destructive
        busy={busy}
        onConfirm={() => void confirmCancel()}
        onCancel={() => setCancellingAccount(null)}
      />

      {/* Botón inferior de regreso */}
      <div>
        <button
          type="button"
          onClick={() => navigate(ROUTES.CUSTOMERS)}
          className="text-sm font-medium text-muted hover:text-foreground hover:underline"
        >
          ← Volver al listado
        </button>
      </div>
    </div>
  );
}