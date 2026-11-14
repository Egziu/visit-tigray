// Abstract SVG illustrations. They are decorative (aria-hidden) and never pretend to be photographs.

export function Emblem({ className }: { className?: string }) {
  // Stylised stele with eight-pointed star — a design motif, not an official emblem.
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="46" height="46" rx="12" fill="currentColor" />
      <path d="M24 8 l3 6 6 -3 -3 6 6 3 -6 3 3 6 -6 -3 -3 6 -3 -6 -6 3 3 -6 -6 -3 6 -3 -3 -6 6 3z" fill="var(--color-gold)" opacity=".95" />
      <rect x="20" y="20" width="8" height="20" rx="1.5" fill="var(--color-bg)" opacity=".92" />
      <rect x="22" y="24" width="4" height="2" fill="currentColor" />
      <rect x="22" y="29" width="4" height="2" fill="currentColor" />
      <rect x="22" y="34" width="4" height="2" fill="currentColor" />
    </svg>
  );
}

export function HeroLandscape({ className }: { className?: string }) {
  // Layered sandstone mesas at dusk with a carved stele silhouette.
  return (
    <svg viewBox="0 0 1440 760" preserveAspectRatio="xMidYMid slice" className={className} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0f2a24" />
          <stop offset=".55" stopColor="#2c4a3c" />
          <stop offset="1" stopColor="#b98a5a" />
        </linearGradient>
        <linearGradient id="mesaFar" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7c5a3c" />
          <stop offset="1" stopColor="#4b3a2a" />
        </linearGradient>
        <linearGradient id="mesaNear" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a8714a" />
          <stop offset="1" stopColor="#5a3a22" />
        </linearGradient>
        <radialGradient id="sun" cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#f3d9a6" />
          <stop offset="1" stopColor="#f3d9a6" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="1440" height="760" fill="url(#sky)" />
      <circle cx="1060" cy="420" r="240" fill="url(#sun)" opacity=".55" />
      <circle cx="1060" cy="420" r="70" fill="#f1d39b" opacity=".9" />
      <path d="M0 470 L120 470 L170 430 L420 430 L470 470 L640 470 L700 410 L940 410 L990 470 L1440 470 L1440 760 L0 760Z" fill="url(#mesaFar)" opacity=".85" />
      <path d="M0 560 L260 560 L330 480 L640 480 L700 560 L900 560 L960 505 L1240 505 L1300 560 L1440 560 L1440 760 L0 760Z" fill="url(#mesaNear)" />
      <g stroke="#3b2717" strokeOpacity=".35" strokeWidth="2">
        <path d="M330 500 L640 500 M345 520 L630 520 M960 525 L1240 525 M975 540 L1225 540" />
      </g>
      <path d="M0 640 C 240 600 520 690 760 640 S 1200 600 1440 650 L1440 760 L0 760Z" fill="#2a1d12" opacity=".55" />
      {/* stele silhouette */}
      <g fill="#14100c" opacity=".9">
        <path d="M222 640 L222 300 Q240 270 258 300 L258 640Z" />
        <rect x="228" y="330" width="24" height="8" fill="#5a3a22" />
        <rect x="228" y="380" width="24" height="8" fill="#5a3a22" />
        <rect x="228" y="430" width="24" height="8" fill="#5a3a22" />
        <rect x="228" y="480" width="24" height="8" fill="#5a3a22" />
        <path d="M290 640 L290 430 Q302 412 314 430 L314 640Z" />
      </g>
      {/* olive tree */}
      <g fill="#1f2a16" opacity=".85">
        <rect x="1180" y="560" width="10" height="70" />
        <ellipse cx="1185" cy="548" rx="58" ry="34" />
        <ellipse cx="1150" cy="566" rx="34" ry="20" />
        <ellipse cx="1222" cy="566" rx="34" ry="20" />
      </g>
    </svg>
  );
}

export function PatternBand({ className }: { className?: string }) {
  // Woven geometric band inspired by textile borders (abstract).
  return (
    <svg viewBox="0 0 240 16" preserveAspectRatio="none" className={className} aria-hidden="true" focusable="false">
      <defs>
        <pattern id="band" width="24" height="16" patternUnits="userSpaceOnUse">
          <path d="M0 8 L6 2 L12 8 L6 14Z M12 8 L18 2 L24 8 L18 14Z" fill="currentColor" opacity=".55" />
          <rect x="5" y="7" width="2" height="2" fill="currentColor" />
          <rect x="17" y="7" width="2" height="2" fill="currentColor" />
        </pattern>
      </defs>
      <rect width="240" height="16" fill="url(#band)" />
    </svg>
  );
}

export function CardArt({ seed, className }: { seed: string; className?: string }) {
  // Deterministic abstract landscape per destination (no photograph available).
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const palettes = [
    ["#d9c3a0", "#b98a5a", "#7c4a26", "#102d27"],
    ["#e4d6bb", "#a99060", "#59613a", "#1f4a3f"],
    ["#efe0c5", "#c9a160", "#8a5a2f", "#2b3c35"],
    ["#dcd2bd", "#9c7b52", "#4b3a2a", "#102d27"],
  ];
  const [sky, far, near, ground] = palettes[h % palettes.length];
  const peak = 90 + (h % 50);
  const mid = 120 + ((h >> 4) % 40);
  return (
    <svg viewBox="0 0 400 260" preserveAspectRatio="xMidYMid slice" className={className} aria-hidden="true" focusable="false">
      <rect width="400" height="260" fill={sky} />
      <circle cx={260 + (h % 80)} cy={70 + ((h >> 3) % 30)} r="26" fill="#fff6e0" opacity=".7" />
      <path d={`M0 ${mid} L80 ${mid} L110 ${peak} L250 ${peak} L280 ${mid} L400 ${mid} L400 260 L0 260Z`} fill={far} />
      <path d={`M0 ${mid + 50} L140 ${mid + 50} L170 ${mid + 15} L320 ${mid + 15} L350 ${mid + 50} L400 ${mid + 50} L400 260 L0 260Z`} fill={near} />
      <rect y="230" width="400" height="30" fill={ground} opacity=".85" />
    </svg>
  );
}
