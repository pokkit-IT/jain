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
  target: "es2016",
  jsx: "transform",
  external: ["react", "react-native"],
  loader: { ".tsx": "tsx", ".ts": "ts" },
  logLevel: "info",
  // Override esbuild's __toESM wrapper — it creates a proxy that breaks
  // React 19's exports when loaded via new Function() + require shim.
  // Passthrough is safe because the PluginHost shim already returns the
  // real CJS module objects directly.
  banner: { js: "var __toESM = (mod) => mod;" },
});

console.log(`[yardsailing] built ${outfile}`);
