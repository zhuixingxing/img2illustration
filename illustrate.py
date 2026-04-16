#!/usr/bin/env python3
"""
图片转插画核心算法库
纯 NumPy + Pillow 实现，无第三方 AI 服务

CLI 用法:
  python illustrate.py photo.jpg                   # 卡通风格
  python illustrate.py photo.jpg -s sketch         # 铅笔素描
  python illustrate.py photo.jpg -s watercolor     # 水彩
"""

import numpy as np
from PIL import Image, ImageEnhance
import sys, os, argparse


# ══════════════════════════════════════════════════════════════
#  基础卷积与模糊（可分离高斯，无第三方依赖）
# ══════════════════════════════════════════════════════════════

def _gaussian_kernel_1d(sigma: float) -> np.ndarray:
    size = max(3, int(6 * sigma) | 1)
    k = size // 2
    x = np.arange(-k, k + 1, dtype=np.float32)
    kern = np.exp(-x ** 2 / (2 * sigma ** 2))
    return kern / kern.sum()


def _convolve_rows(arr: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """沿行方向做 1D 卷积（向量化）"""
    k = len(kernel) // 2
    padded = np.pad(arr, ((0, 0), (k, k)), mode='edge')
    out = np.zeros(arr.shape, dtype=np.float32)
    for i, w in enumerate(kernel):
        out += padded[:, i:i + arr.shape[1]] * w
    return out


def _blur_channel(ch: np.ndarray, sigma: float) -> np.ndarray:
    kern = _gaussian_kernel_1d(sigma)
    blurred = _convolve_rows(ch.astype(np.float32), kern)
    blurred = _convolve_rows(blurred.T, kern).T
    return blurred


def gaussian_blur(img: np.ndarray, sigma: float) -> np.ndarray:
    if img.ndim == 3:
        return np.stack(
            [_blur_channel(img[:, :, c], sigma) for c in range(img.shape[2])],
            axis=2,
        )
    return _blur_channel(img, sigma)


# ══════════════════════════════════════════════════════════════
#  边缘检测（Sobel）
# ══════════════════════════════════════════════════════════════

def _apply_3x3(ch: np.ndarray, kern: np.ndarray) -> np.ndarray:
    padded = np.pad(ch, 1, mode='edge')
    out = np.zeros(ch.shape, dtype=np.float32)
    for i in range(3):
        for j in range(3):
            out += padded[i:i + ch.shape[0], j:j + ch.shape[1]] * kern[i, j]
    return out


def sobel_edges(img: np.ndarray) -> np.ndarray:
    """Sobel 边缘检测，返回 [0,1] 强度图（H×W）"""
    if img.ndim == 3:
        gray = (0.299 * img[:, :, 0] +
                0.587 * img[:, :, 1] +
                0.114 * img[:, :, 2]).astype(np.float32)
    else:
        gray = img.astype(np.float32)

    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    ky = kx.T

    mag = np.sqrt(_apply_3x3(gray, kx) ** 2 + _apply_3x3(gray, ky) ** 2)
    mag /= mag.max() + 1e-8
    return mag


# ══════════════════════════════════════════════════════════════
#  色彩工具
# ══════════════════════════════════════════════════════════════

def posterize(img: np.ndarray, levels: int) -> np.ndarray:
    step = 256.0 / levels
    return (np.floor(img / step) * step).clip(0, 255).astype(np.uint8)


def adjust_saturation(img: np.ndarray, factor: float) -> np.ndarray:
    return np.array(ImageEnhance.Color(Image.fromarray(img.astype(np.uint8))).enhance(factor))


def adjust_contrast(img: np.ndarray, factor: float) -> np.ndarray:
    return np.array(ImageEnhance.Contrast(Image.fromarray(img.astype(np.uint8))).enhance(factor))


# ══════════════════════════════════════════════════════════════
#  风格一：卡通插画
# ══════════════════════════════════════════════════════════════

def style_cartoon(arr: np.ndarray) -> np.ndarray:
    smooth = arr.astype(np.float32)
    for _ in range(4):
        smooth = gaussian_blur(smooth, sigma=2.5)
    flat = posterize(smooth, levels=7)
    flat = adjust_saturation(flat, 1.9)

    edges = sobel_edges(gaussian_blur(arr, sigma=1.0))
    edges = np.power(edges, 0.6)
    mask = (edges > 0.18).astype(np.float32)
    mask = gaussian_blur(mask, sigma=0.7)

    result = flat.astype(np.float32) * (1.0 - mask[:, :, np.newaxis] * 0.92)
    return result.clip(0, 255).astype(np.uint8)


# ══════════════════════════════════════════════════════════════
#  风格二：铅笔素描
# ══════════════════════════════════════════════════════════════

def style_sketch(arr: np.ndarray) -> np.ndarray:
    gray = (0.299 * arr[:, :, 0] +
            0.587 * arr[:, :, 1] +
            0.114 * arr[:, :, 2]).astype(np.float32)

    blurred = gaussian_blur(gray, sigma=6.0)
    inverted = 255.0 - blurred
    s = gray / (inverted / 255.0 + 0.04)
    s = s.clip(0, 255)

    p5, p95 = np.percentile(s, 5), np.percentile(s, 95)
    s = ((s - p5) / (p95 - p5 + 1e-8) * 255).clip(0, 255)

    return np.stack([s, s, s], axis=2).astype(np.uint8)


# ══════════════════════════════════════════════════════════════
#  风格三：水彩
# ══════════════════════════════════════════════════════════════

def style_watercolor(arr: np.ndarray) -> np.ndarray:
    soft = gaussian_blur(arr.astype(np.float32), sigma=3.0)
    soft = posterize(soft, levels=14)
    soft = adjust_saturation(soft, 1.4)
    soft = adjust_contrast(soft, 1.1)

    rng = np.random.default_rng(42)
    noise = rng.normal(0, 7, soft.shape).astype(np.float32)
    soft = (soft.astype(np.float32) + noise).clip(0, 255)

    edges = sobel_edges(arr)
    edges = gaussian_blur(edges, sigma=1.8)
    mask = np.where(edges > 0.10, edges, 0.0).astype(np.float32)
    mask = gaussian_blur(mask, sigma=1.5)

    result = soft * (1.0 - mask[:, :, np.newaxis] * 0.38)
    return result.clip(0, 255).astype(np.uint8)


# ══════════════════════════════════════════════════════════════
#  公共接口
# ══════════════════════════════════════════════════════════════

STYLES = {
    "cartoon":    style_cartoon,
    "sketch":     style_sketch,
    "watercolor": style_watercolor,
}


def process_image(img: Image.Image, style: str = "cartoon",
                  max_size: int = 1024) -> Image.Image:
    """Web 调用入口：PIL Image → PIL Image"""
    img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        scale = max_size / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32)
    result = STYLES[style](arr)
    return Image.fromarray(result)


def convert(input_path: str, output_path: str,
            style: str = "cartoon", max_size: int = 1024) -> None:
    """CLI 入口：文件路径 → 文件路径"""
    img = Image.open(input_path)
    print(f"输入: {input_path}  风格: {style}")
    result = process_image(img, style=style, max_size=max_size)
    result.save(output_path)
    size_kb = os.path.getsize(output_path) // 1024
    print(f"完成: {output_path}  ({size_kb} KB)")


def main() -> None:
    p = argparse.ArgumentParser(description="图片转插画（纯算法，无 AI 服务）")
    p.add_argument("input", help="输入图片路径")
    p.add_argument("-o", "--output", help="输出路径（默认自动命名）")
    p.add_argument("-s", "--style", choices=list(STYLES),
                   default="cartoon", help="插画风格 (默认: cartoon)")
    p.add_argument("--max-size", type=int, default=1024, metavar="PX",
                   help="最长边上限 (默认 1024)")
    args = p.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"错误: 找不到文件 {args.input}")

    out = args.output or (
        os.path.splitext(args.input)[0] + f"_{args.style}.png"
    )
    convert(args.input, out, style=args.style, max_size=args.max_size)


if __name__ == "__main__":
    main()
