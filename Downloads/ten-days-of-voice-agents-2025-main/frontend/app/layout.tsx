import { Public_Sans } from "next/font/google";
import localFont from "next/font/local";
import { headers } from "next/headers";

import { ApplyThemeScript, ThemeToggle } from "@/components/app/theme-toggle";
import { cn, getAppConfig, getStyles } from "@/lib/utils";
import "@/styles/globals.css";

const publicSans = Public_Sans({
  variable: "--font-public-sans",
  subsets: ["latin"],
});

const commitMono = localFont({
  variable: "--font-commit-mono",
  display: "swap",
  src: [
    { path: "../fonts/CommitMono-400-Regular.otf", weight: "400", style: "normal" },
    { path: "../fonts/CommitMono-700-Regular.otf", weight: "700", style: "normal" },
    { path: "../fonts/CommitMono-400-Italic.otf", weight: "400", style: "italic" },
    { path: "../fonts/CommitMono-700-Italic.otf", weight: "700", style: "italic" },
  ],
});

interface RootLayoutProps {
  children: React.ReactNode;
}

export default async function RootLayout({ children }: RootLayoutProps) {
  const hdrs = await headers();
  const appConfig = await getAppConfig(hdrs);
  const { pageTitle, pageDescription } = appConfig;
  const styles = getStyles(appConfig);

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn(
        publicSans.variable,
        commitMono.variable,
        "font-sans antialiased scroll-smooth"
      )}
    >
      <head>
        {styles && <style>{styles}</style>}
        <title>{pageTitle}</title>
        <meta name="description" content={pageDescription} />
        <ApplyThemeScript />
      </head>

      <body className="relative min-h-screen overflow-x-hidden bg-background">
        {children}

        {/* Floating Theme Toggle */}
        <div className="pointer-events-none fixed bottom-4 left-1/2 z-50 -translate-x-1/2">
          <ThemeToggle className="pointer-events-auto translate-y-14 transition-all duration-300 group-hover:translate-y-0" />
        </div>
      </body>
    </html>
  );
}
