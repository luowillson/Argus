"use client";

import { useState } from "react";
import { VIcon } from "@/components/brand/VIcon";
import { cn } from "@/lib/utils";

export function SaveButton({ paperId }: { paperId: string }) {
  // M1 stub: local state only. M8 wires this to /saved API.
  const [saved, setSaved] = useState(false);
  void paperId;
  return (
    <button
      type="button"
      onClick={() => setSaved((s) => !s)}
      className={cn(
        "inline-flex items-center gap-1.5 border px-3 py-1.5 font-sans text-[12px] transition",
        saved
          ? "border-burgundy bg-burgundy text-white"
          : "border-rule text-muted-2 hover:border-ink hover:text-ink",
      )}
    >
      <VIcon name="bookmark" size={13} />
      {saved ? "Saved" : "Save"}
    </button>
  );
}
