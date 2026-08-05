import { spawnSync } from "node:child_process";

const target = process.argv[2];
let passthroughArgs = process.argv.slice(3);

const scripts = {
  setup: {
    win32: ["powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/setup.ps1"]],
    posix: ["bash", ["scripts/setup.sh"]],
  },
  "run-dev": {
    win32: ["powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/run-dev.ps1"]],
    posix: ["bash", ["scripts/run-dev.sh"]],
  },
};

if (!Object.hasOwn(scripts, target)) {
  console.error(`Unknown platform script: ${target}`);
  process.exit(2);
}

const npmConfigFlagMap = [
  ["npm_config_skip_npm", "--skip-npm"],
  ["npm_config_skip_python", "--skip-python"],
  ["npm_config_skip_qdrant_pull", "--skip-qdrant-pull"],
  ["npm_config_skip_qdrant", "--skip-qdrant"],
];

for (const [envName, flag] of npmConfigFlagMap) {
  if (process.env[envName] === "true" && !passthroughArgs.includes(flag)) {
    passthroughArgs.push(flag);
  }
}

if (process.env.npm_config_workspace_root && !passthroughArgs.includes("--workspace-root")) {
  passthroughArgs.push("--workspace-root", process.env.npm_config_workspace_root);
}

if (process.env.npm_config_backend_port && !passthroughArgs.includes("--backend-port")) {
  passthroughArgs.push("--backend-port", process.env.npm_config_backend_port);
}

if (process.env.npm_config_frontend_port && !passthroughArgs.includes("--frontend-port")) {
  passthroughArgs.push("--frontend-port", process.env.npm_config_frontend_port);
}

const platform = process.platform === "win32" ? "win32" : "posix";
const [command, args] = scripts[target][platform];

if (platform === "win32") {
  const powershellFlagMap = new Map([
    ["--skip-npm", "-SkipNpm"],
    ["--skip-python", "-SkipPython"],
    ["--skip-qdrant-pull", "-SkipQdrantPull"],
    ["--skip-qdrant", "-SkipQdrant"],
    ["--workspace-root", "-WorkspaceRoot"],
    ["--backend-port", "-BackendPort"],
    ["--frontend-port", "-FrontendPort"],
  ]);
  passthroughArgs = passthroughArgs.map((arg) => powershellFlagMap.get(arg) ?? arg);
}

const result = spawnSync(command, [...args, ...passthroughArgs], {
  stdio: "inherit",
  shell: false,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
