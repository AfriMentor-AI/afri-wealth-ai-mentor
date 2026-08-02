const { JSDOM } = require("jsdom");
const axeSource = require("fs").readFileSync(
  require.resolve("axe-core/axe.min.js"),
  "utf8"
);
const fs = require("fs");
const path = require("path");

const pages = [
  ".next/server/app/index.html",
  ".next/server/app/welcome.html",
  ".next/server/app/intake.html",
  ".next/server/app/persona.html",
  ".next/server/app/chat.html",
  ".next/server/app/goals.html",
  ".next/server/app/goals/action.html",
  ".next/server/app/library.html",
  ".next/server/app/progress.html",
];

async function auditPage(filePath) {
  const html = fs.readFileSync(filePath, "utf8");
  const dom = new JSDOM(html, {
    runScripts: "outside-only",
    resources: "usable",
    url: "http://localhost:3000/",
  });

  dom.window.eval(axeSource);

  return new Promise((resolve) => {
    dom.window.axe
      .run(dom.window.document, {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21aa"],
        },
      })
      .then((results) => resolve(results))
      .catch((err) => resolve({ error: err.message }));
  });
}

(async () => {
  let totalCritical = 0;
  let totalSerious = 0;
  const summary = [];

  for (const p of pages) {
    if (!fs.existsSync(p)) {
      summary.push({ page: p, error: "file not found" });
      continue;
    }
    try {
      const results = await auditPage(p);
      if (results.error) {
        summary.push({ page: p, error: results.error });
        continue;
      }
      const critical = results.violations.filter((v) => v.impact === "critical");
      const serious = results.violations.filter((v) => v.impact === "serious");
      totalCritical += critical.length;
      totalSerious += serious.length;
      summary.push({
        page: p,
        violations: results.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          nodes: v.nodes.length,
        })),
      });
    } catch (err) {
      summary.push({ page: p, error: err.message });
    }
  }

  console.log(JSON.stringify(summary, null, 2));
  console.log("\n=== TOTALS ===");
  console.log("Critical violations:", totalCritical);
  console.log("Serious violations:", totalSerious);
})();
