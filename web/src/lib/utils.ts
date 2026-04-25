import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function scoreColor(score: number | null): string {
  if (score === null) return "text-muted";
  if (score >= 7) return "text-accept";
  if (score >= 5) return "text-borderline";
  return "text-burgundy";
}
