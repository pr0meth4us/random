import qrcode
from PIL import Image

# 1. Generate QR Code with high error correction (H) so the center logo doesn't break it
qr = qrcode.QRCode(
    version=4,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=16,
    border=2,
)
qr.add_data('https://telegram.me/EGDsupport')
qr.make(fit=True)

# Make the QR code deep blue to match the aesthetic requested
qr_img = qr.make_image(fill_color=(2, 22, 145), back_color="white").convert('RGBA')

# 2. Open the high-res EGD logo and resize it to fit the center (around 1/3 of the QR width)
logo = Image.open('scratch/poster_gen/logo.png').convert("RGBA")
logo_size = int(qr_img.size[0] / 3.5)
logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

# 3. Create a white background for the logo so it doesn't clash with QR dots
logo_bg = Image.new("RGBA", (logo_size + 20, logo_size + 20), "white")
logo_bg.paste(logo, (10, 10), logo)

# 4. Paste the logo into the center of the QR code
pos = (
    (qr_img.size[0] - logo_bg.size[0]) // 2,
    (qr_img.size[1] - logo_bg.size[1]) // 2
)
qr_img.paste(logo_bg, pos, logo_bg)

# 5. Save the new QR code directly into the assets folder
qr_img.save("assets/qr.png")
print("New QR code generated successfully at assets/qr.png!")
