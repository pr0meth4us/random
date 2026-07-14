with open("/Users/nicksng/code/random/poster.html", "r") as f:
    content = f.read()

# Make the QR code clickable
content = content.replace(
    '<img src="assets/qr.png" alt="QR Code" class="qr-code">',
    '<a href="https://telegram.me/EGDsupport" target="_blank">\n            <img src="assets/qr.png" alt="QR Code" class="qr-code">\n        </a>'
)

# Make the handle section clickable too, removing default link styling
content = content.replace(
    '<div class="handle-container">',
    '<a href="https://telegram.me/EGDsupport" target="_blank" class="handle-link" style="text-decoration: none;">\n        <div class="handle-container">'
)
content = content.replace(
    '<span class="handle-text">@EGDsupport</span>\n        </div>',
    '<span class="handle-text">@EGDsupport</span>\n        </div>\n        </a>'
)

with open("/Users/nicksng/code/random/poster.html", "w") as f:
    f.write(content)
