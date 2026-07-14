import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from PIL import Image

# Generate QR code
qr = qrcode.QRCode(
    version=5,
    error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction to allow for a logo in the middle
    box_size=20,
    border=2,
)
qr.add_data('https://t.me/EGDSUPPORT')
qr.make(fit=True)

# ABA Style: Dark Blue (0, 0, 150)
img = qr.make_image(
    image_factory=StyledPilImage,
    module_drawer=RoundedModuleDrawer(),
    color_mask=SolidFillColorMask(front_color=(0, 20, 150), back_color=(255, 255, 255))
)

# Load the EGD Logo from the project directory
logo_path = '/Users/nicksng/code/egd platform/data/logo/egd-logo.21cf446.png'
logo = Image.open(logo_path).convert("RGBA")

# Calculate sizes
qr_w, qr_h = img.size

# The logo should be at most 1/4 the width/height to avoid breaking the QR code scanning
logo_size = int(qr_w / 3.5)
logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

# Create a white background for the logo to stand out cleanly
logo_bg = Image.new('RGB', (logo_size + 20, logo_size + 20), 'white')

# Calculate centered position for the logo inside the white background
x_offset = (logo_bg.width - logo.width) // 2
y_offset = (logo_bg.height - logo.height) // 2
logo_bg.paste(logo, (x_offset, y_offset), logo)

# Paste the logo block into the exact center of the QR code
pos = ((qr_w - logo_bg.size[0]) // 2, (qr_h - logo_bg.size[1]) // 2)
img.paste(logo_bg, pos)

output_path = '/Users/nicksng/.gemini/antigravity-ide/brain/d5a704cb-df05-4e0d-b5f0-5303be3a20c2/telegram_qr_aba_logo.png'
img.save(output_path)
print(f"Generated ABA styled QR at {output_path}")
