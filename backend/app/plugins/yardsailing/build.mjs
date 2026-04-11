import { build } from "esbuild";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, mkdirSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname);

const entry = join(ROOT, "components", "index.ts");
const outfile = join(ROOT, "bundle", "yardsailing.js");
const outdir = dirname(outfile);
if (!existsSync(outdir)) mkdirSync(outdir, { recursive: true });

await build({
  entryPoints: [entry],
  bundle: true,
  outfile,
  format: "iife",
  platform: "neutral",
  target: "es2020",
  jsx: "transform",
  external: ["react", "react-native"],
  loader: { ".tsx": "tsx", ".ts": "ts" },
  logLevel: "info",
});

console.log(`[yardsailing] built ${outfile}`);
