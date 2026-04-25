"use client";

import { useState } from "react";
import { toast } from "sonner";
import { VIcon } from "@/components/brand/VIcon";
import { savePaper, unsavePaper } from "@/lib/api";
import { cn } from "@/lib/utils";

export function SaveButton({
  paperId,
  initialSaved = false,
}: {
  paperId: string;
  initialSaved?: boolean;
}) {
  const [saved, setSaved] = useState(initialSaved);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    if (busy) return;
    const next = !saved;
    setSaved(next); // optimistic
    setBusy(true);
    try {
      if (next) {
        await savePaper(paperId);
        toast.success("Added to reading list");
      } else {
        await unsavePaper(paperId);
        toast.success("Removed from reading list");
      }
    } catch {
      setSaved(!next); // revert
      toast.error("Could not update reading list — is the API running?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      className={cn(
        "inline-flex items-center gap-1.5 border px-3 py-1.5 font-sans text-[12px] transition",
        saved
          ? "border-burgundy bg-burgundy text-white"
          : "border-rule text-muted-2 hover:border-ink hover:text-ink",
        busy && "cursor-wait opacity-60",
      )}
    >
      <VIcon name="bookmark" size={13} />
      {saved ? "Saved" : "Save"}
    </button>
  );
}
