import { app, dialog } from "electron";

const startPath = process.argv[2] || process.cwd();

try {
  await app.whenReady();
  const result = await dialog.showOpenDialog({
    title: "Select project directory",
    defaultPath: startPath,
    properties: ["openDirectory"],
  });

  const selectedPath = result.canceled ? "" : result.filePaths[0] || "";
  process.stdout.write(`${JSON.stringify({ cancelled: result.canceled, path: selectedPath })}\n`);
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  process.stdout.write(`${JSON.stringify({ error: message })}\n`);
  process.exitCode = 1;
} finally {
  app.quit();
}
