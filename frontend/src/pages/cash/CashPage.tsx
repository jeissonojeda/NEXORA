import { useState, type FormEvent } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useAsync, extractErrorMessage } from '../../hooks/useAsync';
import {
  closeRegister,
  createManualMovement,
  getCurrentRegister,
  listMovements,
  listRegisters,
  openRegister,
} from '../../services/cash';
import type { CashMovementType, RegisterStatus } from '../../types/cash';
import {
  cashPaymentMethodLabel,
  movementTypeLabel,
  registerStatusLabel,
} from '../../types/cash';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import LoadingState from '../../components/ui/LoadingState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import { formatCurrency, formatDateTime } from '../../utils/format';

const PAGE_SIZE = 10;

const REGISTER_STATUS_TONE: Record<RegisterStatus, 'green' | 'gray' | 'red'> = {
  OPEN: 'green',
  CLOSED: 'gray',
  CANCELLED: 'red',
};

const MOVEMENT_TYPE_TONE: Record<CashMovementType, 'blue' | 'green' | 'red' | 'amber'> = {
  OPENING: 'blue',
  SALE: 'green',
  RECEIVABLE_PAYMENT: 'green',
  CASH_IN: 'green',
  CASH_OUT: 'red',
  ADJUSTMENT: 'amber',
};

type ManualKind = 'CASH_IN' | 'CASH_OUT';

function SummaryCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className={`nx-card p-4 ${accent ? 'nx-brand-gradient text-white' : ''}`}>
      <p className={`text-xs font-medium uppercase tracking-wide ${accent ? 'text-white/80' : 'text-muted'}`}>
        {label}
      </p>
      <p className={`mt-1 text-lg font-bold tabular-nums ${accent ? '' : 'text-foreground'}`}>
        {value}
      </p>
    </div>
  );
}

export default function CashPage() {
  const { user } = useAuth();
  const canOperate =
    user?.roles.some((role) => ['ADMIN', 'CASHIER'].includes(role.name)) ??
    false;

  const [openModal, setOpenModal] = useState(false);
  const [openingAmount, setOpeningAmount] = useState('');
  const [openingNotes, setOpeningNotes] = useState('');
  const [manualModal, setManualModal] = useState<ManualKind | null>(null);
  const [manualAmount, setManualAmount] = useState('');
  const [manualDescription, setManualDescription] = useState('');
  const [closeModal, setCloseModal] = useState(false);
  const [countedAmount, setCountedAmount] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const registerState = useAsync(() => getCurrentRegister(), []);
  const current = registerState.data;
  const [page, setPage] = useState(1);

  const movementsState = useAsync(
    () =>
      current
        ? listMovements(current.id, {
            skip: (page - 1) * PAGE_SIZE,
            limit: PAGE_SIZE,
          })
        : Promise.resolve({ items: [], total: 0 }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [current?.id, page],
  );

  const historyState = useAsync(
    () => listRegisters({ limit: 20 }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [current?.id],
  );

  if (!canOperate) {
    return (
      <div className="space-y-4">
        <PageHeader title="Caja" subtitle="Operación del turno y control de efectivo." />
        <ErrorAlert message="No tienes permisos para operar la caja." />
      </div>
    );
  }

  async function handleOpen(event: FormEvent) {
    event.preventDefault();
    setActionError(null);
    setSaving(true);
    try {
      await openRegister({
        opening_amount: Number(openingAmount || '0'),
        notes: openingNotes || null,
      });
      setOpenModal(false);
      setOpeningAmount('');
      setOpeningNotes('');
      await registerState.reload();
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleManualMovement(event: FormEvent) {
    event.preventDefault();
    if (!manualModal) return;
    setActionError(null);
    setSaving(true);
    try {
      await createManualMovement({
        movement_type: manualModal,
        amount: Number(manualAmount),
        description: manualDescription,
      });
      setManualModal(null);
      setManualAmount('');
      setManualDescription('');
      await Promise.all([registerState.reload(), movementsState.reload()]);
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleClose(event: FormEvent) {
    event.preventDefault();
    if (!current) return;
    setActionError(null);
    setSaving(true);
    try {
      await closeRegister(current.id, Number(countedAmount || '0'));
      setCloseModal(false);
      setCountedAmount('');
      await Promise.all([
        registerState.reload(),
        historyState.reload(),
        movementsState.reload(),
      ]);
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  function differencePreview(): number | null {
    if (!current || countedAmount === '') return null;
    return Number(countedAmount) - Number(current.summary.expected_cash);
  }

  const preview = differencePreview();

  return (
    <div className="animate-fade-in space-y-4">
      <PageHeader
        title="Caja"
        subtitle="Operación del turno y control de efectivo esperado."
        actions={
          current ? (
            <Badge tone={REGISTER_STATUS_TONE[current.status]}>
              {registerStatusLabel(current.status)}
            </Badge>
          ) : (
            <button
              type="button"
              onClick={() => setOpenModal(true)}
              className="nx-btn nx-btn-success"
            >
              Abrir caja
            </button>
          )
        }
      />

      {actionError && <ErrorAlert message={actionError} />}
      {registerState.error && (
        <ErrorAlert message={registerState.error} />
      )}

      {!registerState.loading && !current && (
        <div className="nx-card p-6">
          <EmptyState
            title="No hay caja abierta"
            hint="Abre la caja con un monto inicial para comenzar el turno."
          />
        </div>
      )}

      {current && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <SummaryCard
              label="Monto inicial"
              value={formatCurrency(current.opening_amount)}
            />
            <SummaryCard
              label="Ventas en efectivo"
              value={formatCurrency(current.summary.cash_sales_total)}
            />
            <SummaryCard
              label="Abonos recibidos (efectivo)"
              value={formatCurrency(
                current.summary.cash_receivable_payments_total,
              )}
            />
            <SummaryCard
              label="Ingresos manuales"
              value={formatCurrency(current.summary.cash_in_total)}
            />
            <SummaryCard
              label="Egresos"
              value={formatCurrency(current.summary.cash_out_total)}
            />
            <SummaryCard
              label="Tarjeta / Transferencia"
              value={`${formatCurrency(current.summary.card_sales_total)} · ${formatCurrency(
                Number(current.summary.transfer_sales_total) +
                  Number(current.summary.card_receivable_payments_total) +
                  Number(current.summary.transfer_receivable_payments_total),
              )}`}
            />
            <SummaryCard label="Movimientos" value={String(current.summary.movement_count)} />
            <SummaryCard
              label="Efectivo esperado"
              value={formatCurrency(current.summary.expected_cash)}
              accent
            />
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                setManualModal('CASH_IN');
                setManualAmount('');
                setManualDescription('');
              }}
              className="nx-btn nx-btn-primary"
            >
              + Registrar ingreso
            </button>
            <button
              type="button"
              onClick={() => {
                setManualModal('CASH_OUT');
                setManualAmount('');
                setManualDescription('');
              }}
              className="nx-btn nx-btn-secondary text-amber-600 dark:text-amber-400"
            >
              − Registrar egreso
            </button>
            <button
              type="button"
              onClick={() => {
                setCountedAmount(current.summary.expected_cash);
                setCloseModal(true);
              }}
              className="nx-btn nx-btn-secondary ml-auto"
            >
              Cerrar caja
            </button>
          </div>

          <div className="nx-card overflow-hidden">
            <div className="border-b border-line px-4 py-3 text-sm font-semibold text-foreground">
              Movimientos del turno
            </div>
            {movementsState.loading ? (
              <div className="p-5">
                <LoadingState rows={5} />
              </div>
            ) : movementsState.data?.total === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="Sin movimientos"
                  hint="Aún no hay movimientos registrados en este turno."
                />
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                <table className="nx-table">
                  <thead>
                    <tr>
                      <th className="text-left">Fecha</th>
                      <th className="text-left">Tipo</th>
                      <th className="hidden text-left md:table-cell">Medio</th>
                      <th className="text-left">Descripción</th>
                      <th className="text-right">Monto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {movementsState.data?.items.map((movement) => {
                      const inflow =
                        movement.movement_type === 'CASH_OUT'
                          ? false
                          : movement.payment_method === null ||
                            movement.payment_method === 'CASH';
                      const electronic =
                        movement.payment_method === 'CARD' ||
                        movement.payment_method === 'TRANSFER';
                      return (
                        <tr key={movement.id} className="hover:bg-surface-2">
                          <td className="whitespace-nowrap text-muted">
                            {formatDateTime(movement.created_at)}
                          </td>
                          <td className="text-muted">
                            <Badge tone={MOVEMENT_TYPE_TONE[movement.movement_type]}>
                              {movementTypeLabel(movement.movement_type)}
                            </Badge>
                          </td>
                          <td className="hidden text-muted md:table-cell">
                            {cashPaymentMethodLabel(movement.payment_method)}
                          </td>
                          <td className="max-w-xs truncate text-muted">
                            {movement.description}
                          </td>
                          <td
                            className={`text-right font-medium tabular-nums ${
                              electronic
                                ? 'text-faint'
                                : inflow
                                  ? 'text-green-600 dark:text-green-400'
                                  : 'text-red-600 dark:text-red-400'
                            }`}
                          >
                            {movement.movement_type === 'CASH_OUT' ? '−' : ''}
                            {formatCurrency(movement.amount)}
                            {electronic && ' (no efectivo)'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
                <div className="border-t border-line px-4 py-3">
                  <Pagination
                    page={page}
                    pageSize={PAGE_SIZE}
                    total={movementsState.data?.total ?? 0}
                    onChange={setPage}
                  />
                </div>
              </>
            )}
          </div>
        </>
      )}

      {/* Historial de cajas */}
      <div className="nx-card overflow-hidden">
        <div className="border-b border-line px-4 py-3 text-sm font-semibold text-foreground">
          Historial de cajas
        </div>
        {historyState.loading ? (
          <div className="p-5">
            <LoadingState rows={5} />
          </div>
        ) : historyState.data?.total === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Sin cajas anteriores"
              hint="Aquí aparecerá cada turno cerrado con su diferencia."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="nx-table">
            <thead>
              <tr>
                <th className="text-left">Cajero</th>
                <th className="text-left">Apertura</th>
                <th className="hidden text-left md:table-cell">Cierre</th>
                <th className="text-left">Estado</th>
                <th className="text-right">Inicial</th>
                <th className="text-right">Esperado</th>
                <th className="text-right">Contado</th>
                <th className="text-right">Diferencia</th>
              </tr>
            </thead>
            <tbody>
              {historyState.data?.items.map((item) => (
                <tr key={item.id} className="hover:bg-surface-2">
                  <td className="text-foreground">{item.user_username}</td>
                  <td className="whitespace-nowrap text-muted">
                    {formatDateTime(item.opened_at)}
                  </td>
                  <td className="hidden whitespace-nowrap text-muted md:table-cell">
                    {item.closed_at ? formatDateTime(item.closed_at) : '—'}
                  </td>
                  <td>
                    <Badge tone={REGISTER_STATUS_TONE[item.status]}>
                      {registerStatusLabel(item.status)}
                    </Badge>
                  </td>
                  <td className="text-right text-muted">
                    {formatCurrency(item.opening_amount)}
                  </td>
                  <td className="text-right text-muted">
                    {item.expected_amount ? formatCurrency(item.expected_amount) : '—'}
                  </td>
                  <td className="text-right text-muted">
                    {item.counted_amount ? formatCurrency(item.counted_amount) : '—'}
                  </td>
                  <td
                    className={`text-right font-semibold tabular-nums ${
                      item.difference == null
                        ? 'text-faint'
                        : Number(item.difference) === 0
                          ? 'text-foreground'
                          : Number(item.difference) > 0
                            ? 'text-primary'
                            : 'text-red-600 dark:text-red-400'
                    }`}
                  >
                    {item.difference == null ? '—' : formatCurrency(item.difference)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* Modal apertura */}
      <Modal open={openModal} title="Abrir caja" onClose={() => setOpenModal(false)}>
        <form onSubmit={handleOpen} className="space-y-4">
          <div>
            <label htmlFor="opening-amount" className="nx-label">
              Monto inicial
            </label>
            <input
              id="opening-amount"
              type="number"
              min="0"
              step="0.01"
              required
              value={openingAmount}
              onChange={(e) => setOpeningAmount(e.target.value)}
              className="nx-input"
              placeholder="0.00"
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="opening-notes" className="nx-label">
              Notas (opcional)
            </label>
            <textarea
              id="opening-notes"
              rows={2}
              value={openingNotes}
              onChange={(e) => setOpeningNotes(e.target.value)}
              className="nx-textarea"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpenModal(false)}
              className="nx-btn nx-btn-secondary"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="nx-btn nx-btn-success"
            >
              {saving ? 'Abriendo…' : 'Abrir caja'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal ingreso/egreso manual */}
      <Modal
        open={manualModal !== null}
        title={
          manualModal === 'CASH_IN'
            ? 'Registrar ingreso de efectivo'
            : 'Registrar egreso de efectivo'
        }
        onClose={() => setManualModal(null)}
      >
        <form onSubmit={handleManualMovement} className="space-y-4">
          <div>
            <label htmlFor="manual-amount" className="nx-label">
              Monto
            </label>
            <input
              id="manual-amount"
              type="number"
              min="0.01"
              step="0.01"
              required
              value={manualAmount}
              onChange={(e) => setManualAmount(e.target.value)}
              className="nx-input"
              placeholder="0.00"
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="manual-description" className="nx-label">
              Motivo (obligatorio)
            </label>
            <input
              id="manual-description"
              type="text"
              required
              minLength={3}
              value={manualDescription}
              onChange={(e) => setManualDescription(e.target.value)}
              className="nx-input"
              placeholder={
                manualModal === 'CASH_IN'
                  ? 'Ej.: Fondo adicional, cobro pendiente…'
                  : 'Ej.: Gasto menor, retiro…'
              }
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setManualModal(null)}
              className="nx-btn nx-btn-secondary"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className={`nx-btn ${
                manualModal === 'CASH_IN'
                  ? 'nx-btn-primary'
                  : 'nx-btn-secondary text-amber-600 dark:text-amber-400'
              }`}
            >
              {saving ? 'Guardando…' : 'Registrar'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal cierre */}
      <Modal open={closeModal} title="Cerrar caja" onClose={() => setCloseModal(false)}>
        {current && (
          <form onSubmit={handleClose} className="space-y-4">
            <div className="rounded-xl border border-line bg-surface px-3 py-3 text-sm">
              <div className="flex justify-between py-1">
                <span className="text-muted">Efectivo esperado</span>
                <span className="font-bold text-foreground">
                  {formatCurrency(current.summary.expected_cash)}
                </span>
              </div>
            </div>
            <div>
              <label htmlFor="counted-amount" className="nx-label">
                Efectivo contado
              </label>
              <input
                id="counted-amount"
                type="number"
                min="0"
                step="0.01"
                required
                value={countedAmount}
                onChange={(e) => setCountedAmount(e.target.value)}
                className="nx-input"
                placeholder="0.00"
                autoFocus
              />
            </div>
            {preview !== null && (
              <div
                className={`rounded-lg p-3 text-sm font-medium ${
                  preview === 0
                    ? 'bg-green-50 text-green-800 dark:bg-green-500/10 dark:text-green-300'
                    : preview > 0
                      ? 'bg-blue-50 text-blue-800 dark:bg-blue-500/10 dark:text-blue-300'
                      : 'bg-red-50 text-red-800 dark:bg-red-500/10 dark:text-red-300'
                }`}
                role="alert"
              >
                {preview === 0
                  ? 'Cuadra perfecto: sin diferencia.'
                  : preview > 0
                    ? `Sobrante de ${formatCurrency(String(preview))}`
                    : `Faltante de ${formatCurrency(String(Math.abs(preview)))}`}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCloseModal(false)}
                className="nx-btn nx-btn-secondary"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving}
                className="nx-btn nx-btn-danger"
              >
                {saving ? 'Cerrando…' : 'Confirmar cierre'}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}