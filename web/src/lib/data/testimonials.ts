// 研究报告页的见证(testimonials)。
// ⚠️ 目前为占位内容,请替换成真实评价(拿到用户/客户同意后再放真名与职称)。
// tag = 平台 + 场景,例如 'OpenRouter · 生产环境',增强可信度。

export interface Testimonial {
  quote: string;
  name: string;
  role: string;
  tag: string;
}

export const testimonials: Testimonial[] = [
  {
    quote: '[见证占位 —— 换成真实评价:这份报告帮我在选中转站时避开了一次跑路。]',
    name: '[姓名]',
    role: 'CTO',
    tag: 'OpenRouter · 生产环境',
  },
  {
    quote: '[见证占位 —— 换成真实评价:隐藏费用那一节直接帮我省下每月一大笔。]',
    name: '[姓名]',
    role: '独立开发者',
    tag: 'AiHubMix · 个人项目',
  },
  {
    quote: '[见证占位 —— 换成真实评价:省了我至少 100 小时自己一家家调研的时间。]',
    name: '[姓名]',
    role: '技术负责人',
    tag: 'DeepSeek · 创业团队',
  },
];
