#!/usr/bin/env python3
import argparse
import qrcode
import sys

def main():
    parser = argparse.ArgumentParser(description="Generate a QR code from text or URL.")
    parser.add_argument("--data", "-d", required=True, help="The data (text or URL) to encode")
    parser.add_argument("--output", "-o", default="qr.png", help="Output file path (e.g. qr.png)")
    parser.add_argument("--fill-color", "-f", default="black", help="QR code fill color")
    parser.add_argument("--back-color", "-b", default="white", help="QR code background color")
    parser.add_argument("--box-size", "-s", type=int, default=10, help="Size of each box in pixels")
    parser.add_argument("--border", type=int, default=4, help="Border thickness in boxes")

    args = parser.parse_args()

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=args.box_size,
            border=args.border,
        )
        qr.add_data(args.data)
        qr.make(fit=True)

        img = qr.make_image(fill_color=args.fill_color, back_color=args.back_color)
        img.save(args.output)
        print(f"Successfully generated QR code to {args.output}")
    except Exception as e:
        print(f"Error generating QR code: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
