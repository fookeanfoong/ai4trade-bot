/**
 * Central app state: auth session, entitlement, legal-acceptance record,
 * capital, and notification preferences. One provider consumed app-wide.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import * as api from '@/lib/api';
import * as storage from '@/lib/storage';
import { KEYS } from '@/lib/storage';
import { LEGAL_VERSIONS } from '@/lib/compliance';
import type { AcceptanceRecord, AuthUser, Entitlement } from '@/lib/types';

export interface NotifPrefs {
  signals: boolean;
  news: boolean;
  product: boolean;
}

const DEFAULT_NOTIF_PREFS: NotifPrefs = { signals: true, news: true, product: false };

interface AppContextValue {
  ready: boolean;
  user: AuthUser | null;
  entitlement: Entitlement | null;
  acceptance: AcceptanceRecord | null;
  capitalUsd: number;
  notifPrefs: NotifPrefs;
  /** True while a session token exists. */
  isAuthenticated: boolean;
  /** True when the stored acceptance matches the current legal versions. */
  hasCurrentAcceptance: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, dob: string) => Promise<void>;
  logout: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  refreshEntitlement: () => Promise<void>;
  refreshAcceptance: () => Promise<void>;
  setCapital: (usd: number) => Promise<void>;
  setNotifPrefs: (prefs: NotifPrefs) => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);
  const [acceptance, setAcceptance] = useState<AcceptanceRecord | null>(null);
  const [capitalUsd, setCapitalUsd] = useState(0);
  const [notifPrefs, setNotifPrefsState] = useState<NotifPrefs>(DEFAULT_NOTIF_PREFS);

  const isAuthenticated = user !== null;

  const hasCurrentAcceptance = useMemo(() => {
    if (!acceptance) return false;
    return (
      acceptance.termsVersion === LEGAL_VERSIONS.terms &&
      acceptance.privacyVersion === LEGAL_VERSIONS.privacy &&
      acceptance.riskDisclosureVersion === LEGAL_VERSIONS.riskDisclosure
    );
  }, [acceptance]);

  // Boot: hydrate from local storage, then best-effort refresh from backend.
  useEffect(() => {
    (async () => {
      const [token, email, capital, prefs, cachedAcceptance] = await Promise.all([
        storage.get(KEYS.authToken),
        storage.get(KEYS.userEmail),
        storage.get(KEYS.capitalUsd),
        storage.getJSON<NotifPrefs>(KEYS.notifPrefs, DEFAULT_NOTIF_PREFS),
        storage.getJSON<AcceptanceRecord | null>(KEYS.acceptanceRecord, null),
      ]);

      if (capital) setCapitalUsd(Number(capital) || 0);
      setNotifPrefsState(prefs);
      setAcceptance(cachedAcceptance);

      if (token && email) {
        // We have a session; reconstruct a minimal user then refresh.
        setUser({ userId: 'me', email, joinDate: '' });
        await Promise.allSettled([refreshEntitlement(), refreshAcceptance()]);
      }
      setReady(true);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshEntitlement = useCallback(async () => {
    try {
      setEntitlement(await api.getEntitlement());
    } catch {
      /* keep previous / null on failure */
    }
  }, []);

  const refreshAcceptance = useCallback(async () => {
    const record = await api.getAcceptance();
    if (record) setAcceptance(record);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const { user: u } = await api.login(email, password);
      setUser(u);
      await Promise.allSettled([refreshEntitlement(), refreshAcceptance()]);
    },
    [refreshEntitlement, refreshAcceptance],
  );

  const signup = useCallback(
    async (email: string, password: string, dob: string) => {
      const { user: u } = await api.signup(email, password, dob);
      setUser(u);
      await refreshEntitlement();
    },
    [refreshEntitlement],
  );

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
    setEntitlement(null);
  }, []);

  const deleteAccount = useCallback(async () => {
    await api.deleteAccount();
    setUser(null);
    setEntitlement(null);
    setAcceptance(null);
  }, []);

  const setCapital = useCallback(async (usd: number) => {
    setCapitalUsd(usd);
    await storage.set(KEYS.capitalUsd, String(usd));
    try {
      await api.updateCapital(usd);
    } catch {
      /* stored locally; will re-sync opportunistically */
    }
  }, []);

  const setNotifPrefs = useCallback(async (prefs: NotifPrefs) => {
    setNotifPrefsState(prefs);
    await storage.setJSON(KEYS.notifPrefs, prefs);
  }, []);

  const value: AppContextValue = {
    ready,
    user,
    entitlement,
    acceptance,
    capitalUsd,
    notifPrefs,
    isAuthenticated,
    hasCurrentAcceptance,
    login,
    signup,
    logout,
    deleteAccount,
    refreshEntitlement,
    refreshAcceptance,
    setCapital,
    setNotifPrefs,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
