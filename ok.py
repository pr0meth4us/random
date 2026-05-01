import cv2
import numpy as np


def find_and_circle_differences(image_path):
    image = cv2.imread(image_path)

    if image is None:
        print(f"Error: Could not load '{image_path}'.")
        return

    height, width, _ = image.shape
    half_height = height // 2

    # 1. Shave off the edges to ignore the outer cyan borders completely
    top_half = image[15:half_height - 15, 15:width - 15]
    bottom_half = image[half_height + 15:height - 15, 15:width - 15]

    # 2. Force exact dimensions
    min_height = min(top_half.shape[0], bottom_half.shape[0])
    top_half = top_half[:min_height, :]
    bottom_half = bottom_half[:min_height, :]

    gray_top = cv2.cvtColor(top_half, cv2.COLOR_BGR2GRAY)
    gray_bottom = cv2.cvtColor(bottom_half, cv2.COLOR_BGR2GRAY)

    # 3. Blur the images slightly to smooth over JPEG artifacts and misaligned pixels
    gray_top = cv2.GaussianBlur(gray_top, (5, 5), 0)
    gray_bottom = cv2.GaussianBlur(gray_bottom, (5, 5), 0)

    diff = cv2.absdiff(gray_top, gray_bottom)

    # 4. Turn up the threshold so it only triggers on hard differences (bold text)
    _, thresh = cv2.threshold(diff, 60, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    result_image = top_half.copy()
    for contour in contours:
        area = cv2.contourArea(contour)

        # 5. THE FIX: Strict area filter.
        # Only draw a circle if the difference is roughly the size of a single number.
        # This prevents the giant overlapping border circles and tiny speckles.
        if 50 < area < 800:
            x, y, w, h = cv2.boundingRect(contour)
            center = (x + w // 2, y + h // 2)
            radius = max(w, h) // 2 + 10
            cv2.circle(result_image, center, radius, (0, 0, 255), 2)

    output_filename = "differences_circled_fixed.jpg"
    cv2.imwrite(output_filename, result_image)
    print(f"Done. Check '{output_filename}' for a much less stupid result.")


# Run the script
file_name = "657508906_1990854864882756_6868413732217022383_n.jpg"
find_and_circle_differences(file_name)