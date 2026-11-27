"""``python -m zengo``. Absolute import so PyInstaller can use this file as its entry point."""

from zengo.app import main

raise SystemExit(main())
