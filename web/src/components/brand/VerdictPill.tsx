import { cn } from "@/lib/utils";
import type { Verdict } from "@/lib/types";

type Props = {
  verdict: Verdict;
  className?: string;
};

const STYLES: Record<Verdict, string> = {
  "Strong Accept": "bg-accept/10 text-accept border-accept/40",
  Accept: "bg-accept/8 text-accept border-accept/30",
  "Weak Accept": "bg-borderline/10 text-borderline border-borderline/30",
  Borderline: "bg-rule-soft text-muted-2 border-rule",
  Reject: "bg-burgundy/8 text-burgundy border-burgundy/30",
  "Insufficient reviews": "bg-rule-soft text-muted-2 border-rule",
};

export function VerdictPill({ verdict, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border px-2.5 py-1 font-sans text-[11px] font-medium tracking-wide uppercase",
        STYLES[verdict],
        className,
      )}
    >
      {verdict}
    </span>
  );
}
