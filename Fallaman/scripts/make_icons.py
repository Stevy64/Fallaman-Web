from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "static" / "icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)


def make_icon(size: int, name: str) -> None:
    image = Image.new("RGB", (size, size), "#FE724C")
    draw = ImageDraw.Draw(image)
    margin = size * 0.16
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=int(size * 0.18),
        outline="#FFFFFF",
        width=max(8, size // 28),
    )
    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.42))
    except OSError:
        font = ImageFont.load_default()
    text = "F"
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2, (size - h) / 2 - size * 0.05), text, fill="#FFFFFF", font=font)
    image.save(ICON_DIR / name)


if __name__ == "__main__":
    make_icon(192, "icon-192.png")
    make_icon(512, "icon-512.png")
    make_icon(1200, "og.png")
    print(f"icons generated in {ICON_DIR}")
