// AI4Trade Signals — Service Worker
// 外壳(HTML/CSS/JS/图标)走「缓存优先」保证离线可开;
// 信号数据 data/signals.json 走「网络优先」保证尽量新鲜。
const CACHE = 'a4t-shell-v5';
const SHELL = [
  './',
  './index.html',
  './styles.css',
  './app.js',
  './config.js',
  './i18n.js',
  './manifest.webmanifest',
  './icons/icon.svg',
  './icons/maskable.svg',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // 信号 / 路线图等数据:网络优先,失败回退缓存
  if (url.pathname.includes('/data/')) {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // 外壳:缓存优先
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
});
