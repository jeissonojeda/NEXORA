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
import type { RegisterStatus } from '../../types/cash';
import {
  cashPaymentMethodLabel,
  movementTypeLabel,
  registerStatusLabel,
} from '../../types/cash';
import Badge from '../../components/ui/Badge';
import EmptyState from '../../components/ui/EmptyState';
import ErrorAlert from '../../components/ui/ErrorAlert';
import Modal from '../../components/ui/Modal';
import Pagination from '../../components/ui/Pagination';
import { formatCurrency, formatDateTime } from '../../utils/format';

const inputClass =
  'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none';

const PAGE_SIZE = 10;

const REGISTER_STATUS_TONE: Record<RegisterStatus, 'green' | 'gray' | 'red'> = {
  OPEN: 'green',
  CLOSED: 'gray',
  CANCELLED: 'red',
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
    <div
      className={`rounded-lg p-4 shadow ${
        accent ? 'bg-blue-600 text-white' : 'bg-white'
      }`}
    >
      <p
        className={`text-xs font-medium uppercase tracking-wide ${
          accent ? 'text-blue-100' : 'text-gray-500'
        }`}
      >
        {label}
      </p>
      <p
        className={`mt-1 text-lg font-bold ${accent ? '' : 'text-gray-900'}`}
      >
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
        <h2 className="text-xl font-bold text-gray-900">Caja</h2>
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-gray-900">Caja</h2>
        {current ? (
          <Badge tone={REGISTER_STATUS_TONE[current.status]}>
            {registerStatusLabel(current.status)}
          </Badge>
        ) : (
          <button
            type="button"
            onClick={() => setOpenModal(true)}
            className="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700"
          >
            Abrir caja
          </button>
        )}
      </div>

      {actionError && <ErrorAlert message={actionError} />}
      {registerState.error && (
        <ErrorAlert message={registerState.error} />
      )}

      {!registerState.loading && !current && (
        <div className="rounded-lg bg-white p-6 shadow">
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
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
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
              className="rounded-md bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700"
            >
              − Registrar egreso
            </button>
            <button
              type="button"
              onClick={() => {
                setCountedAmount(current.summary.expected_cash);
                setCloseModal(true);
              }}
              className="ml-auto rounded-md bg-gray-800 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-900"
            >
              Cerrar caja
            </button>
          </div>

          <div className="overflow-hidden rounded-lg bg-white shadow">
            <div className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
              Movimientos del turno
            </div>
            {movementsState.loading ? (
              <p className="px-4 py-10 text-center text-sm text-gray-500">
                Cargando movimientos…
              </p>
            ) : movementsState.data?.total === 0 ? (
              <EmptyState
                title="Sin movimientos"
                hint="Aún no hay movimientos registrados en este turno."
              />
            ) : (
              <>
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    <tr>
                      <th className="px-4 py-3 text-left font-semibold text-gray-600">Fecha</th>
                      <th className="px-4 py-3 text-left font-semibold text-gray-600">Tipo</th>
                      <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">Medio</th>
                      <th className="px-4 py-3 text-left font-semibold text-gray-600">Descripción</th>
                      <th className="px-4 py-3 text-right font-semibold text-gray-600">Monto</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
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
                        <tr key={movement.id} className="hover:bg-gray-50">
                          <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                            {formatDateTime(movement.created_at)}
                          </td>
                          <td className="px-4 py-3 text-gray-800">
                            {movementTypeLabel(movement.movement_type)}
                          </td>
                          <td className="hidden px-4 py-3 text-gray-600 md:table-cell">
                            {cashPaymentMethodLabel(movement.payment_method)}
                          </td>
                          <td className="max-w-xs truncate px-4 py-3 text-gray-600">
                            {movement.description}
                          </td>
                          <td
                            className={`px-4 py-3 text-right font-medium ${
                              electronic
                                ? 'text-gray-500'
                                : inflow
                                  ? 'text-green-700'
                                  : 'text-red-700'
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
                <Pagination
                  page={page}
                  pageSize={PAGE_SIZE}
                  total={movementsState.data?.total ?? 0}
                  onChange={setPage}
                />
              </>
            )}
          </div>
        </>
      )}

      {/* Historial de cajas */}
      <div className="overflow-hidden rounded-lg bg-white shadow">
        <div className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
          Historial de cajas
        </div>
        {historyState.loading ? (
          <p className="px-4 py-10 text-center text-sm text-gray-500">
            Cargando historial…
          </p>
        ) : historyState.data?.total === 0 ? (
          <EmptyState
            title="Sin cajas anteriores"
            hint="Aquí aparecerá cada turno cerrado con su diferencia."
          />
        ) : (
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Cajero</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Apertura</th>
                <th className="hidden px-4 py-3 text-left font-semibold text-gray-600 md:table-cell">Cierre</th>
                <th className="px-4 py-3 text-left font-semibold text-gray-600">Estado</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Inicial</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Esperado</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Contado</th>
                <th className="px-4 py-3 text-right font-semibold text-gray-600">Diferencia</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {historyState.data?.items.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-800">{item.user_username}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                    {formatDateTime(item.opened_at)}
                  </td>
                  <td className="hidden whitespace-nowrap px-4 py-3 text-gray-600 md:table-cell">
                    {item.closed_at ? formatDateTime(item.closed_at) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={REGISTER_STATUS_TONE[item.status]}>
                      {registerStatusLabel(item.status)}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {formatCurrency(item.opening_amount)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {item.expected_amount ? formatCurrency(item.expected_amount) : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">
                    {item.counted_amount ? formatCurrency(item.counted_amount) : '—'}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-semibold ${
                      item.difference == null
                        ? 'text-gray-400'
                        : Number(item.difference) === 0
                          ? 'text-gray-700'
                          : Number(item.difference) > 0
                            ? 'text-blue-700'
                            : 'text-red-700'
                    }`}
                  >
                    {item.difference == null ? '—' : formatCurrency(item.difference)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal apertura */}
      <Modal open={openModal} title="Abrir caja" onClose={() => setOpenModal(false)}>
        <form onSubmit={handleOpen} className="space-y-4">
          <div>
            <label htmlFor="opening-amount" className="block text-xs font-medium text-gray-500">
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
              className={`mt-1 ${inputClass}`}
              placeholder="0.00"
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="opening-notes" className="block text-xs font-medium text-gray-500">
              Notas (opcional)
            </label>
            <textarea
              id="opening-notes"
              rows={2}
              value={openingNotes}
              onChange={(e) => setOpeningNotes(e.target.value)}
              className={`mt-1 ${inputClass}`}
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setOpenModal(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
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
            <label htmlFor="manual-amount" className="block text-xs font-medium text-gray-500">
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
              className={`mt-1 ${inputClass}`}
              placeholder="0.00"
              autoFocus
            />
          </div>
          <div>
            <label htmlFor="manual-description" className="block text-xs font-medium text-gray-500">
              Motivo (obligatorio)
            </label>
            <input
              id="manual-description"
              type="text"
              required
              minLength={3}
              value={manualDescription}
              onChange={(e) => setManualDescription(e.target.value)}
              className={`mt-1 ${inputClass}`}
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
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className={`rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
                manualModal === 'CASH_IN'
                  ? 'bg-blue-600 hover:bg-blue-700'
                  : 'bg-amber-600 hover:bg-amber-700'
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
            <div className="rounded-md bg-gray-50 p-3 text-sm">
              <div className="flex justify-between py-1">
                <span className="text-gray-500">Efectivo esperado</span>
                <span className="font-bold text-gray-900">
                  {formatCurrency(current.summary.expected_cash)}
                </span>
              </div>
            </div>
            <div>
              <label htmlFor="counted-amount" className="block text-xs font-medium text-gray-500">
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
                className={`mt-1 ${inputClass}`}
                placeholder="0.00"
                autoFocus
              />
            </div>
            {preview !== null && (
              <div
                className={`rounded-md p-3 text-sm font-medium ${
                  preview === 0
                    ? 'bg-green-50 text-green-800'
                    : preview > 0
                      ? 'bg-blue-50 text-blue-800'
                      : 'bg-red-50 text-red-800'
                }`}
                role="alert"
              >
                {preview === 0
                  ? 'Cuadra perfecto: sin diferencia.'
                  : preview > 0
                    ? `⚠ Sobrante de ${formatCurrency(String(preview))}`
                    : `⚠ Faltante de ${formatCurrency(String(Math.abs(preview)))}`}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCloseModal(false)}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-gray-800 px-4 py-2 text-sm font-semibold text-white hover:bg-gray-900 disabled:opacity-50"
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
