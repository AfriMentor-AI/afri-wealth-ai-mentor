// Exact background motif from the Stitch export's splash_welcome_screen
// code.html (class="sankofa-bg"), reproduced verbatim for fidelity.
// Per DESIGN.md: treated as a background shape at low opacity, not a logo.
export function SankofaMotif({ className = "", size = 200 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" className={className} aria-hidden="true">
      <path
        className="text-primary"
        d="M100 20c-40 0-70 30-70 70 0 50 70 90 70 90s70-40 70-90c0-40-30-70-70-70zm0 130s-40-30-40-60c0-25 20-40 40-40s40 15 40 40c0 30-40 60-40 60z"
        fill="currentColor"
      />
      <path
        className="text-primary"
        d="M100 50c-15 0-25 10-25 25 0 20 25 35 25 35s25-15 25-35c0-15-10-25-25-25z"
        fill="currentColor"
      />
    </svg>
  );
}
