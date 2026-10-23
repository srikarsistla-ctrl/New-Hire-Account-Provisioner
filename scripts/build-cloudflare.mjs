import { mkdir, copyFile, readdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const output = resolve(root, 'public');
await mkdir(resolve(output, 'static'), { recursive: true });
for (const file of await readdir(resolve(root, 'frontend'))) {
  if (file.endsWith('.html')) await copyFile(resolve(root, 'frontend', file), resolve(output, file));
  else if (/\.(css|js)$/.test(file)) await copyFile(resolve(root, 'frontend', file), resolve(output, 'static', file));
}
console.log('Cloudflare assets prepared: HTML pages plus /static/ scripts and styles.');

// Keep Python's module root separate from virtual environments and local data.
const modules = [
  'app/__init__.py', 'app/agent/__init__.py', 'app/agent/validator.py',
  'app/agent/policy.py', 'app/agent/recommender.py',
  ...((await readdir(resolve(root, 'cloudflare'))).filter(f => f.endsWith('.py')).map(f => `cloudflare/${f}`)),
];
for (const file of modules) {
  const target = resolve(root, 'worker-src', file);
  await mkdir(resolve(target, '..'), { recursive: true });
  await copyFile(resolve(root, file), target);
}
console.log('Worker source prepared without local environments, tests, or secrets.');
