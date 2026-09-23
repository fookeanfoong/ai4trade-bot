#!/usr/bin/env python3
"""生成 install_gold_pullback.ps1:一个文件装好 GoldPullback EA + preset。

EA 源码和 preset 直接嵌在脚本里,所以用户只需下载一个 .ps1(或配套 .bat)。
改了 mql5/GoldPullback.mq5 或 preset 之后重跑本脚本:

    python3 make_gold_installer.py
"""

from __future__ import annotations

EA = "mql5/GoldPullback.mq5"
PRESET = "presets/gold/pullback_all_0.02.set"
OUT_PS1 = "install_gold_pullback.ps1"
OUT_BAT = "install_gold_pullback.bat"

TEMPLATE = r"""# GoldPullback 一键安装(Windows PowerShell)
# 做的事:
#   1) 找到本机所有 MT5 数据目录(%APPDATA%\MetaQuotes\Terminal\*)
#   2) 写入 MQL5\Experts\GoldPullback.mq5 和 MQL5\Presets\GoldPullback_all_0.02.set
#   3) 用 MetaEditor 编译,打印编译结果
# 用法:双击同目录的 install_gold_pullback.bat
#   或:powershell -ExecutionPolicy Bypass -File install_gold_pullback.ps1
# 由 make_gold_installer.py 生成,别手改。

$ErrorActionPreference = "Stop"

$ea = @'
__EA__
'@

$preset = @'
__PRESET__
'@

$root = Join-Path $env:APPDATA "MetaQuotes\Terminal"
if (-not (Test-Path $root)) {
    Write-Host "没找到 MT5 数据目录:$root" -ForegroundColor Red
    Write-Host "请先在 MT5 里点 文件 -> 打开数据文件夹,确认 MT5 已安装并运行过一次。"
    exit 1
}

$utf8bom = New-Object System.Text.UTF8Encoding $true
$n = 0
Get-ChildItem $root -Directory | ForEach-Object {
    $mql = Join-Path $_.FullName "MQL5"
    if (-not (Test-Path $mql)) { return }
    $n++
    $experts = Join-Path $mql "Experts"
    $presets = Join-Path $mql "Presets"
    New-Item -ItemType Directory -Force -Path $experts, $presets | Out-Null

    $eaPath = Join-Path $experts "GoldPullback.mq5"
    $setPath = Join-Path $presets "GoldPullback_all_0.02.set"
    [System.IO.File]::WriteAllText($eaPath, $ea, $utf8bom)
    [System.IO.File]::WriteAllText($setPath, $preset, [System.Text.Encoding]::Unicode)

    $origin = Join-Path $_.FullName "origin.txt"
    $install = if (Test-Path $origin) { (Get-Content $origin -Raw).Trim() } else { "" }
    Write-Host ""
    Write-Host "== $install" -ForegroundColor Cyan
    Write-Host "   EA     -> $eaPath"
    Write-Host "   preset -> $setPath"

    $me = if ($install) { Join-Path $install "metaeditor64.exe" } else { "" }
    if ($me -and (Test-Path $me)) {
        $log = Join-Path $experts "GoldPullback.compile.log"
        & $me /compile:"$eaPath" /log:"$log" | Out-Null
        Start-Sleep -Seconds 2
        $ex5 = [System.IO.Path]::ChangeExtension($eaPath, ".ex5")
        if (Test-Path $ex5) {
            Write-Host "   编译成功 -> $ex5" -ForegroundColor Green
        } else {
            Write-Host "   编译失败,日志如下(截图发给 Claude):" -ForegroundColor Red
            if (Test-Path $log) { Get-Content $log | Select-String -Pattern "error|warning|result" }
        }
    } else {
        Write-Host "   没找到 metaeditor64.exe,请在 MetaEditor 里打开 GoldPullback.mq5 按 F7 编译" -ForegroundColor Yellow
    }
}

if ($n -eq 0) {
    Write-Host "Terminal 目录下没有 MQL5 文件夹,MT5 可能还没运行过。" -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "装好了。接下来在 MT5:" -ForegroundColor Green
Write-Host "  1) 导航器(Ctrl+N)-> EA交易 -> 右键 刷新"
Write-Host "  2) 把 GoldPullback 拖到 XAUUSD 图表(任意周期都行,EA 自己用 H1/H4)"
Write-Host "  3) 输入 -> 加载 -> 选 GoldPullback_all_0.02.set -> 勾允许算法交易 -> 确定"
"""

BAT = "@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0install_gold_pullback.ps1\"\r\npause\r\n"


def main():
    ea = open(EA, encoding="utf-8").read().rstrip("\n")
    preset = open(PRESET, encoding="utf-8").read().rstrip("\n")
    for name, body in (("EA", ea), ("preset", preset)):
        if any(line.startswith("'@") for line in body.splitlines()):
            raise SystemExit(f"{name} 里有以 '@ 开头的行,会截断 PowerShell here-string")
    ps1 = TEMPLATE.replace("__EA__", ea).replace("__PRESET__", preset)
    # PowerShell 5.1 读无 BOM 的 UTF-8 会把中文当 ANSI,必须带 BOM + CRLF
    with open(OUT_PS1, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(ps1)
    with open(OUT_BAT, "w", encoding="ascii", newline="") as f:
        f.write(BAT)
    print(f"wrote {OUT_PS1}, {OUT_BAT}")


if __name__ == "__main__":
    main()
