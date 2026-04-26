"use client";

import { useEffect } from "react";
import { API_BASE_URL } from "@/lib/api";
import { syncLocalCorpusFromRemote } from "@/lib/localPapers";

const FALLBACK_SYNC_INTERVAL_MS = 5 * 60_000;

export function CorpusSync() {
  useEffect(() => {
    let cancelled = false;
    let syncing = false;

    async function sync() {
      if (cancelled || syncing) return;
      syncing = true;
      try {
        await syncLocalCorpusFromRemote();
      } catch {
        // Keep the current local corpus if the API is unavailable.
      } finally {
        syncing = false;
      }
    }

    const events = new EventSource(`${API_BASE_URL}/corpus/events`);
    events.addEventListener("corpus-version", () => {
      void sync();
    });

    const fallbackInterval = setInterval(sync, FALLBACK_SYNC_INTERVAL_MS);

    function syncOnFocus() {
      if (document.visibilityState === "visible") void sync();
    }

    document.addEventListener("visibilitychange", syncOnFocus);
    window.addEventListener("focus", sync);
    return () => {
      cancelled = true;
      events.close();
      clearInterval(fallbackInterval);
      document.removeEventListener("visibilitychange", syncOnFocus);
      window.removeEventListener("focus", sync);
    };
  }, []);

  return null;
}
