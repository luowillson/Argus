"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getSearchDestination } from "@/lib/query";
import { TopNav } from "./TopNav";

type Props = {
  initialQuery?: string;
};

export function SearchHeaderBar({ initialQuery = "" }: Props) {
  const router = useRouter();
  const [q, setQ] = useState(initialQuery);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const destination = getSearchDestination(q);
    if (!destination) return;
    router.push(destination.href);
  }

  return (
    <TopNav>
      <form
        onSubmit={submit}
        className="flex h-8 max-w-[540px] flex-1 items-stretch bg-white"
      >
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="flex-1 border-none bg-transparent px-3.5 text-[14px] text-ink outline-none"
        />
        <button
          type="submit"
          className="cursor-pointer bg-ink px-4 text-[13px] text-white"
        >
          Search
        </button>
      </form>

      <nav className="ml-auto flex items-center gap-7 opacity-90">
        <Link href="/search" className="cursor-pointer">
          Browse
        </Link>
        <Link
          href="/saved"
          className="cursor-pointer border-l border-cream/25 pl-7"
        >
          Saved
        </Link>
      </nav>
    </TopNav>
  );
}
