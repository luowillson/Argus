"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { VIcon } from "@/components/brand/VIcon";
import { submitSearch } from "@/lib/searchSubmit";

export function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      await submitSearch(q, router);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-8 flex max-w-[720px] items-stretch border-[1.5px] border-ink bg-white sm:mt-9"
    >
      <div className="flex items-center px-[18px] text-muted-2">
        <VIcon name="search" size={18} />
      </div>
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Paper title, arXiv ID, or OpenReview link"
        className="min-w-0 flex-1 border-none bg-transparent py-4 font-serif text-[16px] text-ink outline-none placeholder:text-muted/60 sm:py-5 sm:text-[17px]"
      />
      <button
        type="submit"
        disabled={busy}
        className="cursor-pointer bg-burgundy px-5 font-sans text-[14px] font-medium tracking-[0.04em] text-white hover:bg-burgundy/90 disabled:opacity-60 sm:px-8"
      >
        {busy ? "Looking up…" : "Verify"}
      </button>
    </form>
  );
}
