import { useState } from 'react';
import Icon from '../ui/Icon';
import Badge from '../ui/Badge';
import { extractErrorMessage } from '../../hooks/useAsync';
import { chatAi } from '../../services/aiOperational';
import {
  AI_ACTION_LABELS,
  AI_ACTION_TYPE_LABELS,
  type AiActionProposal,
  type AiChatResponse,
} from '../../types/ai';

interface Props {
  onPropose: (p: AiActionProposal) => void;
}

interface ChatMsg {
  role: 'user' | 'assistant';
  text: string;
  proposals: AiActionProposal[];
  toolSummary: string | null;
}

const SUGGESTIONS = [
  '¿Qué productos tienen stock bajo?',
  'Sugiere reabastecer proveedor principal',
  'Proponer compra de leche a Distribuidora ABC',
];

export default function AiChatPanel({ onPropose }: Props) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    setSending(true);
    setError(null);
    setMessages((m) => [...m, { role: 'user', text: message, proposals: [], toolSummary: null }]);
    setInput('');
    try {
      const res: AiChatResponse = await chatAi(message);
      const toolCount = res.tool_results?.length ?? 0;
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: res.message,
          proposals: res.action_proposals ?? [],
          toolSummary:
            toolCount > 0
              ? `${toolCount} consulta${toolCount === 1 ? '' : 's'} a datos del negocio`
              : null,
        },
      ]);
    } catch (e) {
      setError(extractErrorMessage(e));
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: 'No pude procesar tu solicitud.',
          proposals: [],
          toolSummary: null,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex h-[480px] flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <div className="rounded-2xl bg-primary-soft p-4 text-primary">
              <Icon name="sparkles" size={32} />
            </div>
            <p className="text-sm text-muted">
              Pregunta sobre tu negocio en lenguaje natural. NEXORA AI puede
              consultar datos y <span className="font-medium text-foreground">proponer acciones</span>{' '}
              que siempre deberás confirmar antes de ejecutarse.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  className="rounded-full border border-line-strong bg-surface px-3 py-1.5 text-xs text-muted hover:bg-surface-2 hover:text-foreground"
                  onClick={() => send(s)}
                  disabled={sending}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                m.role === 'user'
                  ? 'bg-primary text-white'
                  : 'bg-surface text-foreground'
              }`}
            >
              <p className="whitespace-pre-wrap">{m.text}</p>

              {m.toolSummary && (
                <p className="mt-2 flex items-center gap-1 text-xs text-muted">
                  <Icon name="search" size={13} /> {m.toolSummary}
                </p>
              )}

              {m.proposals.length > 0 && (
                <div className="mt-3 space-y-2">
                  {m.proposals.map((p, j) => (
                    <div
                      key={j}
                      className="flex items-center justify-between gap-3 rounded-xl border border-line bg-surface-2 p-3"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <Badge tone="purple">
                            {AI_ACTION_LABELS[p.action_name] || p.action_name}
                          </Badge>
                          <Badge tone="blue">
                            {AI_ACTION_TYPE_LABELS[p.action_type] || p.action_type}
                          </Badge>
                        </div>
                        <p className="mt-1 text-xs text-faint">
                          Se requiere tu confirmación para ejecutar.
                        </p>
                      </div>
                      <button
                        className="nx-btn nx-btn-primary mx-0 !px-3 !py-1.5 text-xs"
                        onClick={() => onPropose(p)}
                      >
                        Revisar
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex items-center gap-2 text-sm text-muted">
            <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
            Pensando…
          </div>
        )}
      </div>

      {error && <p className="mb-2 text-sm text-red-500">{error}</p>}

      <div className="mt-3 flex items-end gap-2 border-t border-line pt-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          rows={2}
          placeholder="Escribe una consulta o instrucción…"
          className="nx-textarea flex-1"
        />
        <button
          className="nx-btn nx-btn-primary !px-3"
          onClick={() => void send()}
          disabled={sending || !input.trim()}
          aria-label="Enviar"
        >
          <Icon name="check" size={18} />
        </button>
      </div>
    </div>
  );
}
