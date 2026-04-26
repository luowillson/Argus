"use client";

import { VIcon } from "@/components/brand/VIcon";

type Props = {
  query: string;
  onSubmit: (query: string) => void;
};

export function AuthorRankingSearch({ query, onSubmit }: Props) {
  return (
    <form
      autoComplete="off"
      onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        onSubmit(String(data.get("q") ?? ""));
      }}
      className="flex h-8 min-w-[280px] max-w-[420px] flex-1 items-center bg-white font-sans text-[13px]"
    >
      <div className="pointer-events-none flex items-center pl-3 text-muted-2">
        <VIcon name="search" size={14} />
      </div>
      <input
        type="search"
        name="q"
        defaultValue={query}
        autoComplete="off"
        autoCorrect="off"
        spellCheck={false}
        aria-label="Search authors"
        placeholder="Search author name"
        className="flex-1 border-none bg-transparent px-2.5 text-ink outline-none placeholder:text-muted/60"
      />
    </form>
  );
}
