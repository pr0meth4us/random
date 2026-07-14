from PIL import Image, ImageDraw, ImageFont
import os

bg = Image.open("scratch/poster_gen/poster.png").convert("RGBA")
qr = Image.open("scratch/poster_gen/qr.png").convert("RGBA")
logo = Image.open("scratch/poster_gen/logo.png").convert("RGBA")

# 3. Create a clean white card
card_x0, card_y0 = 80, 290
card_x1, card_y1 = 453, 765
card_w = card_x1 - card_x0
card_h = card_y1 - card_y0

draw = ImageDraw.Draw(bg)
draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=25, fill=(255, 255, 255, 255))

# 4. Resize and paste new QR code
qr_size = 320
qr = qr.resize((qr_size, qr_size), Image.LANCZOS)
qr_x = card_x0 + (card_w - qr_size) // 2
qr_y = card_y0 + 50
bg.paste(qr, (qr_x, qr_y), qr)

# 5. Resize and paste new EGD logo
logo_size = 140
logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
logo_x = card_x0 + (card_w - logo_size) // 2
logo_y = card_y0 - (logo_size // 2)
bg.paste(logo, (logo_x, logo_y), logo)

# 6. Add Telegram logo (drawn) and text
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 34)
except:
    font = ImageFont.load_default()

text = "@EGDSUPPORT"
text_bbox = draw.textbbox((0, 0), text, font=font)
text_w = text_bbox[2] - text_bbox[0]
text_h = text_bbox[3] - text_bbox[1]

tg_size = 36
spacing = 10
total_w = tg_size + spacing + text_w
start_x = card_x0 + (card_w - total_w) // 2
content_y = qr_y + qr_size + 30

# Draw TG logo
tg_img = Image.new('RGBA', (tg_size, tg_size), (255, 255, 255, 0))
tg_draw = ImageDraw.Draw(tg_img)
tg_draw.ellipse([0, 0, tg_size, tg_size], fill=(0, 136, 204))
# Paper plane points
cx, cy = tg_size // 2, tg_size // 2
plane_points = [
    (cx - 8, cy - 2),
    (cx + 10, cy - 8),
    (cx + 4, cy + 10),
    (cx + 1, cy + 3),
    (cx - 2, cy + 4)
]
tg_draw.polygon(plane_points, fill=(255, 255, 255))
bg.paste(tg_img, (start_x, content_y - 2), tg_img)

# Draw text (matching the new QR code's dark blue tone)
draw.text((start_x + tg_size + spacing, content_y), text, fill=(0, 0, 150, 255), font=font)

# Save result to the artifact directory so it can be easily shared
out_path = "/Users/nicksng/.gemini/antigravity-ide/brain/d5a704cb-df05-4e0d-b5f0-5303be3a20c2/egd_poster_final.png"
bg.save(out_path)
print(f"Saved to {out_path}")
