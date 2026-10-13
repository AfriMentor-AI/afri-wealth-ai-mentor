export function ProgressRing({ progressPct, size = 64, label, caption }: { progressPct: number; size?: number; label?: string; caption?: string }) {
  const stroke = size >= 80 ? 9 : 7;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, progressPct));
  return (
    <div className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }} role="img" aria-label={`${pct}% complete`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-outline-variant/60" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c - (pct / 100) * c} className="stroke-sunburst-gold transition-[stroke-dashoffset] duration-500" />
      </svg>
      <span className="absolute flex flex-col items-center leading-none">
        <span className="font-title-md text-on-surface" style={{ fontSize: size < 72 ? 15 : 20 }}>{label ?? `${pct}%`}</span>
        {caption && size >= 72 && <span className="mt-0.5 font-eyebrow text-[8px] uppercase text-on-surface-variant">{caption}</span>}
      </span>
    </div>
  );
}
