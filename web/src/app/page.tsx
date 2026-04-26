import { TopNav } from "@/components/nav/TopNav";
import { Hero } from "@/components/landing/Hero";
import { SemanticGraph } from "@/components/landing/SemanticGraph";
import { StatsFooter } from "@/components/landing/StatsFooter";

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-paper text-ink">
      <TopNav />
      <main className="relative z-10 pb-28 xl:grid xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] xl:items-start">
        <Hero />
        <SemanticGraph />
      </main>
      <StatsFooter />
    </div>
  );
}
