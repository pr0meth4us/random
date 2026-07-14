from PIL import Image, ImageDraw, ImageFont

qr = Image.open("scratch/poster_gen/qr.png").convert("RGBA")
logo = Image.open("scratch/poster_gen/logo.png").convert("RGBA")

# Dimensions for the standalone group
group_w = 500
group_h = 650

# Create a transparent background
bg = Image.new("RGBA", (group_w, group_h), (255, 255, 255, 0))
draw = ImageDraw.Draw(bg)

# 4. Resize and paste new QR code
qr_size = 400
qr = qr.resize((qr_size, qr_size), Image.LANCZOS)
qr_x = (group_w - qr_size) // 2
qr_y = 100
bg.paste(qr, (qr_x, qr_y), qr)

# 5. Resize and paste new EGD logo
logo_size = 160
logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
logo_x = (group_w - logo_size) // 2
logo_y = 0  # Overlap slightly over the top, or just at the top
bg.paste(logo, (logo_x, logo_y), logo)

# 6. Add Telegram logo (drawn) and text
try:
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 40)
except:
    font = ImageFont.load_default()

text = "@EGDSUPPORT"
text_bbox = draw.textbbox((0, 0), text, font=font)
text_w = text_bbox[2] - text_bbox[0]
text_h = text_bbox[3] - text_bbox[1]

tg_size = 45
spacing = 15
total_w = tg_size + spacing + text_w
start_x = (group_w - total_w) // 2
content_y = qr_y + qr_size + 30

# Draw TG logo
tg_img = Image.new('RGBA', (tg_size, tg_size), (255, 255, 255, 0))
tg_draw = ImageDraw.Draw(tg_img)
tg_draw.ellipse([0, 0, tg_size, tg_size], fill=(0, 136, 204))
# Paper plane points
cx, cy = tg_size // 2, tg_size // 2
plane_points = [
    (cx - 10, cy - 3),
    (cx + 12, cy - 10),
    (cx + 5, cy + 12),
    (cx + 1, cy + 3),
    (cx - 3, cy + 5)
]
tg_draw.polygon(plane_points, fill=(255, 255, 255))
bg.paste(tg_img, (start_x, content_y - 2), tg_img)

# Draw text
draw.text((start_x + tg_size + spacing, content_y), text, fill=(0, 0, 150, 255), font=font)

out_path = "/Users/nicksng/.gemini/antigravity-ide/brain/d5a704cb-df05-4e0d-b5f0-5303be3a20c2/egd_qr_group_transparent.png"
bg.save(out_path)
print(f"Saved to {out_path}")
