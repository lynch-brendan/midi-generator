#!/usr/bin/env python3
"""Generate Nasty app icon: dark FL-grey square with pink gradient N mark."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os, subprocess, sys

OUT = os.path.dirname(os.path.abspath(__file__))
SIZE = 1024

# --- 1) Draw the master icon at 1024px ---
img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Rounded-square background (macOS 26% corner radius look)
radius = int(SIZE * 0.235)
bg = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
bg_draw = ImageDraw.Draw(bg)
# Dark blue-grey gradient
for y in range(SIZE):
    t = y / SIZE
    r = int(0x2a + (0x1a - 0x2a) * t)
    g = int(0x30 + (0x1e - 0x30) * t)
    b = int(0x3a + (0x28 - 0x3a) * t)
    bg_draw.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

# Mask for rounded corners
mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE, SIZE], radius=radius, fill=255)
bg.putalpha(mask)

# Inner rim highlight (top light, bottom shadow) for depth
rim = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
rim_draw = ImageDraw.Draw(rim)
rim_draw.rounded_rectangle([0, 0, SIZE, SIZE], radius=radius,
                            outline=(255, 255, 255, 50), width=4)
rim_mask = Image.new('L', (SIZE, SIZE), 0)
ImageDraw.Draw(rim_mask).rounded_rectangle([0, 0, SIZE, SIZE], radius=radius, outline=255, width=4)
rim.putalpha(rim_mask)

img.paste(bg, (0, 0), bg)
img.paste(rim, (0, 0), rim)

# --- 2) Draw the "N" wordmark in the center with pink→blue gradient ---
# Simulate gradient by drawing text into a mask, then filling with a gradient image
def find_font():
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

font_path = find_font()
font_size = int(SIZE * 0.7)
try:
    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
except Exception:
    font = ImageFont.load_default()

# Draw big N centered
text = "N"
tmp = Image.new('L', (SIZE, SIZE), 0)
td = ImageDraw.Draw(tmp)
# Measure
try:
    bbox = td.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (SIZE - tw) // 2 - bbox[0]
    ty = (SIZE - th) // 2 - bbox[1] - int(SIZE * 0.03)
except Exception:
    tw, th = td.textsize(text, font=font)
    tx = (SIZE - tw) // 2
    ty = (SIZE - th) // 2
td.text((tx, ty), text, font=font, fill=255)

# Build the pink→blue gradient the N will be filled with
grad = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(SIZE):
    t = y / SIZE
    # top: pink #ff5c93, bottom: blue #6b7cff
    r = int(0xff + (0x6b - 0xff) * t)
    g = int(0x5c + (0x7c - 0x5c) * t)
    b = int(0x93 + (0xff - 0x93) * t)
    gd.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

# Apply the N mask to the gradient
letter = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
letter.paste(grad, (0, 0), tmp)

# Drop shadow behind the N
shadow = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
shadow_mask = tmp.filter(ImageFilter.GaussianBlur(radius=SIZE // 60))
ImageDraw.Draw(shadow).bitmap((0, int(SIZE * 0.02)), shadow_mask, fill=(0, 0, 0, 140))

img.paste(shadow, (0, 0), shadow)
img.paste(letter, (0, 0), letter)

# Master PNG
master_png = os.path.join(OUT, "icon.png")
img.save(master_png, "PNG")
print(f"Wrote {master_png}")

# --- 3) Also emit a .iconset dir for iconutil, then build .icns ---
iconset_dir = os.path.join(OUT, "icon.iconset")
os.makedirs(iconset_dir, exist_ok=True)
sizes = [
    (16,  "icon_16x16.png"),
    (32,  "icon_16x16@2x.png"),
    (32,  "icon_32x32.png"),
    (64,  "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]
for size, name in sizes:
    resized = img.resize((size, size), Image.LANCZOS)
    resized.save(os.path.join(iconset_dir, name), "PNG")

# Build .icns via iconutil (macOS built-in)
icns_path = os.path.join(OUT, "icon.icns")
try:
    subprocess.run(["iconutil", "-c", "icns", "-o", icns_path, iconset_dir], check=True)
    print(f"Wrote {icns_path}")
except Exception as e:
    print(f"iconutil failed: {e}", file=sys.stderr)
    sys.exit(1)

# Also Windows .ico via PIL
ico_path = os.path.join(OUT, "icon.ico")
img.save(ico_path, format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(f"Wrote {ico_path}")
