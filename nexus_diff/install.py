"""Instalación: comando `nexus` en el PATH, skills y plugin/comando de opencode."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .analyze import TOOL_DIR

SKILLS_SOURCE = TOOL_DIR / "skills"
OPENCODE_SOURCE = TOOL_DIR / "opencode"
LAUNCHER = TOOL_DIR / "nexus.py"
CLAUDE_SKILLS = Path.home() / ".claude" / "skills"  # opencode también las lee de aquí
OPENCODE_CONFIG = Path.home() / ".config" / "opencode"


def nexus_command() -> str:
    """Cómo invocar Nexus-diff desde una skill: `nexus` si está en el PATH."""
    if shutil.which("nexus"):
        return "nexus"
    return f'python "{LAUNCHER.resolve().as_posix()}"'


def _write(dest: Path, text: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")


def install_cli() -> tuple[bool, str]:
    """`pip install -e` de esta carpeta: crea el ejecutable `nexus` en el PATH de Python."""
    proc = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--editable", str(TOOL_DIR)],
                          capture_output=True, text=True)
    detail = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, detail


def skill_names() -> list[str]:
    return sorted(p.parent.name for p in SKILLS_SOURCE.glob("*/SKILL.md"))


def install_skills(dest_root: Path | None = None, force: bool = False,
                   command: str | None = None) -> tuple[list[Path], list[Path]]:
    """Copia cada skill; devuelve (instaladas, omitidas porque ya existían)."""
    dest_root = dest_root or CLAUDE_SKILLS
    command = command or nexus_command()
    done, skipped = [], []
    for name in skill_names():
        dest = dest_root / name
        if dest.exists() and not force:
            skipped.append(dest)
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SKILLS_SOURCE / name, dest)
        skill_file = dest / "SKILL.md"
        _write(skill_file, skill_file.read_text(encoding="utf-8").replace("{{NEXUS}}", command))
        done.append(dest)
    return done, skipped


def install_opencode_plugin(dest: Path | None = None, force: bool = False) -> Path | None:
    dest = dest or OPENCODE_CONFIG / "plugins" / "nexus-diff.js"
    if dest.exists() and not force:
        return None
    # El plugin corre dentro de opencode: rutas absolutas a este Python y a este nexus.py.
    text = (OPENCODE_SOURCE / "nexus-diff.js").read_text(encoding="utf-8")
    text = text.replace("{{NEXUS}}", LAUNCHER.resolve().as_posix())
    text = text.replace("{{PYTHON}}", Path(sys.executable).resolve().as_posix())
    _write(dest, text)
    return dest


def install_opencode_commands(dest_dir: Path | None = None, force: bool = False) -> list[Path]:
    """Comandos `/nexus-…` de opencode (las skills ya las encuentra solo)."""
    dest_dir = dest_dir or OPENCODE_CONFIG / "commands"
    done = []
    for source in sorted((OPENCODE_SOURCE / "commands").glob("*.md")):
        dest = dest_dir / source.name
        if dest.exists() and not force:
            continue
        _write(dest, source.read_text(encoding="utf-8"))
        done.append(dest)
    return done
