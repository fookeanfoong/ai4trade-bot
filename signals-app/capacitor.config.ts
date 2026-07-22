import type { CapacitorConfig } from '@capacitor/cli';

/**
 * Capacitor configuration for AI4Trade Signals.
 *
 * Target: Android only, for distribution on Huawei AppGallery Global.
 * applicationId / appId MUST match the package registered in AppGallery Connect
 * and in `android/app/agconnect-services.json`.
 */
const config: CapacitorConfig = {
  appId: 'com.ai4trade.signals',
  appName: 'AI4Trade Signals',
  webDir: 'dist',
  // No iOS target — Huawei AppGallery / Android only.
  android: {
    // Huawei devices ship without Google Play Services; keep everything HMS-based.
    allowMixedContent: false,
  },
  plugins: {
    PushNotifications: {
      // On HMS devices push is delivered via Push Kit (see src/lib/hms/push.ts).
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
  server: {
    // Production loads bundled assets; androidScheme https is required for
    // secure-context web APIs (IndexedDB, crypto) used by the offline cache.
    androidScheme: 'https',
  },
};

export default config;
