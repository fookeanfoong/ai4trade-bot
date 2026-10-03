# ============================================================================
#  CryptoEmaMacdScalper(BTC/ETH/SOL M5 EMA+MACD 剥头皮)—— 一键安装/更新到 MT5
#
#  用法(PowerShell,普通权限即可):
#      irm "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/epic-hawking-tl5tac/mql5/update_crypto_mt5.ps1" | iex
#
#  ⚠️ 跑之前先把 MetaEditor 里打开的 CryptoEmaMacdScalper.mq5 **关掉**(标签页的 X)。
#     F7 编译的是编辑器缓冲区,不是磁盘文件 —— 不关会以为编译了新版,其实还是旧代码。
#
#  本脚本会:
#     1. 检测 MetaEditor 是否在运行,在运行就提醒你先关文件
#     2. 下载 EA + 2 个 preset,**校验内容标记**,确认拿到的确实是本版
#     3. 删掉旧的 .ex5 —— 编译失败时 EA 直接加载不了,而不是静默跑旧代码
# ============================================================================

$ErrorActionPreference = 'Stop'

$Base  = "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/epic-hawking-tl5tac"
# 仓库里的路径 -> (MQL5 子目录, 安装后的文件名)
$Files = [ordered]@{
    "mql5/CryptoEmaMacdScalper.mq5"    = @("Experts", "CryptoEmaMacdScalper.mq5")
    "presets/crypto/default.set"       = @("Presets", "CryptoEmaMacd_default.set")
    "presets/crypto/defensive.set"     = @("Presets", "CryptoEmaMacd_defensive.set")
}
$Main = "mql5/CryptoEmaMacdScalper.mq5"

# 本版必须包含的标记
$MustHave = @(
    '__DATETIME__',          # 编译戳([VERSION] 日志)
    'InpOneTradePerCross',   # 同一次交叉只交易一次
    'ManagePartialTP1',      # 净额账户 1.5R 平半仓
    'ManageTrailing',        # 强趋势止损跟随 EMA20
    'NewsBlocked',           # 新闻过滤
    'SymbolWhitelisted'      # 只做前 10 大币种
)

Write-Host ""
Write-Host "=== CryptoEmaMacdScalper 安装/更新 ===" -ForegroundColor Cyan

# --- 1) MetaEditor 开着就提醒 -------------------------------------------------
$me = Get-Process -Name "metaeditor64","metaeditor" -ErrorAction SilentlyContinue
if ($me) {
    Write-Host ""
    Write-Host "⚠️  检测到 MetaEditor 正在运行。" -ForegroundColor Yellow
    Write-Host "    如果 CryptoEmaMacdScalper.mq5 在里面开着,请先关掉那个标签页," -ForegroundColor Yellow
    Write-Host "    否则 F7 编译的还是编辑器里的旧内容。" -ForegroundColor Yellow
    Write-Host ""
    $ans = Read-Host "已经关掉了吗?(y = 继续 / 其它 = 退出)"
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

$utf8bom = New-Object System.Text.UTF8Encoding $true
$okAll = $true
foreach ($r in $roots) {
    Write-Host ""
    Write-Host "-> $($r.FullName)" -ForegroundColor White

    foreach ($src in $Files.Keys) {
        $sub, $name = $Files[$src]
        $dir  = Join-Path $r.FullName "MQL5\$sub"
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $dest = Join-Path $dir $name
        $tmp  = [System.IO.Path]::GetTempFileName()

        try {
            Invoke-WebRequest -Uri "$Base/$src" -OutFile $tmp -UseBasicParsing
            $size = (Get-Item $tmp).Length
            if ($size -lt 100) { throw "只有 $size 字节,不像有效文件" }
            $txt = [System.IO.File]::ReadAllText($tmp, [System.Text.Encoding]::UTF8)

            if ($src -eq $Main) {
                foreach ($m in $MustHave) {
                    if ($txt -notmatch [regex]::Escape($m)) { throw "校验失败:缺少标记 '$m'(下到的可能是旧版)" }
                }
                Write-Host "   [校验] 标记齐全" -ForegroundColor DarkGray
                $ex5 = Join-Path $dir "CryptoEmaMacdScalper.ex5"
                if (Test-Path $ex5) {
                    Remove-Item -Force $ex5 -ErrorAction SilentlyContinue
                    Write-Host "   [清理] 已删除旧的 .ex5(必须重新编译才能用)" -ForegroundColor DarkGray
                }
            }

            # 带 BOM 的 UTF-8 写入:MetaEditor 才不会把中文注释/字符串读成乱码
            [System.IO.File]::WriteAllText($dest, $txt, $utf8bom)
            Remove-Item -Force $tmp -ErrorAction SilentlyContinue
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
    exit 1
}

Write-Host "文件已就位且校验通过。接下来在 MT5 / MetaEditor 里:" -ForegroundColor Cyan
Write-Host "  1. MetaEditor 导航器 -> Experts -> 双击 CryptoEmaMacdScalper.mq5,按 F7 —— 应显示 0 errors"
Write-Host "  2. MT5 打开 BTCUSD 图表,周期切到 M5(旧版已挂的:图表右键 -> 智能交易系统 -> 删除)"
Write-Host "  3. 把 EA 拖上图 -> 勾【允许算法交易】-> 输入参数页【载入】选 CryptoEmaMacd_default.set -> 确定"
Write-Host "  4. 图表左上角出现 L1~L4 / S1~S4 检查表 = 在工作"
Write-Host ""
Write-Host "确认跑的是新版:日志里 [VERSION] 的编译时间应该是刚才那一分钟。" -ForegroundColor Yellow
Write-Host "四个条件同时满足很少见,几小时甚至几天不开仓是正常的 —— 看左上角哪条是 [X]。" -ForegroundColor Yellow
Write-Host "先回测 + 模拟盘。不构成投资建议。" -ForegroundColor Yellow
