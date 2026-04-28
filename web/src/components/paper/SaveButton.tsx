"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { VIcon } from "@/components/brand/VIcon";
import { fetchSavedStatus, savePaper, unsavePaper } from "@/lib/api";
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

  useEffect(() => {
    const controller = new AbortController();
    fetchSavedStatus(paperId, { signal: controller.signal })
      .then(setSaved)
      .catch(() => undefined);
    return () => controller.abort();
  }, [paperId]);

  async function toggle() {
    if (busy) return;
    const next = !saved;
    setSaved(next);
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
      setSaved(!next);
      toast.error("Could not update reading list");
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
        "inline-flex cursor-pointer items-center gap-1.5 border px-3 py-1.5 font-sans text-[12px] transition",
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
