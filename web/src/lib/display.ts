import type { PaymentMethod, Region } from '@/lib/types';

// 付款方式与地区的展示标签(跨语言通用短名,便于国内用户识别)
export const paymentLabel: Record<PaymentMethod, string> = {
  alipay: '支付宝 Alipay',
  wechat: '微信 WeChat',
  unionpay: '银联 UnionPay',
  card: 'Card',
  paypal: 'PayPal',
  usdt: 'USDT',
  wise: 'Wise',
  sepa: 'SEPA',
};

export const paymentShort: Record<PaymentMethod, string> = {
  alipay: '支付宝',
  wechat: '微信',
  unionpay: '银联',
  card: 'Card',
  paypal: 'PayPal',
  usdt: 'USDT',
  wise: 'Wise',
  sepa: 'SEPA',
};

export const regionLabel: Record<Region, string> = {
  CN: '中国大陆',
  HK: '香港',
  TW: '台湾',
  JP: '日本',
  KR: '韩国',
  SG: '新加坡',
  EU: '欧盟',
  US: '美国',
  Global: '全球',
};

export const ALL_REGIONS: Region[] = ['CN', 'HK', 'TW', 'JP', 'KR', 'SG', 'EU', 'US', 'Global'];
export const ALL_PAYMENTS: PaymentMethod[] = [
  'alipay',
  'wechat',
  'unionpay',
  'card',
  'paypal',
  'usdt',
  'wise',
  'sepa',
];
