#!/usr/bin/env node
// Downloads every Stitch-hosted image referenced in lib/stitchImages.ts into
// public/stitch/ and rewrites the map to point at the local files, so the app
// no longer depends on Stitch/Google image URLs.
//
//   node scripts/fetch-stitch-images.mjs
//
// Requires Node 18+ (global fetch) and internet access. Safe to re-run: entries
// already pointing at /stitch/... are skipped.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const file = path.join(root, "lib", "stitchImages.ts");
const outDir = path.join(root, "public", "stitch");
const EXT = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/svg+xml": "svg", "image/gif": "gif", "image/avif": "avif" };

let src = await readFile(file, "utf8");
const entries = [...src.matchAll(/^\s*(i_[A-Za-z0-9]+):\s*"(https?:\/\/[^"]+)",?$/gm)];
if (!entries.length) {
  console.log("Nothing to download — all images are already local.");
  process.exit(0);
}
await mkdir(outDir, { recursive: true });

let ok = 0, failed = 0;
const queue = [...entries];
async function worker() {
  for (let m; (m = queue.shift()); ) {
    const [, key, url] = m;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const type = (res.headers.get("content-type") || "").split(";")[0].trim();
      const ext = EXT[type] || "jpg";
      await writeFile(path.join(outDir, `${key}.${ext}`), Buffer.from(await res.arrayBuffer()));
      src = src.replace(`"${url}"`, `"/stitch/${key}.${ext}"`);
      ok++;
    } catch (e) {
      failed++;
      console.warn(`✗ ${key}: ${e.message}`);
    }
  }
}
await Promise.all(Array.from({ length: 6 }, worker));
await writeFile(file, src.replace(/Remote URLs are Stitch-hosted;[^\n]*\n\/\/ to download[^\n]*/, "Images are served from /public/stitch."));
console.log(`Downloaded ${ok}, failed ${failed}. ${failed ? "Re-run to retry the failures (they still use remote URLs)." : "All images are local."}`);
