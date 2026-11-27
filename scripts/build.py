"""Build a single-file executable for the current OS with PyInstaller.

PyInstaller does not cross-compile: run this on Windows for ``zengo.exe`` and
on Linux for the ``zengo`` binary. Output goes to ``dist/``.

    python scripts/build.py
"""

from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    PyInstaller.__main__.run(
        [
            str(ROOT / "src" / "zengo" / "__main__.py"),
            "--name=zengo",
            "--onefile",
            "--windowed",  # no console window on Windows
            f"--icon={ROOT / 'packaging' / 'icons' / 'zengo.ico'}",  # (Windows only)
            "--noconfirm",
            "--clean",
            f"--paths={ROOT / 'src'}",
            f"--distpath={ROOT / 'dist'}",
            f"--workpath={ROOT / 'build'}",
            f"--specpath={ROOT / 'build'}",
        ]
    )


if __name__ == "__main__":
    main()
