/**
 * REST client for the existing aicompareapi.com backend.
 *
 * Endpoints:
 *   POST /auth/signup        { email, password, dob }         -> { token, user }
 *   POST /auth/login         { email, password }              -> { token, user }
 *   POST /auth/logout
 *   DELETE /auth/account
 *   GET  /signals/today                                        -> Signal[]
 *   GET  /news/latest?category=                                -> NewsArticle[]
 *   GET  /guides/list                                          -> Guide[]
 *   POST /user/acceptance    { terms_version, ... }            -> AcceptanceRecord
 *   GET  /user/acceptance                                      -> AcceptanceRecord | null
 *   GET  /user/entitlement                                     -> Entitlement
 *   POST /user/capital       { capital_usd }
 *
 * Auth is a bearer token stored via Preferences. When the network is
 * unavailable the caller falls back to the offline cache (see lib/offline.ts).
 */
import * as storage from './storage';
import { KEYS } from './storage';
import { LEGAL_VERSIONS } from './compliance';
import type {
  AcceptanceRecord,
  AuthUser,
  Entitlement,
  Guide,
  NewsArticle,
  Signal,
} from './types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'https://aicompareapi.com/api').replace(
  /\/$/,
  '',
);

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const token = await storage.get(KEYS.authToken);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(await authHeader()),
    ...((init.headers as Record<string, string>) ?? {}),
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.message ?? body.error ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Auth ------------------------------------------------------------------

export interface AuthResult {
  token: string;
  user: AuthUser;
}

/**
 * Sign up. `dob` is an ISO date (yyyy-mm-dd); the backend re-validates the
 * 18+ age gate server-side. The client also validates before calling.
 */
export async function signup(email: string, password: string, dob: string): Promise<AuthResult> {
  const result = await request<AuthResult>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password, dob }),
  });
  await persistAuth(result);
  return result;
}

export async function login(email: string, password: string): Promise<AuthResult> {
  const result = await request<AuthResult>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  await persistAuth(result);
  return result;
}

async function persistAuth(result: AuthResult): Promise<void> {
  await storage.set(KEYS.authToken, result.token);
  await storage.set(KEYS.userEmail, result.user.email);
}

export async function logout(): Promise<void> {
  try {
    await request('/auth/logout', { method: 'POST' });
  } finally {
    await storage.remove(KEYS.authToken);
  }
}

export async function deleteAccount(): Promise<void> {
  await request('/auth/account', { method: 'DELETE' });
  await storage.clearAll();
}

// --- Content ---------------------------------------------------------------

export async function getTodaySignals(): Promise<Signal[]> {
  return request<Signal[]>('/signals/today');
}

export async function getLatestNews(category?: string): Promise<NewsArticle[]> {
  const q = category && category !== 'all' ? `?category=${encodeURIComponent(category)}` : '';
  return request<NewsArticle[]>(`/news/latest${q}`);
}

export async function getGuides(): Promise<Guide[]> {
  return request<Guide[]>('/guides/list');
}

// --- User / compliance -----------------------------------------------------

/**
 * Record legal acceptance on the backend. Called from the Risk Disclosure
 * onboarding screen once all three checkboxes are ticked.
 * The backend stamps timestamp + ip server-side; we send the versions and
 * app version we accepted against.
 */
export async function recordAcceptance(appVersion: string): Promise<AcceptanceRecord> {
  const record = await request<AcceptanceRecord>('/user/acceptance', {
    method: 'POST',
    body: JSON.stringify({
      terms_version: LEGAL_VERSIONS.terms,
      privacy_version: LEGAL_VERSIONS.privacy,
      risk_disclosure_version: LEGAL_VERSIONS.riskDisclosure,
      app_version: appVersion,
    }),
  });
  await storage.setJSON(KEYS.acceptanceRecord, record);
  return record;
}

export async function getAcceptance(): Promise<AcceptanceRecord | null> {
  try {
    const record = await request<AcceptanceRecord | null>('/user/acceptance');
    if (record) await storage.setJSON(KEYS.acceptanceRecord, record);
    return record;
  } catch (err) {
    // Offline / not-yet-recorded: fall back to the cached copy if present.
    if (err instanceof ApiError && err.status === 404) return null;
    return storage.getJSON<AcceptanceRecord | null>(KEYS.acceptanceRecord, null);
  }
}

export async function getEntitlement(): Promise<Entitlement> {
  return request<Entitlement>('/user/entitlement');
}

export async function updateCapital(capitalUsd: number): Promise<void> {
  await request('/user/capital', {
    method: 'POST',
    body: JSON.stringify({ capital_usd: capitalUsd }),
  });
}

export { BASE_URL };
