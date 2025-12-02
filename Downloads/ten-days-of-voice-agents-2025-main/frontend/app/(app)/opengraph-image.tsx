import { headers } from "next/headers";
import { ImageResponse } from "next/og";
import getImageSize from "buffer-image-size";
import mime from "mime";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { APP_CONFIG_DEFAULTS } from "@/app-config";
import { getAppConfig } from "@/lib/utils";

export const alt = "Open Graph Image";
export const size = { width: 1200, height: 628 };
export const contentType = "image/png";

type Dimensions = { width: number; height: number };
type ImageData = { base64: string; dimensions: Dimensions };

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

const isRemote = (uri: string) => uri.startsWith("http");
const filePathExists = (uri: string) => existsSync(join(process.cwd(), uri));

async function loadFile(uri: string): Promise<ArrayBuffer> {
  // Remote URL
  if (isRemote(uri)) {
    const res = await fetch(uri);
    if (!res.ok) throw new Error(`Failed to fetch ${uri}`);
    return res.arrayBuffer();
  }

  // Local filesystem
  if (filePathExists(uri)) {
    const file = await readFile(join(process.cwd(), uri));
    return file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength);
  }

  // Production fallback (load from public CDN)
  const publicUri = uri.replace("public/", "");
  const url = `https://${process.env.VERCEL_URL}/${publicUri}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch ${url}`);
  return res.arrayBuffer();
}

async function readImage(uri: string, fallback?: string): Promise<ImageData> {
  try {
    const data = await loadFile(uri);
    const buffer = Buffer.from(data);
    const type = mime.getType(uri);

    return {
      base64: `data:${type};base64,${buffer.toString("base64")}`,
      dimensions: getImageSize(buffer),
    };
  } catch (err) {
    if (fallback) return readImage(fallback);
    throw err;
  }
}

const scaleToHeight = (dim: Dimensions, h: number) => {
  const scale = h / dim.height;
  return { width: dim.width * scale, height: h };
};

const cleanTitle = (title: string) =>
  title === APP_CONFIG_DEFAULTS.pageTitle ? "Voice Agent" : title;

// -----------------------------------------------------------------------------
// Image Generation
// -----------------------------------------------------------------------------

export default async function Image() {
  const hdrs = await headers();
  const config = await getAppConfig(hdrs);

  const pageTitle = cleanTitle(config.pageTitle);

  // Logo / wordmark logic
  const logoUri = config.logoDark || config.logo;
  const isLocal = logoUri.includes("lk-logo");
  const wordmarkUri = isLocal
    ? "public/lk-wordmark.svg"
    : logoUri;

  // Load fonts
  const fonts = [];
  try {
    const mono = await loadFile("public/commit-mono-400-regular.woff");
    fonts.push({
      name: "CommitMono",
      data: mono,
      style: "normal" as const,
      weight: 400 as const,
    });
  } catch {}

  try {
    const everett = await loadFile("public/everett-light.woff");
    fonts.push({
      name: "Everett",
      data: everett,
      style: "normal" as const,
      weight: 300 as const,
    });
  } catch {}

  // Background
  const { base64: bg } = await readImage("public/opengraph-image-bg.png");

  // Wordmark
  const {
    base64: wordmark,
    dimensions: wDims,
  } = await readImage(wordmarkUri);
  const wSize = scaleToHeight(wDims, isLocal ? 32 : 64);

  // Logo
  const {
    base64: logo,
    dimensions: lDims,
  } = await readImage(logoUri, "public/lk-logo-dark.svg");
  const lSize = scaleToHeight(lDims, 24);

  // ---------------------------------------------------------------------------
  // Render OG Image
  // ---------------------------------------------------------------------------

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: size.width,
          height: size.height,
          backgroundImage: `url(${bg})`,
          backgroundSize: "100% 100%",
          backgroundPosition: "center",
        }}
      >
        {/* Wordmark */}
        <div
          style={{
            position: "absolute",
            top: 30,
            left: 30,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <img src={wordmark} width={wSize.width} height={wSize.height} />
        </div>

        {/* Logo */}
        <div
          style={{
            position: "absolute",
            top: 200,
            left: 460,
            display: "flex",
            alignItems: "center",
          }}
        >
          <img src={logo} width={lSize.width} height={lSize.height} />
        </div>

        {/* Title */}
        <div
          style={{
            position: "absolute",
            bottom: 100,
            left: 30,
            width: 380,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <div
            style={{
              backgroundColor: "#1F1F1F",
              padding: "2px 8px",
              borderRadius: 4,
              width: 72,
              fontSize: 12,
              fontFamily: "CommitMono",
              fontWeight: 600,
              color: "#999",
              letterSpacing: 0.8,
            }}
          >
            SANDBOX
          </div>

          <div
            style={{
              fontSize: 48,
              fontWeight: 300,
              fontFamily: "Everett",
              color: "white",
              lineHeight: 1,
            }}
          >
            {pageTitle}
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts,
    }
  );
}
