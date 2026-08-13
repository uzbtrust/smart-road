"""Put the Smart Road app on the account's existing Hugging Face Space.

    zsh -ic '.venv/bin/python deploy/push_space.py'

Run it through an interactive zsh so HF_TOKEN comes out of ~/.zshrc. The token
is read from the environment by huggingface_hub and is never printed here.

Why this renames instead of creating: a free account can no longer create a
Docker Space -- create_repo answers 402, "hosting Gradio and Docker Spaces on
free cpu-basic requires a PRO subscription" -- yet uzbtrust/triagegeist is a
free cpu-basic Docker Space that runs. Older Spaces were kept; new ones are
not allowed. So deleting one and creating another would lose the old Space and
still hit the paywall. Renaming reuses the grandfathered Space and never
touches create_repo. It is also reversible: the rename can be undone and the
previous contents stay in the Space's git history.

Idempotent: if the rename already happened, it carries on to the upload.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The Space we are taking over, and what it becomes.
OLD_SPACE = "uzbtrust/triagegeist"
SPACE = "uzbtrust/smart-road"

#: What the Space needs to run. Weights are not here -- app.py falls back to
#: hf_hub_download when models/ is absent, which on the Space it always is.
PAYLOAD = (
    ("deploy/hf_space/README.md", "README.md"),
    ("deploy/hf_space/Dockerfile", "Dockerfile"),
    ("deploy/hf_space/requirements.txt", "requirements.txt"),
    # Streamlit paints its chrome from this before any injected CSS runs, so
    # without it the Space starts on the default theme and flashes white.
    (".streamlit/config.toml", ".streamlit/config.toml"),
    ("app.py", "app.py"),
    ("smartroad", "smartroad"),
    ("samples", "samples"),
)


def stage(into: Path) -> None:
    for src_rel, dst_rel in PAYLOAD:
        src, dst = ROOT / src_rel, into / dst_rel
        if src.is_dir():
            shutil.copytree(src, dst,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
        print(f"  + {dst_rel}")


def main() -> int:
    if not os.environ.get("HF_TOKEN"):
        sys.exit("HF_TOKEN muhitda yo'q — skriptni `zsh -ic` orqali ishga tushiring.")

    from huggingface_hub import HfApi
    from huggingface_hub.errors import RepositoryNotFoundError

    api = HfApi(token=os.environ["HF_TOKEN"])
    print(f"Hugging Face: {api.whoami()['name']}")

    try:
        api.space_info(SPACE)
        print(f"{SPACE} allaqachon mavjud — nom o'zgartirish o'tkazib yuborildi.")
    except RepositoryNotFoundError:
        before = api.list_repo_files(OLD_SPACE, repo_type="space")
        print(f"{OLD_SPACE} ichidagi fayllar ({len(before)} ta), tarixda saqlanadi:")
        for f in before:
            print(f"    {f}")
        api.move_repo(from_id=OLD_SPACE, to_id=SPACE, repo_type="space")
        print(f"\n{OLD_SPACE} → {SPACE}")

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "space"
        staged.mkdir()
        stage(staged)
        print("Yuklanmoqda …")
        # Sweep out whatever the previous app left behind; a stray Dockerfile
        # dependency or entrypoint would break the build in a confusing way.
        api.upload_folder(folder_path=str(staged), repo_id=SPACE,
                          repo_type="space",
                          delete_patterns=["*", "**/*"],
                          commit_message="Smart Road — ASTM D6433 PCI")

    api.restart_space(SPACE)
    print(f"\nTayyor: https://huggingface.co/spaces/{SPACE}")
    print("Birinchi build 10–15 daqiqa (torch katta). Build logini kuzating.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
