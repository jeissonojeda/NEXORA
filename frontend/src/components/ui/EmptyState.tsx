import Icon from './Icon';
import type { IconName } from './Icon';

interface EmptyStateProps {
  title: string;
  hint?: string;
  icon?: IconName;
}

export default function EmptyState({ title, hint, icon = 'layers' }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-faint">
        <Icon name={icon} size={26} />
      </div>
      <p className="text-base font-semibold text-foreground">{title}</p>
      {hint && <p className="mt-1 text-sm text-faint">{hint}</p>}
    </div>
  );
}