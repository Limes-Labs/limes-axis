import { cn } from "@/lib/cn";
import { brandTokens } from "@/lib/foundation";

/**
 * The Limes Axis mark from the brand kit: a vertical signal-blue axis with a
 * diamond at the center and three rays converging from each side.
 *
 * Colors are token-driven so the mark flips with the theme: the axis and
 * diamond always render in Signal Blue while the rays use `currentColor`
 * (navy on light, near-white on dark).
 *
 * AxisMarkGlyph renders the raw SVG group so the mark can live inside other
 * SVG scenes; AxisMark is the standalone <svg>.
 */

const signal = `rgb(var(--signal, ${brandTokens.signalChannels}))`;

export function AxisMarkGlyph({
  cx,
  cy,
  r,
  rayColor = "currentColor",
}: {
  cx: number;
  cy: number;
  r: number; // half-height of the vertical axis
  rayColor?: string;
}) {
  const s = r / 20; // scale relative to the 40-unit reference height
  const strokeW = 2.4 * s;
  const gap = 6.5 * s; // where rays stop, short of the diamond
  const rayLen = 13 * s;
  const diag = 8.5 * s;

  return (
    <g>
      {/* vertical axis */}
      <line
        x1={cx}
        y1={cy - r}
        x2={cx}
        y2={cy + r}
        style={{ stroke: signal }}
        strokeWidth={strokeW * 0.85}
        strokeLinecap="round"
      />
      {/* rays, left and right */}
      {[-1, 1].map((side) => (
        <g key={side}>
          <line
            x1={cx + side * (gap + rayLen)}
            y1={cy}
            x2={cx + side * gap}
            y2={cy}
            style={{ stroke: rayColor }}
            strokeWidth={strokeW}
            strokeLinecap="round"
          />
          <line
            x1={cx + side * (gap + diag)}
            y1={cy - 7.5 * s}
            x2={cx + side * gap * 0.92}
            y2={cy - 1.8 * s}
            style={{ stroke: rayColor }}
            strokeWidth={strokeW * 0.8}
            strokeLinecap="round"
          />
          <line
            x1={cx + side * (gap + diag)}
            y1={cy + 7.5 * s}
            x2={cx + side * gap * 0.92}
            y2={cy + 1.8 * s}
            style={{ stroke: rayColor }}
            strokeWidth={strokeW * 0.8}
            strokeLinecap="round"
          />
        </g>
      ))}
      {/* center diamond */}
      <rect
        x={cx - 4 * s}
        y={cy - 4 * s}
        width={8 * s}
        height={8 * s}
        rx={1.2 * s}
        style={{ fill: signal }}
        transform={`rotate(45 ${cx} ${cy})`}
      />
    </g>
  );
}

export function AxisMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      className={cn("axis-mark", className)}
      aria-hidden="true"
      focusable="false"
    >
      <AxisMarkGlyph cx={24} cy={24} r={20} />
    </svg>
  );
}

export default AxisMark;
