/**
 * Render a built (and optionally inline-populated) report.html headlessly and print what the
 * page mounted: a cheap end-to-end check that the bundle boots and the data binds.
 *   node scripts/smoke.mjs <report.html> [session-id-prefix]
 */
import { readFileSync } from "node:fs";
import { JSDOM, VirtualConsole } from "jsdom";

const [file, prefix = ""] = process.argv.slice(2);
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => {
  if (!/Not implemented/.test(String(e.message))) console.error("jsdom:", e.message);
});
vc.on("error", (...a) => console.error("page:", ...a));
// jsdom runs no ES modules. The single-file bundle has no imports left, so evaluating its text as a
// classic script once the DOM exists is equivalent to the deferred module a browser would run.
const parsed = new JSDOM(readFileSync(file, "utf8"));
const bundle = parsed.window.document.querySelector('script[type="module"]');
const html = parsed.serialize().replace(bundle.outerHTML, "");
const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost/report.html", virtualConsole: vc });
dom.window.eval(bundle.textContent);
dom.window.onerror = (m) => console.error("window error:", m);
await new Promise((r) => setTimeout(r, 2000));
const d = dom.window.document;
const rows = [...d.querySelectorAll("#SessionTable tbody tr")];
console.log(`rows=${rows.length} count=${d.querySelector("#SessionCount")?.textContent ?? "?"} meta=${d.querySelector("#ReportMeta")?.textContent ?? "?"}`);
if (!rows.length) {
  console.log("body:", d.body.textContent.slice(0, 300));
  process.exit(1);
}
const target = rows.find((r) => r.dataset.sid?.startsWith(prefix)) ?? rows[0];
console.log("row:", [...target.querySelectorAll("td")].map((td) => td.textContent.trim()).join(" | "));
dom.window.location.hash = "#session=" + target.dataset.sid;
await new Promise((r) => setTimeout(r, 800));
console.log(
  `session: ${d.querySelector("#SessionTitle")?.textContent} | header: ${d.querySelector("#ReportTitle")?.textContent} | meta rows=${d.querySelectorAll("#SessionMetaTable tr").length} | header links=${d.querySelectorAll("#ReportHeader a").length}`,
);
console.log("--xh-accent:", d.documentElement.style.getPropertyValue("--xh-accent"));

// Parity checklist: every element id the glossary names must be on the page once the session is open.
const IDS = [
  "ReportHeader",
  "ReportTitle",
  "ReportMeta",
  "ThemeToggle",
  "SessionView",
  "SessionHeader",
  "SessionTitle",
  "SessionMetaTable",
  "ChartAxisToggle",
  "TokenWaterfallChart",
  "ContextWindowChart",
  "ContextWindowNote",
  "ReconciliationPanel",
  "CostByTierPanel",
  "RatesApplied",
  "OutputPerTurnChart",
  "TurnTiersChart",
  "SkillCoveragePanelWrap",
  "SkillCoveragePanel",
  "SkillCoverageSummary",
  "ShowIgnored",
  "RecordKindsPanel",
  "SessionTurnTablePanel",
  "SessionTurnTable",
  "ViewToggle",
  "RecordViewToggle",
  "FinalMessagePanel",
  "FinalMessage",
];
const missing = IDS.filter((id) => !d.getElementById(id));
console.log(missing.length ? `MISSING ids: ${missing.join(", ")}` : `all ${IDS.length} glossary ids present`);
const turns = d.querySelectorAll("#SessionTurnTable tbody tr.SessionTurnRow").length;
dom.window.location.hash = `#session=${target.dataset.sid}&turn=2&view=detailed`;
await new Promise((r) => setTimeout(r, 1500));
const cards = d.querySelectorAll('.rec[data-el="RecordCard"]').length;
const labels = {};
for (const e of d.querySelectorAll("[data-el]")) labels[e.dataset.el] = (labels[e.dataset.el] || 0) + 1;
const top = Object.entries(labels)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 12)
  .map(([k, v]) => `${k}×${v}`)
  .join(", ");
console.log(`turn rows=${turns} | detailed view: RecordCards=${cards} | labels: ${top}`);
const back = d.getElementById("TokenAccumulationChart");
console.log(
  `overview TokenAccumulationChart present after returning: ${((dom.window.location.hash = "#"), await new Promise((r) => setTimeout(r, 800)), Boolean(d.getElementById("TokenAccumulationChart")))}${back ? "" : ""}`,
);
