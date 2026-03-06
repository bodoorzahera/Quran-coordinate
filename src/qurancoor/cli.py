#!/usr/bin/env python3
"""
qurancoor CLI - unified command-line interface.

Usage:
    qurancoor serve   --images-dir ./images [--port 8003]
    qurancoor generate --build-db -q quran.com-images
    qurancoor generate -b . -q quran.com-images -o output --all
    qurancoor build-freq --mushaf-dir ./mushaf --db word_freq.db
"""
import sys


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print("qurancoor - Quran Word Coordinates System")
        print()
        print("Commands:")
        print("  serve       Launch the web viewer/editor")
        print("  generate    Generate word coordinates from mushaf images")
        print("  build-freq  Build word frequency database")
        print()
        print("Data API (Python):")
        print("  from qurancoor import get_page, get_word, find_word_at, get_ayah")
        print()
        print("Usage: qurancoor <command> [options]")
        print("       qurancoor <command> --help  for command-specific help")
        return

    cmd = sys.argv[1]
    sys.argv = [f"qurancoor {cmd}"] + sys.argv[2:]

    if cmd == "serve":
        from qurancoor.server import main as serve_main
        serve_main()
    elif cmd == "generate":
        from qurancoor.generate import main as gen_main
        gen_main()
    elif cmd == "build-freq":
        from qurancoor.build_freq import main as freq_main
        freq_main()
    else:
        print(f"Unknown command: {cmd}")
        print("Available commands: serve, generate, build-freq")
        sys.exit(1)


if __name__ == "__main__":
    main()
