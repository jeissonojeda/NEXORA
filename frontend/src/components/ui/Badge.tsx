type Tone = 'green' | 'red' | 'blue' | 'gray' | 'amber';

const TONES: Record<Tone, string> = {
  green: 'bg-green-100 text-green-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-blue-100 text-blue-800',
  gray: 'bg-gray-200 text-gray-700',
  amber: 'bg-amber-100 text-amber-800',
};

interface BadgeProps {
  tone?: Tone;
  children: React.ReactNode;
}

export default function Badge({ tone = 'gray', children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
