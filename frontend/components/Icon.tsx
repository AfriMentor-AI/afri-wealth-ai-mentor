export function Icon({ name, filled, className = "", size }: { name: string; filled?: boolean; className?: string; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className={`material-symbols-outlined ${filled ? "icon-fill" : ""} ${className}`}
      style={size ? { fontSize: size } : undefined}
    >
      {name}
    </span>
  );
}
