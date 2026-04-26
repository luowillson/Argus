import { TopNav } from "@/components/nav/TopNav";
import { Hero } from "@/components/landing/Hero";
import { SemanticGraph } from "@/components/landing/SemanticGraph";
import { StatsFooter } from "@/components/landing/StatsFooter";

export default function LandingPage() {
  return (
    <div className="relative flex min-h-dvh flex-col overflow-hidden bg-paper text-ink">
      <TopNav />
      <main className="relative z-10 grid min-h-0 flex-1 pb-24 lg:pb-22 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] xl:items-center">
        <Hero />
        <SemanticGraph />
      </main>
      <StatsFooter />
    </div>
  );
}
