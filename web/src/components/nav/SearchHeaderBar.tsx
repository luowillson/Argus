"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { VIcon } from "@/components/brand/VIcon";
import { getSearchDestination } from "@/lib/query";
import { TopNav } from "./TopNav";

type Props = {
  initialQuery?: string;
  /** When provided, the input becomes controlled by the parent. */
  value?: string;
  /** Called on every keystroke when the input is controlled. */
  onChange?: (next: string) => void;
  /**
   * Custom submit handler. If provided, the default routing logic is skipped
   * and the parent decides what to do with the submitted query.
   */
  onSubmitOverride?: (query: string) => void;
};

export function SearchHeaderBar({
  initialQuery = "",
  value,
  onChange,
  onSubmitOverride,
}: Props) {
  const router = useRouter();
  const isControlled = value !== undefined;
  const [internalQ, setInternalQ] = useState(initialQuery);
  const q = isControlled ? value! : internalQ;
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  function handleChange(next: string) {
    if (onChange) onChange(next);
    if (!isControlled) setInternalQ(next);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (onSubmitOverride) {
      onSubmitOverride(q);
      return;
    }
    const destination = getSearchDestination(q);
    if (!destination) return;
    router.push(destination.href);
  }

  return (
    <TopNav>
      <form
        onSubmit={submit}
        className="flex h-8 max-w-[540px] flex-1 items-center bg-white"
      >
        <div className="pointer-events-none flex items-center pl-3 text-muted-2">
          <VIcon name="search" size={14} />
        </div>
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => handleChange(e.target.value)}
          aria-label="Search papers"
          placeholder="Paper title, arXiv ID, or OpenReview link"
          className="flex-1 border-none bg-transparent px-2.5 text-[14px] text-ink outline-none placeholder:text-muted/60"
        />
      </form>

      <nav className="ml-auto flex items-center gap-7 opacity-90">
        <Link href="/search" className="cursor-pointer">
          Browse
        </Link>
        <Link href="/ranking" className="cursor-pointer">
          Ranking
        </Link>
        <Link
          href="/explore"
          className="cursor-pointer border-l border-cream/25 pl-7"
        >
          Explore
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
