// DepthWizard mark: three nested peaks drawn as contour layers (elevation), and a satellite on its orbit above them.
export default function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M2.5 26 C 8 26, 10 13, 16 9.5 C 22 13, 24 26, 29.5 26" />
      <path d="M8 26 C 11 26, 13 17, 16 14.8 C 19 17, 21 26, 24 26" />
      <path d="M12.6 26 C 14 26, 15 21, 16 20.2 C 17 21, 18 26, 19.4 26" />
      <path d="M5 7.5 A 13 5 0 0 1 27 7.5" strokeWidth="1.3" opacity=".65" />
      <circle cx="22.6" cy="4.1" r="2" fill="currentColor" stroke="none" />
    </svg>
  );
}
