import { formatChange, formatChangePct } from "@/lib/formatters";

interface ChangeIndicatorProps {
  change: number | null;
  changePct: number | null;
  size?: "sm" | "md";
}

export function ChangeIndicator({ change, changePct, size = "md" }: ChangeIndicatorProps) {
  const abs = formatChange(change);
  const pct = formatChangePct(changePct);
  const textSize = size === "sm" ? "text-[11px]" : "text-xs";

  return (
    <span className={`${textSize} font-mono inline-flex items-center gap-1`}>
      <span className={abs.className}>{abs.text}</span>
      <span className={`${pct.className}`}>({pct.text})</span>
    </span>
  );
}
