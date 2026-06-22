#!/usr/bin/env python3
"""
Directory File Traversal Script

Traverses all files in a directory with intelligent exclusion defaults.
By default excludes common binary files, images, build artifacts, and dependency directories.
Enhanced with comprehensive Java/Spring Boot exclusions.
"""

import argparse
import os
from pathlib import Path
from typing import List, Optional, Set


class FileTraverser:
    # Default directories to exclude (common build/dependency folders)
    DEFAULT_EXCLUDE_DIRS = {
        # Python
        '__pycache__', '.pytest_cache', 'venv', '.venv', 'env', '.env', '_site',
        'site-packages', '.tox', 'build', 'dist', '*.egg-info',

        # Node.js
        'node_modules', '.npm', '.yarn', '.pnpm-store',

        # Next.js / React / Frontend
        '.next', 'out', 'build', 'dist', '.cache', '.parcel-cache',
        '.nuxt', '.output', '.vercel', '.netlify', 'coverage',
        '.turbo', '.swc', 'storybook-static', '.storybook',
        '.docusaurus', '.vuepress', '.gatsby-cache', 'public/sw.js',

        # Java/Spring Boot/Maven/Gradle
        'target', '.gradle', '.m2', 'bin', 'classes', 'test-classes',
        'generated-sources', 'generated-test-sources', '.mvn',
        'gradle-wrapper', 'wrapper',

        # Version control
        '.git', '.svn', '.hg', '.bzr',

        # IDEs
        '.vscode', '.idea', '.vs', '.eclipse', '.metadata', '.recommenders',
        '.settings', 'nbproject',

        # Build systems
        'cmake-build-debug', 'cmake-build-release',

        # Others
        '.tmp', 'temp', 'logs', '.logs'
    }

    # Default file extensions to exclude
    DEFAULT_EXCLUDE_EXTENSIONS = {
        # Compiled/Binary
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib', '.exe', '.bin', '.o', '.obj',
        '.class', '.jar', '.war', '.ear', '.jmod','.pdf',

        # Source maps and compiled JS/CSS
        '.map', '.min.js', '.min.css',

        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.svg', '.ico',
        '.webp', '.raw', '.cr2', '.nef', '.orf', '.sr2', '.avif',

        # Videos
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp',

        # Audio
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',

        # Archives
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.lzma',

        # Documents (often binary)
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',

        # Fonts
        '.ttf', '.otf', '.woff', '.woff2', '.eot',

        # Database
        '.db', '.sqlite', '.sqlite3', '.mdb',

        # Log files (can be huge)
        '.log', '.out',

        # Temporary files
        '.tmp', '.temp', '.swp', '.swo', '.bak', '.backup', '~',

        # Package files
        '.deb', '.rpm', '.msi', '.dmg', '.pkg',

        # Certificates
        '.p12', '.pfx', '.crt', '.cer', '.key', '.pem'
    }

    # Default filenames to exclude
    DEFAULT_EXCLUDE_NAMES = {
        # System files
        '.DS_Store', 'Thumbs.db', 'desktop.ini',

        # Lock files
        'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'bun.lockb',
        'Pipfile.lock', 'poetry.lock', 'composer.lock', 'Gemfile.lock',

        # Next.js / React / Frontend specific
        'next-env.d.ts', 'next.config.js', 'next.config.mjs', 'next.config.ts',
        'tsconfig.tsbuildinfo', '.eslintcache', '.stylelintcache',
        'sw.js', 'workbox-*.js', 'precache-manifest.*.js', 'service-worker.js',
        '.env.local', '.env.development.local', '.env.test.local', '.env.production.local',
        'cypress.json', 'jest.config.js', 'jest.config.ts', 'vitest.config.js',
        'playwright.config.js', 'playwright.config.ts', 'movies.yml', 'watchlog.yml', 'leaderboard.yml',

        # Java/Spring Boot specific files
        '.env', 'application.properties', 'application.yml', 'application.yaml',
        'application-dev.properties', 'application-prod.properties', 'application-test.properties',
        'application-local.properties', 'bootstrap.properties', 'bootstrap.yml',
        'gradle.properties', 'gradlew', 'gradlew.bat', 'mvnw', 'mvnw.cmd',
        'pom.xml.versionsBackup', '.classpath', '.project',

        # Large config/data files
        'requirements.txt'  # Remove this if you want to include requirements
    }

    # Special patterns for more complex exclusions
    DEFAULT_EXCLUDE_PATTERNS = {
        # Environment files
        r'\.env.*',  # .env, .env.local, .env.production, etc.
        r'application-.*\.properties',  # application-{profile}.properties
        r'application-.*\.ya?ml',  # application-{profile}.yml/yaml

        # Next.js / Frontend patterns
        r'.*\.chunk\.js',  # webpack chunks
        r'.*\.chunk\.css',  # webpack chunks
        r'.*-[a-f0-9]{8,}\.js',  # hashed filenames
        r'.*-[a-f0-9]{8,}\.css',  # hashed filenames
        r'sw\.js',  # service worker
        r'workbox-.*\.js',  # workbox files
        r'precache-manifest\..*\.js',  # precache manifest
        r'.*\.hot-update\.js',  # webpack hot updates
        r'.*\.hot-update\.json',  # webpack hot updates
    }

    def __init__(self,
                 path: str,
                 exclude_dirs: Optional[List[str]] = None,
                 exclude_extensions: Optional[List[str]] = None,
                 exclude_names: Optional[List[str]] = None,
                 use_defaults: bool = True):
        """
        Initialize the file traverser.

        Args:
            path: Directory path (relative or absolute)
            exclude_dirs: List of directory names to exclude
            exclude_extensions: List of file extensions to exclude (with or without dots)
            exclude_names: List of full file names to exclude
            use_defaults: Whether to use smart default exclusions
        """
        self.path = Path(path).resolve()

        # Start with defaults if enabled
        if use_defaults:
            self.exclude_dirs = self.DEFAULT_EXCLUDE_DIRS.copy()
            self.exclude_extensions = self.DEFAULT_EXCLUDE_EXTENSIONS.copy()
            self.exclude_names = self.DEFAULT_EXCLUDE_NAMES.copy()
            self.exclude_patterns = self.DEFAULT_EXCLUDE_PATTERNS.copy()
        else:
            self.exclude_dirs = set()
            self.exclude_extensions = set()
            self.exclude_names = set()
            self.exclude_patterns = set()

        # Add user-specified exclusions
        if exclude_dirs:
            self.exclude_dirs.update(exclude_dirs)
        if exclude_extensions:
            self.exclude_extensions.update(self._normalize_extensions(exclude_extensions))
        if exclude_names:
            self.exclude_names.update(exclude_names)

        if not self.path.exists():
            raise FileNotFoundError(f"Directory not found: {self.path}")
        if not self.path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.path}")

    @staticmethod
    def _normalize_extensions(extensions: List[str]) -> Set[str]:
        """Normalize extensions to include leading dots and lowercase."""
        normalized = set()
        for ext in extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            normalized.add(ext.lower())
        return normalized

    def _should_exclude_dir(self, dir_name: str) -> bool:
        """Check if directory should be excluded."""
        return dir_name in self.exclude_dirs

    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded based on extension, name, or pattern."""
        import re

        # Check file name exclusion
        if file_path.name in self.exclude_names:
            return True

        # Check extension exclusion
        if file_path.suffix.lower() in self.exclude_extensions:
            return True

        # Check pattern exclusions
        for pattern in self.exclude_patterns:
            if re.match(pattern, file_path.name):
                return True

        # Check for hidden files (starting with .) but allow some exceptions
        allowed_hidden = {'.gitignore', '.env.example', '.dockerignore', '.editorconfig',
                          '.babelrc', '.eslintrc.js', '.eslintrc.json', '.prettierrc',
                          '.prettierrc.json', '.nvmrc', '.node-version'}
        if file_path.name.startswith('.') and file_path.name not in allowed_hidden:
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
                            # Skip binary files rather than trying to decode
                            outfile.write(f"[Skipped: Binary file detected]\n")
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
                relative_path = file_path.relative_to(self.path)
                print(f"{relative_path}")
            except ValueError:
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

    def print_exclusions(self):
        """Print current exclusion settings for debugging."""
        print("Current exclusion settings:")
        print(f"Excluded directories ({len(self.exclude_dirs)}): {sorted(self.exclude_dirs)}")
        print(f"Excluded extensions ({len(self.exclude_extensions)}): {sorted(self.exclude_extensions)}")
        print(f"Excluded filenames ({len(self.exclude_names)}): {sorted(self.exclude_names)}")
        print(f"Excluded patterns ({len(self.exclude_patterns)}): {sorted(self.exclude_patterns)}")


def main():
    parser = argparse.ArgumentParser(
        description="Traverse directories with intelligent exclusion defaults",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s src app                           # Use smart defaults (includes Next.js/Java/Spring Boot exclusions)
  %(prog)s src --no-defaults --exclude-ext .py  # No defaults, only exclude .py
  %(prog)s src --exclude-dirs build target      # Add to default exclusions
  %(prog)s src --list-only                       # List files that would be processed
  %(prog)s src --show-exclusions                 # Show what's being excluded
        """
    )

    parser.add_argument('paths', nargs='+', help='One or more directory paths')

    parser.add_argument('--exclude-dirs', nargs='*', default=[],
                        help='Additional directory names to exclude')

    parser.add_argument('--exclude-ext', nargs='*', default=[],
                        help='Additional file extensions to exclude (e.g. .pyc .log)')

    parser.add_argument('--exclude-names', nargs='*', default=[],
                        help='Additional full file names to exclude')

    parser.add_argument('--no-defaults', action='store_true',
                        help='Disable default exclusions (only use specified exclusions)')

    parser.add_argument('-o', '--output', default='combined_files.txt',
                        help='Output file name')

    parser.add_argument('--list-only', action='store_true',
                        help='List file names only, do not combine contents')

    parser.add_argument('--info', action='store_true',
                        help='Show detailed file information')

    parser.add_argument('--show-exclusions', action='store_true',
                        help='Show current exclusion settings')

    args = parser.parse_args()

    try:
        # When combining contents we open the output file once
        outfile_handle = None
        if not args.list_only and not args.info and not args.show_exclusions:
            outfile_handle = open(args.output, 'w', encoding='utf-8')

        for path in args.paths:
            traverser = FileTraverser(
                path=path,
                exclude_dirs=args.exclude_dirs,
                exclude_extensions=args.exclude_ext,
                exclude_names=args.exclude_names,
                use_defaults=not args.no_defaults
            )

            if args.show_exclusions:
                print(f"\nExclusions for {path}:")
                traverser.print_exclusions()
                print()
            elif args.info:
                traverser.get_file_info()
            elif args.list_only:
                traverser.print_files()
            else:
                # Combine files to output
                files = traverser.traverse()
                if not files:
                    print(f"No files found in {path}")
                    continue

                outfile_handle.write(f"{'=' * 80}\n")
                outfile_handle.write(f"Directory: {traverser.path}\n")
                outfile_handle.write(f"Total files: {len(files)}\n")
                outfile_handle.write(f"{'=' * 80}\n\n")

                for file_path in sorted(files):
                    try:
                        relative = file_path.relative_to(traverser.path)
                        outfile_handle.write(f"{'=' * 20} FILE: {relative} {'=' * 20}\n")

                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except UnicodeDecodeError:
                            outfile_handle.write(f"[Skipped: Binary file detected]\n")
                            continue
                        except Exception as e:
                            outfile_handle.write(f"[Error reading file: {e}]\n")
                            continue

                        outfile_handle.write(content)
                        if not content.endswith('\n'):
                            outfile_handle.write('\n')
                        outfile_handle.write(f"\n{'=' * 60}\n\n")
                    except Exception as e:
                        print(f"Warning: Could not process {file_path}: {e}")

        if outfile_handle:
            outfile_handle.close()
            print(f"Combined output written to '{args.output}'")

    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())