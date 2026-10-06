"""`nexus init` y `nexus sections`: proponer y revisar las secciones de un proyecto.

La propuesta es determinista: parte de la configuración genérica, añade reglas
según el stack detectado y crea una sección por cada carpeta de primer nivel cuyo
código quedaría como "Lógica de aplicación" o "Sin clasificar". La skill
`nexus-setup` usa después `nexus sections` para que la IA la refine con
nombres del negocio.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath

from . import gitsource
from .sections import GENERIC_CONFIG, UNCLASSIFIED, SectionMatcher, load_config

FALLBACK = "Lógica de aplicación"
MIN_DIR_FILES = 3
MAX_EXAMPLES = 5
# Carpetas que nombran una capa técnica o un contenedor genérico, no un dominio del negocio.
LAYER_DIRS = {
    "templates", "static", "static_src", "public", "assets", "styles", "components", "pages", "docs", "doc",
    "scripts", "tools", "bin", "tests", "test", "__tests__", "config", "configs", "settings", "src", "lib",
    "app", "apps", "packages", "vendor", "examples", "migrations", "projectsettings", "media", "locale",
}

_STACK_SECTIONS = {
    "Unity": [
        {"nombre": "Escenas y prefabs", "descripcion": "Escenas y objetos prefabricados del juego.",
         "rutas": ["**/*.unity", "**/*.prefab"]},
        {"nombre": "Scripts de juego", "descripcion": "Comportamiento del juego (C#).",
         "rutas": ["Assets/**/*.cs"]},
        {"nombre": "Recursos gráficos y audio", "descripcion": "Texturas, materiales, modelos y sonidos.",
         "rutas": ["**/*.mat", "**/*.png", "**/*.jpg", "**/*.fbx", "**/*.anim", "**/*.controller",
                   "**/*.wav", "**/*.mp3", "**/*.shader", "**/*.asset"]},
    ],
    "Django": [
        {"nombre": "Permisos / Seguridad", "descripcion": "Autenticación, roles y controles de acceso.",
         "rutas": ["**/permissions*.py", "**/decorators*.py", "**/middleware*.py", "**/mixins*.py",
                   "**/auth*.py"]},
    ],
}


def detect_stack(root: Path, files: list[str]) -> list[str]:
    names = {PurePosixPath(f).name for f in files}
    stack = []
    if "manage.py" in names:
        stack.append("Django")
    if any(f.startswith("Assets/") for f in files) and any(f.startswith("ProjectSettings/") for f in files):
        stack.append("Unity")
    package = root / "package.json"
    if package.exists():
        try:
            deps = json.loads(package.read_text(encoding="utf-8"))
            deps = {**deps.get("dependencies", {}), **deps.get("devDependencies", {})}
        except (ValueError, OSError):
            deps = {}
        for dep, label in (("next", "Next.js"), ("react", "React"), ("vue", "Vue"), ("svelte", "Svelte"),
                           ("express", "Express"), ("tailwindcss", "Tailwind")):
            if dep in deps:
                stack.append(label)
        stack.append("Node.js")
    if names & {"pyproject.toml", "requirements.txt", "setup.py"} or any(f.endswith(".py") for f in files):
        stack.append("Python")
    if "Cargo.toml" in names:
        stack.append("Rust")
    if "go.mod" in names:
        stack.append("Go")
    if any(f.endswith(".csproj") for f in files) and "Unity" not in stack:
        stack.append(".NET")
    return list(dict.fromkeys(stack))


def classify(matcher: SectionMatcher, files: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Archivos por sección (en el orden de la configuración) y archivos excluidos."""
    groups: dict[str, list[str]] = {s["nombre"]: [] for s in matcher.sections}
    excluded = []
    for path in files:
        if matcher.excluded(path):
            excluded.append(path)
        else:
            groups.setdefault(matcher.section_for(path), []).append(path)
    return groups, excluded


def _title(folder: str) -> str:
    return folder.replace("_", " ").replace("-", " ").strip().capitalize()


def propose(root: Path) -> tuple[dict, list[str]]:
    """Configuración propuesta para el repo y stack detectado."""
    files = gitsource.tracked_and_untracked(root)
    stack = detect_stack(root, files)
    config = copy.deepcopy(load_config(GENERIC_CONFIG))
    sections = config["secciones"]

    extra = [s for label in stack for s in _STACK_SECTIONS.get(label, [])]
    # Las reglas del stack van antes de las genéricas por tipo de archivo: son más específicas.
    tests_at = next(i for i, s in enumerate(sections) if s["nombre"] == "Tests") + 1
    sections[tests_at:tests_at] = copy.deepcopy(extra)

    matcher = SectionMatcher(config)
    by_dir: dict[str, list[str]] = {}
    for path in files:
        if "/" in path and not matcher.excluded(path):
            by_dir.setdefault(path.split("/", 1)[0], []).append(path)
    domain = []
    for folder, paths in sorted(by_dir.items()):
        is_layer = folder.lower() in LAYER_DIRS or folder.startswith(".")
        is_module = f"{folder}/apps.py" in paths  # app de Django: ya se reparte bien por capas
        if len(paths) >= MIN_DIR_FILES and not is_layer and not is_module:
            domain.append({"nombre": _title(folder),
                           "descripcion": f"Todo lo de la carpeta «{folder}» (pendiente de describir).",
                           "rutas": [f"{folder}/**"]})
    # Un dominio agrupa todo lo suyo (código, datos, recursos): va antes de las capas genéricas.
    sections[tests_at + len(extra):tests_at + len(extra)] = domain

    config = {"proyecto": {"nombre": root.name, "stack": stack, "generado_por": "nexus init"}, **config}
    return config, files


def coverage(matcher: SectionMatcher, files: list[str]) -> dict:
    groups, excluded = classify(matcher, files)
    return {
        "total": len(files),
        "excluidos": len(excluded),
        "secciones": [
            {"nombre": name, "archivos": len(paths), "ejemplos": paths[:MAX_EXAMPLES]}
            for name, paths in groups.items() if paths
        ],
        "sin_clasificar": groups.get(UNCLASSIFIED, []),
        "logica_generica": groups.get(FALLBACK, []),
    }


def format_coverage(report: dict, origin: str, limit: int = 40) -> str:
    lines = [f"{report['total']} archivos · {report['excluidos']} excluidos · secciones de configuración {origin}"]
    for section in report["secciones"]:
        lines.append(f"  {section['archivos']:>5}  {section['nombre']}")
        for example in section["ejemplos"]:
            lines.append(f"           · {example}")
    loose = report["sin_clasificar"]
    if loose:
        lines.append(f"\nSin clasificar ({len(loose)}):")
        lines += [f"  {path}" for path in loose[:limit]]
        if len(loose) > limit:
            lines.append(f"  … y {len(loose) - limit} más")
    return "\n".join(lines)
