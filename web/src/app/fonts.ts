import { Inter } from 'next/font/google';

// next/font 在构建时下载并「自托管」字体,运行时不向 Google 发起任何请求
// —— 满足国内可访问性要求(不用 Google Fonts CDN)。
export const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

// 中文字体(思源黑体 / 系统黑体)通过 CSS 变量 --font-noto-sc 预留。
// 一期优先使用用户设备本地已装的中文字体以保证首屏 < 100KB 与 LCP < 2s;
// 如需完整自托管思源黑体,可将 woff2 子集放入 /public/fonts 并改用 next/font/local。
