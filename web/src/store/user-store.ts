'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// 一期/三期为无后端 mock:用户会话、收藏、降价提醒、评价均存本地(localStorage)。
// 二期接入真实后端时,替换这些 action 的实现即可,组件无需改动。

export interface MockUser {
  email: string;
  name: string;
  createdAt: string;
}

export interface LocalReview {
  id: string;
  providerSlug: string;
  providerName: string;
  rating: number;
  content: string;
  createdAt: string;
}

interface UserState {
  user: MockUser | null;
  favorites: string[]; // provider slugs
  alerts: string[]; // provider slugs 已开启降价提醒
  reviews: LocalReview[];
  login: (email: string, name?: string) => void;
  logout: () => void;
  toggleFavorite: (slug: string) => void;
  toggleAlert: (slug: string) => void;
  addReview: (r: Omit<LocalReview, 'id' | 'createdAt'>) => void;
  removeReview: (id: string) => void;
  exportData: () => string;
  deleteAllData: () => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set, get) => ({
      user: null,
      favorites: [],
      alerts: [],
      reviews: [],
      login: (email, name) =>
        set({ user: { email, name: name || email.split('@')[0], createdAt: new Date().toISOString() } }),
      logout: () => set({ user: null }),
      toggleFavorite: (slug) =>
        set((s) => ({
          favorites: s.favorites.includes(slug)
            ? s.favorites.filter((x) => x !== slug)
            : [...s.favorites, slug],
        })),
      toggleAlert: (slug) =>
        set((s) => ({
          alerts: s.alerts.includes(slug) ? s.alerts.filter((x) => x !== slug) : [...s.alerts, slug],
        })),
      addReview: (r) =>
        set((s) => ({
          reviews: [
            { ...r, id: `local-${s.reviews.length + 1}-${Date.now()}`, createdAt: new Date().toISOString() },
            ...s.reviews,
          ],
        })),
      removeReview: (id) => set((s) => ({ reviews: s.reviews.filter((x) => x.id !== id) })),
      // GDPR:导出用户全部本地数据为 JSON
      exportData: () => {
        const { user, favorites, alerts, reviews } = get();
        return JSON.stringify({ user, favorites, alerts, reviews, exportedAt: new Date().toISOString() }, null, 2);
      },
      // GDPR:删除用户全部数据
      deleteAllData: () => set({ user: null, favorites: [], alerts: [], reviews: [] }),
    }),
    { name: 'aggreapi.user.v1' }
  )
);
