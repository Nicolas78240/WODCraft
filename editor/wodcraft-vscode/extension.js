/* eslint-disable no-restricted-syntax */
const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

function getConfig() {
  const cfg = vscode.workspace.getConfiguration('wodcraft');
  return {
    python: cfg.get('pythonPath', 'python3'),
    cli: cfg.get('cliPath', 'wodc_merged.py'),
    catalog: cfg.get('catalogPath', ''),
    track: cfg.get('track', 'RX'),
    gender: cfg.get('gender', 'male'),
  };
}

function spawnLint(python, cli, filePath, opts) {
  const args = [cli, 'lint', filePath, '--track', opts.track, '--gender', opts.gender];
  if (opts.catalog) args.push('--catalog', opts.catalog);
  return cp.spawn(python, args, { cwd: vscode.workspace.rootPath || undefined });
}

function parseIssues(output) {
  const issues = [];
  const re = /^(WARNING|ERROR)\s+([A-Z]\d{3})\s+([^:]+):\s+(.*)$/;
  for (const line of output.split(/\r?\n/)) {
    const m = re.exec(line.trim());
    if (m) {
      issues.push({ level: m[1], code: m[2], path: m[3], msg: m[4] });
    }
  }
  return issues;
}

function findRanges(doc, issue) {
  const text = doc.getText();
  const ranges = [];
  function addRangeForPattern(pattern) {
    const idx = text.indexOf(pattern);
    if (idx >= 0) {
      const pos = doc.positionAt(idx);
      ranges.push(new vscode.Range(pos, doc.positionAt(idx + pattern.length)));
    }
  }
  // Heuristics by code
  if (issue.code === 'W001') {
    const m = /Unknown movement '([^']+)'/.exec(issue.msg);
    if (m) addRangeForPattern(m[1]);
  } else if (issue.code === 'W002') {
    const m = /Suspicious load '([^']+)'/.exec(issue.msg);
    if (m) addRangeForPattern(m[1]);
  } else if (issue.code === 'E010') {
    // REST must be > 0
    addRangeForPattern('REST 0s');
  } else if (issue.code === 'E020') {
    // EMOM has no slots -> highlight BLOCK EMOM
    addRangeForPattern('BLOCK EMOM');
  } else if (issue.code === 'W050') {
    const m = /Alias '([^']+)' ->/.exec(issue.msg);
    if (m) addRangeForPattern(m[1]);
  }
  if (ranges.length === 0) {
    ranges.push(new vscode.Range(0, 0, 0, 1));
  }
  return ranges;
}

function activate(context) {
  const collection = vscode.languages.createDiagnosticCollection('wodcraft');
  context.subscriptions.push(collection);

  let timer = null;
  const debouncedValidate = (doc) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => validate(doc), 500);
  };

  async function validate(doc) {
    if (!doc || doc.languageId !== 'wodcraft') return;
    const cfg = getConfig();
    try {
      // Write to a temp file for CLI
      const tmp = path.join(os.tmpdir(), `wodcraft_${Date.now()}.wod`);
      fs.writeFileSync(tmp, doc.getText(), 'utf8');
      const child = spawnLint(cfg.python, cfg.cli, tmp, cfg);
      let out = '';
      let err = '';
      child.stdout.on('data', (d) => (out += d.toString()));
      child.stderr.on('data', (d) => (err += d.toString()));
      child.on('close', () => {
        fs.unlink(tmp, () => {});
        const diags = [];
        const issues = parseIssues(out + '\n' + err);
        for (const issue of issues) {
          const severity = issue.level === 'ERROR' ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning;
          for (const range of findRanges(doc, issue)) {
            diags.push(new vscode.Diagnostic(range, `${issue.code} ${issue.msg}`, severity));
          }
        }
        collection.set(doc.uri, diags);
      });
    } catch (e) {
      collection.set(doc.uri, [new vscode.Diagnostic(new vscode.Range(0,0,0,1), String(e), vscode.DiagnosticSeverity.Error)]);
    }
  }

  context.subscriptions.push(vscode.workspace.onDidOpenTextDocument(validate));
  context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((e) => debouncedValidate(e.document)));
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument(validate));

  if (vscode.window.activeTextEditor) {
    validate(vscode.window.activeTextEditor.document);
  }
}

function deactivate() {}

module.exports = { activate, deactivate };

