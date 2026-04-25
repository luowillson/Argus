type Props = {
  tldr: string;
  aiReady?: boolean;
};

export function TldrSection({ tldr, aiReady = true }: Props) {
  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between">
        <div className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
          AI-distilled summary
        </div>
        {!aiReady && (
          <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-borderline">
            insights pending
          </div>
        )}
      </div>
      <p className="mt-2 max-w-[820px] font-serif text-[19px] leading-[1.6]">
        {tldr}
      </p>
    </section>
  );
}
