# ============================================================================
#  XAUUSD ScalperGuard —— 一键更新到 MT5
#
#  自动找到 MT5 数据目录，把 EA 和参数预设放到正确位置。
#  装了多个 MT5 终端会全部更新一遍。
#
#  用法（PowerShell，普通权限即可，不需要管理员）：
#      .\update_mt5.ps1
#
#  或者不下载文件，直接一行跑：
#      iwr -useb "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/gold-mt5-auto-trading-lr5tju/mql5/update_mt5.ps1" | iex
#
#  更新完还要在 MT5 里做（这一步没法自动化）：
#      1. F4 开 MetaEditor -> 双击 XAUUSD_ScalperGuard.mq5 -> F7 编译
#      2. 图表右键 -> 智能交易系统 -> 删除
#      3. 重新把 EA 拖到图表上 -> 勾"允许算法交易" -> 载入 .set -> 确定
# ============================================================================

$ErrorActionPreference = 'Stop'

$Base  = "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/gold-mt5-auto-trading-lr5tju/mql5"
$Files = @{
    "XAUUSD_ScalperGuard.mq5"     = "Experts"
    "ScalperGuard_aggressive.set" = "Presets"
    "ScalperGuard_scalp.set"      = "Presets"
    "ScalperGuard_v2_200.set"     = "Presets"
}

Write-Host ""
Write-Host "=== XAUUSD ScalperGuard 更新 ===" -ForegroundColor Cyan

# MT5 的数据目录在 %APPDATA%\MetaQuotes\Terminal\<一串十六进制>\
# 只认里面有 MQL5\Experts 的那些 —— 其余是 Common、缓存之类，放进去 MT5 看不到
$roots = @()
$tpath = Join-Path $env:APPDATA "MetaQuotes\Terminal"
if (Test-Path $tpath) {
    $roots = Get-ChildItem $tpath -Directory -ErrorAction SilentlyContinue |
             Where-Object { Test-Path (Join-Path $_.FullName "MQL5\Experts") }
}

if (-not $roots -or $roots.Count -eq 0) {
    Write-Host "找不到 MT5 数据目录。" -ForegroundColor Red
    Write-Host "请先在 MT5 里点【文件 -> 打开数据文件夹】确认它装在哪，" -ForegroundColor Yellow
    Write-Host "然后把文件手动放进 MQL5\Experts\ 和 MQL5\Presets\。" -ForegroundColor Yellow
    exit 1
}

Write-Host "找到 $($roots.Count) 个 MT5 终端目录" -ForegroundColor Gray
$okAll = $true

foreach ($r in $roots) {
    Write-Host ""
    Write-Host "-> $($r.FullName)" -ForegroundColor White

    foreach ($name in $Files.Keys) {
        $sub = $Files[$name]
        $dir = Join-Path $r.FullName "MQL5\$sub"
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $dest = Join-Path $dir $name

        try {
            # 先下到临时文件再覆盖：下载中途失败时不会把已有的好文件截断成半截
            $tmp = [System.IO.Path]::GetTempFileName()
            Invoke-WebRequest -Uri "$Base/$name" -OutFile $tmp -UseBasicParsing
            $size = (Get-Item $tmp).Length
            if ($size -lt 100) { throw "下载内容只有 $size 字节，不像是有效文件" }
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
if ($okAll) {
    Write-Host "文件已就位。接下来在 MT5 里手动做这三步：" -ForegroundColor Cyan
    Write-Host "  1. F4 开 MetaEditor -> 双击 XAUUSD_ScalperGuard.mq5 -> F7 编译（应显示 0 errors）"
    Write-Host "  2. 图表右键 -> 智能交易系统 -> 删除"
    Write-Host "  3. 重新拖 EA 上图 -> 勾【允许算法交易】-> 输入参数页点【载入】选 .set -> 确定"
    Write-Host ""
    Write-Host "确认是新版：参数列表里能看到 InpUseV2Scoring" -ForegroundColor Yellow
} else {
    Write-Host "有文件更新失败，别急着重编译 —— 先解决上面报红的那几条。" -ForegroundColor Red
    exit 1
}
