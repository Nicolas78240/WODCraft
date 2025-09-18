import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { existsSync } from 'node:fs';
import { writeFile, unlink } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const LOG_PREFIX = '[wodcraft-mcp]';
const DEBUG = process.env.WODCRAFT_MCP_DEBUG === '1';
function log(...args) {
    if (!DEBUG)
        return;
    console.error(LOG_PREFIX, ...args);
}
function logError(...args) {
    if (!DEBUG)
        return;
    console.error(LOG_PREFIX, ...args);
}
const STRUCTURE_GUIDE = [
    '# WODCraft DSL — Guide rapide',
    '',
    '## 1. Bloc minimal',
    '```wod',
    'module wod.example.progressive v1 {',
    '  wod AMRAP 20:00 {',
    '    20/16 cal Row',
    '    REST 2:00',
    '    15m Farmer_Carry PROGRESS("+15m/round") @22.5kg/15kg',
    '  }',
    '',
    '  score AMRAP {',
    '    rounds: Rounds',
    '    meters: Distance(m)',
    '  }',
    '}',
    '```',
    '',
    '## 2. Syntaxe d\'une ligne',
    '1. Quantité : `10`, `200m`, `20/16 cal`, `MAXREP`',
    '2. Mouvement snake_case : `Farmer_Carry`',
    '3. Progression optionnelle : `PROGRESS("+15m/round")`',
    '4. Charge optionnelle : `@95lb/65lb`, `@RX(M:24kg,F:16kg)`',
    '5. Tempo / note optionnelles',
    '',
    '## 3. Types de score supportés',
    '- `Time`, `Rounds`, `Reps`',
    '- `Distance(m)`, `Load(kg)`',
    '- `Calories`, `Tempo`',
    '- `Int`, `Float`, `Bool`, `String`',
    '',
    '## 4. Multi-blocs avec repos',
    '```wod',
    'module wod.day.sample v1 {',
    '  wod AMRAP 7:00 {',
    '    10 Push_up',
    '    10 Sit_up',
    '    10 Pull_up',
    '    REST 2:00',
    '  }',
    '',
    '  wod EMOM 10:00 {',
    '    5 Thruster @43kg/30kg',
    '    5 Burpee',
    '    REST 2:00',
    '  }',
    '',
    '  wod ForTime cap 10:00 {',
    '    21 Snatch @43kg/30kg',
    '    21 Pull_up',
    '    15 Snatch @43kg/30kg',
    '    15 Pull_up',
    '    9 Snatch @43kg/30kg',
    '    9 Pull_up',
    '  }',
    '}',
    '```',
    '',
    '## 5. Orchestration via `session`',
    '```wod',
    'session "Pull Pyramid" {',
    '  components {',
    '    wod import wod.block.a@v1',
    '    wod import wod.block.b@v1',
    '    wod import wod.block.c@v1',
    '  }',
    '  scoring { wod ForTime time+reps }',
    '}',
    '```',
    '',
    '## 6. Rappels pratiques',
    '- Pas de commentaires `#` : utiliser `//` ou `notes:`',
    '- Time cap via `ForTime cap 10:00` ou `notes`',
    '- Les repos se déclarent avec `REST 2:00`',
    '- Modules en minuscules : `module wod.category.name v1`',
    '- Mouvement en snake_case (`pull_up`, `farmer_carry`)',
].join('\n');
const RESOURCE_REGISTRY = [];
function registerResource(name, uri, meta, loader) {
    RESOURCE_REGISTRY.push({ name, uri, title: meta.title, description: meta.description, loader });
    server.registerResource(name, uri, meta, async () => {
        const { text, mimeType } = await loader();
        return { contents: [{ uri, text, mimeType }] };
    });
}
const server = new McpServer({ name: 'wodcraft-mcp', version: '0.1.0' });
// ---- Config ----
function getEnv(name, def) {
    return process.env[name] ?? def;
}
function resolveCliArgs() {
    const envCli = getEnv('WODCRAFT_CLI');
    if (envCli) {
        return envCli
            .split(/\s+/)
            .map((part) => part.trim())
            .filter(Boolean);
    }
    // dev install: attempt merged script, otherwise fallback to module
    const thisFile = fileURLToPath(import.meta.url);
    const guess = path.resolve(path.dirname(thisFile), '../../wodc_merged.py');
    if (existsSync(guess)) {
        return [guess];
    }
    return ['-m', 'wodcraft.cli'];
}
const DEFAULTS = {
    PYTHON: getEnv('WODCRAFT_PYTHON', 'python3'),
    CLI_ARGS: resolveCliArgs(),
    CATALOG: getEnv('WODCRAFT_CATALOG', ''),
    TRACK: getEnv('WODCRAFT_TRACK', 'RX'),
    GENDER: getEnv('WODCRAFT_GENDER', 'male'),
};
log('Booting server with config', { ...DEFAULTS, CLI_ARGS: DEFAULTS.CLI_ARGS.join(' ') });
async function runWithTimeout(cmd, args, context, timeoutMs = 4000) {
    log(`${context.tool}: spawning`, cmd, args.join(' '));
    return new Promise((resolve) => {
        const child = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'] });
        let stdout = '';
        let stderr = '';
        const timer = setTimeout(() => {
            const message = `Process timeout after ${timeoutMs}ms`;
            stderr += `\n${message}`;
            logError(`${context.tool}: ${message}`);
            try {
                child.kill('SIGKILL');
            }
            catch { }
        }, timeoutMs);
        child.stdout.on('data', (d) => (stdout += d.toString()));
        child.stderr.on('data', (d) => (stderr += d.toString()));
        child.on('close', (code) => {
            clearTimeout(timer);
            const payload = { code: code ?? 0, stdout, stderr };
            const outcome = payload.code === 0 ? 'completed' : `exited with ${payload.code}`;
            log(`${context.tool}: ${outcome}`);
            const stdoutPreview = payload.stdout.trim();
            if (stdoutPreview) {
                const sample = stdoutPreview.length > 400 ? `${stdoutPreview.slice(0, 400)}…` : stdoutPreview;
                log(`${context.tool}: stdout`, sample);
            }
            const stderrPreview = payload.stderr.trim();
            if (stderrPreview) {
                const sample = stderrPreview.length > 400 ? `${stderrPreview.slice(0, 400)}…` : stderrPreview;
                logError(`${context.tool}: stderr`, sample);
            }
            resolve(payload);
        });
    });
}
async function lintViaPython(dsl) {
    const f = path.join(tmpdir(), `wodcraft_${Date.now()}.wod`);
    await writeFile(f, dsl, 'utf8');
    const args = [...DEFAULTS.CLI_ARGS, 'lint', f];
    if (DEFAULTS.CATALOG)
        args.push('--catalog', DEFAULTS.CATALOG);
    const { stdout, stderr } = await runWithTimeout(DEFAULTS.PYTHON, args, { tmpFile: f, tool: 'lint' });
    await unlink(f).catch(() => { });
    const lines = (stdout + '\n' + stderr).split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    const re = /^(WARNING|ERROR)\s+([A-Z]\d{3})\s+([^:]+):\s+(.*)$/;
    return lines
        .map((ln) => re.exec(ln))
        .filter(Boolean)
        .map((m) => ({ level: m[1], code: m[2], path: m[3], message: m[4] }));
}
async function parseViaPython(dsl) {
    const f = path.join(tmpdir(), `wodcraft_${Date.now()}.wod`);
    await writeFile(f, dsl, 'utf8');
    const args = [...DEFAULTS.CLI_ARGS, 'parse', f];
    if (DEFAULTS.CATALOG)
        args.push('--catalog', DEFAULTS.CATALOG);
    const res = await runWithTimeout(DEFAULTS.PYTHON, args, { tmpFile: f, tool: 'parse' });
    await unlink(f).catch(() => { });
    if (res.code !== 0) {
        const message = res.stderr.trim() || res.stdout.trim() || `parse exited with code ${res.code}`;
        throw new Error(message);
    }
    const text = res.stdout.trim();
    try {
        return JSON.parse(text);
    }
    catch (e) {
        logError('parseViaPython: invalid JSON payload', text);
        throw new Error('Failed to parse AST JSON');
    }
}
// Simple name generator
function defaultName(params) {
    return `${params.mode.toLowerCase()}-${params.duration}`.replace(/\s+/g, "-");
}
// ---- Generator (very naive template) ----
function generateDsl(opts) {
    const title = opts.name ?? defaultName({ mode: opts.mode, duration: opts.duration });
    const team = opts.teamSize ?? 1;
    const lines = [];
    // Simple heuristics
    if (opts.focus?.includes('legs'))
        lines.push('20 air_squat;');
    else if (opts.focus?.includes('pull'))
        lines.push('10 pullups;');
    else
        lines.push('15 burpees;');
    if (opts.equipment?.includes('kettlebell'))
        lines.push('12 kettlebell_swing @24/16kg;');
    else if (opts.equipment?.includes('barbell'))
        lines.push('10 thrusters @43/30kg;');
    else if (opts.equipment?.includes('dumbbell'))
        lines.push('10 dumbbell_snatch @22.5/15kg;');
    else
        lines.push('10 pushups;');
    lines.push('200m run;');
    let head = '';
    if (opts.mode === 'AMRAP' || opts.mode === 'EMOM')
        head = `BLOCK ${opts.mode} ${opts.duration}`;
    else if (opts.mode === 'FT')
        head = 'BLOCK FT';
    else if (opts.mode === 'RFT')
        head = 'BLOCK RFT 3';
    else if (opts.mode === 'CHIPPER')
        head = 'BLOCK CHIPPER';
    const block = `${head} {\n  ${lines.join('\n  ')}\n}`;
    const tracks = 'TRACKS [RX, INTERMEDIATE, SCALED]';
    const cap = opts.mode === 'AMRAP' || opts.mode === 'EMOM' ? `\nCAP ${opts.duration}` : '';
    return `WOD "${title}"\nTEAM ${team}\n${tracks}${cap}\n\n${block}\n`;
}
// ---- Parser / Compiler ----
async function compileFromDsl(dsl) {
    // Returns the AST JSON produced by the canonical Python parser
    return parseViaPython(dsl);
}
// ---- Linter ----
async function lintDsl(dsl) {
    return lintViaPython(dsl);
}
// ---- Renderer ----
function normalizeProgram(value) {
    if (typeof value === 'string') {
        try {
            return JSON.parse(value);
        }
        catch (err) {
            throw new Error('Compiled payload must be JSON or object');
        }
    }
    return value ?? {};
}
function flattenToText(node) {
    if (node === null || node === undefined)
        return '';
    if (typeof node === 'string' || typeof node === 'number')
        return String(node);
    if (typeof node === 'object') {
        if (typeof node.raw === 'string')
            return node.raw;
        if (typeof node.name === 'string')
            return node.name;
        if (node.type === 'DURATION' && Array.isArray(node.children)) {
            const [mins, secs] = node.children;
            if (typeof mins === 'number' && typeof secs === 'number') {
                const mm = mins.toString().padStart(2, '0');
                const ss = secs.toString().padStart(2, '0');
                return `${mm}:${ss}`;
            }
        }
    }
    if (Array.isArray(node))
        return node.map(flattenToText).filter(Boolean).join(' ');
    if (typeof node === 'object' && Array.isArray(node?.children))
        return flattenToText(node.children);
    return '';
}
function describeLoad(load) {
    if (!load)
        return '';
    if (typeof load === 'string')
        return load;
    if (load.raw)
        return String(load.raw);
    if (load.type === 'LOAD_DUAL' && load.per_gender) {
        const male = describeLoad(load.per_gender.male);
        const female = describeLoad(load.per_gender.female);
        return `${male}/${female}`.trim();
    }
    if (load.type === 'LOAD_VARIANT' && load.variants) {
        const formatted = Object.entries(load.variants)
            .map(([k, v]) => `${k}:${describeLoad(v)}`)
            .filter(Boolean)
            .join(', ');
        if (formatted && load.label)
            return `${load.label}(${formatted})`;
        return formatted || load.label || '';
    }
    if (load.type === 'LOAD_VALUE') {
        const unit = load.unit ?? '';
        return load.value !== undefined ? `${load.value}${unit}` : unit;
    }
    return flattenToText(load);
}
function formatMovement(move) {
    if (!move)
        return '';
    if (move.type === 'REST') {
        return formatRest(move);
    }
    const quantity = move.quantity || {};
    const qtyText = quantity.raw ?? flattenToText(quantity);
    let label = [qtyText, move.movement ?? flattenToText(move.children?.[1])]
        .filter(Boolean)
        .join(' ')
        .trim();
    const loadText = describeLoad(move.load);
    if (loadText)
        label = label ? `${label} @ ${loadText}` : `@ ${loadText}`;
    const progress = move.progression?.raw ?? flattenToText(move.progression);
    if (progress)
        label = label ? `${label} (progress ${progress})` : `progress ${progress}`;
    const note = move.note ?? flattenToText(move.children?.[5]);
    if (note)
        label = label ? `${label} — ${note}` : note;
    return label;
}
function formatRest(rest) {
    const duration = rest?.duration || {};
    const raw = duration.raw ?? rest.raw ?? flattenToText(duration);
    if (raw)
        return `REST ${raw}`.trim();
    const seconds = rest?.seconds ?? duration.seconds;
    if (typeof seconds === 'number') {
        const minutes = Math.floor(seconds / 60)
            .toString()
            .padStart(2, '0');
        const secs = (seconds % 60).toString().padStart(2, '0');
        return `REST ${minutes}:${secs}`;
    }
    return 'REST';
}
function renderNotes(value) {
    if (value === null || value === undefined)
        return [];
    const queue = Array.isArray(value) ? value : [value];
    const lines = [];
    queue.forEach((item) => {
        if (item === null || item === undefined)
            return;
        if (Array.isArray(item)) {
            item.forEach((inner) => {
                if (inner === null || inner === undefined)
                    return;
                lines.push(`> ${typeof inner === 'string' ? inner : JSON.stringify(inner)}`);
            });
            return;
        }
        if (typeof item === 'object') {
            lines.push(`> ${JSON.stringify(item)}`);
            return;
        }
        lines.push(`> ${String(item)}`);
    });
    return lines;
}
function toMarkdown(value) {
    const parsed = normalizeProgram(value);
    const modules = Array.isArray(parsed.modules) ? parsed.modules : [];
    if (!modules.length) {
        return '# WODCraft\nAucun module trouvé dans l\'AST.';
    }
    const lines = [];
    modules.forEach((mod, idx) => {
        const title = mod.id ?? `module_${idx + 1}`;
        lines.push(`# ${title}`);
        const wods = Array.isArray(mod.body?.children)
            ? mod.body.children.flatMap((child) => child?.children || [])
            : mod.body?.children || [];
        const actualWods = wods.filter((node) => node?.type === 'WOD');
        if (!actualWods.length) {
            lines.push('_Pas de bloc WOD dans ce module._');
            lines.push('');
            return;
        }
        actualWods.forEach((wod, wIdx) => {
            const formText = flattenToText(wod.form ?? []);
            lines.push(`## WOD ${wIdx + 1}${formText ? ` — ${formText}` : ''}`);
            const movements = Array.isArray(wod.movements) ? wod.movements : [];
            movements.forEach((move) => {
                if (!move)
                    return;
                const line = formatMovement(move);
                lines.push(`- ${line}`.trim());
            });
            const noteLines = renderNotes(wod.notes);
            noteLines.forEach((note) => lines.push(note));
            lines.push('');
        });
    });
    return lines.join('\n').trim();
}
// ---- Resources ----
registerResource('guide-structure', 'wodcraft://guide/structure', {
    title: 'WODCraft DSL Quickstart',
    description: 'Structure, duals, progressions et scoring',
}, async () => ({ text: STRUCTURE_GUIDE, mimeType: 'text/markdown' }));
server.registerTool('list_resources', {
    title: 'List available resources',
    description: 'Show URIs exposed by the WODCraft MCP server',
}, async () => {
    const lines = RESOURCE_REGISTRY.map((res) => `- ${res.uri} — ${res.title}`);
    const text = lines.length ? lines.join('\n') : 'No resources registered.';
    return { content: [{ type: 'text', text }] };
});
server.registerTool('get_resource', {
    title: 'Fetch a resource by URI',
    description: 'Return the contents of a registered resource',
    inputSchema: { uri: z.string().describe('e.g., wodcraft://guide/structure') },
}, async ({ uri }) => {
    const entry = RESOURCE_REGISTRY.find((r) => r.uri === uri);
    if (!entry) {
        return { content: [{ type: 'text', text: `Unknown resource URI: ${uri}` }], isError: true };
    }
    const { text, mimeType } = await entry.loader();
    const payload = { type: 'text', text };
    if (mimeType)
        payload.mimeType = mimeType;
    return { content: [payload] };
});
registerResource('movements', 'wodcraft://movements', {
    title: 'Movement Catalog',
    description: 'Basic movement catalog with default loads',
}, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../data/movements.json', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { text, mimeType: 'application/json' };
});
registerResource('example-basic', 'wodcraft://examples/basic', {
    title: 'Example DSL',
    description: 'A simple example of the WODCraft DSL',
}, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../examples/example_basic.wod', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { text, mimeType: 'text/plain' };
});
registerResource('compiled-schema', 'wodcraft://schema/compiled?v=0.1', {
    title: 'Compiled WOD JSON Schema',
    description: 'JSON Schema used by compile_wod output',
}, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../schemas/compiled_wod.schema.json', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { text, mimeType: 'application/schema+json' };
});
registerResource('spec', 'wodcraft://spec', { title: 'WODCraft Spec', description: 'WODCraft DSL specification (source of truth)' }, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../../WODCraft_spec.md', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { text, mimeType: 'text/markdown' };
});
// ---- Tools ----
server.registerTool('draft_wod', {
    title: 'Generate a WOD draft',
    description: 'Create a WODCraft DSL and compiled JSON from constraints',
    inputSchema: {
        mode: z.enum(['AMRAP', 'FT', 'EMOM', 'RFT', 'CHIPPER']),
        duration: z.string().describe('e.g., "12:00" for AMRAP/EMOM'),
        level: z.enum(['rx', 'intermediate', 'scaled']).optional(),
        equipment: z.array(z.string()).optional(),
        focus: z.array(z.string()).optional(),
        teamSize: z.number().int().min(1).max(6).optional(),
        name: z.string().optional(),
    },
}, async ({ mode, duration, level, equipment, focus, name, teamSize }) => {
    log('draft_wod: generating DSL', { mode, duration, level, equipment, focus, name, teamSize });
    const dsl = generateDsl({ mode, duration, level, equipment, focus, name, teamSize });
    const compiled = await compileFromDsl(dsl);
    const md = toMarkdown(compiled);
    return { content: [{ type: 'text', text: dsl }, { type: 'text', text: JSON.stringify(compiled, null, 2) }, { type: 'text', text: md }] };
});
server.registerTool('lint_wod', {
    title: 'Lint a WOD DSL',
    description: 'Run canonical linter and return structured issues',
    inputSchema: { dsl: z.string() },
}, async ({ dsl }) => {
    log('lint_wod: linting DSL', { length: dsl.length });
    const issues = await lintDsl(dsl);
    return { content: [{ type: 'text', text: JSON.stringify({ issues }, null, 2) }] };
});
server.registerTool('compile_wod', {
    title: 'Compile DSL to JSON',
    description: 'Parse WODCraft DSL (Lark grammar) into structured JSON',
    inputSchema: { dsl: z.string() },
}, async ({ dsl }) => {
    try {
        log('compile_wod: compiling DSL', { length: dsl.length });
        const compiled = await compileFromDsl(dsl);
        return { content: [{ type: 'text', text: JSON.stringify(compiled, null, 2) }] };
    }
    catch (e) {
        logError('compile_wod: error', e);
        return { content: [{ type: 'text', text: `Error: ${e?.message ?? e}` }], isError: true };
    }
});
server.registerTool('to_markdown', {
    title: 'Render WOD to Markdown',
    description: 'Transform compiled JSON into Markdown',
    inputSchema: { compiled: z.any() },
}, async ({ compiled }) => {
    const md = toMarkdown(compiled);
    return { content: [{ type: 'text', text: md }] };
});
server.registerTool('generate_variants', {
    title: 'Generate scaled variants',
    description: 'Add RX / INTERMEDIATE / SCALED suggestions to a compiled WOD',
    inputSchema: { compiled: z.any() },
}, async ({ compiled }) => {
    const program = normalizeProgram(compiled);
    program.variants = program.variants ?? {
        RX: ['as written'],
        INTERMEDIATE: ['reduce load or distance by ~25%'],
        SCALED: ['use assistance or lighter implements'],
    };
    return { content: [{ type: 'text', text: JSON.stringify(program, null, 2) }] };
});
// ---- Prompt ----
server.registerPrompt('design-wod', {
    title: 'Design a WOD from constraints',
    description: 'Prompt template for creating a WOD that calls draft_wod appropriately',
    argsSchema: {
        goals: z.string().describe("Short goals, e.g., 'engine + legs'"),
        level: z.enum(['rx', 'intermediate', 'scaled']).optional(),
        duration: z.string().optional(),
        equipment: z.string().optional(),
    },
}, ({ goals, level, duration, equipment }) => ({
    messages: [{
            role: 'user',
            content: {
                type: 'text',
                text: `Create a Cross-Training workout (WOD) balancing ${goals}. Target: ${level ?? 'intermediate'}. Duration: ${duration ?? '20:00'}. Equipment: ${equipment ?? 'bodyweight'}.
Return both a WODCraft DSL (v0.1) and a JSON plan. Then provide a brief coaching tip.`
            }
        }]
}));
// ---- Boot (STDIO) ----
const transport = new StdioServerTransport();
await server.connect(transport);
export { generateDsl, lintDsl, compileFromDsl, toMarkdown };
