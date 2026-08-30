import type { ReactNode } from 'react';
import Icon from './Icon';
import type { IconName } from './Icon';

type KpiTone = 'blue' | 'green' | 'amber' | 'red' | 'purple' | 'gray';

const TONE_BADGE: Record<KpiTone, string> = {
  blue: 'bg-primary-soft text-primary',
  green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  amber: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
  red: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400',
  purple: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-400',
  gray: 'bg-surface-2 text-muted',
};

interface KpiCardProps {
  label: string;
  value: string | number;
  icon: IconName;
  tone?: KpiTone;
  sub?: ReactNode;
  loading?: boolean;
}

export default function KpiCard({
  label,
  value,
  icon,
  tone = 'blue',
  sub,
  loading = false,
}: KpiCardProps) {
  return (
    <div className="nx-card nx-card-hover flex items-start gap-4 p-5">
      <span
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${TONE_BADGE[tone]}`}
      >
        <Icon name={icon} size={22} />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wider text-faint">{label}</p>
        {loading ? (
          <div className="mt-2 h-6 w-24 animate-pulse rounded-md bg-surface-2" />
        ) : (
          <p className="mt-0.5 truncate text-xl font-bold text-foreground">{value}</p>
        )}
        {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
      </div>
    </div>
  );
}