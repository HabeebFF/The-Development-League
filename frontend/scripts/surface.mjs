// Prints the site's "surface": every page route and every API call site's path argument.
// Used by the redesign PRs to show routes and data fetches are unchanged:
//   node scripts/surface.mjs > after.txt   (compare with the same run on main)
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const walk = (dir) =>
  readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    if (f === "node_modules" || f.startsWith(".")) return [];
    return statSync(p).isDirectory() ? walk(p) : [p];
  });

const files = ["app", "components", "lib"].flatMap((d) => walk(join(root, d))).filter((f) => /\.(tsx?|mjs)$/.test(f) && !/\.test\.ts$/.test(f));

const routes = files
  .filter((f) => /\/page\.tsx$/.test(f))
  .map((f) => "/" + relative(join(root, "app"), f).replace(/\/?page\.tsx$/, ""))
  .sort();

// First argument of api(...), useApi(...), apiGet/apiPost-style helpers and fetch(...), normalised for spacing.
const calls = new Set();
const re = /\b(api|useApi|fetch|apiPost|apiPut|apiPatch|apiDelete|apiSend|send)\s*(<[^>(]*>)?\s*\(\s*([^,)]*(?:\([^)]*\)[^,)]*)*)/g;
for (const f of files) {
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(re)) {
    const arg = m[3].replace(/\s+/g, " ").trim();
    if (arg) calls.add(`${m[1]}(${arg})`);
  }
}

console.log("# routes");
for (const r of routes) console.log(r);
console.log("\n# api call arguments");
for (const c of [...calls].sort()) console.log(c);
