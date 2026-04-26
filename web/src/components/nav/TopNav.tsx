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
        "bg-burgundy text-cream font-sans",
        variant === "landing"
          ? "h-14 px-3 text-[13px] sm:h-16 sm:px-8 sm:text-[14px] lg:px-12"
          : "h-16 px-8 text-[14px]",
        className,
      )}
    >
      <div className="flex h-full items-center gap-3 sm:gap-7">
        <Link
          href="/"
          className="flex cursor-pointer items-center gap-3 text-[18px] font-semibold leading-none tracking-[0.025em]"
        >
          <VerosMark size={24} className="text-cream" />
          <span>Veros</span>
        </Link>

        {children ? (
          <div className="flex flex-1 items-center gap-7">{children}</div>
        ) : (
          <div className="ml-auto flex items-center gap-3 sm:gap-7">
            <Link href="/search" className="cursor-pointer">
              Browse
            </Link>
            <Link href="/ranking" className="cursor-pointer">
              Ranking
            </Link>
            <Link href="/explore" className="cursor-pointer">
              Explore
            </Link>
            <Link href="/saved" className="cursor-pointer">
              Saved
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
