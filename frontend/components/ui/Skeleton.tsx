export function Skeleton({ className = "" }: { className?: string }) {
  // Per DESIGN.md: "flat gray-wash rectangles that match the exact
  // border-radius of the component they represent, to prevent layout shift."
  return (
    <div
      className={`animate-pulse rounded bg-[#e0e0e0] ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}
