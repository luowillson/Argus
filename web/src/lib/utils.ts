import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function scoreColor(score: number): string {
  if (score >= 7) return "text-accept";
  if (score >= 5) return "text-borderline";
  return "text-burgundy";
}
