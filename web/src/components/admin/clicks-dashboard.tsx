'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { MousePointerClick, TrendingUp, Calendar, Link2, AlertTriangle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { ClickStats } from '@/lib/clicks';

const PRIMARY = 'hsl(var(--primary))';

function StatTile({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {icon}
          {label}
        </div>
        <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
        {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export function ClicksDashboard({ stats }: { stats: ClickStats }) {
  const maxProvider = Math.max(1, ...stats.byProvider.map((p) => p.clicks));
  const top = stats.byProvider[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">联盟点击后台</h1>
          <p className="text-sm text-muted-foreground">
            每次「前往中转站」的点击都会记在这里,用来核对哪家带量、对账返佣。
          </p>
        </div>
        {stats.isDemo && (
          <Badge variant="secondary" className="gap-1">
            <AlertTriangle className="h-3.5 w-3.5" />
            演示数据
          </Badge>
        )}
      </div>

      {stats.isDemo && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
          <div>
            <p className="font-medium">这是示例预览,还没有真实点击。</p>
            <p className="mt-1 text-muted-foreground">
              打开任意中转站页面点一次「前往」按钮,刷新本页即可看到真实数据(本地开发 /
              长驻服务器有效;无状态部署请接二期数据库)。
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          icon={<MousePointerClick className="h-3.5 w-3.5" />}
          label="总点击"
          value={stats.total}
        />
        <StatTile icon={<Calendar className="h-3.5 w-3.5" />} label="今日" value={stats.today} />
        <StatTile
          icon={<TrendingUp className="h-3.5 w-3.5" />}
          label="近 7 天"
          value={stats.last7d}
        />
        <StatTile
          icon={<Link2 className="h-3.5 w-3.5" />}
          label="带量最多"
          value={top ? top.name : '—'}
          sub={top ? `${top.clicks} 次点击` : undefined}
        />
      </div>

      {/* 14 天趋势 */}
      <Card>
        <CardContent className="p-4">
          <h2 className="mb-3 text-sm font-semibold">近 14 天点击趋势</h2>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.byDay} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis
                  dataKey="day"
                  tickFormatter={(d: string) => d.slice(5)}
                  tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: 'hsl(var(--muted))', opacity: 0.4 }}
                  contentStyle={{
                    background: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="clicks" fill={PRIMARY} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* 各中转站点击排行 */}
      <Card>
        <CardContent className="p-4">
          <h2 className="mb-3 text-sm font-semibold">各中转站点击排行</h2>
          <div className="space-y-2">
            {stats.byProvider.map((p) => (
              <div key={p.provider_id} className="flex items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={p.logo} alt="" width={24} height={24} className="h-6 w-6 shrink-0 rounded" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate font-medium">
                      {p.name}
                      {!p.affiliateUrl && (
                        <span className="ml-2 text-xs text-amber-500">未配置返佣链接</span>
                      )}
                    </span>
                    <span className="tabular-nums text-muted-foreground">{p.clicks}</span>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${(p.clicks / maxProvider) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 来源页 */}
        <Card>
          <CardContent className="p-4">
            <h2 className="mb-3 text-sm font-semibold">点击来源页 Top</h2>
            <table className="w-full text-sm">
              <tbody>
                {stats.bySourcePage.slice(0, 8).map((r) => (
                  <tr key={r.page} className="border-b border-border/60 last:border-0">
                    <td className="py-1.5 pr-2">
                      <code className="text-xs text-muted-foreground">{r.page}</code>
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{r.clicks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* 最近点击 */}
        <Card>
          <CardContent className="p-4">
            <h2 className="mb-3 text-sm font-semibold">最近点击</h2>
            {stats.recent.length === 0 ? (
              <p className="text-sm text-muted-foreground">暂无真实点击记录。</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {stats.recent.map((c, i) => (
                    <tr key={i} className="border-b border-border/60 last:border-0">
                      <td className="py-1.5 pr-2 font-medium">{c.provider_slug ?? c.provider_id}</td>
                      <td className="py-1.5 pr-2 text-xs text-muted-foreground">
                        <code>{c.source_page ?? '—'}</code>
                      </td>
                      <td className="py-1.5 text-right text-xs text-muted-foreground">
                        {c.ts.slice(5, 16).replace('T', ' ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
