import { execFile } from "node:child_process";
import { promisify } from "node:util";

import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

const execFileAsync = promisify(execFile);

const LANGUAGE_ID = "wodcraft";
const CLIENT_ID = "wodcraft";
const CLIENT_NAME = "WODCraft Language Server";
const MODULE = "wodcraft.lsp";
const INSTALL_HINT = "pip install 'wodcraft[lsp]'";

let client: LanguageClient | undefined;
let output: vscode.OutputChannel | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  output = vscode.window.createOutputChannel(CLIENT_NAME);
  context.subscriptions.push(output);

  context.subscriptions.push(
    vscode.commands.registerCommand("wodcraft.restartServer", async () => {
      await stopClient();
      await startClient(context);
    }),
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (
        event.affectsConfiguration("wodcraft.pythonPath") ||
        event.affectsConfiguration("wodcraft.server.enabled") ||
        event.affectsConfiguration("wodcraft.server.arguments")
      ) {
        await stopClient();
        await startClient(context);
      }
    }),
  );

  await startClient(context);
}

export async function deactivate(): Promise<void> {
  await stopClient();
}

function configuration(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration("wodcraft");
}

async function startClient(context: vscode.ExtensionContext): Promise<void> {
  const config = configuration();
  if (!config.get<boolean>("server.enabled", true)) {
    log("The language server is disabled (wodcraft.server.enabled).");
    return;
  }

  const python = config.get<string>("pythonPath", "python3").trim() || "python3";
  const extraArgs = config.get<string[]>("server.arguments", []);

  const problem = await checkInterpreter(python);
  if (problem !== undefined) {
    reportUnavailable(python, problem);
    return;
  }

  const args = ["-m", MODULE, ...extraArgs];
  const serverOptions: ServerOptions = {
    run: { command: python, args, transport: TransportKind.stdio },
    debug: { command: python, args: [...args, "--log-level", "DEBUG"], transport: TransportKind.stdio },
  };

  const channel = output ?? vscode.window.createOutputChannel(CLIENT_NAME);
  output = channel;

  const clientOptions: LanguageClientOptions = {
    documentSelector: [
      { scheme: "file", language: LANGUAGE_ID },
      { scheme: "untitled", language: LANGUAGE_ID },
    ],
    outputChannel: channel,
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.wod"),
    },
  };

  client = new LanguageClient(CLIENT_ID, CLIENT_NAME, serverOptions, clientOptions);
  context.subscriptions.push({ dispose: () => void stopClient() });

  try {
    await client.start();
    log(`Started: ${python} ${args.join(" ")}`);
  } catch (error) {
    client = undefined;
    reportUnavailable(python, describe(error));
  }
}

async function stopClient(): Promise<void> {
  const running = client;
  client = undefined;
  if (running === undefined) {
    return;
  }
  try {
    await running.stop();
  } catch (error) {
    log(`Could not stop the server cleanly: ${describe(error)}`);
  }
}

/** Returns undefined when `python -m wodcraft.lsp` can be imported, else the reason why not. */
async function checkInterpreter(python: string): Promise<string | undefined> {
  const probe = "import importlib.util as u, sys;" +
    "missing=[n for n in ('wodcraft.lsp','pygls') if u.find_spec(n) is None];" +
    "sys.exit('missing module(s): '+', '.join(missing) if missing else 0)";
  try {
    await execFileAsync(python, ["-c", probe], { timeout: 20_000 });
    return undefined;
  } catch (error) {
    const failure = error as NodeJS.ErrnoException & { stderr?: string };
    if (failure.code === "ENOENT") {
      return `interpreter not found: ${python}`;
    }
    const stderr = (failure.stderr ?? "").trim();
    return stderr.length > 0 ? stderr.split("\n").slice(-3).join(" ") : describe(error);
  }
}

function reportUnavailable(python: string, reason: string): void {
  const message =
    `WODCraft: the language server could not start with "${python}". ${reason}. ` +
    `Install it with \`${INSTALL_HINT}\`, then set \`wodcraft.pythonPath\` to that interpreter. ` +
    "Syntax highlighting and snippets keep working.";
  log(message);
  void vscode.window
    .showWarningMessage(message, "Open settings", "Show log")
    .then((choice) => {
      if (choice === "Open settings") {
        void vscode.commands.executeCommand("workbench.action.openSettings", "wodcraft.pythonPath");
      } else if (choice === "Show log") {
        output?.show(true);
      }
    });
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function log(message: string): void {
  output?.appendLine(`[${new Date().toISOString()}] ${message}`);
}
