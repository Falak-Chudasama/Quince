import esbuild from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, 'dist');
const publicDir = path.resolve(__dirname, 'public');

// Ensure dist directory exists
fs.mkdirSync(distDir, { recursive: true });

function copyRecursive(src, dest) {
  if (fs.statSync(src).isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const file of fs.readdirSync(src)) {
      copyRecursive(path.join(src, file), path.join(dest, file));
    }
  } else {
    fs.copyFileSync(src, dest);
  }
}

async function build() {
  console.log('Building Quince Chrome Extension with esbuild...');

  // 1. Bundle TypeScript files
  await esbuild.build({
    entryPoints: [
      { in: 'src/background/index.ts', out: 'background' },
      { in: 'src/content/index.ts', out: 'content' },
      { in: 'src/content/main-world.ts', out: 'main-world' },
      { in: 'src/popup/popup.ts', out: 'popup' },
      { in: 'src/options/options.ts', out: 'options' },
    ],
    bundle: true,
    outdir: 'dist',
    target: ['chrome116'],
    platform: 'browser',
    sourcemap: true,
    logLevel: 'info',
  });

  // 2. Copy static files from public/
  if (fs.existsSync(publicDir)) {
    copyRecursive(publicDir, distDir);
  }

  // 3. Copy HTML and CSS from popup and options
  fs.copyFileSync(path.resolve(__dirname, 'src/popup/popup.html'), path.join(distDir, 'popup.html'));
  fs.copyFileSync(path.resolve(__dirname, 'src/popup/popup.css'), path.join(distDir, 'popup.css'));
  fs.copyFileSync(path.resolve(__dirname, 'src/options/options.html'), path.join(distDir, 'options.html'));
  fs.copyFileSync(path.resolve(__dirname, 'src/options/options.css'), path.join(distDir, 'options.css'));

  console.log('Build complete! Output in extension/dist');
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
