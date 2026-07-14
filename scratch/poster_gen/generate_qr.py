import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
import os

qr = qrcode.QRCode(
    version=4,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=20,
    border=2,
)
qr.add_data('https://t.me/EGDSUPPORT')
qr.make(fit=True)

# Create a QR code with rounded modules and a dark blue color (to match the EGD theme)
img = qr.make_image(
    image_factory=StyledPilImage,
    module_drawer=RoundedModuleDrawer(),
    color_mask=SolidFillColorMask(front_color=(0, 0, 150), back_color=(255, 255, 255))
)

output_path = '/Users/nicksng/.gemini/antigravity-ide/brain/d5a704cb-df05-4e0d-b5f0-5303be3a20c2/telegram_qr.png'
img.save(output_path)
print(f"Generated QR at {output_path}")
