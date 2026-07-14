html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EGD Poster</title>
    <!-- Import modern font -->
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@600;700;800&display=swap');

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background: linear-gradient(135deg, #e0f2fe 0%, #dbeafe 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Inter', sans-serif;
        }

        .poster-card {
            background-color: #ffffff;
            width: 480px;
            border-radius: 32px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 0 40px 40px 40px;
            position: relative;
        }

        .logo {
            width: 140px;
            height: 140px;
            margin-top: -50px;
            margin-bottom: 20px;
            filter: drop-shadow(0 10px 15px rgba(0,0,0,0.1));
            z-index: 10;
        }

        /* Container for the JS injected QR code */
        #qr-code-container {
            width: 340px;
            height: 340px;
            margin-bottom: 30px;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .handle-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }

        .handle-text {
            color: #002277; /* Deep blue to match ABA style */
            font-size: 38px;
            font-weight: 800;
            letter-spacing: 0.5px;
        }

        .telegram-icon {
            width: 42px;
            height: 42px;
        }
    </style>
    <!-- Import QR Code Styling JS Library -->
    <script type="text/javascript" src="https://unpkg.com/qr-code-styling@1.5.0/lib/qr-code-styling.js"></script>
</head>
<body>

    <div class="poster-card">
        
        <img src="assets/logo.png" alt="EGD Logo" class="logo">
        
        <a href="https://telegram.me/EGDsupport" target="_blank" style="text-decoration: none;">
            <div id="qr-code-container"></div>
        </a>
        
        <a href="https://telegram.me/EGDsupport" target="_blank" style="text-decoration: none;">
            <div class="handle-container">
                <svg class="telegram-icon" viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="120" cy="120" r="120" fill="#002277"/>
                    <path d="M54,118.5 l124.7,-47 c5.8,-2.2 10.9,1.4 8.9,7.6 l-21.2,100 c-1.5,7 -5.7,8.7 -11.5,5.5 l-31.9,-23.5 -15.4,14.8 c-1.7,1.7 -3.1,3.1 -6.4,3.1 l2.3,-32.7 59.5,-53.8 c2.6,-2.3 -0.6,-3.6 -4,-1.3 l-73.6,46.3 -31.7,-9.9 c-6.9,-2.2 -7,-6.9 1.4,-10.2 Z" fill="#FFFFFF"/>
                </svg>
                <span class="handle-text">@EGDsupport</span>
            </div>
        </a>

    </div>

    <script type="text/javascript">
        const qrCode = new QRCodeStyling({
            width: 340,
            height: 340,
            data: "https://telegram.me/EGDsupport",
            image: "assets/logo.png",
            dotsOptions: {
                color: "#000000",
                type: "rounded" // ABA style rounded dots
            },
            cornersSquareOptions: {
                color: "#002277", // ABA deep blue
                type: "extra-rounded" // ABA style rounded corner eyes
            },
            cornersDotOptions: {
                color: "#002277", // ABA deep blue
                type: "dot" // Round inner eye balls
            },
            backgroundOptions: {
                color: "#ffffff",
            },
            imageOptions: {
                crossOrigin: "anonymous",
                margin: 10,
                imageSize: 0.35 // Proper size for center logo
            }
        });

        qrCode.append(document.getElementById("qr-code-container"));
    </script>
</body>
</html>
"""

with open("/Users/nicksng/code/random/poster.html", "w") as f:
    f.write(html_content)
