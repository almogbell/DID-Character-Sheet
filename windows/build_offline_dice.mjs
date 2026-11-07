import { existsSync, mkdirSync, cpSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { build } from 'esbuild';

const here = process.cwd();
const sourceDir = join(here, 'node_modules', '@3d-dice', 'dice-box', 'dist');
const outputDir = join(here, 'dice_libs');
const diceBoxDir = join(outputDir, 'dice-box');
if (!existsSync(sourceDir)) throw Error('DiceBox distribution not installed. Run npm install first.');
if (!existsSync(join(sourceDir, 'dice-box.es.min.js'))) throw Error('Unexpected DiceBox package layout: missing dist/dice-box.es.min.js.');
if (!existsSync(join(sourceDir, 'assets'))) throw Error('Unexpected DiceBox package layout: missing dist/assets. Check installed DiceBox layout.');
mkdirSync(outputDir, { recursive: true });
// Copy the COMPLETE distribution: workers, models and materials may be loaded lazily.
cpSync(sourceDir, diceBoxDir, { recursive: true, force: true });
await build({
  entryPoints: [join(here, 'd100_dependencies_entry.js')],
  outfile: join(outputDir, 'd100_deps.js'),
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: 'es2020',
  legalComments: 'inline',
  sourcemap: false,
  minify: true,
  logLevel: 'info',
});
const dice = readFileSync(join(here, 'dice.html'), 'utf8');
const physics = readFileSync(join(here, 'd100_physics.js'), 'utf8');
if (!dice.includes('./dice_libs/dice-box/dice-box.es.min.js') || !physics.includes('./dice_libs/d100_deps.js')) {
  throw Error('Offline source imports were overwritten or changed.');
}
for (const [name, content] of [['dice.html',dice],['d100_physics.js',physics]]) {
  if (/https:\/\/(?:unpkg\.com|esm\.sh)/.test(content)) throw Error(`Found CDN import in ${name}`);
}
console.log('OFFLINE ASSET BUILD FINISHED.');
console.log('Copied complete DiceBox dist:', diceBoxDir);
console.log('Bundled Three.js + cannon-es:', join(outputDir, 'd100_deps.js'));
console.log('Next: build with PyInstaller, then install and test with network disconnected.');
