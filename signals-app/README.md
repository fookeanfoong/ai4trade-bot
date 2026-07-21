# AI4Trade Signals

Mobile app delivering **daily pre-market educational stock analysis** for
US-market tickers — entry, stop-loss and target levels, position-sized to the
user's capital. Companion app to **aicompareapi.com**.

> **Educational content only. Not investment advice. Trading carries risk of loss.**

- **Stack:** Capacitor 6 · React 18 · TypeScript · Tailwind CSS · Vite
- **Target:** Android only, for distribution on **Huawei AppGallery Global**
- **Package / applicationId:** `com.ai4trade.signals`
- **Android:** target API 34, min API 24
- **HMS:** Push Kit (notifications), In-App Purchases (subscriptions), Analytics (optional)

---

## Table of contents

1. [Quick start (web dev)](#quick-start-web-dev)
2. [Environment variables](#environment-variables)
3. [Project layout](#project-layout)
4. [Compliance — where the strings live](#compliance--where-the-strings-live)
5. [Android / Huawei setup](#android--huawei-setup)
   - [Place `agconnect-services.json`](#1-place-agconnect-servicesjson)
   - [Configure HMS IAP product IDs](#2-configure-hms-iap-product-ids)
   - [Build & sign the release AAB](#3-build--sign-the-release-aab)
   - [Safeguarding the keystore](#4-safeguarding-the-keystore)
   - [Upload to AppGallery Connect](#5-upload-to-appgallery-connect)
6. [Backend endpoints](#backend-endpoints)
7. [Push notifications](#push-notifications)

---

## Quick start (web dev)

```bash
cd signals-app
cp .env.example .env        # fill in values (see below)
npm install
npm run dev                 # http://localhost:5173
```

The app runs in the browser for development. HMS features (Push, IAP, Analytics)
are native-only and safely no-op on web — you can exercise every screen, the
onboarding + legal-acceptance flow, i18n, and the offline cache in the browser.

Useful scripts:

| Script | What it does |
| --- | --- |
| `npm run dev` | Vite dev server |
| `npm run build` | Type-check + production web build to `dist/` |
| `npm run verify` | Compliance word-scan **+** build (run before every release) |
| `npm run check:compliance` | Scan locale files for banned marketing words |
| `npm run lint` | ESLint |
| `npm run cap:add:android` | Generate the native Android project (`android/`) |
| `npm run cap:sync` | Copy web build + plugins into `android/` |
| `npm run android:build:release` | Build a signed release AAB (see below) |

---

## Environment variables

Copy `.env.example` → `.env`. Only `VITE_`-prefixed vars are exposed to the app.

| Var | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Base URL of the aicompareapi.com REST API |
| `VITE_FINNHUB_API_KEY` | Finnhub key for the News feed (free tier 60 calls/min). **Proxy through the backend in production** — do not ship a key in the client bundle. |
| `VITE_TERMS_VERSION` / `VITE_PRIVACY_VERSION` / `VITE_RISK_DISCLOSURE_VERSION` | Version stamps of the hosted legal docs. Bump when a doc changes to force re-acceptance. |
| `VITE_SUPPORT_EMAIL` | Address the Settings → Contact support row opens |

> **API keys:** none are committed. Provide them via `.env` locally and via your
> CI/secrets store for builds. Ask the project owner before wiring any real
> third-party key.

---

## Project layout

```
signals-app/
├── src/
│   ├── lib/
│   │   ├── compliance.ts     ← ALL AppGallery compliance strings + banned-word list
│   │   ├── api.ts            ← REST client (aicompareapi.com)
│   │   ├── browser.ts        ← in-app browser (@capacitor/browser) — all legal links
│   │   ├── storage.ts        ← Capacitor Preferences wrapper
│   │   ├── offline.ts        ← IndexedDB cache (signals / news / guides)
│   │   ├── position.ts       ← position sizing from capital
│   │   ├── fixtures.ts       ← placeholder data (pre-API / offline demo)
│   │   └── hms/              ← push.ts · iap.ts · analytics.ts (native bridges)
│   ├── context/AppContext.tsx  ← auth · entitlement · acceptance · prefs
│   ├── i18n/                  ← react-i18next: en · zh-Hans · zh-Hant
│   ├── components/            ← ComplianceFooter · TabBar · SignalCard · CandleChart · …
│   ├── screens/
│   │   ├── onboarding/        ← Welcome · AgeConfirm · CreateAccount · CapitalInput
│   │   │                        · RiskDisclosure (3 checkboxes, wired) · NotificationPermission
│   │   ├── Signals.tsx · News.tsx · Learn.tsx · Paywall.tsx · Settings.tsx
│   │   └── auth/AuthScreen.tsx
│   └── App.tsx               ← routing gates (onboarding → auth → acceptance → app)
├── android/                  ← Capacitor Android project (HMS-configured)
├── scripts/
│   ├── build-release.sh      ← one-command signed AAB build
│   └── check-compliance.mjs  ← banned-word guard (CI)
└── capacitor.config.ts
```

---

## Compliance — where the strings live

AppGallery rejects finance/education apps that read as investment advice. Every
compliance requirement is centralised so future updates touch one place.

- **All disclaimer copy:** `src/lib/compliance.ts` (canonical English) **and**
  the `compliance.*` / `onboarding.risk*` keys in `src/i18n/locales/*.json`
  (translations). Edit copy in the locale files; edit URLs/versions/prefix in
  `compliance.ts`.
- **The three legal URLs** (`LEGAL_URLS` in `compliance.ts`):
  `https://aicompareapi.com/terms`, `/privacy`, `/risk-disclosure`.
  Opened **only** via the in-app browser (`src/lib/browser.ts` → `openLegal`).
- **Banned words** (buy, sell now, guaranteed, profit, winner, sure win,
  recommendation): listed in `compliance.ts` and enforced by
  `npm run check:compliance` over the locale files. Runs in `npm run verify`.
- **Push prefix** `[Educational]`: `compliance.ts` (`PUSH_PREFIX`,
  `buildPushBody`) for JS, and re-enforced natively in
  `android/.../HmsMessagingService.java` (`ensureEducationalPrefix`).

Where each required disclaimer surfaces:

| Requirement | Location in code |
| --- | --- |
| Risk Disclosure & Acceptance (3 checkboxes, cannot skip, backend timestamp) | `screens/onboarding/RiskDisclosure.tsx` |
| Persistent footer on every Signals view (+ "Learn more" → Risk Disclosure) | `components/ComplianceFooter.tsx` (via `MainLayout`) |
| Paywall micro-copy (auto-renew + Terms link) | `screens/Paywall.tsx` |
| Settings legal section (3 rows + "Acceptance recorded on …") | `screens/Settings.tsx` |
| First-signal modal (once per install) | `components/FirstSignalModal.tsx` + `screens/Signals.tsx` |
| Push body `[Educational]` prefix | `lib/hms/push.ts` + `HmsMessagingService.java` |
| Age gate (18+) | `screens/onboarding/AgeConfirm.tsx` (client) + `/auth/signup` (server) |

---

## Android / Huawei setup

The `android/` project is already generated and HMS-configured. If you ever need
to regenerate it: `npm run build && npm run cap:add:android`, then re-apply the
HMS edits (they live in `android/build.gradle`, `android/app/build.gradle`,
`android/app/src/main/AndroidManifest.xml`, and the `com/ai4trade/signals/*.java`
bridge files).

**Prerequisites:** JDK 17, Android SDK (API 34), `ANDROID_HOME` set. Do **not**
run `playwright install`-style browser fetches; standard Android tooling only.

### 1. Place `agconnect-services.json`

1. In **AppGallery Connect** → *My projects* → your project → add an Android app
   with package name **`com.ai4trade.signals`**.
2. Download **`agconnect-services.json`**.
3. Put it at **`android/app/agconnect-services.json`**.
   - `android/app/agconnect-services.json.example` shows the expected shape.
   - The real file is **gitignored** — never commit it.
4. Register your signing certificate's **SHA-256 fingerprint** in AppGallery
   Connect (*Project settings → General information → SHA-256 certificate
   fingerprint*). Get it with:
   ```bash
   keytool -list -v -keystore ai4trade-release.jks -alias ai4trade
   ```

When the file is present, `android/app/build.gradle` auto-applies the
`com.huawei.agconnect` plugin. Without it the app still builds, but Push/IAP/
Analytics will not function.

### 2. Configure HMS IAP product IDs

Create these **subscription** products in AppGallery Connect
(*Operate → Products → Subscriptions*). The IDs must match exactly — they are
defined in `src/lib/hms/iap.ts` (`PRODUCTS`):

| Product ID | Plan | Price | Label |
| --- | --- | --- | --- |
| `sub_monthly` | Monthly | USD $20.00 | — |
| `sub_6month` | 6 Months | USD $108.00 | Save 10% |
| `sub_yearly` | Yearly | USD $208.00 | Best Value — Save 13% |

Notes:
- Put all three in **one subscription group** so upgrades/downgrades pro-rate.
- Configure the **3 US-trading-day free trial** on the group (the UI also shows
  the "3 US trading days free — no card required" banner).
- Prices are illustrative labels in the UI; the authoritative price shown at
  purchase comes from HMS via `queryProducts()`.
- Entitlement is verified server-side via `GET /user/entitlement`; the client
  IAP check is only a fast hint.

### 3. Build & sign the release AAB

One command (wraps build → `cap sync` → `bundleRelease`):

```bash
cd signals-app
./scripts/build-release.sh
# → android/app/build/outputs/bundle/release/app-release.aab
```

Manual equivalent:

```bash
npm ci
npm run build
npx cap sync android
cd android
./gradlew bundleRelease
```

**Signing** is wired in `android/app/build.gradle`. Create the keystore and
credentials file:

```bash
# 1. Generate a release keystore (KEEP IT SAFE — see below)
keytool -genkeypair -v \
  -keystore ai4trade-release.jks \
  -alias ai4trade \
  -keyalg RSA -keysize 2048 -validity 10000

# 2. Copy the template and fill in your paths/passwords
cp android/keystore.properties.example android/keystore.properties
#   storeFile=../ai4trade-release.jks   (relative to android/, or absolute)
#   storePassword=…  keyAlias=ai4trade  keyPassword=…
```

`keystore.properties` and `*.jks/*.keystore` are **gitignored**. If
`keystore.properties` is missing, the release build is unsigned (debug builds
still work).

### 4. Safeguarding the keystore

> **Losing this keystore means you can never update the app on AppGallery under
> the same identity.** Treat it like a production secret.

- **Back it up** in at least two secure, encrypted locations (e.g. a password
  manager vault + an encrypted offline drive). Never in the git repo.
- Store the keystore password, key alias, and key password in a secrets manager
  — separately from the keystore file.
- In CI, inject the keystore as a base64-encoded secret and write it to disk at
  build time; write `keystore.properties` from secret vars. Never echo them to
  logs.
- Restrict access to the people who cut releases.
- Record the **SHA-256 fingerprint** (also registered in AppGallery Connect) so
  you can verify a build was signed with the right key.

### 5. Upload to AppGallery Connect

1. **AppGallery Connect** → your app → *Distribute → App information* — complete
   listing, category (Finance/Education), age rating (**18+**), and privacy URL
   (`https://aicompareapi.com/privacy`).
2. *Distribute → Version information* → **Software package** → upload
   `app-release.aab`.
3. Provide the **data-safety / privacy** declarations and link the three legal
   docs (Terms, Privacy, Risk Disclosure).
4. For the compliance review, note that the app is **educational content, not
   investment advice**, enforces an **18+ age gate**, and requires explicit
   **acceptance of Terms, Privacy, and Risk Disclosure** before use.
5. Submit for review.

---

## Backend endpoints

Consumed from `src/lib/api.ts` (base = `VITE_API_BASE_URL`):

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/signup` | `{ email, password, dob }` — server re-validates 18+ |
| POST | `/auth/login` | `{ email, password }` |
| POST | `/auth/logout` | |
| DELETE | `/auth/account` | delete account |
| GET | `/signals/today` | today's educational setups |
| GET | `/news/latest?category=` | market news (backend proxies Finnhub) |
| GET | `/guides/list` | Learn guides |
| POST | `/user/acceptance` | record legal acceptance (see below) |
| GET | `/user/acceptance` | latest acceptance record (Settings + re-prompt) |
| GET | `/user/entitlement` | `{ status, tier, expires_at, trial_days_used }` |
| POST | `/user/capital` | `{ capital_usd }` |

**`POST /user/acceptance`** — the client sends
`{ terms_version, privacy_version, risk_disclosure_version, app_version }`;
the **backend stamps `timestamp` and `ip`** and stores the record against the
user account. Returns the stored `AcceptanceRecord`, which Settings displays as
"Acceptance recorded on …". If the stored versions differ from the current
`VITE_*_VERSION` values, the app re-prompts for acceptance on next launch.

---

## Push notifications

- Native delivery: **HMS Push Kit** via `HmsMessagingService.java`, which
  displays notifications and **forces the `[Educational]` prefix** on every body.
- The **backend must send bodies in the canonical format**:
  `[Educational] {ticker} setup for {date} — tap to view analysis`.
  The native service re-applies the prefix defensively, but the backend should
  send it correctly.
- Device tokens arrive via `onNewToken` (persisted by `TokenStore`) and via the
  Capacitor `registration` event; forward the token to your backend so it can
  target the device. Notification preferences live in Settings and Preferences
  (`notif_prefs`).

---

_Compliance is a product requirement, not a formality. Before any release run
`npm run verify` and re-read [Compliance — where the strings live](#compliance--where-the-strings-live)._
