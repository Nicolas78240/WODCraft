/* eslint-disable no-restricted-syntax */
const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

function getConfig() {
  const cfg = vscode.workspace.getConfiguration('wodcraft');
  return {
    cliExec: cfg.get('cliExecutable', 'wodc'),
    catalog: cfg.get('catalogPath', ''),
    track: cfg.get('track', 'RX'),
    gender: cfg.get('gender', 'male'),
    preferredAsLabel: cfg.get('preferredAsLabel', true),
    modulesPath: cfg.get('modulesPath', 'modules'),
  };
}

let MOVEMENT_SUGGESTIONS = [];
let LAST_CATALOG = null;
let MOVEMENT_META = [];
let MODULE_IMPORTS = [];
let VARS_BY_REF = new Map(); // key: 'ns.name' or 'ns.name@vX' -> [varNames]
let MODULE_PATHS = new Map(); // key: 'ns.name' -> filepath

function loadCatalog(catalogPath) {
  try {
    if (!catalogPath) return;
    const full = path.isAbsolute(catalogPath)
      ? catalogPath
      : path.join(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd(), catalogPath);
    if (!fs.existsSync(full)) return;
    const raw = JSON.parse(fs.readFileSync(full, 'utf8'));
    const root = raw.movements || raw;
    const meta = [];
    if (root && typeof root === 'object') {
      for (const [id, spec] of Object.entries(root)) {
        const preferred = (spec && spec.preferred) ? String(spec.preferred) : id.replace(/_/g, ' ').replace(/\b\w/g, c=>c.toUpperCase());
        const cat = (spec && spec.category) ? String(spec.category) : '';
        const aliases = Array.isArray(spec?.aliases) ? spec.aliases : [];
        meta.push({ id, preferred, category: cat, aliases });
      }
    }
    MOVEMENT_META = meta.sort((a,b)=>a.id.localeCompare(b.id));
    // Build default suggestions with current config
    const cfg = getConfig();
    MOVEMENT_SUGGESTIONS = MOVEMENT_META.map(({id, preferred, category, aliases}) => {
      const label = cfg.preferredAsLabel ? preferred : id;
      const ci = new vscode.CompletionItem(label, vscode.CompletionItemKind.Value);
      ci.detail = (cfg.preferredAsLabel ? id : preferred) + (category ? ` — ${category}` : '');
      ci.insertText = id; // keep snake_case ids in code
      ci.filterText = [id, preferred, ...aliases].join(' ');
      ci.documentation = new vscode.MarkdownString(
        `Preferred: **${preferred}**\n\nID: \\`${id}\\`\n\nAliases: ${aliases.length ? aliases.join(', ') : '—'}\n\nCategory: ${category || '—'}`
      );
      return ci;
    });
    LAST_CATALOG = full;
  } catch (e) {
    // ignore
  }
}

function spawnLintUnified(exec, filePath) {
  return cp.spawn(exec, ['lint', filePath], { cwd: vscode.workspace.rootPath || undefined });
}

function spawnValidateUnified(exec, filePath) {
  return cp.spawn(exec, ['validate', filePath], { cwd: vscode.workspace.rootPath || undefined });
}

function spawnProgrammingLintUnified(exec, filePath) {
  return cp.spawn(exec, ['lint', filePath], { cwd: vscode.workspace.rootPath || undefined });
}

function spawnSessionCompileUnified(exec, filePath, modulesPath) {
  return cp.spawn(exec, ['session', filePath, '--modules-path', modulesPath, '--format', 'json'], { cwd: vscode.workspace.rootPath || undefined });
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
    // Load catalog suggestions if available
    if (cfg.catalog && cfg.catalog !== LAST_CATALOG) loadCatalog(cfg.catalog);
    try {
      // Write to a temp file for CLI
      const tmp = path.join(os.tmpdir(), `wodcraft_${Date.now()}.wod`);
      const text = doc.getText();
      fs.writeFileSync(tmp, text, 'utf8');
      // Heuristic: detect vNext (module/session/programming)
      const isVNext = /\bmodule\s+[A-Za-z]/.test(text) || /\bsession\s+"/.test(text) || /\bprogramming\s*\{/.test(text);
      const hasProgramming = /\bprogramming\s*\{/.test(text);
      const hasSession = /\bsession\s+\"/.test(text);
      let child;
      if (isVNext) {
        // Prefer programming lint, else validate
        child = hasProgramming ? spawnProgrammingLintUnified(cfg.cliExec, tmp) : spawnValidateUnified(cfg.cliExec, tmp);
      } else {
        child = spawnLintUnified(cfg.cliExec, tmp);
      }
      let out = '';
      let err = '';
      child.stdout.on('data', (d) => (out += d.toString()));
      child.stderr.on('data', (d) => (err += d.toString()));
      child.on('close', () => {
        fs.unlink(tmp, () => {});
        const diags = [];
        if (!isVNext) {
          const issues = parseIssues(out + '\n' + err);
          for (const issue of issues) {
            const severity = issue.level === 'ERROR' ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning;
            for (const range of findRanges(doc, issue)) {
              diags.push(new vscode.Diagnostic(range, `${issue.code} ${issue.msg}`, severity));
            }
          }
        } else {
          const textOut = (out + '\n' + err).trim();
          if (hasProgramming) {
            // Expect JSON with reports
            try {
              const parsed = JSON.parse(textOut);
              const reports = parsed.reports || [];
              for (const rep of reports) {
                const issues = rep.issues || [];
                for (const it of issues) {
                  const lvl = (it.level || 'warning').toLowerCase();
                  const sev = lvl === 'error' ? vscode.DiagnosticSeverity.Error : (lvl === 'info' ? vscode.DiagnosticSeverity.Information : vscode.DiagnosticSeverity.Warning);
                  diags.push(new vscode.Diagnostic(new vscode.Range(0,0,0,1), `${it.code || 'P000'} ${it.msg || 'programming issue'}`, sev));
                }
              }
            } catch {
              // Fallback to validate
              if (/Invalid syntax:/i.test(textOut)) {
                const msg = textOut.replace(/^.*Invalid syntax:\s*/i, '').split(/\n/)[0];
                diags.push(new vscode.Diagnostic(new vscode.Range(0,0,0,1), `V001 ${msg}`, vscode.DiagnosticSeverity.Error));
              }
            }
          } else {
            // Validate (syntax) and optionally session compile
            if (/Invalid syntax:/i.test(textOut)) {
              const msg = textOut.replace(/^.*Invalid syntax:\s*/i, '').split(/\n/)[0];
              diags.push(new vscode.Diagnostic(new vscode.Range(0,0,0,1), `V001 ${msg}`, vscode.DiagnosticSeverity.Error));
            } else if (hasSession) {
              // Try to compile session
              const child2 = spawnSessionCompileUnified(cfg.cliExec, tmp, cfg.modulesPath || 'modules');
              let out2 = '', err2 = '';
              child2.stdout.on('data', d => (out2 += d.toString()));
              child2.stderr.on('data', d => (err2 += d.toString()));
              child2.on('close', () => {
                const t2 = (out2 + '\n' + err2).trim();
                if (/Session compilation failed:/i.test(t2)) {
                  const msg = t2.replace(/^.*Session compilation failed:\s*/i, '').split(/\n/)[0];
                  diags.push(new vscode.Diagnostic(new vscode.Range(0,0,0,1), `C001 ${msg}`, vscode.DiagnosticSeverity.Error));
                }
                collection.set(doc.uri, diags);
              });
              return; // wait child2
            }
          }
        }
        collection.set(doc.uri, diags);
      });
    } catch (e) {
      collection.set(doc.uri, [new vscode.Diagnostic(new vscode.Range(0,0,0,1), String(e), vscode.DiagnosticSeverity.Error)]);
    }
  }

  context.subscriptions.push(vscode.workspace.onDidOpenTextDocument((doc)=>{ validate(doc); if (doc.languageId==='wodcraft') refreshModules(); }));
  context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((e) => debouncedValidate(e.document)));
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument((doc)=>{ validate(doc); if (doc.languageId==='wodcraft') refreshModules(); }));
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(() => {
    const cfg = getConfig();
    loadCatalog(cfg.catalog);
  }));

  if (vscode.window.activeTextEditor) {
    const doc = vscode.window.activeTextEditor.document;
    validate(doc);
    if (doc.languageId==='wodcraft') refreshModules();
  }

  // Completion provider: offer catalog movements and common keywords
  const KEYWORDS = ['WOD','TEAM','CAP','SCORE','TRACKS','BUYIN','CASHOUT','REST','BLOCK','TRACK','TIEBREAK','WORK','PARTITION','AMRAP','EMOM','FT','RFT','CHIPPER','TABATA','INTERVAL',
    // vNext
    'module','vars','warmup','skill','strength','wod','score','session','components','import','override','scoring','meta','exports','json','html','ics','programming','team','realized','achievements'];
  const keywordItems = KEYWORDS.map(k => {
    const it = new vscode.CompletionItem(k, vscode.CompletionItemKind.Keyword);
    return it;
  });
  const provider = vscode.languages.registerCompletionItemProvider({ language: 'wodcraft' }, {
    provideCompletionItems(doc, pos) {
      const cfg = getConfig();
      if (cfg.catalog && cfg.catalog !== LAST_CATALOG) loadCatalog(cfg.catalog);
      // Re-label movement suggestions based on current setting
      const movementItems = MOVEMENT_META.map(({id, preferred, category, aliases}) => {
        const label = cfg.preferredAsLabel ? preferred : id;
        const ci = new vscode.CompletionItem(label, vscode.CompletionItemKind.Value);
        ci.detail = (cfg.preferredAsLabel ? id : preferred) + (category ? ` — ${category}` : '');
        ci.insertText = id;
        ci.filterText = [id, preferred, ...aliases].join(' ');
        ci.documentation = new vscode.MarkdownString(
          `Preferred: **${preferred}**\n\nID: \\`${id}\\`\n\nAliases: ${aliases.length ? aliases.join(', ') : '—'}\n\nCategory: ${category || '—'}`
        );
        return ci;
      });
      // Module imports (vNext): suggest ns.name@vX scanned from workspace, especially after 'import '
      const line = doc.lineAt(pos.line).text.substr(0, pos.character);
      let moduleItems = MODULE_IMPORTS.map((m)=>{
        const ci = new vscode.CompletionItem(m, vscode.CompletionItemKind.Module);
        ci.insertText = m;
        ci.detail = 'module (workspace)';
        return ci;
      });
      if (!/\bimport\s+$/i.test(line)) {
        // If not after 'import ', de-prioritize module items
        moduleItems = moduleItems.slice(0, 10);
      }
      // Context-aware suggestions
      const contextItems = [];
      // Units after '@'
      if (/@\s*\d*\s*$/.test(line) || /@\s*$/.test(line)) {
        ['kg','lb','%1RM'].forEach(u => {
          const it = new vscode.CompletionItem(u, vscode.CompletionItemKind.Unit);
          it.insertText = u;
          it.detail = 'unit';
          contextItems.push(it);
        });
      }
      // Tempo common patterns
      if (/\btempo\s*$/i.test(line) || /\btempo\s+"?[0-9X]{0,4}$/.test(line)) {
        ['31X1','30X1','32X1','20X2','41X1','11X1'].forEach(t => {
          const it = new vscode.CompletionItem(t, vscode.CompletionItemKind.Value);
          it.insertText = t;
          it.detail = 'tempo';
          contextItems.push(it);
        });
      }
      // Time durations for AMRAP/EMOM/cap
      if (/(AMRAP|EMOM)\s*$/i.test(line) || /\bcap\s*$/i.test(line)) {
        ['5:00','10:00','12:00','15:00','20:00','30:00'].forEach(d => {
          const it = new vscode.CompletionItem(d, vscode.CompletionItemKind.Value);
          it.insertText = d;
          it.detail = 'duration';
          contextItems.push(it);
        });
      }
      // Inside override { ... } suggest common vars
      try {
        const textUpto = doc.getText(new vscode.Range(new vscode.Position(0,0), pos));
        const lastOverride = textUpto.lastIndexOf('override');
        const lastOpen = textUpto.lastIndexOf('{');
        const lastClose = textUpto.lastIndexOf('}');
        if (lastOverride !== -1 && lastOpen > lastOverride && lastClose < lastOpen) {
          // Find nearby import ref on the same line or previous lines
          let refId = null;
          for (let ln = pos.line; ln >= Math.max(0, pos.line - 3); ln--) {
            const ltext = doc.lineAt(ln).text;
            const m = /\bimport\s+([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)(?:@v[0-9.]+)?/i.exec(ltext);
            if (m) { refId = m[1]; break; }
          }
          let varList = [];
          if (refId) {
            varList = getVarsForRef(refId);
          }
          if (!varList || !varList.length) {
            varList = ['percent_1rm','tempo','sets','reps'];
          }
          for (const v of varList) {
            const it = new vscode.CompletionItem(v.name || v, vscode.CompletionItemKind.Variable);
            it.insertText = (v.name || v);
            if (typeof v === 'string') {
              it.detail = 'override var';
            } else {
              const t = v.type ? (v.type.name + (v.type.units?`(${v.type.units.join('|')})`:'')) : '';
              const d = v.default != null ? ` default=${v.default}` : '';
              it.detail = `override var — ${t}${d}`;
              if (v.constraints && Array.isArray(v.constraints)) {
                const lines = v.constraints.map(c=>`- ${c.key} = ${c.value}`).join('\n');
                it.documentation = new vscode.MarkdownString(`Constraints:\n${lines}`);
              }
            }
            contextItems.push(it);
          }
        }
      } catch {}
      // Combine keyword + modules + movements
      return [...keywordItems, ...moduleItems, ...contextItems, ...movementItems];
    }
  }, ['.', '@', '"', ':']);
  context.subscriptions.push(provider);

  // Hover provider: show module vars on import line
  const hoverProv = vscode.languages.registerHoverProvider({ language: 'wodcraft' }, {
    provideHover(doc, pos) {
      const line = doc.lineAt(pos.line).text;
      const m = /\bimport\s+([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)(?:@v[0-9.]+)?/i.exec(line);
      if (!m) return;
      const ref = m[1];
      const vars = getVarsForRef(ref) || [];
      if (!vars.length) return;
      const md = new vscode.MarkdownString();
      md.appendMarkdown(`**Module Vars for ${ref}**\n\n`);
      for (const v of vars) {
        const t = v.type ? (v.type.name + (v.type.units?`(${v.type.units.join('|')})`:'')) : '';
        const d = v.default != null ? ` default=${v.default}` : '';
        md.appendMarkdown(`- \\`${v.name}\\` — ${t}${d}\n`);
        if (v.constraints && Array.isArray(v.constraints)) {
          v.constraints.forEach(c=> md.appendMarkdown(`   - ${c.key} = ${c.value}\n`));
        }
      }
      md.isTrusted = true;
      return new vscode.Hover(md);
    }
  });
  context.subscriptions.push(hoverProv);

  // CodeLens: open module file from import line
  const codeLensProv = vscode.languages.registerCodeLensProvider({ language: 'wodcraft' }, {
    provideCodeLenses(doc) {
      const lenses = [];
      for (let i=0; i<Math.min(doc.lineCount, 1000); i++) {
        const text = doc.lineAt(i).text;
        const m = /\bimport\s+([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)(?:@v[0-9.]+)?/i.exec(text);
        if (m) {
          const ref = m[1];
          const file = MODULE_PATHS.get(ref);
          if (file) {
            const range = new vscode.Range(i, 0, i, text.length);
            lenses.push(new vscode.CodeLens(range, { command: 'wodcraft.openModule', title: 'Open Module', arguments: [file] }));
          }
        }
      }
      return lenses;
    }
  });
  context.subscriptions.push(codeLensProv);

  // Command to open module
  const openCmd = vscode.commands.registerCommand('wodcraft.openModule', (file) => {
    if (!file) return;
    vscode.workspace.openTextDocument(file).then(doc => vscode.window.showTextDocument(doc));
  });
  context.subscriptions.push(openCmd);
}

function refreshModules() {
  try {
    const folders = vscode.workspace.workspaceFolders || [];
    if (!folders.length) return;
    const root = folders[0].uri.fsPath;
    const globs = ['**/*.wod'];
    const mods = new Set();
    const varsMap = new Map();
    for (const g of globs) {
      const files = vscode.workspace.findFiles(g, '**/node_modules/**', 2000);
      files.then(uris => {
        uris.forEach(uri => {
          try {
            const content = require('fs').readFileSync(uri.fsPath, 'utf8');
            const re = /\bmodule\s+([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\s+v(\d+(?:\.\d+)?)\b/g;
            let m;
            while ((m = re.exec(content))) {
              mods.add(`${m[1]}@v${m[2]}`);
              MODULE_PATHS.set(m[1], uri.fsPath);
              // Extract vars block
              const varsBlock = /\bvars\s*\{([\s\S]*?)\}/m.exec(content);
              if (varsBlock && varsBlock[1]) {
                const vars = [];
                const lines = varsBlock[1].split(/\n/);
                for (const ln of lines) {
                  const mm = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:/.exec(ln);
                  if (mm) vars.push(mm[1]);
                }
                if (vars.length) {
                  varsMap.set(m[1], vars.map(n=>({name:n})));
                  varsMap.set(`${m[1]}@v${m[2]}`, vars.map(n=>({name:n})));
                }
              }
            }
          } catch {}
        });
        MODULE_IMPORTS = Array.from(mods).sort();
        VARS_BY_REF = varsMap;
      });
    }
  } catch {}
}

function getVarsForRef(refId) {
  // Try cache
  if (VARS_BY_REF.has(refId)) return VARS_BY_REF.get(refId);
  // Try without version
  const base = refId.split('@')[0];
  if (VARS_BY_REF.has(base)) return VARS_BY_REF.get(base);
  // Try parse module file via vNext CLI
  try {
    const file = MODULE_PATHS.get(base);
    if (!file) return [];
    const cfg = getConfig();
    const res = cp.spawnSync(cfg.cliExec, ['parse', file], { cwd: vscode.workspace.rootPath || undefined });
    if (res.status === 0) {
      const parsed = JSON.parse((res.stdout||'').toString());
      const mods = parsed.modules || [];
      if (mods.length) {
        const body = mods[0].body || [];
        let varsNode = null;
        for (const it of (Array.isArray(body)?body: [body])) {
          if (it && it.type === 'VARS') { varsNode = it; break; }
          // body might be nested under MODULE_BODY/children
          if (it && it.type === 'MODULE_BODY' && Array.isArray(it.children)) {
            for (const ch of it.children) {
              if (ch && ch.type === 'BODY' && Array.isArray(ch.children)) {
                for (const ch2 of ch.children) {
                  if (ch2 && ch2.type === 'VARS') { varsNode = ch2; break; }
                }
              }
            }
          }
        }
        const vars = (varsNode && Array.isArray(varsNode.decls)) ? varsNode.decls.map(d => ({
          name: d.name,
          type: d.type,
          default: d.default,
          constraints: d.constraints,
        })) : [];
        VARS_BY_REF.set(base, vars);
        VARS_BY_REF.set(refId, vars);
        return vars;
      }
    }
  } catch {}
  return [];
}

function deactivate() {}

module.exports = { activate, deactivate };
