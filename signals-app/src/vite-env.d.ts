/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_FINNHUB_API_KEY?: string;
  readonly VITE_TERMS_VERSION?: string;
  readonly VITE_PRIVACY_VERSION?: string;
  readonly VITE_RISK_DISCLOSURE_VERSION?: string;
  readonly VITE_SUPPORT_EMAIL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
