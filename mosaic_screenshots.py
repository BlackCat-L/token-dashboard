#!/usr/bin/env python3
"""对截图中的项目名列和首条消息列打马赛克"""
from PIL import Image
import os

SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")

# (left, top, right, bottom)
REGIONS = {
    "01-overview.png": [
        (130, 440, 335, 1285),   # 项目列
        (1150, 440, 1249, 1285), # 首条消息列
    ],
    "02-daily-trend.png": [],
    "03-heatmap.png": [],
    "04-tools.png": [],
    "05-task-types.png": [],
}

def mosaic(img, region, block=12):
    x1, y1, x2, y2 = region
    crop = img.crop(region)
    w, h = max(1, (x2-x1)//block), max(1, (y2-y1)//block)
    img.paste(crop.resize((w, h), Image.BOX).resize((x2-x1, y2-y1), Image.NEAREST), (x1, y1))

for filename, regions in REGIONS.items():
    path = os.path.join(SCREENSHOTS_DIR, filename)
    if not regions or not os.path.exists(path):
        continue
    img = Image.open(path).convert("RGB")
    for r in regions:
        mosaic(img, r)
    img.save(path)
    print(f"已处理: {filename}")
