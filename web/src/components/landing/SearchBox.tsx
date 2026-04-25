"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { VIcon } from "@/components/brand/VIcon";
import { getSearchDestination } from "@/lib/query";

export function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const destination = getSearchDestination(q);
    if (!destination) return;
    router.push(destination.href);
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
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Paper title, arXiv ID, or OpenReview link"
        className="flex-1 border-none bg-transparent py-5 font-serif text-[17px] text-ink outline-none placeholder:text-muted/60"
      />
      <button
        type="submit"
        className="cursor-pointer bg-burgundy px-8 font-sans text-[14px] font-medium tracking-[0.04em] text-white hover:bg-burgundy/90"
      >
        Verify
      </button>
    </form>
  );
}
