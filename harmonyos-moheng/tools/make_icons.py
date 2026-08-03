#!/usr/bin/env python3
"""
生成应用图标（墨衡印章样式）。
提交图标 / 桌面图标 / 最近任务列表图标使用同一张源图，保证三者完全一致。
不使用任何第三方厂商标识，仅以自造品牌名的“衡”字为标记。
"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
ZHU = (200, 68, 46)      # 朱砂 #C8442E
PAPER = (251, 251, 249)  # 纸白 #FBFBF9

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def composite(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), ZHU + (255,))
    d = ImageDraw.Draw(img)
    # 内描边，营造印章/账簿框感
    m = int(size * 0.11)
    lw = max(2, int(size * 0.018))
    d.rectangle([m, m, size - m, size - m], outline=PAPER + (235,), width=lw)
    # 居中“衡”字
    glyph = "衡"
    fs = int(size * 0.5)
    font = ImageFont.truetype(FONT, fs)
    bbox = d.textbbox((0, 0), glyph, font=font)
    gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - gw) / 2 - bbox[0]
    y = (size - gh) / 2 - bbox[1]
    d.text((x, y), glyph, font=font, fill=PAPER + (255,))
    return img


def main():
    targets = [
        # AppScope 应用级图标
        (os.path.join(ROOT, "AppScope/resources/base/media/app_icon.png"), 1024),
        # entry 模块图标（与应用图标同源）
        (os.path.join(ROOT, "entry/src/main/resources/base/media/app_icon.png"), 1024),
        (os.path.join(ROOT, "entry/src/main/resources/base/media/startIcon.png"), 512),
        # 分层图标（可选，前景为透明标记，背景为纯朱砂）
        (os.path.join(ROOT, "entry/src/main/resources/base/media/foreground.png"), 1024),
        (os.path.join(ROOT, "entry/src/main/resources/base/media/background.png"), 1024),
    ]
    for path, size in targets:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        name = os.path.basename(path)
        if name == "foreground.png":
            # 透明前景：仅白色“衡”字，供分层图标使用
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT, int(size * 0.46))
            bbox = d.textbbox((0, 0), "衡", font=font)
            gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            d.text(((size - gw) / 2 - bbox[0], (size - gh) / 2 - bbox[1]),
                   "衡", font=font, fill=PAPER + (255,))
        elif name == "background.png":
            img = Image.new("RGBA", (size, size), ZHU + (255,))
        else:
            img = composite(size)
        img.save(path)
        print("wrote", path, size)


if __name__ == "__main__":
    main()
