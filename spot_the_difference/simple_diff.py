"""
simple_diff.py
--------------
Finds and circles differences between the top and bottom halves of an image
(e.g., spot-the-difference puzzle).
"""

from pathlib import Path
import cv2


def find_and_circle_differences(image_path: Path):
    """
    Loads the puzzle image, splits it into top and bottom halves,
    computes the pixel difference, and circles the differences.
    """
    image = cv2.imread(str(image_path))

    if image is None:
        print(f"Error: Could not load '{image_path}'.")
        return

    height, width, _ = image.shape
    half_height = height // 2

    # 1. Shave off the edges to ignore the outer cyan borders completely
    top_half = image[15 : half_height - 15, 15 : width - 15]
    bottom_half = image[half_height + 15 : height - 15, 15 : width - 15]

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

        # 5. Strict area filter:
        # Only draw a circle if the difference is roughly the size of a single number.
        if 50 < area < 800:
            x, y, w, h = cv2.boundingRect(contour)
            center = (x + w // 2, y + h // 2)
            radius = max(w, h) // 2 + 10
            cv2.circle(result_image, center, radius, (0, 0, 255), 2)

    script_dir = Path(__file__).resolve().parent
    output_path = script_dir / "differences_circled_fixed.jpg"
    cv2.imwrite(str(output_path), result_image)
    print(f"Done. Check '{output_path}' for the results.")


if __name__ == "__main__":
    # Run the script with default test image
    SCRIPT_DIR = Path(__file__).resolve().parent
    TEST_IMAGE = SCRIPT_DIR / "test_image.jpg"
    find_and_circle_differences(TEST_IMAGE)