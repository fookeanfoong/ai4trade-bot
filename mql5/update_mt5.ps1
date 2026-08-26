# ============================================================================
#  XAUUSD ScalperGuard —— 一键更新到 MT5
#
#  用法（PowerShell，普通权限即可）：
#      iwr -useb "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/gold-mt5-auto-trading-lr5tju/mql5/update_mt5.ps1" | iex
#
#  ⚠️ 跑之前先把 MetaEditor 里打开的 XAUUSD_ScalperGuard.mq5 **关掉**（标签页的 X）。
#     MetaEditor 会把文件缓存在编辑器缓冲区里，磁盘上换了新文件它也未必重新加载，
#     而 F7 编译的是**缓冲区**不是磁盘 —— 这会让你以为编译了新版，其实还是旧代码。
#
#  本脚本会做三件事来防住这个坑：
#     1. 检测 MetaEditor 是否在运行，在运行就提醒你先关文件
#     2. 下载后**校验内容标记**，确认拿到的确实是新版
#     3. 删掉旧的 .ex5 —— 编译失败时 EA 直接加载不了，而不是继续静默跑旧代码
# ============================================================================

$ErrorActionPreference = 'Stop'

$Base  = "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/gold-mt5-auto-trading-lr5tju/mql5"
$Files = @{
    "XAUUSD_ScalperGuard.mq5"     = "Experts"
    "ScalperGuard_aggressive.set" = "Presets"
    "ScalperGuard_scalp.set"      = "Presets"
    "ScalperGuard_v2_200.set"     = "Presets"
    "ScalperGuard_sim200.set"     = "Presets"
    "ScalperGuard_fomc.set"       = "Presets"
    "ScalperGuard_backtest.set"   = "Presets"
    "ScalperGuard_old200.set"     = "Presets"
    "ScalperGuard_observe200.set" = "Presets"
}

# 新版必须包含 / 必须不包含的标记。命中即证明拿到的是修好之后的版本。
$MustHave = @(
    '__DATETIME__',            # 编译戳（旧版是 C 写法的 __TIME__，MQL5 不认）
    'InpAllowMultiPosition',   # 多仓
    'InpUseLooseEntry',        # 宽松入场 路径D
    'InpSlMaxATRMult',         # 止损上限跟随 ATR
    'InpTesterQuiet',          # 策略测试器静默（回测支持）
    'InpEntryTF',              # 触发周期（进场延迟）
    'InpExitOnStall',          # 停滞离场
    'g_dirSell',               # 面板多空计数（方向闸门诊断）
    'EffectiveFreeMargin',     # 保证金按虚拟本金算
    'PriceActionDir',          # 纯K线方向（模式4）
    'InpCounterMoveATR',       # 逆势闸门
    'InpFixedLot'              # 固定手数
)
$MustNotHave = @(
    'double targetNote'        # 旧版的类型笔误
)

Write-Host ""
Write-Host "=== XAUUSD ScalperGuard 更新 ===" -ForegroundColor Cyan

# --- 1) MetaEditor 开着就提醒 -------------------------------------------------
$me = Get-Process -Name "metaeditor64","metaeditor" -ErrorAction SilentlyContinue
if ($me) {
    Write-Host ""
    Write-Host "⚠️  检测到 MetaEditor 正在运行。" -ForegroundColor Yellow
    Write-Host "    如果 XAUUSD_ScalperGuard.mq5 在里面开着，请先关掉那个标签页，" -ForegroundColor Yellow
    Write-Host "    否则 F7 编译的还是编辑器里的旧内容，不是这次下载的新文件。" -ForegroundColor Yellow
    Write-Host ""
    $ans = Read-Host "已经关掉了吗？(y = 继续 / 其它 = 退出)"
    if ($ans -ne 'y' -and $ans -ne 'Y') {
        Write-Host "已退出。关掉文件后重跑本脚本。" -ForegroundColor Red
        exit 1
    }
}

# --- 2) 找 MT5 数据目录 -------------------------------------------------------
$roots = @()
$tpath = Join-Path $env:APPDATA "MetaQuotes\Terminal"
if (Test-Path $tpath) {
    $roots = Get-ChildItem $tpath -Directory -ErrorAction SilentlyContinue |
             Where-Object { Test-Path (Join-Path $_.FullName "MQL5\Experts") }
}
if (-not $roots -or $roots.Count -eq 0) {
    Write-Host "找不到 MT5 数据目录。请在 MT5 里点【文件 -> 打开数据文件夹】确认位置。" -ForegroundColor Red
    exit 1
}
Write-Host "找到 $($roots.Count) 个 MT5 终端目录" -ForegroundColor Gray

$okAll = $true
foreach ($r in $roots) {
    Write-Host ""
    Write-Host "-> $($r.FullName)" -ForegroundColor White

    foreach ($name in $Files.Keys) {
        $sub  = $Files[$name]
        $dir  = Join-Path $r.FullName "MQL5\$sub"
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $dest = Join-Path $dir $name
        $tmp  = [System.IO.Path]::GetTempFileName()

        try {
            Invoke-WebRequest -Uri "$Base/$name" -OutFile $tmp -UseBasicParsing
            $size = (Get-Item $tmp).Length
            if ($size -lt 100) { throw "只有 $size 字节，不像有效文件" }

            # --- 3) 内容校验：只对主文件做，确认确实是新版 ---
            if ($name -eq "XAUUSD_ScalperGuard.mq5") {
                $txt = Get-Content $tmp -Raw -Encoding UTF8
                foreach ($m in $MustHave) {
                    if ($txt -notmatch [regex]::Escape($m)) { throw "校验失败：缺少标记 '$m'（下到的可能是旧版）" }
                }
                foreach ($m in $MustNotHave) {
                    if ($txt -match [regex]::Escape($m)) { throw "校验失败：仍含旧版标记 '$m'" }
                }
                Write-Host "   [校验] 新版标记齐全：$($MustHave -join ', ')" -ForegroundColor DarkGray

                # 旧 .ex5 删掉 —— 编译不过时 EA 直接加载不了，
                # 好过它继续静默跑旧二进制让你以为改动生效了
                $ex5 = Join-Path $dir "XAUUSD_ScalperGuard.ex5"
                if (Test-Path $ex5) {
                    Remove-Item -Force $ex5 -ErrorAction SilentlyContinue
                    Write-Host "   [清理] 已删除旧的 .ex5（必须重新编译才能用）" -ForegroundColor DarkGray
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
    Write-Host "有文件失败，先解决上面报红的几条，别急着编译。" -ForegroundColor Red
    exit 1
}

Write-Host "文件已就位且校验通过。接下来在 MT5 / MetaEditor 里：" -ForegroundColor Cyan
Write-Host "  1. MetaEditor 里若还开着 XAUUSD_ScalperGuard.mq5，先关掉标签页"
Write-Host "  2. 重新打开它（导航器里双击），按 F7 编译 —— 应显示 0 errors"
Write-Host "  3. MT5 图表右键 -> 智能交易系统 -> 删除"
Write-Host "  4. 重新拖 EA 上图 -> 勾【允许算法交易】-> 输入参数页【载入】选 .set -> 确定"
Write-Host ""
Write-Host "确认跑的是新版：日志第一行 [VERSION] 的编译时间应该是刚才那一分钟。" -ForegroundColor Yellow
Write-Host "旧 .ex5 已删除，所以编译不过的话 EA 会直接加载失败 —— 不会再出现" -ForegroundColor Yellow
Write-Host "「以为更新了、其实还在跑旧代码」这种情况。" -ForegroundColor Yellow
