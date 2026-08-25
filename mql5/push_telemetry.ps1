# ============================================================================
#  把 MT5 的运行数据推到 GitHub，好让 Claude 在云端读得到
#
#  用法：先手动跑一次确认能通，再挂进「任务计划程序」每 15 分钟跑一次。
#      powershell -ExecutionPolicy Bypass -File push_telemetry.ps1
#
#  ⚠️ 日志里有账户余额和每一笔成交。确认仓库是 **Private** 再用。
#     公开仓库就别推 —— 那等于把交易记录发到网上。
# ============================================================================

param(
    [string]$RepoDir = "$env:USERPROFILE\ai4trade-bot",
    [string]$Branch  = "claude/gold-mt5-auto-trading-lr5tju"
)

$ErrorActionPreference = 'Stop'

# --- 1) 找 MT5 数据目录里的 Files 文件夹 ---
$tpath = Join-Path $env:APPDATA "MetaQuotes\Terminal"
$files = Get-ChildItem $tpath -Directory -ErrorAction SilentlyContinue |
         ForEach-Object { Join-Path $_.FullName "MQL5\Files" } |
         Where-Object { Test-Path (Join-Path $_ "XAUUSD_ScalperGuard_log.csv") }

if (-not $files) { Write-Host "找不到 EA 的日志文件。EA 跑过至少一次了吗？" -ForegroundColor Red; exit 1 }
$src = $files | Select-Object -First 1
Write-Host "数据源: $src" -ForegroundColor Gray

# --- 2) 仓库没有就克隆 ---
if (-not (Test-Path (Join-Path $RepoDir ".git"))) {
    Write-Host "克隆仓库到 $RepoDir ..." -ForegroundColor Gray
    git clone --branch $Branch "https://github.com/fookeanfoong/ai4trade-bot.git" $RepoDir
}

Push-Location $RepoDir
try {
    # 先拉，免得和 Claude 推的改动打架
    git checkout $Branch  2>&1 | Out-Null
    git pull --rebase --autostash origin $Branch 2>&1 | Out-Null

    $dst = Join-Path $RepoDir "telemetry"
    New-Item -ItemType Directory -Force -Path $dst | Out-Null

    foreach ($f in @("XAUUSD_ScalperGuard_log.csv", "XAUUSD_ScalperGuard_status.json")) {
        $p = Join-Path $src $f
        if (Test-Path $p) {
            Copy-Item $p (Join-Path $dst $f) -Force
            Write-Host "  已复制 $f ($((Get-Item $p).Length) 字节)" -ForegroundColor DarkGray
        }
    }

    # 顺带记一份快照时间，方便判断遥测有没有断
    (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") |
        Set-Content (Join-Path $dst "last_push.txt") -NoNewline

    git add telemetry
    if ((git diff --cached --name-only) -eq $null) {
        Write-Host "没有变化，跳过。" -ForegroundColor Gray
    } else {
        git -c user.name="mt5-telemetry" -c user.email="mt5@local" `
            commit -q -m "telemetry $(Get-Date -Format 'yyyy-MM-ddTHH:mmZ')"
        git push origin $Branch
        Write-Host "已推送。" -ForegroundColor Green
    }
}
finally { Pop-Location }
