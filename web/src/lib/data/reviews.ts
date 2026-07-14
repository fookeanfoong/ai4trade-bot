import type { Review } from '@/lib/types';

// 一期 mock 评价。verified_purchase 为二期托管交易后才有真实来源,一期为社区自述。
export const reviews: Review[] = [
  { id: 'r1', provider_id: 'p_openrouter', rating: 5, content: '一个 Key 直连所有模型,自动路由很省心,海外项目一直在用。', verified_purchase: false, created_at: '2026-06-20T10:00:00Z', region: 'EU', use_case: '生产环境', author: 'devlin' },
  { id: 'r2', provider_id: 'p_aihubmix', rating: 5, content: '支付宝直接充值,国内不用梯子就能调 Claude,延迟也低。', verified_purchase: false, created_at: '2026-06-25T08:30:00Z', region: 'CN', use_case: '个人开发', author: '小王' },
  { id: 'r3', provider_id: 'p_aihubmix', rating: 4, content: '整体稳定,偶尔高峰期排队,客服响应还算快。', verified_purchase: false, created_at: '2026-07-01T14:10:00Z', region: 'CN', use_case: '创业团队', author: 'ada' },
  { id: 'r4', provider_id: 'p_deepbricks', rating: 4, content: '价格是真的便宜,GPT-4o 折扣力度大,适合跑批量任务。', verified_purchase: false, created_at: '2026-06-28T09:00:00Z', region: 'CN', use_case: '数据处理', author: 'zhou' },
  { id: 'r5', provider_id: 'p_api2d', rating: 5, content: 'forward key 兼容官方 SDK,几乎零改造,发票也能开。', verified_purchase: false, created_at: '2026-07-03T11:20:00Z', region: 'HK', use_case: '企业', author: 'mikko' },
  { id: 'r6', provider_id: 'p_ohmygpt', rating: 4, content: '付款方式多,海外 PayPal 也支持,节点选择灵活。', verified_purchase: false, created_at: '2026-06-30T16:45:00Z', region: 'JP', use_case: '个人开发', author: 'kenji' },
  { id: 'r7', provider_id: 'p_closeai', rating: 4, content: '老牌子,能开发票,财务报销友好。', verified_purchase: false, created_at: '2026-06-18T13:00:00Z', region: 'CN', use_case: '企业', author: 'lily' },
  { id: 'r8', provider_id: 'p_laozhang', rating: 4, content: '新用户送了额度,社区群里问题都有人答。', verified_purchase: false, created_at: '2026-07-05T19:30:00Z', region: 'CN', use_case: '学习', author: 'tommy' },
  { id: 'r9', provider_id: 'p_poloai', rating: 4, content: '欧洲节点对我们跨境团队很友好,支持 SEPA。', verified_purchase: false, created_at: '2026-07-08T07:15:00Z', region: 'EU', use_case: '创业团队', author: 'hans' },
  { id: 'r10', provider_id: 'p_gptapius', rating: 4, content: '美区直连线路稳定,价格透明没有隐藏费用。', verified_purchase: false, created_at: '2026-07-09T12:00:00Z', region: 'US', use_case: '生产环境', author: 'ryan' },
];

export function getReviewsByProvider(providerId: string): Review[] {
  return reviews.filter((r) => r.provider_id === providerId);
}

export function avgRating(providerId: string): number {
  const rs = getReviewsByProvider(providerId);
  if (rs.length === 0) return 0;
  return Math.round((rs.reduce((s, r) => s + r.rating, 0) / rs.length) * 10) / 10;
}
