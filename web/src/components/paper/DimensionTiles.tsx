type Props = {
  novelty: number | null;
  technical: number | null;
  clarity: number | null;
  impact: number | null;
  pending?: boolean;
  className?: string;
};

const LABELS: [string, "novelty" | "technical" | "clarity" | "impact"][] = [
  ["Novelty", "novelty"],
  ["Technical", "technical"],
  ["Clarity", "clarity"],
  ["Impact", "impact"],
];

export function DimensionTiles({
  novelty,
  technical,
  clarity,
  impact,
  pending = false,
}: Props) {
  const values = { novelty, technical, clarity, impact } as const;
  return (
    <div className="grid grid-cols-4 gap-3">
      {LABELS.map(([label, key]) => {
        const v = values[key];
        return (
          <div key={key} className="border border-rule bg-white px-3 py-3">
            <div className="font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">
              {label}
            </div>
            <div className="mt-1.5 text-[34px] font-medium leading-none tracking-[-0.025em] tabular-nums text-ink">
              {pending || v === null ? (
                <span className="text-muted/50">—</span>
              ) : (
                <>
                  {v}
                  <span className="ml-0.5 font-sans text-[14px] font-normal text-muted">
                    /100
                  </span>
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
