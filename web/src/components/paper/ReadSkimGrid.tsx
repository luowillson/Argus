type Props = {
  deep: string[];
  skim: string[];
};

export function ReadSkimGrid({ deep, skim }: Props) {
  return (
    <section className="mt-8 grid grid-cols-2 gap-10">
      <div>
        <div className="border-b-[1.5px] border-accept pb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-accept">
          Read deeply
        </div>
        <ul className="mt-3 list-disc pl-5 font-serif text-[15px] leading-[1.85]">
          {deep.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>
      <div>
        <div className="border-b-[1.5px] border-borderline pb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-borderline">
          Skim or skip
        </div>
        <ul className="mt-3 list-disc pl-5 font-serif text-[15px] leading-[1.85] text-muted-2">
          {skim.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
