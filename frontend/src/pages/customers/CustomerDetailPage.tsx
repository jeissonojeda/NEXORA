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
import ErrorAlert from '../../components/ui/ErrorAlert';
import Modal from '../../components/ui/Modal';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

function statusTone(status: string): 'amber' | 'blue' | 'green' | 'red' {
  if (status === 'PAID') return 'green';
  if (status === 'PARTIALLY_PAID') return 'blue';
  if (status === 'CANCELLED') return 'red';
  return 'amber';
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
          className="text-sm font-medium text-blue-600 hover:text-blue-800"
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to={ROUTES.CUSTOMERS}
            className="text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            ← Clientes
          </Link>
          <h2 className="mt-1 text-xl font-bold text-gray-900">
            {customer ? customer.name : 'Cargando…'}
          </h2>
          {customer && (
            <p className="mt-0.5 text-sm text-gray-500">
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
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            + Nueva cuenta por cobrar
          </button>
        )}
      </div>

      {customer && !customer.is_active && (
        <p className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
          Cliente inactivo: no puede usarse en ventas futuras; su historial se
          conserva.
        </p>
      )}

      {/* Resumen de crédito */}
      {credit && summary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
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
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Límite
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-gray-900">
              {formatCurrency(credit.credit_limit)}
            </p>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Saldo actual
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-gray-900">
              {formatCurrency(credit.current_balance)}
            </p>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Disponible
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-green-700">
              {formatCurrency(credit.credit_available)}
            </p>
          </div>
          <div className="rounded-lg bg-white p-4 shadow">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              Deuda vigente
            </p>
            <p className="mt-1 tabular-nums text-lg font-semibold text-gray-900">
              {formatCurrency(summary.total_balance)}
            </p>
          </div>
        </div>
      )}

      {actionError && <ErrorAlert message={actionError} />}

      {/* Cuentas por cobrar */}
      <div className="overflow-hidden rounded-lg bg-white shadow">
        <h3 className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
          Cuentas por cobrar
          {summary &&
            ` (${summary.open_count} pendientes · ${summary.partially_paid_count} abonadas · ${summary.paid_count} pagadas · ${summary.cancelled_count} anuladas)`}
        </h3>
        {statementState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">Cargando…</p>
        ) : (statement?.accounts.total ?? 0) === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">
            Sin cuentas por cobrar registradas.
          </p>
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Fecha</th>
                <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                  Descripción
                </th>
                <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 sm:table-cell">
                  Vencimiento
                </th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Original</th>
                <th className="hidden px-4 py-3 text-right font-semibold text-gray-600 sm:table-cell">
                  Abonado
                </th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Saldo</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {statement?.accounts.items.map((account) => (
                <tr key={account.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-600">
                    {formatDateTime(account.created_at)}
                  </td>
                  <td className="hidden max-w-[240px] truncate px-4 py-3 text-gray-600 md:table-cell">
                    {account.description || '—'}
                  </td>
                  <td className="hidden px-4 py-3 text-gray-600 sm:table-cell">
                    {account.due_date ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-800">
                    {formatCurrency(account.original_amount)}
                  </td>
                  <td className="hidden px-4 py-3 text-right tabular-nums text-gray-800 sm:table-cell">
                    {formatCurrency(account.paid_amount)}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-gray-900">
                    {formatCurrency(account.balance)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(account.status)}>
                      {receivableStatusLabel(account.status)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {canPay &&
                      (account.status === 'OPEN' ||
                        account.status === 'PARTIALLY_PAID') && (
                        <button
                          type="button"
                          onClick={() => {
                            setPaymentError(null);
                            setPayingAccount(account);
                          }}
                          className="mr-2 text-sm font-medium text-blue-600 hover:text-blue-800"
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
                          className="text-sm font-medium text-red-600 hover:text-red-800"
                        >
                          Anular
                        </button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Historial de pagos */}
      <div className="overflow-hidden rounded-lg bg-white shadow">
        <h3 className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
          Historial de pagos
        </h3>
        {(statement?.payments.total ?? 0) === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">
            Sin pagos registrados.
          </p>
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Fecha</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Monto</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Método</th>
                <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                  Referencia
                </th>
                <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">
                  Registrado por
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {statement?.payments.items.map((payment) => (
                <tr key={payment.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-600">
                    {formatDateTime(payment.created_at)}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums text-green-700">
                    +{formatCurrency(payment.amount)}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {paymentMethodLabel(payment.payment_method)}
                  </td>
                  <td className="hidden px-4 py-3 text-gray-600 md:table-cell">
                    {payment.reference || '—'}
                  </td>
                  <td className="hidden px-4 py-3 text-gray-600 md:table-cell">
                    {payment.created_by_username ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
            <label htmlFor="receivable-amount" className="block text-sm font-medium text-gray-700">
              Monto <span className="text-red-500">*</span>
            </label>
            <input
              id="receivable-amount"
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              className={`mt-1 ${inputClass}`}
            />
            {formErrors.amount && (
              <p className="mt-1 text-xs text-red-600">{formErrors.amount}</p>
            )}
          </div>
          <div>
            <label htmlFor="receivable-due" className="block text-sm font-medium text-gray-700">
              Fecha de vencimiento
            </label>
            <input
              id="receivable-due"
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className={`mt-1 ${inputClass}`}
            />
          </div>
          <div>
            <label htmlFor="receivable-desc" className="block text-sm font-medium text-gray-700">
              Descripción
            </label>
            <textarea
              id="receivable-desc"
              rows={2}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className={`mt-1 ${inputClass}`}
              placeholder="Ej. Mercadería fiada del sábado"
            />
          </div>
          {actionError && (
            <p
              role="alert"
              className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {actionError}
            </p>
          )}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
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
          className="text-sm font-medium text-gray-600 hover:text-gray-800"
        >
          ← Volver al listado
        </button>
      </div>
    </div>
  );
}
