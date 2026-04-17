import { build } from "esbuild";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname);

const entry = join(ROOT, "components", "index.ts");
const outfile = join(ROOT, "bundle", "custody.js");
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
  external: ["react", "react-native", "@react-native-community/datetimepicker"],
  loader: { ".tsx": "tsx", ".ts": "ts" },
  logLevel: "info",
});

let content = readFileSync(outfile, "utf-8");
content = content.replace(
  /var __toESM = \([^)]*\) => \([^;]*\);/,
  "var __toESM = (mod) => mod;",
);
writeFileSync(outfile, content);

console.log(`[custody] built ${outfile}`);
