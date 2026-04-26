import Link from "next/link";
import { VerosMark } from "@/components/brand/VerosMark";
import { cn } from "@/lib/utils";

type Props = {
  variant?: "landing" | "compact";
  children?: React.ReactNode;
  className?: string;
};

export function TopNav({ variant = "landing", children, className }: Props) {
  return (
    <header
      className={cn(
        "h-16 bg-burgundy text-cream font-sans text-[14px]",
        variant === "landing" ? "px-12" : "px-8",
        className,
      )}
    >
      <div className="flex h-full items-center gap-7">
        <Link
          href="/"
          className="flex cursor-pointer items-center gap-2.5 font-semibold tracking-[0.025em]"
        >
          <VerosMark size={20} className="text-cream" />
          <span>Veros</span>
        </Link>

        {children ? (
          <div className="flex flex-1 items-center gap-7">{children}</div>
        ) : (
          <div className="ml-auto flex items-center gap-7 opacity-90">
            <Link href="/search" className="cursor-pointer">
              Browse
            </Link>
            <Link href="/ranking" className="cursor-pointer">
              Ranking
            </Link>
            <Link
              href="/saved"
              className="cursor-pointer border-l border-cream/25 pl-7"
            >
              Saved
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
