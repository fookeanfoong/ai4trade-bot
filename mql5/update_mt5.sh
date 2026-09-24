#!/usr/bin/env bash
# ============================================================================
#  XAUUSD ScalperGuard —— 一键更新到 MT5 (Mac / Linux / Wine 版)
#
#  用法（终端里）：
#      curl -fsSL "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/scalperguard-live/mql5/update_mt5.sh" | bash
#
#  如果自动找不到 MT5 目录，就手动指定再跑：
#      MQL5DIR="/你的路径/MQL5" bash -c "$(curl -fsSL .../update_mt5.sh)"
#  （MT5 里【文件 -> 打开数据文件夹】进去就是含 MQL5 的那层）
# ============================================================================
set -euo pipefail

BASE="https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/scalperguard-live/mql5"

FILES=(
  "XAUUSD_ScalperGuard.mq5|Experts"
  "Gold_Sniper_Scalper.mq5|Experts"
  "Ultimate_ICT_Gold_Scalper_v3.0.mq5|Experts"
  "GOLD_ORB.mq5|Experts"
  "MonkeyAttack_GoldPivot.mq5|Experts"
  "GMarket.mq5|Experts"
  "GoldAIScalper.mq5|Experts"
  "NyaoScalper.mq5|Experts"
  "GMarket_small.set|Presets"
  "ScalperGuard_aggressive.set|Presets"
  "ScalperGuard_scalp.set|Presets"
  "ScalperGuard_v2_200.set|Presets"
  "ScalperGuard_sim200.set|Presets"
  "ScalperGuard_fomc.set|Presets"
  "ScalperGuard_backtest.set|Presets"
  "ScalperGuard_old200.set|Presets"
  "ScalperGuard_observe200.set|Presets"
  "ScalperGuard_cool30.set|Presets"
  "ScalperGuard_vwap.set|Presets"
  "ScalperGuard_invert.set|Presets"
  "ScalperGuard_range.set|Presets"
  "ScalperGuard_turbo.set|Presets"
  "ScalperGuard_basket.set|Presets"
  "ScalperGuard_turbofx.set|Presets"
  "ScalperGuard_micro.set|Presets"
  "ScalperGuard_rangefx.set|Presets"
  "ScalperGuard_rl15.set|Presets"
  "ScalperGuard_aixau.set|Presets"
)

# --- 找 MQL5 目录 ------------------------------------------------------------
find_mql5() {
  if [ -n "${MQL5DIR:-}" ]; then echo "$MQL5DIR"; return; fi
  # Mac 常见的 Wine / 原生 MT5 位置，找里面带 Experts 的 MQL5 文件夹
  local roots=(
    "$HOME/Library/Application Support"
    "$HOME/Library/PlayOnMac/wineprefix"
    "$HOME/.wine/drive_c"
    "$HOME/.mt5"
  )
  for r in "${roots[@]}"; do
    [ -d "$r" ] || continue
    # 找到第一个 .../MQL5/Experts
    local hit
    hit=$(find "$r" -maxdepth 8 -type d -name Experts -path '*/MQL5/Experts' 2>/dev/null | head -1 || true)
    if [ -n "$hit" ]; then dirname "$hit"; return; fi
  done
}

MQL5="$(find_mql5 || true)"
if [ -z "${MQL5:-}" ] || [ ! -d "$MQL5" ]; then
  echo "找不到 MT5 的 MQL5 目录。"
  echo "在 MT5 里【文件 -> 打开数据文件夹】看路径，然后这样跑："
  echo '  MQL5DIR="/那个路径/MQL5" bash -c "$(curl -fsSL '"$BASE"'/update_mt5.sh)"'
  exit 1
fi
echo "MQL5 目录: $MQL5"

mkdir -p "$MQL5/Experts" "$MQL5/Presets"

ok=1
for entry in "${FILES[@]}"; do
  name="${entry%%|*}"; sub="${entry##*|}"
  dest="$MQL5/$sub/$name"
  if curl -fsSL "$BASE/$name" -o "$dest.tmp"; then
    sz=$(wc -c < "$dest.tmp" | tr -d ' ')
    if [ "$sz" -lt 100 ]; then echo "  [失败] $name 只有 $sz 字节"; rm -f "$dest.tmp"; ok=0; continue; fi
    mv -f "$dest.tmp" "$dest"
    printf "  [OK]   %s/%s  (%s 字节)\n" "$sub" "$name" "$sz"
  else
    echo "  [失败] $name 下载失败"; rm -f "$dest.tmp"; ok=0
  fi
done

# 删旧的 .ex5 —— 逼你重新编译，避免静默跑旧二进制
rm -f "$MQL5/Experts/XAUUSD_ScalperGuard.ex5"

echo ""
if [ "$ok" -ne 1 ]; then echo "有文件失败，先解决上面报红的再编译。"; exit 1; fi
echo "文件已就位。接下来："
echo "  1. 只改了 .set：MT5 输入参数页【载入】选新的 .set 即可，不用编译"
echo "  2. 改了 .mq5：MetaEditor 打开 XAUUSD_ScalperGuard.mq5 -> F7 编译(0 errors) -> 删 EA 重挂"
