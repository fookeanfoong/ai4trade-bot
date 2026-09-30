# ============================================================================
#  BTCScalper(XM BTCUSD#)—— 一键安装/更新到 MT5
#
#  用法(PowerShell,普通权限即可):
#      irm "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/jolly-lamport-55kb0p/mql5/install_btc.ps1" | iex
#
#  和 update_mt5.ps1 同样的三道保险:
#     1. MetaEditor 开着就提醒先关 BTCScalper.mq5(F7 编译的是编辑器缓冲区,不是磁盘)
#     2. 下载后校验内容标记,确认拿到的是这一版
#     3. 删掉旧的 BTCScalper.ex5 —— 编译不过时 EA 直接加载不了,不会静默跑旧代码
# ============================================================================

$ErrorActionPreference = 'Stop'

$Base = "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/jolly-lamport-55kb0p"
# 远端路径 -> (MQL5 子目录, 本地文件名)
$Files = [ordered]@{
    "mql5/BTCScalper.mq5"                = @("Experts", "BTCScalper.mq5")
    "presets/btc/default_validated.set"  = @("Presets", "BTCScalper_validated.set")
    "presets/btc/m5_fast.set"            = @("Presets", "BTCScalper_m5_fast.set")
}

$MustHave = @(
    'InpMaxSpreadATRPct',    # 点差占 ATR 上限
    'InpDeadMarketRatio',    # 死市过滤
    'InpCrashPct',           # 崩盘/暴涨保护
    'InpMaxHoldBars',        # 时间止损
    'InpWeekendRiskMult',    # 周末降风险
    'DailyVWAP',             # 当日 VWAP
    'PERIOD_H1'              # 默认周期 = 样本外验证通过的 H1
)

Write-Host ""
Write-Host "=== BTCScalper 安装 / 更新 ===" -ForegroundColor Cyan

# --- 1) MetaEditor 开着就提醒 -------------------------------------------------
$me = Get-Process -Name "metaeditor64","metaeditor" -ErrorAction SilentlyContinue
if ($me) {
    Write-Host ""
    Write-Host "⚠️  检测到 MetaEditor 正在运行。" -ForegroundColor Yellow
    Write-Host "    如果 BTCScalper.mq5 在里面开着,请先关掉那个标签页," -ForegroundColor Yellow
    Write-Host "    否则 F7 编译的还是编辑器里的旧内容。" -ForegroundColor Yellow
    Write-Host ""
    $ans = Read-Host "已经关掉了吗?(y = 继续 / 其它 = 退出)"
    if ($ans -ne 'y' -and $ans -ne 'Y') {
        Write-Host "已退出。关掉文件后重跑本脚本。" -ForegroundColor Red
        return
    }
}

# --- 2) 找 MT5 数据目录 -------------------------------------------------------
$roots = @()
$tpath = Join-Path $env:APPDATA "MetaQuotes\Terminal"
if (Test-Path $tpath) {
    $roots = @(Get-ChildItem $tpath -Directory -ErrorAction SilentlyContinue |
               Where-Object { Test-Path (Join-Path $_.FullName "MQL5\Experts") })
}
if ($roots.Count -eq 0) {
    Write-Host "找不到 MT5 数据目录。请在 MT5 里点【文件 -> 打开数据文件夹】确认位置。" -ForegroundColor Red
    return
}
Write-Host "找到 $($roots.Count) 个 MT5 终端目录" -ForegroundColor Gray

$okAll = $true
foreach ($r in $roots) {
    Write-Host ""
    Write-Host "-> $($r.FullName)" -ForegroundColor White

    foreach ($remote in $Files.Keys) {
        $sub  = $Files[$remote][0]
        $name = $Files[$remote][1]
        $dir  = Join-Path $r.FullName "MQL5\$sub"
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $dest = Join-Path $dir $name
        $tmp  = [System.IO.Path]::GetTempFileName()

        try {
            Invoke-WebRequest -Uri "$Base/$remote" -OutFile $tmp -UseBasicParsing
            $size = (Get-Item $tmp).Length
            if ($size -lt 100) { throw "只有 $size 字节,不像有效文件" }

            # --- 3) 主文件校验 + 删旧 .ex5 ---
            if ($name -eq "BTCScalper.mq5") {
                $txt = Get-Content $tmp -Raw -Encoding UTF8
                foreach ($m in $MustHave) {
                    if ($txt -notmatch [regex]::Escape($m)) { throw "校验失败:缺少标记 '$m'(下到的可能是旧版)" }
                }
                Write-Host "   [校验] 标记齐全" -ForegroundColor DarkGray
                $ex5 = Join-Path $dir "BTCScalper.ex5"
                if (Test-Path $ex5) {
                    Remove-Item -Force $ex5 -ErrorAction SilentlyContinue
                    Write-Host "   [清理] 已删除旧的 BTCScalper.ex5(必须重新编译)" -ForegroundColor DarkGray
                }
            }

            Move-Item -Force $tmp $dest
            Write-Host ("   [OK]   MQL5\{0}\{1}  ({2:N0} 字节)" -f $sub, $name, $size) -ForegroundColor Green
        }
        catch {
            Write-Host ("   [失败] {0} : {1}" -f $name, $_.Exception.Message) -ForegroundColor Red
            if (Test-Path $tmp) { Remove-Item -Force $tmp -ErrorAction SilentlyContinue }
            $okAll = $false
        }
    }
}

Write-Host ""
if (-not $okAll) {
    Write-Host "有文件失败,先解决上面报红的几条,别急着编译。" -ForegroundColor Red
    return
}

Write-Host "文件已就位。接下来:" -ForegroundColor Cyan
Write-Host "  1. MetaEditor 导航器里双击 Experts\BTCScalper.mq5,按 F7 编译 —— 应显示 0 errors"
Write-Host "     (有报错就把报错截图发给 Claude)"
Write-Host "  2. MT5 打开 BTCUSD# 的 **H1** 图表,把 BTCScalper 拖上去,勾【允许算法交易】"
Write-Host "  3. 输入参数页【载入】-> 选 BTCScalper_validated.set -> 确定"
Write-Host ""
Write-Host "⚠️ 先挂模拟账户。回测优势很薄(验证期 +0.078R/笔),没算隔夜利息。" -ForegroundColor Yellow
Write-Host "   M5 快进快出的 BTCScalper_m5_fast.set 回测是亏的,只用于观察。" -ForegroundColor Yellow
Write-Host "   日志第一行会打印点差 —— 如果远大于 `$30,把 InpMaxSpreadUSD 调成你的实际值。" -ForegroundColor Yellow
