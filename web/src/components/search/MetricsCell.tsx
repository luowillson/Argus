type Props = {
  novelty: number;
  technical: number;
  clarity: number;
  impact: number;
};

export function MetricsCell({ novelty, technical, clarity, impact }: Props) {
  const items: [string, number][] = [
    ["nov", novelty],
    ["tech", technical],
    ["clar", clarity],
    ["imp", impact],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 font-sans text-[13px] text-muted-2">
      {items.map(([label, v]) => (
        <div key={label} className="flex items-baseline justify-between gap-2">
          <dt className="font-mono text-[11px] uppercase tracking-wide text-muted">
            {label}
          </dt>
          <dd className="tabular-nums text-[15px] font-medium text-ink">
            {v}
            <span className="ml-0.5 text-[11px] text-muted">/100</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}
