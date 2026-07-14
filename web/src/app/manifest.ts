import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'AggreAPI — AI API 中转站比价',
    short_name: 'AggreAPI',
    description: 'AI API 中转站比价平台',
    start_url: '/zh',
    display: 'standalone',
    background_color: '#0b1220',
    theme_color: '#0b1220',
    icons: [{ src: '/og-default.svg', sizes: 'any', type: 'image/svg+xml' }],
  };
}
