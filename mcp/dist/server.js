import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { writeFile, readFile, unlink } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const server = new McpServer({ name: 'wodcraft-mcp', version: '0.1.0' });
// ---- Config ----
function getEnv(name, def) {
    return process.env[name] ?? def;
}
function resolveCliPath() {
    const envCli = getEnv('WODCRAFT_CLI');
    if (envCli)
        return envCli;
    // try repo root: ../../wodc_merged.py from dist/server.js
    const thisFile = fileURLToPath(import.meta.url);
    const guess = path.resolve(path.dirname(thisFile), '../../wodc_merged.py');
    return guess;
}
const DEFAULTS = {
    PYTHON: getEnv('WODCRAFT_PYTHON', 'python3'),
    CLI: resolveCliPath(),
    CATALOG: getEnv('WODCRAFT_CATALOG', ''),
    TRACK: getEnv('WODCRAFT_TRACK', 'RX'),
    GENDER: getEnv('WODCRAFT_GENDER', 'male'),
};
async function runWithTimeout(cmd, args, inputFile, timeoutMs = 4000) {
    return new Promise((resolve) => {
        const child = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'] });
        let stdout = '';
        let stderr = '';
        const timer = setTimeout(() => {
            stderr += `\nProcess timeout after ${timeoutMs}ms`;
            try {
                child.kill('SIGKILL');
            }
            catch { }
        }, timeoutMs);
        child.stdout.on('data', (d) => (stdout += d.toString()));
        child.stderr.on('data', (d) => (stderr += d.toString()));
        child.on('close', (code) => {
            clearTimeout(timer);
            resolve({ code: code ?? 0, stdout, stderr });
        });
    });
}
async function lintViaPython(dsl) {
    const f = path.join(tmpdir(), `wodcraft_${Date.now()}.wod`);
    await writeFile(f, dsl, 'utf8');
    const args = [DEFAULTS.CLI, 'lint', f, '--track', DEFAULTS.TRACK, '--gender', DEFAULTS.GENDER];
    if (DEFAULTS.CATALOG)
        args.push('--catalog', DEFAULTS.CATALOG);
    const { stdout, stderr } = await runWithTimeout(DEFAULTS.PYTHON, args, f);
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
    const out = path.join(tmpdir(), `wodcraft_${Date.now()}.json`);
    await writeFile(f, dsl, 'utf8');
    const args = [DEFAULTS.CLI, 'parse', f, '-o', out, '--track', DEFAULTS.TRACK, '--gender', DEFAULTS.GENDER];
    if (DEFAULTS.CATALOG)
        args.push('--catalog', DEFAULTS.CATALOG);
    const res = await runWithTimeout(DEFAULTS.PYTHON, args, f);
    const text = await readFile(out, 'utf8').catch(async () => {
        // maybe printed to stdout
        return res.stdout;
    });
    await unlink(f).catch(() => { });
    try {
        return JSON.parse(text);
    }
    catch (e) {
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
function toMarkdown(w) {
    const lines = [];
    lines.push(`# ${w.name}`);
    lines.push(`**Mode**: ${w.mode} \u00A0\u00A0 **Durée**: ${w.timecap}`);
    lines.push("");
    w.blocks.forEach((b, i) => {
        lines.push(`## Bloc ${i + 1}${b.label ? ` — ${b.label}` : ""}`);
        b.moves.forEach(m => {
            const load = m.load ? ` @ ${m.load.male ?? ""}${m.load.female ? `/${m.load.female}` : ""}` : "";
            lines.push(`- ${m.reps} ${m.movement}${load}`);
        });
        lines.push("");
    });
    if (w.scales) {
        lines.push("## Scales");
        ["RX", "INTERMEDIATE", "SCALED"].forEach(k => {
            const arr = w.scales[k];
            if (arr?.length) {
                lines.push(`**${k}**`);
                arr.forEach((s) => lines.push(`- ${s}`));
                lines.push("");
            }
        });
    }
    if (w.notes) {
        lines.push("## Notes");
        lines.push(w.notes);
    }
    return lines.join("\n");
}
// ---- Resources ----
server.registerResource('movements', 'wodcraft://movements', {
    title: 'Movement Catalog',
    description: 'Basic movement catalog with default loads',
}, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../data/movements.json', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { contents: [{ uri: 'wodcraft://movements', text }] };
});
server.registerResource('example-basic', 'wodcraft://examples/basic', {
    title: 'Example DSL',
    description: 'A simple example of the WODCraft DSL',
}, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../examples/example_basic.wod', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { contents: [{ uri: 'wodcraft://examples/basic', text, mimeType: 'text/plain' }] };
});
server.registerResource('compiled-schema', 'wodcraft://schema/compiled?v=0.1', {
    title: 'Compiled WOD JSON Schema',
    description: 'JSON Schema used by compile_wod output',
}, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../schemas/compiled_wod.schema.json', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { contents: [{ uri: 'wodcraft://schema/compiled?v=0.1', text, mimeType: 'application/schema+json' }] };
});
server.registerResource('spec', 'wodcraft://spec', { title: 'WODCraft Spec', description: 'WODCraft DSL specification (source of truth)' }, async () => {
    const fs = await import('node:fs/promises');
    const p = new URL('../../WODCraft_spec.md', import.meta.url);
    const text = await fs.readFile(p, 'utf-8');
    return { contents: [{ uri: 'wodcraft://spec', text, mimeType: 'text/markdown' }] };
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
    const issues = await lintDsl(dsl);
    return { content: [{ type: 'text', text: JSON.stringify({ issues }, null, 2) }] };
});
server.registerTool('compile_wod', {
    title: 'Compile DSL to JSON',
    description: 'Parse WODCraft DSL (Lark grammar) into structured JSON',
    inputSchema: { dsl: z.string() },
}, async ({ dsl }) => {
    try {
        const compiled = await compileFromDsl(dsl);
        return { content: [{ type: 'text', text: JSON.stringify(compiled, null, 2) }] };
    }
    catch (e) {
        return { content: [{ type: 'text', text: `Error: ${e?.message ?? e}` }] };
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
    const wod = compiled;
    wod.scales = wod.scales ?? {};
    wod.scales.RX = wod.scales.RX ?? ['as written'];
    wod.scales.INTERMEDIATE = wod.scales.INTERMEDIATE ?? ['reduce run distance by 25%'];
    wod.scales.SCALED = wod.scales.SCALED ?? ['incline or knee push-ups', 'lighten loads by 30-40%'];
    return { content: [{ type: 'text', text: JSON.stringify(wod, null, 2) }] };
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
