import { headers } from "next/headers";
import { getAppConfig } from "@/lib/utils";

interface LayoutProps {
  children: React.ReactNode;
}

export default async function Layout({ children }: LayoutProps) {
  const hdrs = await headers();
  const { companyName, logo, logoDark } = await getAppConfig(hdrs);

  const lightLogo = logo;
  const darkLogo = logoDark || logo;

  return (
    <>
      <header className="fixed top-0 left-0 z-50 hidden w-full items-center justify-between px-6 py-4 md:flex">
        <a
          href="https://livekit.io"
          target="_blank"
          rel="noopener noreferrer"
          className="transition-transform duration-300 hover:scale-110"
          aria-label={`${companyName} homepage`}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={lightLogo}
            alt={`${companyName} Logo`}
            className="block h-7 w-auto dark:hidden"
          />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={darkLogo}
            alt={`${companyName} Logo`}
            className="hidden h-7 w-auto dark:block"
          />
        </a>

        <p className="font-mono text-xs font-semibold tracking-wider text-foreground uppercase">
          Built with{" "}
          <a
            href="https://docs.livekit.io/agents"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4 hover:text-primary"
          >
            LiveKit Agents
          </a>
        </p>
      </header>

      <main className="min-h-screen">{children}</main>
    </>
  );
}
