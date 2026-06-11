#!/usr/bin/env python3
"""
pdf_merger.py
-------------
A utility script to merge multiple PDF documents into a single PDF file.
"""

import argparse
from pathlib import Path
from typing import List
from pypdf import PdfMerger, errors


def merge_pdfs(input_paths: List[Path], output_path: Path) -> None:
    """
    Merges the specified PDF files into a single output PDF.

    Args:
        input_paths: List of Path objects to the input PDF files.
        output_path: Path object where the merged PDF will be saved.
    """
    merger = PdfMerger()

    try:
        for path in input_paths:
            if not path.exists():
                print(f"Error: Input file '{path}' does not exist.")
                return
            print(f"Adding: {path}")
            merger.append(str(path))

        # Ensure parent directory of output exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Saving merged file to: {output_path}")
        with open(output_path, "wb") as output_file:
            merger.write(output_file)

        print("✅ Success! PDF files merged successfully.")

    except errors.PyPdfError as err:
        print(f"❌ PDF processing error: {err}")
    except IOError as err:
        print(f"❌ I/O error: {err}")
    finally:
        merger.close()


def main() -> None:
    """
    Parses command-line arguments and runs the PDF merger.
    """
    parser = argparse.ArgumentParser(
        description="Merge multiple PDF files into a single PDF."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="List of PDF files to merge (in the order they should appear).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="merged.pdf",
        help="Path to the output merged PDF file (default: merged.pdf).",
    )

    args = parser.parse_args()

    input_paths = [Path(p).resolve() for p in args.inputs]
    output_path = Path(args.output).resolve()

    merge_pdfs(input_paths, output_path)


if __name__ == "__main__":
    main()
