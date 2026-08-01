/**
 * HMS In-App Purchases (IAP) bridge — subscriptions.
 *
 * Huawei IAP has no official Capacitor plugin, so this module talks to a thin
 * native bridge plugin registered on the Android side (see
 * android/app/src/main/java/com/ai4trade/signals/HmsIapPlugin.java, generated
 * per the README). The bridge exposes:
 *   - queryProducts(productIds)      -> IapProduct[]
 *   - purchase(productId)            -> IapPurchase
 *   - restorePurchases()             -> IapPurchase[]  (owned subscriptions)
 *   - isEnvReady()                   -> boolean
 *
 * On web (dev) the bridge is absent, so every call resolves to a safe stub and
 * the UI shows products from PRODUCTS with purchasing disabled.
 */
import { Capacitor, registerPlugin } from '@capacitor/core';

/** The three subscription products, matching AppGallery Connect IAP config. */
export const PRODUCTS = [
  {
    productId: 'sub_monthly',
    title: 'Monthly',
    priceLabel: 'USD $20.00',
    badge: null as string | null,
    period: 'month',
  },
  {
    productId: 'sub_6month',
    title: '6 Months',
    priceLabel: 'USD $108.00',
    badge: 'Save 10%',
    period: '6 months',
  },
  {
    productId: 'sub_yearly',
    title: 'Yearly',
    priceLabel: 'USD $208.00',
    badge: 'Best Value — Save 13%',
    period: 'year',
  },
] as const;

export type ProductId = (typeof PRODUCTS)[number]['productId'];
export const PRODUCT_IDS: ProductId[] = PRODUCTS.map((p) => p.productId);

export interface IapProduct {
  productId: string;
  price: string;
  currency: string;
  title: string;
}

export interface IapPurchase {
  productId: string;
  purchaseToken: string;
  /** HMS purchase state: 0 = purchased/owned. */
  purchaseState: number;
  /** Whether the subscription is currently active (not expired/cancelled). */
  active: boolean;
}

/** Native bridge contract implemented by HmsIapPlugin on Android. */
interface HmsIapPlugin {
  isEnvReady(): Promise<{ ready: boolean }>;
  queryProducts(options: { productIds: string[] }): Promise<{ products: IapProduct[] }>;
  purchase(options: { productId: string }): Promise<{ purchase: IapPurchase }>;
  restorePurchases(): Promise<{ purchases: IapPurchase[] }>;
}

const HmsIap = registerPlugin<HmsIapPlugin>('HmsIap');

function isNative(): boolean {
  return Capacitor.getPlatform() !== 'web' && Capacitor.isPluginAvailable('HmsIap');
}

export async function isIapReady(): Promise<boolean> {
  if (!isNative()) return false;
  try {
    const { ready } = await HmsIap.isEnvReady();
    return ready;
  } catch {
    return false;
  }
}

export async function queryProducts(): Promise<IapProduct[]> {
  if (!isNative()) return [];
  const { products } = await HmsIap.queryProducts({ productIds: PRODUCT_IDS });
  return products;
}

/** Start a subscription purchase. Throws if IAP is unavailable. */
export async function purchase(productId: ProductId): Promise<IapPurchase> {
  if (!isNative()) {
    throw new Error('In-app purchases are only available on Huawei devices.');
  }
  const { purchase: result } = await HmsIap.purchase({ productId });
  return result;
}

/** Restore owned subscriptions. Returns [] on web. */
export async function restorePurchases(): Promise<IapPurchase[]> {
  if (!isNative()) return [];
  const { purchases } = await HmsIap.restorePurchases();
  return purchases;
}

/**
 * Local entitlement check derived from owned purchases. The authoritative
 * check is server-side via /user/entitlement; this is the fast client hint.
 */
export function hasActiveSubscription(purchases: IapPurchase[]): boolean {
  return purchases.some((p) => p.active && PRODUCT_IDS.includes(p.productId as ProductId));
}
