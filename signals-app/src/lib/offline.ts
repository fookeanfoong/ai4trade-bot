/**
 * Offline cache backed by IndexedDB (via `idb`).
 * Caches last-viewed signals, latest news, and all guides so the app is
 * usable without a network connection.
 *
 * Pattern used by callers: try the network first; on failure read the cache.
 * On success, write through to the cache.
 */
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { Guide, NewsArticle, Signal } from './types';

interface Ai4TradeDB extends DBSchema {
  signals: { key: string; value: { id: string; data: Signal[]; cachedAt: number } };
  news: { key: string; value: { id: string; data: NewsArticle[]; cachedAt: number } };
  guides: { key: string; value: { id: string; data: Guide[]; cachedAt: number } };
}

let dbPromise: Promise<IDBPDatabase<Ai4TradeDB>> | null = null;

function db(): Promise<IDBPDatabase<Ai4TradeDB>> {
  if (!dbPromise) {
    dbPromise = openDB<Ai4TradeDB>('ai4trade-signals', 1, {
      upgrade(database) {
        database.createObjectStore('signals', { keyPath: 'id' });
        database.createObjectStore('news', { keyPath: 'id' });
        database.createObjectStore('guides', { keyPath: 'id' });
      },
    });
  }
  return dbPromise;
}

async function put<T>(store: 'signals' | 'news' | 'guides', id: string, data: T): Promise<void> {
  try {
    const database = await db();
    // @ts-expect-error — store value shape is uniform across stores.
    await database.put(store, { id, data, cachedAt: Date.now() });
  } catch {
    /* IndexedDB unavailable (e.g. private mode) — cache silently disabled. */
  }
}

async function read<T>(store: 'signals' | 'news' | 'guides', id: string): Promise<T | null> {
  try {
    const database = await db();
    const row = await database.get(store, id);
    return (row?.data as T) ?? null;
  } catch {
    return null;
  }
}

export const cacheSignals = (s: Signal[]) => put('signals', 'today', s);
export const readSignals = () => read<Signal[]>('signals', 'today');

export const cacheNews = (category: string, n: NewsArticle[]) => put('news', category, n);
export const readNews = (category: string) => read<NewsArticle[]>('news', category);

export const cacheGuides = (g: Guide[]) => put('guides', 'all', g);
export const readGuides = () => read<Guide[]>('guides', 'all');
