// Cross-platform Redocly docs builder (card O1.4).
// Works in sh, PowerShell and CI alike. Resolves the locally-installed redocly binary
// from node_modules/.bin so `npm run build:all` needs no global install and no network.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const SERVICES = [
  "api-gateway", "auth-user-service", "intake-profiling-service",
  "chat-orchestration-service", "persona-prompt-service", "rag-corpus-service",
  "goals-milestones-service", "progress-gamification-service", "insight-library-service",
  "feedback-service", "research-evaluation-service", "voice-service", "notification-service",
];

const only = process.argv[2] ? [process.argv[2]] : SERVICES;

const binName = process.platform === "win32" ? "redocly.cmd" : "redocly";
const localBin = join(process.cwd(), "node_modules", ".bin", binName);
const redocly = existsSync(localBin) ? localBin : binName; // fall back to PATH

for (const service of only) {
  console.log(`Building docs for ${service}...`);
  execFileSync(
    redocly,
    ["build-docs", service, "--config", "../redocly.yaml", "-o", `api/_site/${service}.html`],
    { stdio: "inherit", shell: process.platform === "win32" },
  );
}
console.log(`\nBuilt ${only.length} docs into docs/api/_site/`);
