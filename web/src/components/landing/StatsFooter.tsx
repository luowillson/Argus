export function StatsFooter() {
  return (
    <footer className="absolute bottom-0 left-0 right-0 flex items-center justify-between border-t border-rule px-24 py-5 font-sans text-[13px] text-muted-2">
      <div>
        Indexing{" "}
        <Stat>847,329</Stat> papers across <Stat>142</Stat> venues &nbsp;·&nbsp;{" "}
        <Stat>2.4M</Stat> reviewer comments parsed.
      </div>
      <div className="font-mono text-[11px] text-muted">
        last sync 04/25/26 06:41 UTC
      </div>
    </footer>
  );
}

function Stat({ children }: { children: React.ReactNode }) {
  return (
    <strong className="font-serif text-[16px] font-medium text-ink">
      {children}
    </strong>
  );
}
