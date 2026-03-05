#!/usr/bin/env python3
"""hf_fast_mdl - Fast Hugging Face model file downloader."""

# Keep fast transfer opt-in by default, while allowing user override.
import os

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

import argparse
import curses
import fnmatch
import sys
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.hf_api import RepoFile
from huggingface_hub.errors import (
    EntryNotFoundError,
    GatedRepoError,
    RepositoryNotFoundError,
)


@dataclass
class FileEntry:
    path: str
    size: int
    selected: bool = False


def format_size(size_bytes: int) -> str:
    b = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024.0:
            if unit == "B":
                return f"{int(b)} B"
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} PB"


def fetch_file_list(
    repo_id: str,
    patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    token: str | None = None,
) -> list[FileEntry]:
    api = HfApi()
    try:
        tree = api.list_repo_tree(repo_id, recursive=True, token=token)
        entries = []
        for item in tree:
            if not isinstance(item, RepoFile):
                continue
            if patterns:
                if not any(fnmatch.fnmatch(item.path, p) for p in patterns):
                    continue
            if exclude_patterns:
                if any(fnmatch.fnmatch(item.path, p) for p in exclude_patterns):
                    continue
            size = item.size or 0
            if item.lfs and item.lfs.size:
                size = item.lfs.size
            entries.append(
                FileEntry(
                    path=item.path,
                    size=size,
                )
            )
        entries.sort(key=lambda e: e.path)
        return entries
    except RepositoryNotFoundError:
        print(f"Error: Repository '{repo_id}' not found.", file=sys.stderr)
        sys.exit(1)
    except GatedRepoError:
        print(
            f"Error: Repository '{repo_id}' is gated. "
            "Run `huggingface-cli login` and request access.",
            file=sys.stderr,
        )
        sys.exit(1)
    except OSError as e:
        print(f"Error: Network error: {e}", file=sys.stderr)
        sys.exit(1)


def _picker_main(stdscr, files: list[FileEntry]) -> list[FileEntry]:
    curses.curs_set(0)
    curses.use_default_colors()
    stdscr.keypad(True)

    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_CYAN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)

    cursor = 0
    scroll_offset = 0

    while True:
        max_y, max_x = stdscr.getmaxyx()
        if max_y < 8 or max_x < 40:
            stdscr.erase()
            stdscr.addnstr(0, 0, "Terminal too small (min 40x8)", max_x - 1)
            stdscr.refresh()
            stdscr.getch()
            continue

        header_lines = 3
        footer_lines = 1
        visible_rows = max_y - header_lines - footer_lines

        # Clamp cursor and scroll
        cursor = max(0, min(cursor, len(files) - 1))
        if cursor < scroll_offset:
            scroll_offset = cursor
        elif cursor >= scroll_offset + visible_rows:
            scroll_offset = cursor - visible_rows + 1
        scroll_offset = max(0, scroll_offset)

        stdscr.erase()

        # Header
        total_size = sum(f.size for f in files)
        header = f" {len(files)} files ({format_size(total_size)} total)"
        try:
            stdscr.addnstr(0, 0, header, max_x - 1, curses.color_pair(2) | curses.A_BOLD)
        except curses.error:
            pass

        help_text = " ↑↓ Navigate  SPACE Select  a All  n None  ENTER Confirm  q Quit"
        try:
            stdscr.addnstr(1, 0, help_text, max_x - 1, curses.A_DIM)
        except curses.error:
            pass

        try:
            stdscr.addnstr(2, 0, "─" * (max_x - 1), max_x - 1, curses.A_DIM)
        except curses.error:
            pass

        # File list
        for i in range(visible_rows):
            idx = scroll_offset + i
            if idx >= len(files):
                break
            f = files[idx]
            row = header_lines + i

            marker = ">" if idx == cursor else " "
            check = "x" if f.selected else " "
            size_str = format_size(f.size)

            # Build the line: "> [x] filename        4.9 GB"
            prefix = f"{marker} [{check}] "
            # Reserve space for size on the right
            size_col = max_x - len(size_str) - 2
            name_max = size_col - len(prefix) - 1
            name = f.path
            if len(name) > name_max > 0:
                name = name[: name_max - 1] + "…"

            line = f"{prefix}{name}"
            if len(line) < size_col:
                line += " " * (size_col - len(line))
            line += f" {size_str}"

            attr = curses.A_NORMAL
            if idx == cursor:
                attr = curses.A_REVERSE
            elif f.selected:
                attr = curses.color_pair(1) | curses.A_BOLD

            try:
                stdscr.addnstr(row, 0, line, max_x - 1, attr)
            except curses.error:
                pass

        # Footer
        selected = [f for f in files if f.selected]
        sel_size = sum(f.size for f in selected)
        footer = f" Selected: {len(selected)} files ({format_size(sel_size)}) | {cursor + 1}/{len(files)}"
        try:
            stdscr.addnstr(max_y - 1, 0, footer, max_x - 1, curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            cursor = max(0, cursor - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            cursor = min(len(files) - 1, cursor + 1)
        elif key == ord(" "):
            files[cursor].selected = not files[cursor].selected
            cursor = min(len(files) - 1, cursor + 1)
        elif key in (ord("a"), ord("A")):
            for f in files:
                f.selected = True
        elif key in (ord("n"), ord("N")):
            for f in files:
                f.selected = False
        elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            return [f for f in files if f.selected]
        elif key in (ord("q"), ord("Q"), 27):
            if key == 27:
                stdscr.nodelay(True)
                next_key = stdscr.getch()
                stdscr.nodelay(False)
                if next_key != -1:
                    continue
            return []
        elif key == curses.KEY_PPAGE:
            cursor = max(0, cursor - visible_rows)
        elif key == curses.KEY_NPAGE:
            cursor = min(len(files) - 1, cursor + visible_rows)
        elif key == ord("g"):
            cursor = 0
        elif key == ord("G"):
            cursor = len(files) - 1


def run_picker(files: list[FileEntry]) -> list[FileEntry]:
    if not files:
        print("No files match the given criteria.")
        sys.exit(0)
    return curses.wrapper(_picker_main, files)


def download_files(
    repo_id: str,
    files: list[FileEntry],
    output_dir: Path,
    token: str | None = None,
    cache_dir: Path | None = None,
    force_download: bool = False,
    offline: bool = False,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_size = sum(f.size for f in files)
    size_str = f" ({format_size(total_size)})" if total_size > 0 else ""
    print(f"Downloading {len(files)} file(s){size_str} to {output_dir}/\n")

    errors = 0
    skipped = 0

    for i, entry in enumerate(files, 1):
        size_info = f" ({format_size(entry.size)})" if entry.size > 0 else ""
        print(f"[{i}/{len(files)}] {entry.path}{size_info}")

        dest_file = output_dir / entry.path
        if dest_file.exists() and not force_download:
            skipped += 1
            print("  SKIP: Already exists locally (use --force-download to re-fetch)")
            continue

        try:
            hf_hub_download(
                repo_id=repo_id,
                filename=entry.path,
                local_dir=str(output_dir),
                token=token,
                cache_dir=str(cache_dir) if cache_dir else None,
                force_download=force_download,
                local_files_only=offline,
            )
        except EntryNotFoundError:
            errors += 1
            print(f"  WARNING: File not found on server, skipping: {entry.path}", file=sys.stderr)
        except Exception as e:
            errors += 1
            print(f"  ERROR downloading {entry.path}: {e}", file=sys.stderr)

    print(f"\nDone. Files saved to {output_dir}/")
    if skipped:
        print(f"Skipped {skipped} file(s) that already exist locally.")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hf_fast_mdl",
        description="Fast Hugging Face model file downloader",
    )
    parser.add_argument(
        "repo_id",
        help='Repository ID (e.g. "unsloth/Qwen3.5-9B-GGUF")',
    )
    parser.add_argument(
        "-p",
        "--pattern",
        action="append",
        default=None,
        help='Glob pattern to filter files (e.g. "*.gguf"). Repeatable.',
    )
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        default=None,
        dest="files",
        help="File to download directly (skip picker). Repeatable.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: ./repo-name/)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Hugging Face token (default: uses cached login)",
    )
    parser.add_argument(
        "-x",
        "--exclude-pattern",
        action="append",
        default=None,
        help='Glob pattern to exclude files (e.g. "*.md"). Repeatable.',
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Non-interactive: auto-download all matched files without picker.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Custom Hugging Face cache directory.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use local cache only (no network requests).",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Force re-download even if file exists locally or in cache.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_id = args.repo_id

    if args.output:
        output_dir = args.output.resolve()
    else:
        repo_name = repo_id.split("/")[-1]
        output_dir = Path.cwd() / repo_name

    if args.files:
        entries = [FileEntry(path=f, size=0) for f in args.files]
        failures = download_files(
            repo_id,
            entries,
            output_dir,
            token=args.token,
            cache_dir=args.cache_dir,
            force_download=args.force_download,
            offline=args.offline,
        )
        if failures:
            sys.exit(1)
    else:
        entries = fetch_file_list(
            repo_id,
            patterns=args.pattern,
            exclude_patterns=args.exclude_pattern,
            token=args.token,
        )
        if not entries:
            print("No files found matching the given criteria.")
            sys.exit(0)

        if args.yes:
            selected = entries
        elif not sys.stdout.isatty():
            print(
                "Interactive mode requires a terminal. Use --yes for non-interactive batch downloads.",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            selected = run_picker(entries)
            if not selected:
                print("No files selected.")
                sys.exit(0)

        failures = download_files(
            repo_id,
            selected,
            output_dir,
            token=args.token,
            cache_dir=args.cache_dir,
            force_download=args.force_download,
            offline=args.offline,
        )
        if failures:
            sys.exit(1)


if __name__ == "__main__":
    main()
