"""Interfaz de línea de comandos: scan, report, serve, link, init, sections e install."""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

from . import annotations, gitsource, install, projectinit
from .analyze import analyze, build_matcher
from .gitsource import GitError
from .render import write_report
from .sections import PROJECT_CONFIG

_TYPE_LABEL = {"añadido": "nuevo", "modificado": "modificado", "eliminado": "eliminado", "movido": "movido"}
_RISK_MARK = {0: " ", 1: "·", 2: "!", 3: "‼"}
_NOTE_MARK = {"no_declarado": "[no declarado por la IA]", "desactualizado": "[anotación desactualizada]"}
_COMPACT_DROP = ("diff", "detalles", "resumen_tecnico", "resumen_origen", "lineas")


class _Style:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        if enabled and sys.platform == "win32":
            os.system("")  # activa las secuencias ANSI en la consola de Windows

    def __call__(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text


def format_terminal(data: dict, color: bool) -> str:
    st = _Style(color)
    t = data["totales"]
    base = data["base"] + (f" ({data['base_commit']})" if data["base_commit"] else "")
    out = [
        st(f"Nexus-diff · {data['repo']} · base {base} · {data['modo']}", "1"),
        f"{t['cambios']} {'cambio' if t['cambios'] == 1 else 'cambios'} en "
        f"{t['archivos']} {'archivo' if t['archivos'] == 1 else 'archivos'} "
        f"(+{t['añadidas']} / −{t['eliminadas']} líneas)"
        + (st(f" · {t['riesgo_alto']} de riesgo alto", "31") if t["riesgo_alto"] else ""),
    ]
    if data.get("tarea"):
        out.append(st(f"Tarea declarada por la IA: {data['tarea']}", "36"))
    if t.get("no_declarados"):
        out.append(st(f"⚠ {t['no_declarados']} cambios no declarados por la IA", "33"))
    for claim in data.get("declaraciones_sin_respaldo", []):
        out.append(st(f"⚠ La IA anotó {claim['id']}, pero no hay ningún cambio ahí: {claim['resumen']}", "33"))
    if data.get("configuracion") == "genérica":
        out.append(st(f"Secciones genéricas: ejecuta `nexus init` (o /nexus-setup) para adaptarlas a este proyecto.", "2"))
    if not data["cambios"]:
        out.append("\nNo hay cambios pendientes respecto a la base.")
        return "\n".join(out)

    by_section: dict[str, list[dict]] = {}
    for change in data["cambios"]:
        by_section.setdefault(change["seccion"], []).append(change)
    for section in data["secciones"]:
        changes = by_section.get(section["nombre"])
        if not changes:
            continue
        out.append("")
        out.append(st(f"■ {section['nombre']} ({len(changes)})", "1;36"))
        for c in changes:
            risk_color = {3: "31", 2: "33"}.get(c["riesgo"], "0")
            label = f"[{_TYPE_LABEL.get(c['tipo_cambio'], c['tipo_cambio'])}]"
            text = c.get("resumen_ia") or c["resumen"]
            note = _NOTE_MARK.get(c.get("estado_anotacion"))
            if note:
                text += " " + st(note, "33")
            out.append(f"  {st(_RISK_MARK.get(c['riesgo'], ' '), risk_color)} {label:<12} {text}")
            where = c["archivo"]
            if c["evidencia"]:
                ev = c["evidencia"][0]
                where = f"{ev['archivo']}:{ev['linea_inicio']}" + (" (versión base)" if ev["lado"] == "viejo" else "")
            meta = f"→ {where}"
            if c["etiquetas"]:
                meta += "  " + " ".join(f"#{tag.replace(' ', '-')}" for tag in c["etiquetas"])
            out.append(st(f"      {meta}", "2"))
            if c.get("resumen_ia"):
                out.append(st(f"      regla: {c['resumen']}", "2"))
    return "\n".join(out)


def _config(args) -> Path | None:
    return Path(args.config) if args.config else None


def _store_dir(args) -> Path:
    """Anotaciones: --store, NEXUS_DIFF_STORE o, por defecto, `.git/nexus-diff/anotaciones` del repo."""
    store = getattr(args, "store", None) or os.environ.get("NEXUS_DIFF_STORE")
    if store:
        return Path(store)
    return gitsource.nexus_diff_dir(gitsource.repo_root(args.repo)) / "anotaciones"


def _build(args) -> dict:
    changeset = analyze(args.repo, args.base, args.staged, _config(args))
    store = annotations.load(changeset.base_commit, _store_dir(args))
    return annotations.apply(changeset, store).to_dict()


def compact(data: dict) -> dict:
    """Versión reducida para que la lea un agente: sin diff ni detalles internos."""
    out = {k: v for k, v in data.items() if k != "cambios"}
    out["cambios"] = []
    for change in data["cambios"]:
        item = {k: v for k, v in change.items() if k not in _COMPACT_DROP}
        item["evidencia"] = change["evidencia"][:3]
        out["cambios"].append(item)
    return out


def _cmd_scan(args) -> int:
    data = _build(args)
    if args.compact:
        data = compact(data)
    if args.json == "-":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if args.json:
        Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and not args.no_color
    print(format_terminal(data, color))
    return 0


def _cmd_report(args) -> int:
    output = Path(args.output) if args.output else (
        gitsource.nexus_diff_dir(gitsource.repo_root(args.repo)) / "report.html")
    path = write_report(_build(args), output)
    print(f"Reporte generado: {path}")
    if args.open:
        webbrowser.open(path.resolve().as_uri())
    return 0


def _cmd_serve(args) -> int:
    from .server import serve

    _build(args)  # falla pronto si la base o el repo no son válidos
    serve(lambda: _build(args), port=args.port, open_browser=args.open)
    return 0


def _cmd_link(args) -> int:
    changeset = analyze(args.repo, args.base, args.staged, _config(args))
    if args.clear:
        removed = annotations.clear(changeset.base_commit, _store_dir(args))
        print("Anotaciones borradas." if removed else "No había anotaciones para esta base.")
        return 0
    inline = args.tarea or args.autor or args.cambio
    if args.file and inline:
        print("Usa un archivo JSON o las opciones --tarea/--cambio, no ambos.", file=sys.stderr)
        return 2
    if args.file:
        raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    elif inline:
        # Sin archivo temporal: todo en un único comando, fácil de autorizar en el agente.
        raw = json.dumps({"tarea": args.tarea, "autor": args.autor,
                          "cambios": dict(args.cambio or [])}, ensure_ascii=False)
    else:
        print("Indica las anotaciones con --tarea y --cambio ID TEXTO, o un archivo JSON ('-' = entrada estándar).",
              file=sys.stderr)
        return 2
    try:
        incoming = annotations.parse_input(raw)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    store = annotations.load(changeset.base_commit, _store_dir(args))
    annotations.record(changeset, store, incoming)
    path = annotations.save(changeset.base_commit, store, _store_dir(args))
    annotations.apply(changeset, store)

    by_state: dict[str | None, list] = {}
    for change in changeset.cambios:
        by_state.setdefault(change.estado_anotacion, []).append(change)
    unknown = changeset.declaraciones_sin_respaldo
    missing = by_state.get(annotations.UNDECLARED, [])
    stale = by_state.get(annotations.STALE, [])

    print(f"Anotaciones guardadas en {path}")
    print(f"✓ {len(by_state.get(annotations.ANNOTATED, []))} de {len(changeset.cambios)} cambios anotados")
    if not store["tarea"]:
        print("⚠ Falta 'tarea': resume en 1-2 frases qué se pidió y qué se hizo.")
    if unknown:
        print(f"✗ {len(unknown)} ids no corresponden a ningún cambio actual (quedan como declaraciones sin respaldo):")
        for claim in unknown:
            print(f"    {claim['id']}")
    if missing:
        print(f"⚠ {len(missing)} cambios sin anotar:")
        for change in missing:
            print(f"    {change.id} — {change.resumen}")
    if stale:
        print(f"⚠ {len(stale)} anotaciones desactualizadas (el código cambió después de anotarlo):")
        for change in stale:
            print(f"    {change.id}")
    return 1 if unknown or missing or stale or not store["tarea"] else 0


def _cmd_init(args) -> int:
    root = gitsource.repo_root(args.repo)
    target = root / PROJECT_CONFIG
    config, files = projectinit.propose(root)
    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    if args.print:
        print(text, end="")
        return 0
    if target.exists() and not args.force:
        print(f"Ya existe {target}. Revísalo con `nexus sections` o usa --force para regenerarlo.",
              file=sys.stderr)
        return 1
    target.write_text(text, encoding="utf-8", newline="\n")
    stack = ", ".join(config["proyecto"]["stack"]) or "no detectado"
    print(f"Creado {target} (stack: {stack}).")
    matcher, origin = build_matcher(root)
    print(projectinit.format_coverage(projectinit.coverage(matcher, files), origin))
    print("\nRevisa nombres y descripciones (o usa /nexus-setup para que la IA las adapte al negocio).")
    return 0


def _cmd_sections(args) -> int:
    root = gitsource.repo_root(args.repo)
    matcher, origin = build_matcher(root, _config(args))
    report = projectinit.coverage(matcher, gitsource.tracked_and_untracked(root))
    if args.json:
        print(json.dumps({"configuracion": origin, **report}, ensure_ascii=False, indent=2))
    else:
        print(projectinit.format_coverage(report, origin))
    return 0


def _report_skills(done: list[Path], skipped: list[Path]) -> None:
    for path in done:
        print(f"  skill      {path}")
    for path in skipped:
        print(f"  (ya existe, usa --force) {path}")


def _cmd_install(args) -> int:
    ok = True
    if not args.no_path and install.is_source_checkout():
        print("Instalando el comando `nexus` (pip install -e)…")
        installed, detail = install.install_cli()
        ok &= installed
        print("  comando    nexus" if installed else f"  ✗ pip falló:\n{detail}")
    elif not args.no_path:
        print("El comando `nexus` ya está instalado con pip.")
    print(f"Las skills invocarán: {install.nexus_command()}")
    _report_skills(*install.install_skills(force=True))
    if args.no_opencode:
        return 0 if ok else 1
    if install.OPENCODE_CONFIG.exists():
        print(f"  plugin     {install.install_opencode_plugin(force=True)}")
        for path in install.install_opencode_commands(force=True):
            print(f"  comando    {path}")
        print("Reinicia opencode para cargar el plugin.")
    else:
        print("opencode no está configurado en este equipo: se omite su plugin.")
    return 0 if ok else 1


def _cmd_install_skill(args) -> int:
    done, skipped = install.install_skills(Path(args.dest).expanduser() if args.dest else None, args.force)
    _report_skills(done, skipped)
    return 1 if skipped else 0


def _cmd_install_opencode_plugin(args) -> int:
    dest = install.install_opencode_plugin(Path(args.dest).expanduser() if args.dest else None, args.force)
    if dest is None:
        print("El plugin ya existe. Usa --force para reemplazarlo.", file=sys.stderr)
        return 1
    print(f"Plugin de opencode instalado en {dest}. Reinicia opencode para cargarlo.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexus",
        description="Resume por secciones y en lenguaje natural lo que cambió en un repositorio git.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=".", help="carpeta del repositorio (por defecto, la actual)")
    common.add_argument("--base", default="HEAD", help="commit o rama contra la que comparar (por defecto HEAD)")
    common.add_argument("--staged", action="store_true", help="analizar solo lo que está en el índice (git add)")
    common.add_argument("--config", help=f"secciones y exclusiones (por defecto {PROJECT_CONFIG} del repo o la genérica)")
    common.add_argument("--store", help="carpeta de anotaciones (por defecto .git/nexus-diff/anotaciones del repo)")

    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", parents=[common], help="mostrar los cambios en la terminal")
    scan.add_argument("--json", metavar="RUTA", help="guardar también el resultado en JSON ('-' = imprimirlo)")
    scan.add_argument("--no-color", action="store_true", help="desactivar colores")
    scan.add_argument("--compact", action="store_true", help="JSON reducido (sin diff), pensado para un agente")
    scan.set_defaults(func=_cmd_scan)

    report = sub.add_parser("report", parents=[common], help="generar la página HTML")
    report.add_argument("--output", help="ruta del HTML (por defecto .git/nexus-diff/report.html)")
    report.add_argument("--open", action="store_true", help="abrir el reporte en el navegador")
    report.set_defaults(func=_cmd_report)

    srv = sub.add_parser("serve", parents=[common], help="servir la página en localhost (se actualiza al recargar)")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--open", action="store_true", help="abrir el navegador")
    srv.set_defaults(func=_cmd_serve)

    ann = sub.add_parser("link", parents=[common],
                         help="registrar lo que la IA dice que hizo en cada cambio")
    ann.add_argument("file", nargs="?", help="JSON {tarea, autor, cambios: {id: resumen}} o '-' (entrada estándar)")
    ann.add_argument("--tarea", help="qué se pidió y qué se hizo (1-2 frases)")
    ann.add_argument("--autor", help="quién anota, p. ej. claude-code u opencode")
    ann.add_argument("--cambio", nargs=2, action="append", metavar=("ID", "RESUMEN"),
                     help="anotación de un cambio; repetir por cada id")
    ann.add_argument("--clear", action="store_true", help="borrar las anotaciones de esta base")
    ann.set_defaults(func=_cmd_link)

    repo_only = argparse.ArgumentParser(add_help=False)
    repo_only.add_argument("--repo", default=".", help="carpeta del repositorio (por defecto, la actual)")

    init = sub.add_parser("init", parents=[repo_only],
                          help=f"proponer {PROJECT_CONFIG} para este proyecto (secciones)")
    init.add_argument("--force", action="store_true", help="reemplazar la configuración existente")
    init.add_argument("--print", action="store_true", help="mostrar la propuesta sin escribirla")
    init.set_defaults(func=_cmd_init)

    sec = sub.add_parser("sections", parents=[repo_only], help="ver cómo se clasifican los archivos del repo")
    sec.add_argument("--config", help="probar otra configuración")
    sec.add_argument("--json", action="store_true", help="salida en JSON (para agentes)")
    sec.set_defaults(func=_cmd_sections)

    ins = sub.add_parser("install", help="instalar el comando, las skills y el plugin de opencode")
    ins.add_argument("--no-path", action="store_true", help="no instalar el comando `nexus` con pip")
    ins.add_argument("--no-opencode", action="store_true", help="no instalar el plugin ni los comandos de opencode")
    ins.set_defaults(func=_cmd_install)

    inst = sub.add_parser("install-skill", help="copiar solo las skills (por defecto a ~/.claude/skills)")
    inst.add_argument("--dest", help="carpeta que contendrá las skills")
    inst.add_argument("--force", action="store_true", help="reemplazar si ya existen")
    inst.set_defaults(func=_cmd_install_skill)

    plug = sub.add_parser("install-opencode-plugin", help="copiar solo el plugin de opencode")
    plug.add_argument("--dest", help="ruta del archivo .js destino")
    plug.add_argument("--force", action="store_true", help="reemplazar si ya existe")
    plug.set_defaults(func=_cmd_install_opencode_plugin)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except GitError as exc:
        print(f"Error de git: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
