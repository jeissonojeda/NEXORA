import { createPortal } from 'react-dom';
import { useEffect } from 'react';
import Icon from './Icon';

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}

export default function Modal({ open, title, onClose, children, wide }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={`w-full ${wide ? 'max-w-2xl' : 'max-w-lg'} animate-scale-in overflow-hidden rounded-2xl bg-surface shadow-[var(--nx-shadow-pop)]`}
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-faint hover:bg-surface-2 hover:text-foreground"
            aria-label="Cerrar"
          >
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}