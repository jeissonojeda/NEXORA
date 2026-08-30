export type BadgeTone = 'green' | 'red' | 'blue' | 'gray' | 'amber' | 'purple';

const TONES: Record<BadgeTone, string> = {
  green: 'nx-badge-green',
  red: 'nx-badge-red',
  blue: 'nx-badge-blue',
  gray: 'nx-badge-gray',
  amber: 'nx-badge-amber',
  purple: 'nx-badge-purple',
};

interface BadgeProps {
  tone?: BadgeTone;
  children: React.ReactNode;
}

export default function Badge({ tone = 'gray', children }: BadgeProps) {
  return <span className={`nx-badge ${TONES[tone]}`}>{children}</span>;
}