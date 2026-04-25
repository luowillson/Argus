import type { Metadata } from "next";
import { Newsreader, Inter, IBM_Plex_Mono } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";
import { Providers } from "./providers";

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  style: ["normal", "italic"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Veros — Open peer review, distilled",
  description:
    "Veros aggregates every reviewer comment on OpenReview, weights consensus, and tells you which sections deserve your hour.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${newsreader.variable} ${inter.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-paper text-ink font-serif">
        <Providers>
          {children}
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
        </Providers>
      </body>
    </html>
  );
}
