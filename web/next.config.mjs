import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 预留：未来切国内 CDN 时设置 NEXT_PUBLIC_ASSET_PREFIX（如 https://cdn.example.cn）
  assetPrefix: process.env.NEXT_PUBLIC_ASSET_PREFIX || undefined,
  images: {
    formats: ['image/webp'],
    // Logo / 图片本地打包为主；如需远程图源在此显式声明白名单（避免被墙 CDN）
    remotePatterns: [],
  },
  eslint: {
    // 阶段一构建以产物为准，避免 lint 阻塞交付
    ignoreDuringBuilds: true,
  },
};

export default withNextIntl(nextConfig);
