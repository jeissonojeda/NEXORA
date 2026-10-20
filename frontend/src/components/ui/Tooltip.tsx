import { cloneElement, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

type TooltipSide = 'top' | 'right' | 'bottom' | 'left';

interface TooltipProps {
  label: string;
  children: React.ReactElement;
  side?: TooltipSide;
  disabled?: boolean;
  className?: string;
}

const GAP = 8;
const VIEWPORT_PADDING = 8;

export default function Tooltip({
  label,
  children,
  side = 'top',
  disabled = false,
  className = 'inline-flex',
}: TooltipProps) {
  const id = useId();
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number }>({ top: 0, left: 0 });

  const reposition = useCallback(() => {
    const trigger = triggerRef.current;
    const tip = tipRef.current;
    if (!trigger || !tip) return;

    const t = trigger.getBoundingClientRect();
    const tipRect = tip.getBoundingClientRect();

    let resolvedSide = side;
    if (resolvedSide === 'right' && t.right + GAP + tipRect.width > window.innerWidth - VIEWPORT_PADDING) {
      resolvedSide = 'left';
    } else if (resolvedSide === 'left' && t.left - GAP - tipRect.width < VIEWPORT_PADDING) {
      resolvedSide = 'right';
    } else if (resolvedSide === 'top' && t.top - GAP - tipRect.height < VIEWPORT_PADDING) {
      resolvedSide = 'bottom';
    } else if (resolvedSide === 'bottom' && t.bottom + GAP + tipRect.height > window.innerHeight - VIEWPORT_PADDING) {
      resolvedSide = 'top';
    }

    let top = 0;
    let left = 0;
    switch (resolvedSide) {
      case 'right':
        top = t.top + t.height / 2 - tipRect.height / 2;
        left = t.right + GAP;
        break;
      case 'left':
        top = t.top + t.height / 2 - tipRect.height / 2;
        left = t.left - tipRect.width - GAP;
        break;
      case 'bottom':
        top = t.bottom + GAP;
        left = t.left + t.width / 2 - tipRect.width / 2;
        break;
      case 'top':
      default:
        top = t.top - tipRect.height - GAP;
        left = t.left + t.width / 2 - tipRect.width / 2;
        break;
    }

    left = Math.min(Math.max(left, VIEWPORT_PADDING), window.innerWidth - tipRect.width - VIEWPORT_PADDING);
    top = Math.min(Math.max(top, VIEWPORT_PADDING), window.innerHeight - tipRect.height - VIEWPORT_PADDING);

    setCoords({ top, left });
    setReady(true);
  }, [side]);

  useLayoutEffect(() => {
    if (!open) return;
    reposition();
  }, [open, reposition, label]);

  useEffect(() => {
    if (!open) return;
    const onUpdate = () => reposition();
    window.addEventListener('scroll', onUpdate, true);
    window.addEventListener('resize', onUpdate);
    return () => {
      window.removeEventListener('scroll', onUpdate, true);
      window.removeEventListener('resize', onUpdate);
    };
  }, [open, reposition]);

  const show = open && !disabled;

  const described = show ? id : undefined;
  const trigger = cloneElement(
    children as React.ReactElement<{ 'aria-describedby'?: string }>,
    { 'aria-describedby': described },
  );

  return (
    <>
      <span
        ref={triggerRef}
        className={className}
        onMouseEnter={() => !disabled && setOpen(true)}
        onMouseLeave={() => {
          setOpen(false);
          setReady(false);
        }}
        onFocus={() => !disabled && setOpen(true)}
        onBlur={() => {
          setOpen(false);
          setReady(false);
        }}
      >
        {trigger}
      </span>
      {show &&
        label &&
        createPortal(
          <div
            ref={tipRef}
            id={id}
            role="tooltip"
            style={{
              position: 'fixed',
              top: coords.top,
              left: coords.left,
              visibility: ready ? 'visible' : 'hidden',
            }}
            className="z-[70] max-w-xs rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs font-medium text-foreground shadow-[var(--nx-shadow-pop)]"
          >
            {label}
          </div>,
          document.body,
        )}
    </>
  );
}
