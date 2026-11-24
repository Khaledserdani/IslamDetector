import { DefaultArtifactClient } from "@actions/artifact";
import { stat } from "node:fs/promises";
import { resolve } from "node:path";

function fail(message) {
  console.error(`::error::${message}`);
  process.exitCode = 1;
}

try {
  const name = (process.env.INPUT_NAME || "").trim();
  const relativePath = (process.env.INPUT_PATH || "").trim();
  const retentionDays = Number(process.env.INPUT_RETENTION_DAYS || "30");
  const workspace = process.env.GITHUB_WORKSPACE || process.cwd();

  if (!name) throw new Error("Artifact name is required.");
  if (!relativePath) throw new Error("Artifact path is required.");
  if (!Number.isInteger(retentionDays) || retentionDays < 1 || retentionDays > 90) {
    throw new Error("retention_days must be an integer from 1 to 90.");
  }
  if (!process.env.ACTIONS_RUNTIME_TOKEN || !process.env.ACTIONS_RESULTS_URL) {
    throw new Error("GitHub Actions artifact runtime credentials are unavailable.");
  }

  const filePath = resolve(workspace, relativePath);
  const fileInfo = await stat(filePath);
  if (!fileInfo.isFile() || fileInfo.size === 0) {
    throw new Error(`Artifact file is missing, empty, or not a regular file: ${relativePath}`);
  }

  const client = new DefaultArtifactClient();
  const uploaded = await client.uploadArtifact(name, [filePath], { retentionDays });
  console.log(`Artifact uploaded: name=${name}, id=${uploaded.id}, bytes=${uploaded.size}`);
} catch (error) {
  fail(error instanceof Error ? (error.stack || error.message) : String(error));
}
