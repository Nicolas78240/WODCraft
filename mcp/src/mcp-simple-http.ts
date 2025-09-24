#!/usr/bin/env node

import { createServer, IncomingMessage, ServerResponse } from 'node:http';
import { parse as parseUrl } from 'node:url';
import { z } from 'zod';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { writeFile, unlink } from 'node:fs/promises';
import path from 'node:path';

// Simple HTTP API that exposes MCP functionality without the transport layer complexity
const LOG_PREFIX = '[wodcraft-mcp-simple]';
const DEBUG = true; // Force debug for testing

function log(...args: unknown[]) {
  if (DEBUG) {
    console.error(LOG_PREFIX, ...args);
  }
}

function logError(...args: unknown[]) {
  console.error(LOG_PREFIX, '[ERROR]', ...args);
}

// Configuration
function getEnv(name: string, def?: string): string | undefined {
  return process.env[name] ?? def;
}

function resolveCliArgs(): string[] {
  const envCli = getEnv('WODCRAFT_CLI');
  if (envCli) {
    return envCli
      .split(/\s+/)
      .map((part) => part.trim())
      .filter(Boolean);
  }
  return ['-m', 'wodcraft.cli'];
}

const DEFAULTS = {
  PYTHON: getEnv('WODCRAFT_PYTHON', 'python3')!,
  CLI_ARGS: resolveCliArgs(),
  CATALOG: getEnv('WODCRAFT_CATALOG', ''),
  TRACK: (getEnv('WODCRAFT_TRACK', 'RX') as 'RX' | 'INTERMEDIATE' | 'SCALED'),
  GENDER: (getEnv('WODCRAFT_GENDER', 'male') as 'male' | 'female'),
};

// Core functions
async function runWithTimeout(cmd: string, args: string[], context: { tmpFile: string; tool: string }, timeoutMs = 4000): Promise<{ code: number; stdout: string; stderr: string }> {
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
      } catch {}
    }, timeoutMs);
    child.stdout.on('data', (d) => (stdout += d.toString()));
    child.stderr.on('data', (d) => (stderr += d.toString()));
    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ code: code ?? 0, stdout, stderr });
    });
  });
}

async function lintViaPython(dsl: string) {
  const f = path.join(tmpdir(), `wodcraft_${Date.now()}.wod`);
  await writeFile(f, dsl, 'utf8');
  const args = [...DEFAULTS.CLI_ARGS, 'lint', f];
  if (DEFAULTS.CATALOG) args.push('--catalog', DEFAULTS.CATALOG);
  const { stdout, stderr } = await runWithTimeout(DEFAULTS.PYTHON, args, { tmpFile: f, tool: 'lint' });
  await unlink(f).catch(() => {});

  const output = stdout + '\n' + stderr;
  const issues = [];

  if (output.includes('✗ Invalid syntax:')) {
    const lines = output.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
    for (const line of lines) {
      if (line.startsWith('✗ Invalid syntax:')) {
        let message = line.replace('✗ Invalid syntax:', '').trim();
        issues.push({
          level: 'ERROR',
          code: 'E001',
          path: f,
          message: message
        });
      }
    }
  }

  const lines = output.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  for (const line of lines) {
    const warningMatch = line.match(/^(WARNING|ERROR)\s+([A-Z]\d{3})\s+([^:]+):\s+(.*)$/);
    if (warningMatch) {
      issues.push({
        level: warningMatch[1],
        code: warningMatch[2],
        path: warningMatch[3],
        message: warningMatch[4]
      });
    }
  }

  return issues;
}

async function parseViaPython(dsl: string): Promise<any> {
  const f = path.join(tmpdir(), `wodcraft_${Date.now()}.wod`);
  await writeFile(f, dsl, 'utf8');
  const args = [...DEFAULTS.CLI_ARGS, 'parse', f];
  if (DEFAULTS.CATALOG) args.push('--catalog', DEFAULTS.CATALOG);
  const res = await runWithTimeout(DEFAULTS.PYTHON, args, { tmpFile: f, tool: 'parse' });
  await unlink(f).catch(() => {});
  if (res.code !== 0) {
    const message = res.stderr.trim() || res.stdout.trim() || `parse exited with code ${res.code}`;
    throw new Error(message);
  }
  const text = res.stdout.trim();
  try {
    return JSON.parse(text);
  } catch (e) {
    logError('parseViaPython: invalid JSON payload', text);
    throw new Error('Failed to parse AST JSON');
  }
}

// WOD Generation functions
function defaultName(params: { mode: string; duration?: string }) {
  const duration = params.duration ? params.duration.replace(/\\s+/g, '') : 'generic';
  return `${params.mode.toLowerCase()}-${duration}`;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '.')
    .replace(/^\.+|\.+$/g, '')
    .replace(/\.\.+/g, '.') || 'generated';
}

function generateDsl(opts: {
  name?: string;
  mode: 'AMRAP' | 'FT' | 'EMOM' | 'RFT' | 'CHIPPER';
  duration?: string;
  teamSize?: number;
  level?: 'rx' | 'intermediate' | 'scaled';
  equipment?: string[];
  focus?: string[];
}): string {
  const title = opts.name ?? defaultName({ mode: opts.mode, duration: opts.duration });
  const moduleId = `wod.generated.${slugify(title)}`;

  let form: string = opts.mode;
  if (opts.duration) {
    if (opts.mode === 'FT') {
      form = `ForTime cap ${opts.duration}`;
    } else {
      form = `${opts.mode} ${opts.duration}`;
    }
  }

  const movements = ['15 Burpee', '10 Push_up', '200m Run'];
  const wodBody = movements.map((line) => `    ${line}`).join('\n');

  // Simplifions d'abord sans score block
  let text = `module ${moduleId} v1 {\n`;
  text += `  wod ${form} {\n${wodBody}\n  }\n`;
  text += `}\n`;
  return text;
}

// Markdown rendering
function toMarkdown(compiled: any): string {
  const program = typeof compiled === 'string' ? JSON.parse(compiled) : compiled;
  const modules = Array.isArray(program.modules) ? program.modules : [];
  if (!modules.length) {
    return '# WODCraft\nAucun module trouvé dans l\'AST.';
  }

  const lines: string[] = [];
  modules.forEach((mod: any, idx: number) => {
    const title = mod.id ?? `module_${idx + 1}`;
    lines.push(`# ${title}`);
    lines.push('');
    lines.push('WOD généré avec succès !');
    lines.push('');
  });
  return lines.join('\n').trim();
}

// Parse request body
async function parseBody(req: IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
  });
}

// HTTP Server
const PORT = process.env.PORT || 8080;

const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
  const parsed = parseUrl(req.url || '', true);
  const pathname = parsed.pathname || '';

  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  // Health check endpoint
  if (pathname === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      timestamp: new Date().toISOString()
    }));
    return;
  }

  // Root endpoint
  if (pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      name: 'WODCraft Simple HTTP API',
      version: '0.3.2',
      endpoints: {
        health: '/health',
        draft: '/draft',
        lint: '/lint',
        compile: '/compile'
      }
    }));
    return;
  }

  // Draft WOD endpoint
  if (pathname === '/draft' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      log('draft: generating DSL', body);

      const dsl = generateDsl(body);
      log('Generated DSL:', dsl);
      const compiled = await parseViaPython(dsl);
      const md = toMarkdown(compiled);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: true,
        dsl,
        compiled,
        markdown: md
      }));
    } catch (error: any) {
      logError('draft: error', error);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: false,
        error: error?.message ?? error
      }));
    }
    return;
  }

  // Lint endpoint
  if (pathname === '/lint' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      log('lint: linting DSL', { length: body.dsl?.length });

      const issues = await lintViaPython(body.dsl);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: true,
        issues
      }));
    } catch (error: any) {
      logError('lint: error', error);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: false,
        error: error?.message ?? error
      }));
    }
    return;
  }

  // Compile endpoint
  if (pathname === '/compile' && req.method === 'POST') {
    try {
      const body = await parseBody(req);
      log('compile: compiling DSL', { length: body.dsl?.length });

      const compiled = await parseViaPython(body.dsl);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: true,
        compiled
      }));
    } catch (error: any) {
      logError('compile: error', error);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        success: false,
        error: error?.message ?? error
      }));
    }
    return;
  }

  // 404 for unknown endpoints
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not Found' }));
});

server.listen(PORT, () => {
  console.log(`🚀 WODCraft Simple HTTP API running on port ${PORT}`);
  console.log(`📊 Health check: http://localhost:${PORT}/health`);
  console.log(`🔧 Tools: /draft, /lint, /compile`);
  log('Server configuration:', DEFAULTS);
});

export default server;