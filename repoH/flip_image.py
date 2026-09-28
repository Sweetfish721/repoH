# -*- coding: utf-8 -*-
"""
图片左右翻转 + 原图/翻转图并排展示。

只依赖 Pillow，不依赖 numpy / matplotlib。

主要接口
--------
flip_horizontal(image)                 -> 输入一张图片，返回左右翻转后的图片
make_side_by_side(image, ...)          -> 生成「原图 | 左右翻转」的并排对比图
show_flipped(image, ...)               -> 展示（并可选保存）并排对比图

三种输入都支持：文件路径（str / pathlib.Path）、PIL.Image 对象、图片字节流。

命令行
------
python flip_image.py 图片.png
python flip_image.py 图片.png --auto-save            # 存在原图旁边
python flip_image.py 图片.png -o 对比图.png --no-show
python flip_image.py 图片.png --save-flipped 翻转.png
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

from PIL import Image, ImageDraw, ImageFont, ImageOps

__all__ = ["load_image", "flip_horizontal", "make_side_by_side", "show_flipped"]

ImageLike = Union[str, Path, Image.Image, bytes, bytearray]
Color = Tuple[int, int, int]

# 常见中文字体，按顺序尝试；都找不到时自动退回英文标签
_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",        # 微软雅黑
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",      # 黑体
    r"C:\Windows\Fonts\simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


# ──────────────────────────── 基础工具 ────────────────────────────

def load_image(source: ImageLike) -> Image.Image:
    """把「路径 / PIL 图片 / 字节流」统一读成一张 PIL 图片，并按 EXIF 摆正方向。

    手机照片常常带 EXIF 旋转信息，直接读会躺倒；这里用 exif_transpose 修正。
    """
    if isinstance(source, Image.Image):
        img = source
    elif isinstance(source, (bytes, bytearray)):
        img = Image.open(io.BytesIO(bytes(source)))
    elif isinstance(source, (str, Path)):
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"找不到图片文件：{path}")
        img = Image.open(path)
    else:
        raise TypeError(f"不支持的输入类型：{type(source)!r}（需要路径 / PIL.Image / bytes）")

    img.load()
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass  # 没有 EXIF 或格式不支持时忽略
    return img


def flip_horizontal(image: ImageLike) -> Image.Image:
    """把图片左右翻转（水平镜像），返回新的图片对象，不修改原图。

    参数
    ----
    image : 文件路径 / PIL.Image / 图片字节流

    返回
    ----
    PIL.Image.Image —— 左右翻转后的图片（通道模式与原图一致）
    """
    img = load_image(image)
    return img.transpose(Image.FLIP_LEFT_RIGHT)


def _load_font(size: int) -> Optional[ImageFont.FreeTypeFont]:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return None


def _flatten(img: Image.Image, bg: Color = (255, 255, 255)) -> Image.Image:
    """把带透明通道的图片压到纯色背景上，避免并排时出现黑块。"""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, bg)
        canvas.paste(rgba, mask=rgba.split()[-1])
        return canvas
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


# ──────────────────────────── 并排对比图 ────────────────────────────

def make_side_by_side(
    image: ImageLike,
    *,
    labels: Sequence[str] = ("原图", "左右翻转"),
    title: Optional[str] = None,
    gap: int = 32,
    padding: int = 32,
    label_size: int = 26,
    title_size: int = 34,
    bg: Color = (244, 246, 250),
    card: Color = (255, 255, 255),
    border: Color = (214, 220, 230),
    text_color: Color = (40, 48, 64),
    max_width: int = 2000,
    scale: float = 1.0,
) -> Image.Image:
    """生成「原图 ｜ 左右翻转」的并排对比图（返回新的 PIL 图片）。

    参数
    ----
    image      : 图片路径 / PIL.Image / 字节流
    labels     : 两张图下方的说明文字，默认 ("原图", "左右翻转")
    title      : 顶部标题，None 表示不加
    gap        : 两张图之间的间距（像素）
    padding    : 画布四周留白
    max_width  : 结果图最大宽度，超出会自动等比缩小
    scale      : 额外的整体缩放系数（1.0 表示不缩放）
    """
    original = _flatten(load_image(image))
    flipped = original.transpose(Image.FLIP_LEFT_RIGHT)

    # 整体缩放：先按 max_width 限宽（扣除留白与间距），再乘用户给的 scale
    panel_w = original.width
    avail = max_width - padding * 2 - gap          # 两张图实际可用宽度
    factor = min(1.0, avail / (panel_w * 2)) * scale
    if factor != 1.0:
        new_size = (max(1, round(original.width * factor)), max(1, round(original.height * factor)))
        original = original.resize(new_size, Image.LANCZOS)
        flipped = flipped.resize(new_size, Image.LANCZOS)

    font_label = _load_font(label_size)
    font_title = _load_font(title_size)
    if font_label is None:                      # 找不到中文字体就退回英文
        labels = ("Original", "Flipped")

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    label_h = label_size + 16
    title_h = (title_size + 22) if title else 0

    canvas_w = padding * 2 + original.width * 2 + gap
    canvas_h = padding * 2 + title_h + original.height + label_h
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg)
    draw = ImageDraw.Draw(canvas)

    if title:
        draw.text((padding, padding), title, font=font_title or ImageFont.load_default(), fill=text_color)
        y_img = padding + title_h
    else:
        y_img = padding

    for i, (img, label) in enumerate(zip((original, flipped), labels)):
        x = padding + i * (original.width + gap)
        # 图片白卡 + 细边框
        draw.rectangle([x - 2, y_img - 2, x + img.width + 1, y_img + img.height + 1],
                       fill=card, outline=border)
        canvas.paste(img, (x, y_img))
        # 标签居中放在图片下方
        try:
            box = draw.textbbox((0, 0), label, font=font_label or ImageFont.load_default())
            tw = box[2] - box[0]
        except Exception:
            tw = len(label) * label_size // 2
        draw.text((x + (img.width - tw) / 2, y_img + img.height + 8), label,
                  font=font_label or ImageFont.load_default(), fill=text_color)

    return canvas


def show_flipped(
    image: ImageLike,
    *,
    save_path: Optional[Union[str, Path]] = None,
    show: bool = True,
    title: Optional[str] = None,
    labels: Sequence[str] = ("原图", "左右翻转"),
    **kwargs,
) -> Image.Image:
    """输入一张图片，把原图与左右翻转后的图并排展示出来。

    参数
    ----
    image     : 图片路径 / PIL.Image / 字节流
    save_path : 若给出，则把并排对比图保存到该路径
    show      : 是否调用系统看图程序弹出显示（默认 True）
    title     : 顶部标题
    其余关键字参数透传给 make_side_by_side（gap / padding / max_width / scale 等）

    返回
    ----
    PIL.Image.Image —— 并排对比图本身，方便再保存或继续处理
    """
    canvas = make_side_by_side(image, labels=labels, title=title, **kwargs)
    if save_path:
        out = Path(save_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out)
        print(f"已保存对比图：{out}")
    if show:
        try:
            canvas.show()
        except Exception as exc:                 # 无图形界面时不要中断脚本
            print(f"（无法自动弹出预览窗口：{exc}）")
    return canvas


# ──────────────────────────── 命令行入口 ────────────────────────────

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="输入一张图片，并排展示原图与左右翻转后的图")
    parser.add_argument("image", help="图片路径")
    parser.add_argument("-o", "--output", help="把并排对比图保存到该路径")
    parser.add_argument("--auto-save", action="store_true",
                        help="自动保存到原图旁边，文件名为「原文件名_翻转对比.png」")
    parser.add_argument("--save-flipped", help="另外单独保存一张翻转后的图片")
    parser.add_argument("--title", default=None, help="对比图顶部标题")
    parser.add_argument("--max-width", type=int, default=2000, help="结果图最大宽度（默认 2000）")
    parser.add_argument("--scale", type=float, default=1.0, help="整体缩放系数（默认 1.0）")
    parser.add_argument("--no-show", action="store_true", help="只保存/生成，不弹出预览窗口")
    args = parser.parse_args(argv)

    image = args.image.strip().strip('"').strip("'")   # 容忍拖拽时带进来的引号
    if args.save_flipped:
        out_flip = Path(args.save_flipped).expanduser()
        out_flip.parent.mkdir(parents=True, exist_ok=True)
        flip_horizontal(image).save(out_flip)
        print(f"已保存翻转图：{out_flip}")

    out = args.output
    if out is None and args.auto_save:
        src = Path(image).expanduser()
        out = src.with_name(f"{src.stem}_翻转对比.png")

    show_flipped(image, save_path=out, show=not args.no_show,
                 title=args.title, max_width=args.max_width, scale=args.scale)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
