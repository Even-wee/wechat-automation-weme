#!/usr/bin/env python3
"""
智能去水印：检测图片底部区域是否有文字/水印痕迹，有则裁剪，无则原样保留。

原理：
  - AI 生成图的水印通常是底部一行小字，会造成局部高"边缘密度"（相邻像素亮度突变）
  - 把图片底部区域（默认 15%）切成若干水平条带，逐条计算边缘密度
  - 若某条带边缘密度超过阈值 → 判定有水印 → 裁剪到该条带上方
  - 无条带超阈值 → 判定无水印 → 不裁剪

用法：
  python3 remove_watermark.py <图片路径> [--bottom-ratio 0.15] [--threshold 0.02]
  python3 remove_watermark.py <目录>              # 批处理目录下所有图片
"""
import os
import sys
import argparse
from PIL import Image

def edge_density(gray_img, strip):
    """计算一个水平条带的边缘密度（相邻像素亮度突变比例）"""
    w = gray_img.width
    h = gray_img.height
    pixels = list(gray_img.crop((0, strip, w, min(strip + h, gray_img.height))).getdata())
    if len(pixels) < 2:
        return 0.0
    changes = 0
    prev = pixels[0]
    for p in pixels[1:]:
        if abs(p - prev) > 25:
            changes += 1
        prev = p
    return changes / len(pixels)


def detect_watermark(img, bottom_ratio=0.15, threshold=0.02):
    """
    检测底部区域是否有水印。
    返回: (has_watermark: bool, crop_bottom_px: int 建议裁剪的底部像素数)
    """
    w, h = img.size
    if h < 100:
        return False, 0

    gray = img.convert('L')
    bottom_height = int(h * bottom_ratio)
    bottom_top = h - bottom_height

    # 把底部区域切成 8 条水平条带，逐条检测
    strip_h = max(8, bottom_height // 8)
    detected_strips = []
    for strip in range(bottom_top, h, strip_h):
        density = edge_density(gray, strip)
        if density > threshold:
            detected_strips.append((strip, density))

    if not detected_strips:
        return False, 0

    # 有水印：裁剪到第一条检测到的条带上方，再多留 4px 保险
    first_strip = detected_strips[0][0]
    crop_bottom = h - first_strip + 4
    # 最多裁掉 25%，防止误裁太多
    crop_bottom = min(crop_bottom, int(h * 0.25))
    return True, crop_bottom


def process_image(path, bottom_ratio=0.15, threshold=0.02, inplace=True):
    """处理单张图片，返回 (changed, crop_bottom, original_size, new_size)"""
    img = Image.open(path)
    w, h = img.size
    has_wm, crop_bottom = detect_watermark(img, bottom_ratio, threshold)

    if not has_wm:
        return False, 0, (w, h), (w, h)

    new_h = h - crop_bottom
    cropped = img.crop((0, 0, w, new_h))
    if inplace:
        # 备份原图
        bak_dir = os.path.join(os.path.dirname(path), "backup")
        os.makedirs(bak_dir, exist_ok=True)
        bak = os.path.join(bak_dir, os.path.basename(path))
        if not os.path.exists(bak):
            import shutil
            shutil.copy2(path, bak)
        cropped.save(path, "PNG")
    return True, crop_bottom, (w, h), (w, new_h)


def main():
    parser = argparse.ArgumentParser(description='智能去水印：有则裁剪，无则不裁剪')
    parser.add_argument('target', help='图片路径或目录')
    parser.add_argument('--bottom-ratio', type=float, default=0.15, help='检测底部区域比例 (默认0.15)')
    parser.add_argument('--threshold', type=float, default=0.02, help='边缘密度阈值 (默认0.02)')
    parser.add_argument('--dry-run', action='store_true', help='只检测不裁剪')
    args = parser.parse_args()

    if os.path.isdir(args.target):
        files = [f for f in os.listdir(args.target)
                 if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and not f.startswith('.')]
    else:
        files = [os.path.basename(args.target)]
        args.target = os.path.dirname(args.target) or '.'

    print(f"检测 {len(files)} 张图片 (底部{int(args.bottom_ratio*100)}%, 阈值{args.threshold})")
    changed = 0
    for f in files:
        path = os.path.join(args.target, f)
        try:
            has_wm, crop, old, new = process_image(path, args.bottom_ratio, args.threshold, inplace=not args.dry_run)
            if has_wm:
                changed += 1
                print(f"  ✂️  {f}: {old[0]}x{old[1]} → {new[0]}x{new[1]} (裁掉底部{crop}px)")
            else:
                print(f"  ✅ {f}: 无水印，保留原图 {old[0]}x{old[1]}")
        except Exception as e:
            print(f"  ⚠️  {f}: {e}")

    print(f"\n完成: {changed}/{len(files)} 张检测到水印并裁剪" + ("（dry-run 未实际裁剪）" if args.dry_run else ""))


if __name__ == '__main__':
    main()
