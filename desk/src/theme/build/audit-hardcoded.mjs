// Fails on hardcoded colors in desk/src outside the allowlist. Usage: node audit-hardcoded.mjs [--list]
import fs from "node:fs";
import path from "node:path";
import { THEME_DIR } from "./lib/model.mjs";

const SRC = path.resolve(THEME_DIR, "..");
const allow = JSON.parse(
  fs.readFileSync(path.join(THEME_DIR, "tokens/audit-allow.json"), "utf8")
);
const EXT = new Set([".vue", ".ts", ".js", ".css", ".scss", ".svg"]);
const SKIP_DIRS = new Set(["node_modules", "theme", "types"]);
const families =
  "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const patterns = [
  {
    kind: "hex",
    re: /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|(?=[0-9]*[a-fA-F])[0-9a-fA-F]{3})\b(?![0-9a-fA-F])/g,
  },
  { kind: "rgb/hsl", re: /\b(?:rgba?|hsla?)\(\s*\d/g },
  {
    kind: "tailwind",
    re: new RegExp(
      `\\b(?:bg|text|border|ring|fill|stroke|from|to|via|outline|divide|placeholder|decoration|accent|caret|shadow)-(?:(?:${families})-\\d{2,3}|white|black)(?![\\w-])`,
      "g"
    ),
  },
];

function* walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.isDirectory()) {
      if (!SKIP_DIRS.has(e.name)) yield* walk(path.join(dir, e.name));
    } else if (EXT.has(path.extname(e.name))) yield path.join(dir, e.name);
  }
}

const rel = (f) => path.relative(SRC, f).replace(/\\/g, "/");
const matches = (file, pattern) =>
  pattern.endsWith("/**")
    ? file.startsWith(pattern.slice(0, -2))
    : file === pattern;
const allowed = (file, kind) =>
  allow.files.some(
    (a) => matches(file, a.path) && (!a.kinds || a.kinds.includes(kind))
  );
const findings = [];

for (const file of walk(SRC)) {
  const r = rel(file);
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, i) => {
    for (const { kind, re } of patterns) {
      re.lastIndex = 0;
      for (const m of line.matchAll(re)) {
        if (
          /href=["']#|&#|url\(#/.test(
            line.slice(Math.max(0, m.index - 6), m.index + 1)
          )
        )
          continue;
        if (!allowed(r, kind))
          findings.push({ file: r, line: i + 1, kind, text: m[0] });
      }
    }
  });
}

// An entry marked unreferenced stops being allowed the moment something imports it.
const sources = [...walk(SRC)].filter((f) => !f.endsWith(".svg"));
for (const a of allow.files.filter((e) => e.unreferencedBy)) {
  for (const file of sources) {
    if (matches(rel(file), a.path)) continue;
    if (fs.readFileSync(file, "utf8").includes(a.unreferencedBy)) {
      findings.push({
        file: rel(file),
        line: 0,
        kind: "allowlist",
        text: `now references ${a.unreferencedBy} (${a.path}); convert it to tokens and drop the allowlist entry`,
      });
    }
  }
}

const byFile = new Map();
for (const f of findings) byFile.set(f.file, (byFile.get(f.file) || 0) + 1);
if (process.argv.includes("--list"))
  for (const f of findings)
    console.log(`${f.file}:${f.line}  ${f.kind}  ${f.text}`);

if (findings.length) {
  console.error(
    `\n${findings.length} hardcoded color(s) in ${byFile.size} file(s):`
  );
  for (const [file, n] of [...byFile].sort((a, b) => b[1] - a[1]).slice(0, 25))
    console.error(`  ${String(n).padStart(4)}  ${file}`);
  console.error(
    "\nUse a semantic token (bg-surface-*, text-ink-*, border-outline-*, currentColor, or useChartTheme) or add a reasoned entry to tokens/audit-allow.json."
  );
  process.exit(1);
}
console.log("audit: no hardcoded colors outside the allowlist.");
