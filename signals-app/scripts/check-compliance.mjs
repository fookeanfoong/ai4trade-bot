#!/usr/bin/env node
/**
 * Compliance guard: fails if any banned marketing word appears in user-facing
 * copy (the i18n locale files). Run in CI / pre-release.
 *
 *   node scripts/check-compliance.mjs
 *
 * Banned words (AppGallery rejection risk): buy, sell now, guaranteed, profit,
 * winner, sure win, recommendation.
 *
 * NOTE: matching is word-boundary aware and English-only. The zh-Hans/zh-Hant
 * files are scanned too, but the banned list targets the English strings; add
 * localized banned terms here if your reviewers require it.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const BANNED = ['buy', 'sell now', 'guaranteed', 'profit', 'winner', 'sure win', 'recommendation'];

/**
 * Sanctioned disclaimer phrases. These are compliance strings MANDATED by the
 * spec that legitimately negate an otherwise-banned word (e.g. "Not a
 * recommendation to trade"). They are stripped before scanning so a required
 * disclaimer never trips the promotional-word ban.
 */
const ALLOWED_PHRASES = [
  'not a recommendation to trade',
  'a recommendation, or a solicitation',
];

const here = dirname(fileURLToPath(import.meta.url));
const localesDir = join(here, '..', 'src', 'i18n', 'locales');

function walk(obj, path, hits) {
  for (const [key, value] of Object.entries(obj)) {
    const next = path ? `${path}.${key}` : key;
    if (typeof value === 'string') {
      let lower = value.toLowerCase();
      for (const phrase of ALLOWED_PHRASES) lower = lower.split(phrase).join(' ');
      for (const word of BANNED) {
        const re = new RegExp(`\\b${word.replace(/\s+/g, '\\s+')}\\b`, 'i');
        if (re.test(lower)) hits.push({ path: next, word, value });
      }
    } else if (value && typeof value === 'object') {
      walk(value, next, hits);
    }
  }
}

let failed = false;
for (const file of readdirSync(localesDir).filter((f) => f.endsWith('.json'))) {
  const data = JSON.parse(readFileSync(join(localesDir, file), 'utf8'));
  const hits = [];
  walk(data, '', hits);
  if (hits.length) {
    failed = true;
    console.error(`\n✗ ${file}: banned words found`);
    for (const h of hits) console.error(`   [${h.word}] ${h.path}: "${h.value}"`);
  } else {
    console.log(`✓ ${file}: clean`);
  }
}

if (failed) {
  console.error('\nCompliance check FAILED. Remove banned words before release.');
  process.exit(1);
}
console.log('\nCompliance check passed.');
