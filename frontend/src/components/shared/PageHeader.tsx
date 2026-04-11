"use client";

interface PageHeaderProps {
  title: string;
  loadedAt: Date | null;
  loading?: boolean;
  onRefresh?: () => void;
}

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m ago`;
}

export function PageHeader({ title, loadedAt, loading, onRefresh }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h1 className="text-xs font-bold text-accent uppercase tracking-wider">{title}</h1>
      <div className="flex items-center gap-3 text-[10px] text-muted">
        {loadedAt && (
          <span title={loadedAt.toLocaleString()}>
            Loaded {timeAgo(loadedAt)}
          </span>
        )}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            className="px-2 py-0.5 border border-border rounded hover:border-accent/50 hover:text-accent transition-colors disabled:opacity-30"
          >
            {loading ? "..." : "↻ Refresh"}
          </button>
        )}
      </div>
    </div>
  );
}
