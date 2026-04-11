import Link from "next/link";

interface SymbolLinkProps {
  symbol: string;
  className?: string;
}

export function SymbolLink({ symbol, className }: SymbolLinkProps) {
  return (
    <Link
      href={`/company/${symbol}`}
      className={`text-accent hover:text-accent/80 hover:underline transition-colors ${className || ""}`}
    >
      {symbol}
    </Link>
  );
}
