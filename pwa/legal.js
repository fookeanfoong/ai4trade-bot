// ============================================================================
// AI4Trade Signals — 法律文本(隐私政策 + 条款/免责声明)
// EN + 中文;其他语言回退英文。渲染时会把 {BRAND} {CONTACT} 替换成实际值。
// ⚠️ 这是通用模板,不是律师意见。上线前请自行核对,并填好联系邮箱、公司主体、
//    适用法律等信息(config.js 里 feedback.email 会自动填进 {CONTACT})。
// ============================================================================
(function () {
  const UPDATED = '2026-07';

  const LEGAL = {
    privacy: {
      title: { en: 'Privacy Policy', zh: '隐私政策' },
      updated: UPDATED,
      body: {
        en: `
<p>This Privacy Policy explains how {BRAND} ("we", "the app") handles information when you use our website and app.</p>
<h3>1. Information we collect</h3>
<ul>
  <li><b>Stored on your device only:</b> your capital, daily target, language, and trial/subscription status are saved in your browser's local storage. They stay on your device and are not sent to us.</li>
  <li><b>Information you provide:</b> if you submit feedback or contact us, we receive the message and any email you include.</li>
  <li><b>Payments:</b> subscriptions are processed by <b>Stripe</b>. We never see or store your card number — Stripe handles it under its own privacy policy.</li>
</ul>
<h3>2. How we use information</h3>
<p>To provide and improve the service, respond to your feedback, and manage subscriptions through Stripe. We do not sell your personal information.</p>
<h3>3. Cookies &amp; local storage</h3>
<p>We use your browser's local storage to remember your settings and access status. We do not use third-party advertising trackers.</p>
<h3>4. Sharing</h3>
<p>We share information only with service providers needed to run the app (e.g. Stripe for payments), or where required by law.</p>
<h3>5. Data retention &amp; your rights</h3>
<p>You can clear device-stored data anytime by clearing your browser data. For any feedback/email you sent us, you may request access or deletion by contacting {CONTACT}.</p>
<h3>6. Children</h3>
<p>The service is not intended for anyone under 18.</p>
<h3>7. Changes</h3>
<p>We may update this policy; material changes will be reflected by the "last updated" date.</p>
<h3>8. Contact</h3>
<p>Questions? Email {CONTACT}.</p>`,
        zh: `
<p>本隐私政策说明 {BRAND}（下称"我们""本 App"）在你使用本网站与 App 时如何处理信息。</p>
<h3>1. 我们收集的信息</h3>
<ul>
  <li><b>仅存在你设备上：</b>你的本金、每日目标、语言、试用/订阅状态，保存在你浏览器的本地存储里，留在你设备上，不会发送给我们。</li>
  <li><b>你主动提供的信息：</b>当你提交反馈或联系我们时，我们会收到你的留言以及你填写的邮箱。</li>
  <li><b>支付信息：</b>订阅由 <b>Stripe</b> 处理。我们从不接触或保存你的卡号——由 Stripe 依其隐私政策处理。</li>
</ul>
<h3>2. 我们如何使用信息</h3>
<p>用于提供和改进服务、回复你的反馈、通过 Stripe 管理订阅。我们不会出售你的个人信息。</p>
<h3>3. Cookie 与本地存储</h3>
<p>我们用浏览器本地存储记住你的设置和访问状态。我们不使用第三方广告追踪。</p>
<h3>4. 信息共享</h3>
<p>仅与运行 App 所必需的服务商共享（如 Stripe 处理支付），或在法律要求时共享。</p>
<h3>5. 数据留存与你的权利</h3>
<p>你可随时清除浏览器数据来清空设备上的存储。对于你发给我们的反馈/邮箱，可联系 {CONTACT} 申请查阅或删除。</p>
<h3>6. 未成年人</h3>
<p>本服务不面向 18 岁以下人士。</p>
<h3>7. 变更</h3>
<p>我们可能更新本政策；重大变更将通过"最后更新"日期体现。</p>
<h3>8. 联系我们</h3>
<p>有疑问请邮件联系 {CONTACT}。</p>`,
      },
    },

    terms: {
      title: { en: 'Terms & Disclaimer', zh: '服务条款与免责声明' },
      updated: UPDATED,
      body: {
        en: `
<div class="disclaimer" style="margin-bottom:14px"><b>Not investment advice.</b> {BRAND} is an educational tool. Its signals come from a simulated bot and do not constitute investment advice or any guarantee of returns. Trading involves the risk of losing money.</div>
<h3>1. What the service is</h3>
<p>{BRAND} surfaces informational, simulated trading signals for education and research. We are <b>not</b> a broker, dealer, or investment adviser, and we do not manage money or place trades for you.</p>
<h3>2. No guarantees, your responsibility</h3>
<ul>
  <li>We do not promise profit. Simulated or past results do not predict future results.</li>
  <li>The "daily target" is only used to size positions — it is not a promise you will earn it.</li>
  <li>You make all decisions and place all trades in your own broker. You are solely responsible for your outcomes and for complying with the laws and rules that apply to you.</li>
</ul>
<h3>3. Subscriptions &amp; billing</h3>
<p>The first trading day is free. Paid plans (monthly / yearly) are billed through Stripe and renew automatically until cancelled. You can cancel anytime from your Stripe receipt; cancellation stops future renewals. Contact {CONTACT} for billing questions.</p>
<h3>4. Limitation of liability</h3>
<p>To the maximum extent permitted by law, {BRAND} is not liable for any trading losses or damages arising from use of the service. The service is provided "as is" without warranties.</p>
<h3>5. Acceptable use</h3>
<p>Don't misuse the service, resell the signals, or use them to mislead others.</p>
<h3>6. Changes</h3>
<p>We may update these terms or the service; continued use means you accept the changes.</p>
<h3>7. Contact</h3>
<p>Email {CONTACT}.</p>`,
        zh: `
<div class="disclaimer" style="margin-bottom:14px"><b>非投资建议。</b>{BRAND} 是教育工具。其信号来自模拟机器人，不构成投资建议，也不承诺任何收益。交易有亏损风险。</div>
<h3>1. 本服务是什么</h3>
<p>{BRAND} 提供信息性、模拟的交易信号，供学习与研究。我们<b>不是</b>券商、交易商或投资顾问，不为你管理资金，也不替你下单。</p>
<h3>2. 不作保证，责任在你</h3>
<ul>
  <li>我们不承诺盈利。模拟或过往结果不预示未来结果。</li>
  <li>"每日目标"仅用于计算仓位，不代表你会赚到。</li>
  <li>所有决定与下单都由你在自己的券商完成。你的盈亏，以及遵守适用于你的法律法规，均由你自己负责。</li>
</ul>
<h3>3. 订阅与计费</h3>
<p>首个交易日免费。付费方案（月付/年付）通过 Stripe 计费并自动续订，直至取消。你可随时在 Stripe 收据里取消，取消后不再续订。计费问题请联系 {CONTACT}。</p>
<h3>4. 责任限制</h3>
<p>在法律允许的最大范围内，{BRAND} 不对因使用本服务而产生的任何交易亏损或损害负责。服务按"现状"提供，不含任何担保。</p>
<h3>5. 合理使用</h3>
<p>请勿滥用服务、转售信号，或用其误导他人。</p>
<h3>6. 变更</h3>
<p>我们可能更新条款或服务；继续使用即表示接受变更。</p>
<h3>7. 联系我们</h3>
<p>邮件 {CONTACT}。</p>`,
      },
    },
  };

  window.LEGAL = LEGAL;
})();
