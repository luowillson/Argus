"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { VerosMark } from "@/components/brand/VerosMark";

type Props = {
  initialQuery?: string;
};

export function SearchHeaderBar({ initialQuery = "" }: Props) {
  const router = useRouter();
  const [q, setQ] = useState(initialQuery);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = q.trim();
    if (!trimmed) return;
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <header className="bg-burgundy px-12 py-3 text-cream font-sans text-[13px]">
      <div className="flex items-center gap-7">
        <Link
          href="/"
          className="flex items-center gap-2.5 font-semibold tracking-[0.025em]"
        >
          <VerosMark size={18} className="text-cream" />
          <span>Veros</span>
        </Link>

        <form
          onSubmit={submit}
          className="flex h-8 max-w-[540px] flex-1 items-stretch bg-white"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="flex-1 border-none bg-transparent px-3 text-[13px] text-ink outline-none"
          />
          <button
            type="submit"
            className="bg-ink px-4 text-[12px] text-white"
          >
            Search
          </button>
        </form>

        <nav className="ml-auto flex items-center gap-6">
          <Link href="/search">Browse</Link>
          <Link href="/">API</Link>
          <Link href="/saved">Saved</Link>
        </nav>
      </div>
    </header>
  );
}
