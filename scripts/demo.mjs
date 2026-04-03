import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const appDir = path.join(root, "apps", "web");
const nodeModules = path.join(root, "node_modules");
const sqliteFile = path.join(root, "reasonforge.db");

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: root,
      stdio: "inherit",
      shell: false,
      ...options
    });

    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error(`${command} ${args.join(" ")} exited with ${code}`));
    });
  });
}

async function waitForBootstrap() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch("http://127.0.0.1:3000/api/bootstrap");
      if (response.ok) {
        return;
      }
    } catch {
      // Keep retrying until the dashboard becomes reachable.
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  throw new Error("Timed out waiting for http://127.0.0.1:3000/api/bootstrap");
}

async function main() {
  if (!existsSync(nodeModules)) {
    await run("pnpm", ["install"]);
  }

  process.env.REASONFORGE_DB_PATH = process.env.REASONFORGE_DB_PATH ?? sqliteFile;
  process.env.REASONFORGE_PREFILL_BENCHMARK = "1";
  process.env.REASONFORGE_PROJECT_ROOT = root;

  if (!existsSync(appDir)) {
    throw new Error("apps/web is missing. Install step scaffold did not run.");
  }

  const devServer = spawn("pnpm", ["--filter", "@reasonforge/web", "dev"], {
    cwd: root,
    stdio: "inherit",
    env: {
      ...process.env
    }
  });

  process.on("SIGINT", () => {
    devServer.kill("SIGINT");
  });

  process.on("SIGTERM", () => {
    devServer.kill("SIGTERM");
  });

  await waitForBootstrap();

  const opener = process.platform === "darwin" ? "open" : "xdg-open";
  const browser = spawn(opener, ["http://127.0.0.1:3000"], {
    cwd: root,
    detached: true,
    stdio: "ignore"
  });
  browser.unref();

  await new Promise((resolve, reject) => {
    devServer.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error(`ReasonForge dev server exited with ${code}`));
    });
  });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
