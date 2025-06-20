#!/usr/bin/env python3
"""
Directory File Traversal Script

Traverses all files in a directory with flexible exclusion options.
Supports excluding directories, file extensions, and specific file names.
"""

import os
import argparse
from pathlib import Path
from typing import List, Set, Optional


class FileTraverser:
    def __init__(self,
                 path: str,
                 exclude_dirs: Optional[List[str]] = None,
                 exclude_extensions: Optional[List[str]] = None,
                 exclude_names: Optional[List[str]] = None):
        """
        Initialize the file traverser.

        Args:
            path: Directory path (relative or absolute)
            exclude_dirs: List of directory names to exclude
            exclude_extensions: List of file extensions to exclude (with or without dots)
            exclude_names: List of full file names to exclude
        """
        self.path = Path(path).resolve()
        self.exclude_dirs = set(exclude_dirs or [])
        self.exclude_extensions = set(self._normalize_extensions(exclude_extensions or []))
        self.exclude_names = set(exclude_names or [])

        if not self.path.exists():
            raise FileNotFoundError(f"Directory not found: {self.path}")
        if not self.path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.path}")

    def _normalize_extensions(self, extensions: List[str]) -> List[str]:
        """Normalize extensions to include leading dots."""
        normalized = []
        for ext in extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            normalized.append(ext.lower())
        return normalized

    def _should_exclude_dir(self, dir_name: str) -> bool:
        """Check if directory should be excluded."""
        return dir_name in self.exclude_dirs

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded based on extension or name."""
        # Check file name exclusion
        if file_path.name in self.exclude_names:
            return True

        # Check extension exclusion
        if file_path.suffix.lower() in self.exclude_extensions:
            return True

        return False

    def traverse(self) -> List[Path]:
        """
        Traverse directory and return list of non-excluded files.

        Returns:
            List of Path objects for files that pass all filters
        """
        files = []

        for root, dirs, filenames in os.walk(self.path):
            root_path = Path(root)

            # Filter out excluded directories (modify dirs in-place to prevent traversal)
            dirs[:] = [d for d in dirs if not self._should_exclude_dir(d)]

            for filename in filenames:
                file_path = root_path / filename

                if not self._should_exclude_file(file_path):
                    files.append(file_path)

        return files

    def write_files_to_output(self, output_file: str = "combined_files.txt"):
        """Write content of all non-excluded files to an output file."""
        files = self.traverse()

        if not files:
            print("No files found matching the criteria.")
            return

        try:
            with open(output_file, 'w', encoding='utf-8') as outfile:
                outfile.write(f"Combined file contents from directory: {self.path}\n")
                outfile.write(f"Total files processed: {len(files)}\n")
                outfile.write("=" * 80 + "\n\n")

                for file_path in sorted(files):
                    try:
                        # Get relative path for header
                        try:
                            relative_path = file_path.relative_to(self.path)
                        except ValueError:
                            relative_path = file_path

                        # Write file header
                        outfile.write(f"{'=' * 20} FILE: {relative_path} {'=' * 20}\n")

                        # Try to read file content
                        try:
                            with open(file_path, 'r', encoding='utf-8') as infile:
                                content = infile.read()
                                outfile.write(content)
                                if not content.endswith('\n'):
                                    outfile.write('\n')
                        except UnicodeDecodeError:
                            # Try with different encoding for non-UTF-8 files
                            try:
                                with open(file_path, 'r', encoding='latin-1') as infile:
                                    content = infile.read()
                                    outfile.write(f"[Binary/Non-UTF-8 file content - decoded with latin-1]\n")
                                    outfile.write(content)
                                    if not content.endswith('\n'):
                                        outfile.write('\n')
                            except Exception as e:
                                outfile.write(f"[Error reading file: {e}]\n")
                        except Exception as e:
                            outfile.write(f"[Error reading file: {e}]\n")

                        outfile.write(f"\n{'=' * 60}\n\n")

                    except Exception as e:
                        print(f"Warning: Could not process {file_path}: {e}")
                        continue

            print(f"Successfully combined {len(files)} files into '{output_file}'")

        except IOError as e:
            print(f"Error writing to output file '{output_file}': {e}")

    def print_files(self):
        """Print all non-excluded files with their relative paths."""
        files = self.traverse()

        if not files:
            print("No files found matching the criteria.")
            return

        print(f"Found {len(files)} files:")
        print("-" * 50)

        for file_path in sorted(files):
            try:
                # Try to show relative path from the base directory
                relative_path = file_path.relative_to(self.path)
                print(f"{relative_path}")
            except ValueError:
                # If relative path fails, show absolute path
                print(f"{file_path}")

    def get_file_info(self):
        """Get detailed information about found files."""
        files = self.traverse()

        total_size = 0
        file_types = {}

        for file_path in files:
            try:
                stat = file_path.stat()
                total_size += stat.st_size

                ext = file_path.suffix.lower() or 'no extension'
                file_types[ext] = file_types.get(ext, 0) + 1
            except (OSError, IOError):
                continue

        print(f"Directory: {self.path}")
        print(f"Total files: {len(files)}")
        print(f"Total size: {total_size:,} bytes ({total_size / (1024 * 1024):.2f} MB)")
        print("\nFile types:")
        for ext, count in sorted(file_types.items()):
            print(f"  {ext}: {count} files")


def main():
    parser = argparse.ArgumentParser(
        description="Traverse directory files with exclusion options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/dir
  %(prog)s . --output combined.txt
  %(prog)s ~/project --exclude-dirs __pycache__ .git --output project_code.txt
  %(prog)s /src --exclude-ext .pyc .log --output source_files.txt
  %(prog)s . --exclude-names config.json --list-only
  %(prog)s . --info
        """
    )

    parser.add_argument('path',
                        help='Directory path (relative or absolute)')

    parser.add_argument('--exclude-dirs',
                        nargs='*',
                        default=[],
                        help='Directory names to exclude (optional)')

    parser.add_argument('--exclude-ext',
                        nargs='*',
                        default=[],
                        help='File extensions to exclude (optional, e.g., .pyc .log)')

    parser.add_argument('--exclude-names',
                        nargs='*',
                        default=[],
                        help='Full file names to exclude (optional)')

    parser.add_argument('--output', '-o',
                        default='combined_files.txt',
                        help='Output file name (default: combined_files.txt)')

    parser.add_argument('--list-only',
                        action='store_true',
                        help='List file names only, do not combine contents')

    parser.add_argument('--info',
                        action='store_true',
                        help='Show detailed file information instead of listing files')

    args = parser.parse_args()

    try:
        traverser = FileTraverser(
            path=args.path,
            exclude_dirs=args.exclude_dirs,
            exclude_extensions=args.exclude_ext,
            exclude_names=args.exclude_names
        )

        if args.info:
            traverser.get_file_info()
        elif args.list_only:
            traverser.print_files()
        else:
            # Default behavior: combine file contents into output file
            traverser.write_files_to_output(args.output)

    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())