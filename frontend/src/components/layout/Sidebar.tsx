"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: "◆" },
  { href: "/trade-setup", label: "Trade Setup", icon: "▸" },
  { href: "/nifty", label: "NIFTY", icon: "━" },
  { href: "/banknifty", label: "BANKNIFTY", icon: "━" },
  { href: "/sectors", label: "Sectors", icon: "▦" },
  { href: "/heatmaps", label: "Heatmaps", icon: "▥" },
  { href: "/global", label: "Global", icon: "◎" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="w-44 border-r border-border bg-surface shrink-0 flex flex-col py-2">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`
              flex items-center gap-2 px-4 py-1.5 text-xs transition-colors
              ${active
                ? "text-accent bg-accent-dim border-l-2 border-accent"
                : "text-muted hover:text-foreground hover:bg-surface-hover border-l-2 border-transparent"
              }
            `}
          >
            <span className="w-4 text-center">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
