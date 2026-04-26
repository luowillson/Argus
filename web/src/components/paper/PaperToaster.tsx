"use client";

import { Toaster } from "sonner";

export function PaperToaster() {
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "border border-rule bg-paper text-ink shadow-[0_10px_28px_rgba(28,24,21,0.14)] font-sans rounded-none",
          title: "text-[13px] font-medium text-ink",
          description: "text-[12px] text-muted-2",
          success: "border-l-[3px] border-l-accept",
          error: "border-l-[3px] border-l-burgundy",
          icon: "text-burgundy",
        },
      }}
    />
  );
}
