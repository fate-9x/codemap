import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _util import TempRepo

from nexus_diff import gitsource, install, projectinit
from nexus_diff.analyze import analyze, build_matcher
from nexus_diff.cli import main
from nexus_diff.sections import PROJECT_CONFIG


def run_cli(*args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(list(args))
    return code, out.getvalue()


class ProjectSetupTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo()
        self.repo.write("manage.py", "print('django')\n")
        for app in ("accounts", "reports"):
            self.repo.write(f"{app}/apps.py", "x = 1\n")
            self.repo.write(f"{app}/views.py", "def v():\n    return 1\n")
            self.repo.write(f"{app}/models.py", "class M:\n    pass\n")
        for name in ("modelo.py", "features.py", "datos.csv"):
            self.repo.write(f"ml/{name}", "x = 1\n")
        self.repo.write("templates/base.html", "<p>x</p>\n")
        self.repo.write("README.md", "# Proyecto\n")
        self.repo.commit()
        self.root = self.repo.root

    def tearDown(self):
        self.repo.cleanup()

    def sections_of(self, config: dict) -> list[str]:
        return [s["nombre"] for s in config["secciones"]]

    def test_generic_config_is_used_until_the_project_has_one(self):
        self.assertEqual(build_matcher(self.root)[1], "genérica")
        self.assertEqual(analyze(self.root).configuracion, "genérica")
        code, out = run_cli("scan", "--repo", str(self.root), "--no-color")
        self.assertEqual(code, 0)

    def test_init_proposes_domain_sections_but_not_for_django_apps(self):
        config, _ = projectinit.propose(self.root)
        names = self.sections_of(config)
        self.assertIn("Django", config["proyecto"]["stack"])
        self.assertIn("Ml", names)
        self.assertNotIn("Accounts", names)       # app de Django: se reparte por capas
        self.assertNotIn("Templates", names)      # carpeta de capa, no de dominio
        self.assertLess(names.index("Ml"), names.index("Datos"))  # el dominio gana a la capa
        matcher, _ = build_matcher(self.root, None)
        self.assertEqual(matcher.section_for("ml/datos.csv"), "Datos")  # antes de init

    def test_init_writes_project_config_and_refuses_to_overwrite(self):
        code, out = run_cli("init", "--repo", str(self.root))
        self.assertEqual(code, 0, out)
        self.assertTrue((self.root / PROJECT_CONFIG).exists())
        self.assertEqual(build_matcher(self.root)[1], "proyecto")
        matcher, _ = build_matcher(self.root)
        self.assertEqual(matcher.section_for("ml/datos.csv"), "Ml")
        self.assertEqual(analyze(self.root).configuracion, "proyecto")
        code, _ = run_cli("init", "--repo", str(self.root))
        self.assertEqual(code, 1)
        code, _ = run_cli("init", "--repo", str(self.root), "--force")
        self.assertEqual(code, 0)

    def test_init_print_does_not_write(self):
        code, out = run_cli("init", "--repo", str(self.root), "--print")
        self.assertEqual(code, 0)
        self.assertIn("secciones", json.loads(out))
        self.assertFalse((self.root / PROJECT_CONFIG).exists())

    def test_sections_report(self):
        self.repo.write("raro.xyz", "?\n")
        code, out = run_cli("sections", "--repo", str(self.root), "--json")
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertEqual(report["configuracion"], "genérica")
        self.assertIn("raro.xyz", report["sin_clasificar"])
        self.assertEqual(report["total"], sum(s["archivos"] for s in report["secciones"]) + report["excluidos"])

    def test_annotations_and_report_live_inside_git_dir(self):
        self.repo.write("ml/modelo.py", "x = 2\n")
        store = gitsource.nexus_diff_dir(self.root)
        self.assertEqual(store, (self.root / ".git" / "nexus-diff").resolve())
        code, out = run_cli("link", "--repo", str(self.root), "--tarea", "t",
                            "--cambio", "ml/modelo.py::*", "cambia x")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(list((store / "anotaciones").glob("*.json"))), 1)
        code, _ = run_cli("report", "--repo", str(self.root))
        self.assertEqual(code, 0)
        self.assertTrue((store / "report.html").exists())
        self.assertEqual(self.repo.git("status", "--porcelain").strip(), "M ml/modelo.py")


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="nexus-diff-install-"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_skills_are_templated_with_the_command(self):
        done, skipped = install.install_skills(self.work, command="nexus")
        self.assertEqual({p.name for p in done}, {"nexus-link", "nexus-setup"})
        self.assertEqual(skipped, [])
        for path in done:
            text = (path / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("{{", text)
            self.assertTrue(text.startswith(f"---\nname: {path.name}\n"))
            self.assertIn("nexus scan" if path.name == "nexus-link" else "nexus init", text)
        _, skipped = install.install_skills(self.work, command="nexus")
        self.assertEqual(len(skipped), 2)  # no sobrescribe sin force

    def test_command_falls_back_to_python_launcher(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertTrue(install.nexus_command().startswith('python "'))
        with mock.patch("shutil.which", return_value="C:/x/nexus.exe"):
            self.assertEqual(install.nexus_command(), "nexus")

    def test_opencode_plugin_and_commands(self):
        plugin = install.install_opencode_plugin(self.work / "plugins" / "nexus-diff.js")
        self.assertNotIn("{{", plugin.read_text(encoding="utf-8"))
        self.assertIsNone(install.install_opencode_plugin(plugin))  # ya existe
        commands = install.install_opencode_commands(self.work / "commands")
        self.assertEqual([p.name for p in commands], ["nexus-setup.md"])
        self.assertIn("nexus-setup", commands[0].read_text(encoding="utf-8"))

    def test_install_skill_cli(self):
        code, out = run_cli("install-skill", "--dest", str(self.work))
        self.assertEqual(code, 0, out)
        code, _ = run_cli("install-skill", "--dest", str(self.work))
        self.assertEqual(code, 1)
        code, _ = run_cli("install-skill", "--dest", str(self.work), "--force")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
