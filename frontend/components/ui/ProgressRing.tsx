interface ProgressRingProps {
  progressPct: number;
  size?: number;
  label?: string;
}

// Per DESIGN.md Financial Visualization spec: 8px stroke, Sage Green
// progress over Warm Sand empty track, no gradients.
export function ProgressRing({ progressPct, size = 64, label }: ProgressRingProps) {
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progressPct / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="var(--outline-variant)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="var(--secondary)"
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-500"
        />
      </svg>
      <span className="absolute font-title-md text-on-surface" style={{ fontSize: size < 56 ? "13px" : undefined }}>
        {label ?? `${progressPct}%`}
      </span>
    </div>
  );
}
