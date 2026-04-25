import { TopNav } from "@/components/nav/TopNav";
import { Hero } from "@/components/landing/Hero";
import { StatsFooter } from "@/components/landing/StatsFooter";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-paper text-ink">
      <TopNav />
      <Hero />
      <StatsFooter />
    </div>
  );
}
