#!/usr/bin/env bash
# ============================================================================
# Build a signed release AAB for AI4Trade Signals (Huawei AppGallery).
#
# Prerequisites (see README):
#   - android/app/agconnect-services.json present (from AppGallery Connect)
#   - android/keystore.properties present + the keystore it points to
#   - JDK 17 and the Android SDK installed; ANDROID_HOME / local.properties set
#
# Output: android/app/build/outputs/bundle/release/app-release.aab
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Installing dependencies (npm ci)"
npm ci

echo "==> Building web assets (vite)"
npm run build

echo "==> Syncing Capacitor -> android"
npx cap sync android

# --- Preflight checks ------------------------------------------------------
if [ ! -f android/app/agconnect-services.json ]; then
  echo "WARNING: android/app/agconnect-services.json is missing."
  echo "         HMS Push / IAP / Analytics will not work in this build."
  echo "         Download it from AppGallery Connect and place it there."
fi

if [ ! -f android/keystore.properties ]; then
  echo "ERROR: android/keystore.properties is missing — cannot sign the release."
  echo "       Copy android/keystore.properties.example and fill it in."
  exit 1
fi

echo "==> Assembling signed release bundle (bundleRelease)"
cd android
./gradlew bundleRelease

AAB="app/build/outputs/bundle/release/app-release.aab"
if [ -f "$AAB" ]; then
  echo "==> Done: android/$AAB"
else
  echo "ERROR: expected AAB not found at android/$AAB"
  exit 1
fi
