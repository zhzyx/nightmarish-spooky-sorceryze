from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent / "generated" / "locomotion" / "preview"
rows = [
    ("WALK · 0% / 25% / 50% / 75%", "walk"),
    ("RUN · 0% / 25% / 50% / 75%", "run"),
    ("JUMP · prepare / crouch / apex / landing", "jump"),
]
cell_w, cell_h, header_h = 400, 300, 42
sheet = Image.new("RGB", (cell_w * 4, (cell_h + header_h) * 3), "#101820")
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
except OSError:
    font = ImageFont.load_default()
for row, (title, folder) in enumerate(rows):
    y = row * (cell_h + header_h)
    draw.text((16, y + 10), title, fill="#e8edf2", font=font)
    for col in range(4):
        image = Image.open(root / folder / f"{col}.png").convert("RGB")
        image = image.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        sheet.paste(image, (col * cell_w, y + header_h))
out = root.parent / "locomotion_preview.png"
sheet.save(out, optimize=True)
print(out)
