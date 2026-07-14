import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// 生成本地占位 Logo(圆角方形 + 首字母字标),避免从被墙 CDN 拉取。
// 上线时可用真实品牌 Logo(本地打包)替换同名文件。
const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(__dirname, '../public/logos');
mkdirSync(outDir, { recursive: true });

const brands = [
  { file: 'openrouter', label: 'OR', bg: '#6366F1' },
  { file: 'aihubmix', label: 'AH', bg: '#06B6D4' },
  { file: 'closeai', label: 'CA', bg: '#0EA5E9' },
  { file: 'deepbricks', label: 'DB', bg: '#F59E0B' },
  { file: 'api2d', label: '2D', bg: '#10B981' },
  { file: 'ohmygpt', label: 'OM', bg: '#8B5CF6' },
  { file: 'gptapius', label: 'US', bg: '#EF4444' },
  { file: 'laozhang', label: 'LZ', bg: '#14B8A6' },
  { file: 'aigcbest', label: 'GC', bg: '#EC4899' },
  { file: 'poloai', label: 'PL', bg: '#3B82F6' },
];

for (const b of brands) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96" role="img" aria-label="${b.file} logo">
  <rect width="96" height="96" rx="20" fill="${b.bg}"/>
  <text x="50%" y="50%" dy="0.02em" text-anchor="middle" dominant-baseline="central"
    font-family="Inter, system-ui, sans-serif" font-size="40" font-weight="700" fill="#ffffff">${b.label}</text>
</svg>
`;
  writeFileSync(resolve(outDir, `${b.file}.svg`), svg);
}

// 站点 og / 微信卡片默认图(300x300)
const og = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
  <rect width="300" height="300" fill="#0b1220"/>
  <rect x="24" y="24" width="252" height="252" rx="28" fill="none" stroke="#06B6D4" stroke-width="3"/>
  <text x="50%" y="46%" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="34" font-weight="800" fill="#06B6D4">AggreAPI</text>
  <text x="50%" y="60%" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="16" fill="#cbd5e1">AI API 中转站比价</text>
</svg>
`;
writeFileSync(resolve(outDir, '../og-default.svg'), og);

console.log(`Generated ${brands.length} logos + og image into public/`);
