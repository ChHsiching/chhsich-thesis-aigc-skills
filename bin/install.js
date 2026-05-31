#!/usr/bin/env node
import { execSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const SKILL_NAME = 'thesis-aigc-reduction';

// Claude Code skills directories (try in order)
const SKILL_DIRS = [
  // AionUI custom skills
  join(process.env.HOME, '.config', 'AionUi', 'config', 'skills'),
  // Claude Code global skills
  join(process.env.HOME, '.claude', 'skills'),
];

function findSkillDir() {
  for (const dir of SKILL_DIRS) {
    if (existsSync(dir)) return dir;
  }
  // Fallback: create Claude Code skills dir
  const fallback = SKILL_DIRS[SKILL_DIRS.length - 1];
  mkdirSync(fallback, { recursive: true });
  return fallback;
}

const skillDir = findSkillDir();
const target = join(skillDir, SKILL_NAME);

if (existsSync(target)) {
  console.log(`Updating existing skill at ${target}`);
} else {
  mkdirSync(target, { recursive: true });
  console.log(`Installing skill to ${target}`);
}

// Copy skill files
const files = ['SKILL.md', 'REFERENCE.md', 'EXAMPLES.md'];
for (const f of files) {
  cpSync(join(ROOT, f), join(target, f));
}

// Copy scripts directory
if (existsSync(join(ROOT, 'scripts'))) {
  cpSync(join(ROOT, 'scripts'), join(target, 'scripts'), { recursive: true });
}

console.log(`\nInstalled ${SKILL_NAME} to ${target}`);
console.log('\nFiles:');
for (const f of files) {
  console.log(`  ${f}`);
}
if (existsSync(join(ROOT, 'scripts'))) {
  console.log('  scripts/');
}
console.log('\nRestart your Claude Code session to use the skill.');
