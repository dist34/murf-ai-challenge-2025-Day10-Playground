import * as React from "react";
import { headers } from "next/headers";
import { SessionProvider } from "@/components/app/session-provider";
import { getAppConfig } from "@/lib/utils";

export default async function ComponentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const hdrs = await headers();
  const appConfig = await getAppConfig(hdrs);

  return (
    <SessionProvider appConfig={appConfig}>
      <div className="min-h-svh bg-muted/10 py-12 px-6">
        <div className="mx-auto max-w-4xl space-y-14">
          {/* Header */}
          <header className="space-y-4">
            <h1 className="text-4xl font-semibold tracking-tight">
              LiveKit UI Components
            </h1>

            <p className="text-muted-foreground max-w-prose text-lg leading-relaxed">
              A modern component toolkit for building polished, real-time,
              voice-powered interfaces with LiveKit Agents.
            </p>

            <p className="text-muted-foreground max-w-prose">
              Built with{" "}
              <a
                href="https://shadcn.com"
                className="underline underline-offset-2 hover:text-foreground"
              >
                Shadcn UI
              </a>
              ,{" "}
              <a
                href="https://motion.dev"
                className="underline underline-offset-2 hover:text-foreground"
              >
                Motion
              </a>{" "}
              and{" "}
              <a
                href="https://livekit.io"
                className="underline underline-offset-2 hover:text-foreground"
              >
                LiveKit
              </a>
              .
            </p>

            <p className="text-foreground font-medium">Fully open source.</p>
          </header>

          {/* Content */}
          <main className="space-y-24">{children}</main>
        </div>
      </div>
    </SessionProvider>
  );
}
