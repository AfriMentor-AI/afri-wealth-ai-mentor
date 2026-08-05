interface IconProps {
  name: string;
  className?: string;
  filled?: boolean;
  size?: number;
}

// The Stitch export uses Google's Material Symbols Outlined font via
// ligature text (e.g. <span class="material-symbols-outlined">chat_bubble</span>).
// Matching that exactly (rather than swapping in a different icon set) so
// glyphs line up with the screen.png references.
export function Icon({ name, className = "", filled = false, size }: IconProps) {
  return (
    <span
      className={`material-symbols-outlined select-none ${className}`}
      style={{
        fontVariationSettings: `'FILL' ${filled ? 1 : 0}, 'wght' 400, 'GRAD' 0, 'opsz' 24`,
        fontSize: size ? `${size}px` : undefined,
      }}
      aria-hidden="true"
    >
      {name}
    </span>
  );
}
