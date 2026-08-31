import { useEffect, useState } from 'react';
import Modal from '../ui/Modal';
import Badge from '../ui/Badge';
import LoadingState from '../ui/LoadingState';
import ErrorAlert from '../ui/ErrorAlert';
import Icon from '../ui/Icon';
import { extractErrorMessage } from '../../hooks/useAsync';
import { previewAction, confirmAction } from '../../services/aiOperational';
import {
  AI_ACTION_LABELS,
  AI_ACTION_TYPE_LABELS,
  type AiActionProposal,
  type AiActionPreviewResponse,
} from '../../types/ai';

interface Props {
  proposal: AiActionProposal | null;
  onClose: () => void;
  onDone: () => void;
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export default function AiActionConfirmModal({ proposal, onClose, onDone }: Props) {
  const [preview, setPreview] = useState<AiActionPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!proposal) return;
    let cancelled = false;
    setLoading(true);
    setPreview(null);
    setResult(null);
    setError(null);
    previewAction(proposal.action_name, proposal.args)
      .then((p) => {
        if (!cancelled) setPreview(p);
      })
      .catch((e) => {
        if (!cancelled) setError(extractErrorMessage(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proposal]);

  if (!proposal) return null;

  const idempotencyKey =
    preview?.idempotency_key ||
    `ai:${proposal.action_name}:${Date.now()}`;

  const handleConfirm = async () => {
    setConfirming(true);
    setError(null);
    try {
      const res = await confirmAction(
        proposal.action_name,
        proposal.args,
        idempotencyKey,
      );
      setResult(
        res.replayed
          ? 'Acción ya procesada previamente (no se duplicó).'
          : `Acción confirmada (${res.status}): ${res.reference_id || 'ok'}`,
      );
      onDone();
    } catch (e) {
      setError(extractErrorMessage(e));
    } finally {
      setConfirming(false);
    }
  };

  return (
    <Modal open title="Confirmar acción de NEXORA AI" onClose={onClose} wide>
      {loading ? (
        <LoadingState rows={3} />
      ) : error && !preview ? (
        <>
          <ErrorAlert message={error} />
          <button className="nx-btn nx-btn-secondary mt-4" onClick={onClose}>
            Cerrar
          </button>
        </>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge tone="purple">
              {AI_ACTION_LABELS[proposal.action_name] || proposal.action_name}
            </Badge>
            <Badge tone="blue">
              {AI_ACTION_TYPE_LABELS[proposal.action_type] || proposal.action_type}
            </Badge>
            <span className="text-xs text-faint">
              Requiere: {proposal.permission}
            </span>
          </div>

          <div className="rounded-xl bg-surface p-4">
            <h4 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-foreground">
              <Icon name="eye" size={16} /> Resumen
            </h4>
            {preview ? (
              <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
                {Object.entries(preview.display).map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3 text-sm">
                    <dt className="capitalize text-muted">{k.replaceAll('_', ' ')}:</dt>
                    <dd className="text-right font-medium text-foreground">
                      {formatValue(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <pre className="whitespace-pre-wrap text-xs text-muted">
                {JSON.stringify(proposal.args, null, 2)}
              </pre>
            )}
          </div>

          {error && <ErrorAlert message={error} />}
          {result && (
            <div className="rounded-xl bg-green-50 p-3 text-sm text-green-800 dark:bg-green-500/10 dark:text-green-200">
              {result}
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button className="nx-btn nx-btn-secondary" onClick={onClose}>
              Rechazar
            </button>
            <button
              className="nx-btn nx-btn-primary"
              onClick={handleConfirm}
              disabled={confirming}
            >
              {confirming ? 'Confirmando…' : 'Confirmar acción'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
