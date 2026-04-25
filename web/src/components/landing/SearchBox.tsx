"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { VIcon } from "@/components/brand/VIcon";

export function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = q.trim();
    if (!trimmed) return;
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <form
      onSubmit={submit}
      className="mt-10 flex max-w-[720px] items-stretch border-[1.5px] border-ink bg-white"
    >
      <div className="flex items-center px-[18px] text-muted-2">
        <VIcon name="search" size={18} />
      </div>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Paper title, arXiv ID, or OpenReview link"
        className="flex-1 border-none bg-transparent py-5 font-serif text-[17px] text-ink outline-none placeholder:text-muted/60"
      />
      <button
        type="submit"
        className="bg-burgundy px-8 font-sans text-[14px] font-medium tracking-[0.04em] text-white hover:bg-burgundy/90"
      >
        Verify
      </button>
    </form>
  );
}
