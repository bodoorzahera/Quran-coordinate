#!/usr/bin/env python3
"""
Deploy the Quran Word Coordinates system to a Hugging Face Space (Docker SDK).

Prerequisites
-------------
1. A Hugging Face account + a WRITE access token:  https://huggingface.co/settings/tokens
2. Log in once (caches the token):   hf auth login
   ...or set it in the environment:  export HF_TOKEN=hf_xxx

Usage
-----
    python scripts/deploy_to_hf.py <username>/<space-name>
    # e.g.
    python scripts/deploy_to_hf.py bodoorzahera/quran-word-coords

What it does
------------
- Creates the Space (Docker SDK) if it does not exist.
- Uploads a Space README.md carrying the required HF YAML header (app_port 7860).
- Uploads the whole project EXCEPT things the running app does not need
  (venv, .git, output/, quran.com-images/, debug images, build artifacts).
- The Space then builds the Dockerfile and serves on port 7860.
"""
import os
import sys
from huggingface_hub import HfApi, create_repo

# Files/dirs the running app does NOT need (mirrors .dockerignore) — keeps the
# Space small and the upload fast. The bundled coord data lives in src/qurancoor/data.
IGNORE = [
    ".git/*", "venv/*", "env/*", ".venv/*",
    "**/__pycache__/*", "*.pyc", "*.bak",
    "dist/*", "build/*", "*.egg-info/*",
    "output/*", "output.old/*",
    "quran.com-images/*",
    "npm/node_modules/*", "npm/dist/*",
    "*.db-journal",
    "README.md",  # uploaded separately with the HF header below
]

SPACE_README = """---
title: Quran Word Coordinates
emoji: 📖
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Quran Word Coordinates

Pixel-accurate word coordinates for every word in the Quran (Madani mushaf),
served as a FastAPI web app. See the project on
[GitHub](https://github.com/bodoorzahera/Quran-coordinate).

- `/`            — main viewer
- `/deploy.html` — deployment guide
- `/Features.html` — features overview
"""


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python scripts/deploy_to_hf.py <username>/<space-name>")
    space_id = sys.argv[1]

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    api = HfApi(token=token)  # falls back to the cached `hf auth login` token

    who = api.whoami()
    print(f"Authenticated as: {who.get('name')}")

    print(f"Creating Space (if needed): {space_id}")
    create_repo(space_id, repo_type="space", space_sdk="docker",
                exist_ok=True, token=token)

    print("Uploading Space README (HF header)…")
    api.upload_file(
        path_or_fileobj=SPACE_README.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=space_id, repo_type="space",
        commit_message="Add Space README with HF header",
    )

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Uploading project from {repo_root} (this may take a while — ~550 MB)…")
    try:
        api.upload_large_folder(
            repo_id=space_id, repo_type="space",
            folder_path=repo_root, ignore_patterns=IGNORE,
        )
    except TypeError:
        # older huggingface_hub: upload_large_folder without ignore_patterns
        api.upload_folder(
            repo_id=space_id, repo_type="space",
            folder_path=repo_root, ignore_patterns=IGNORE,
            commit_message="Deploy Quran Word Coordinates",
        )

    print(f"\n✅ Done. Your Space: https://huggingface.co/spaces/{space_id}")
    print("   It will build the Dockerfile and start on port 7860.")


if __name__ == "__main__":
    main()
