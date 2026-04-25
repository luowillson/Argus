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
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 font-sans text-[12px] text-muted-2">
      {items.map(([label, v]) => (
        <div key={label} className="flex items-baseline justify-between gap-2">
          <dt className="font-mono text-[10px] uppercase tracking-wide text-muted">
            {label}
          </dt>
          <dd className="tabular-nums font-medium text-ink">
            {v}
            <span className="ml-0.5 text-[10px] text-muted">/100</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}
