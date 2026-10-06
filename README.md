# Codemap

Revisar lo que cambió en un repositorio (por ejemplo, lo que hizo una IA) **sin leer el diff línea por línea**:
un listado agrupado por sección, con un resumen de una línea por cambio, etiquetas de riesgo y el código como
evidencia a un clic.

Solo usa la biblioteca estándar de Python (3.10+) y git. Los resúmenes automáticos salen de plantillas
deterministas; los escritos por la IA llegan con las [anotaciones](#anotaciones-de-la-ia).

## Instalación

### Requisitos

- **git** y **Python 3.10 o superior**.
- Opcional: **Claude Code** y/o **opencode**, para que la IA anote sus cambios y configure las secciones.
- Opcional: **Node.js**, solo para ejecutar los tests del plugin de opencode.

### Pasos

1. Clona el repositorio en una carpeta donde vaya a quedarse (la instalación queda enlazada a esa carpeta):

   ```bash
   git clone https://github.com/USUARIO/codemap.git
   ```
   ```bash
   cd codemap
   ```

2. Instala Codemap (en Mac o Linux usa `python3` en lugar de `python`):

   ```bash
   python codemap.py install
   ```

   Ese comando hace cuatro cosas:

   - **Instala el comando `codemap`** con `pip install -e`. Queda enlazado a la carpeta clonada, así que los cambios en el código se aplican sin reinstalar.
   - **Copia las skills** `codemap-annotate` y `codemap-setup` a `~/.claude/skills/`. Las usan Claude Code y opencode.
   - **Copia el plugin de opencode** a `~/.config/opencode/plugins/codemap.js`, si opencode está instalado.
   - **Copia el comando `/codemap-setup` de opencode** a `~/.config/opencode/commands/`.

   Las opciones `--no-path` y `--no-opencode` omiten la instalación del comando y la parte de opencode,
   respectivamente.

3. Comprueba que funciona:

   ```bash
   codemap --help
   ```

4. Si usas opencode, reinícialo para que cargue el plugin y el comando `/codemap-setup`.

### Actualizar

```bash
git pull
```

Los cambios en el código se aplican solos. Si cambiaron las skills o el plugin (que son copias), vuelve a
instalarlos:

```bash
codemap install
```

### Problemas frecuentes

- **El sistema no reconoce `codemap`.** La carpeta de ejecutables de Python (`Scripts` en Windows, `bin` en Mac/Linux) no está en el PATH. Añádela al PATH; mientras tanto, `python codemap.py <comando>` funciona igual desde la carpeta clonada.
- **pip responde `externally-managed-environment`.** Ocurre en algunas distribuciones de Linux y con el Python de Homebrew, que protegen el Python del sistema. Instala el comando con [pipx](https://pipx.pypa.io) y el resto con Codemap:

  ```bash
  pipx install -e .
  ```
  ```bash
  python3 codemap.py install --no-path
  ```

- **Moviste la carpeta después de instalar.** El comando, las skills y el plugin apuntan a la ruta anterior. Ejecuta de nuevo `python codemap.py install` desde la nueva ubicación.
- **opencode pide permiso cada vez que la IA ejecuta `codemap`.** Elige "always" la primera vez, o añade la regla `"codemap *": allow` a los permisos de `bash` de tu agente.

### Desinstalar

```bash
pip uninstall codemap
```

Después borra las carpetas `~/.claude/skills/codemap-annotate` y `~/.claude/skills/codemap-setup`, y los archivos
`~/.config/opencode/plugins/codemap.js` y `~/.config/opencode/commands/codemap-setup.md`. Los datos de cada
proyecto están en su `codemap.config.json` y en su carpeta `.git/codemap/`.

## Uso en un proyecto

1. **Configura las secciones una vez por proyecto:** escribe `/codemap-setup` en Claude Code u opencode. La IA ejecuta `codemap init`, revisa la clasificación con `codemap sections` y deja `codemap.config.json` en la raíz del repo con nombres del negocio. Ese archivo se puede commitear. Sin él, Codemap usa secciones genéricas y lo indica.
2. **Trabaja con la IA como siempre.** Al terminar, anota sus cambios (skill + plugin).
3. **Revisa:**

```bash
codemap scan
```

```bash
codemap serve --open
```

| Comando | Qué hace |
|---|---|
| `scan` | Muestra el listado de cambios en la terminal. `--json RUTA` guarda el resultado (`--json -` lo imprime; `--compact` lo reduce para agentes). |
| `report [--open]` | Genera `.git/codemap/report.html`, una página que funciona sin conexión. |
| `serve [--port 8765] [--open]` | Sirve la página en `http://127.0.0.1:8765/`; cada recarga vuelve a analizar el repositorio. `/api/cambios` devuelve el JSON. |
| `annotate --tarea T --cambio ID RESUMEN …` | Registra lo que la IA dice que hizo en cada cambio (ver [Anotaciones de la IA](#anotaciones-de-la-ia)). También acepta un JSON (`annotate ARCHIVO` o `-`). `--clear` borra las anotaciones. |
| `init [--print] [--force]` | Propone `codemap.config.json`: detecta el stack y crea una sección por cada carpeta de dominio. |
| `sections [--json]` | Muestra cómo quedan clasificados todos los archivos del repo y cuáles no encajan en ninguna sección. |
| `install [--no-path] [--no-opencode]` | Instala o actualiza el comando, las skills y el plugin. También existen `install-skill [--dest] [--force]` e `install-opencode-plugin [--dest] [--force]` por separado. |

Opciones comunes:

- `--base REF`: compara contra un commit o una rama (por defecto, `HEAD`). Por ejemplo, `--base HEAD~3` muestra todo lo que cambió en los últimos tres commits más lo que todavía no se commiteó.
- `--staged`: analiza solo lo que está en el índice (`git add`).
- `--repo RUTA`: analiza otro repositorio.
- `--config RUTA`: usa otras reglas de secciones.

Por defecto se comparan el árbol de trabajo y los archivos sin seguimiento contra la base.

**Qué guarda Codemap en cada repositorio:** `codemap.config.json` en la raíz (lo editas tú o la IA, y se
puede versionar). Las anotaciones y el reporte quedan en `.git/codemap/`: git no versiona esa carpeta, no se
ve en el árbol de trabajo y la comparten todas las copias de trabajo (worktrees) del mismo repo.

## Qué muestra

Cada cambio tiene este formato (ver `codemap_core/model.py`):

```json
{
  "id": "app/views.py::calcular",
  "seccion": "Backend / Vistas",
  "archivo": "app/views.py",
  "simbolo": "calcular",
  "tipo_simbolo": "función",
  "tipo_cambio": "modificado",
  "resumen": "Se modificó la función `calcular()` (+2 / −1 líneas): cambian sus parámetros; ahora también hace llamadas de red.",
  "resumen_tecnico": "[MODIFICADO] función calcular · app/views.py:9-12 · +2/−1 · firma: `def calcular(a, b)` → `def calcular(a, b, c=0)` · etiquetas: red",
  "resumen_origen": "regla",
  "etiquetas": ["red"],
  "riesgo": 2,
  "lineas": {"añadidas": 2, "eliminadas": 1},
  "evidencia": [{"archivo": "app/views.py", "linea_inicio": 10, "linea_fin": 11, "lado": "nuevo"}]
}
```

- **Unidad de revisión.** En Python y JavaScript, cada cambio corresponde a una función, un método o una clase. En plantillas HTML y Markdown hay un cambio por archivo, con la lista de bloques o apartados afectados. En el resto de los archivos, un cambio por archivo.
- **Tipos de cambio:** nuevo, modificado, eliminado y movido. Detecta funciones renombradas (cuerpo parecido con otro nombre) y archivos movidos, incluso a carpetas que todavía no están en git.
- **Etiquetas** (`codemap_core/tags.py`): red, escribe en disco, borrado, base de datos, ejecuta procesos, secretos, permisos, **quita permisos** (también se buscan en las líneas eliminadas), desactiva CSRF, dependencias y error de sintaxis. El código que solo se movió o se reindentó no genera etiquetas.
- **Riesgo:** 3 = alto (borrado, secretos, quitar controles de acceso), 2 = medio y 1 = bajo. Dentro de cada sección, los cambios se ordenan de mayor a menor riesgo.

## Anotaciones de la IA

El agente que hizo los cambios es quien mejor sabe *por qué* los hizo. La skill
[`skills/codemap-annotate`](skills/codemap-annotate/SKILL.md), que se instala con `codemap install`, le indica
que, al terminar cada tarea, escriba un resumen en lenguaje natural de cada cambio que detectó Codemap.

Qué hace el agente:

1. Ejecuta `scan --json - --compact`, que lista los cambios con su `id` (`archivo::símbolo`).
2. Ejecuta un único comando: `codemap annotate --autor opencode --tarea '…' --cambio <id> '<resumen>' …`. No crea archivos temporales, así que en el agente basta con autorizar una vez `codemap *`.
3. Si `annotate` devuelve 1, el informe explica qué falta (cambios sin anotar, ids inventados o la tarea) y el agente lo completa.

**El diff sigue siendo la fuente de verdad.** La anotación es lo que la IA *dice* que hizo, y Codemap la contrasta:

| Estado | Significado |
|---|---|
| anotado | La IA describió el cambio y el código no cambió desde entonces. |
| **no declarado** | El cambio está en el código pero la IA no lo mencionó. Aparece primero en la página. |
| desactualizado | El código cambió después de anotarlo (la huella `huella` ya no coincide). |
| declaración sin respaldo | La IA anotó un `id` que no corresponde a ningún cambio. |

En la página, el texto de la IA lleva la marca «según la IA», y debajo queda siempre el resumen que Codemap calcula
del diff. Las etiquetas de riesgo son deterministas: la IA no puede quitarlas.

Las anotaciones se guardan en `.git/codemap/anotaciones/<commit base>.json` del propio repo y se fusionan entre
llamadas. Como cada archivo corresponde a un commit base, después de commitear se pueden seguir viendo con
`--base <ese commit>`.

Para otros agentes (por ejemplo, Cursor) sirven las mismas instrucciones de `SKILL.md`: solo hacen falta los comandos `scan` y `annotate`.

### opencode: activación automática

opencode encuentra las skills en `~/.claude/skills/` sin hacer nada más. Por sí sola, la skill depende de que el
modelo se acuerde de usarla al terminar. El plugin [`opencode/codemap.js`](opencode/codemap.js), que instala
`codemap install`, lo exige. Queda en `~/.config/opencode/plugins/codemap.js`, con rutas absolutas a este Python
y a este `codemap.py`, y hay que reiniciar opencode para que lo cargue. Funciona así:

1. Con el primer mensaje de una sesión guarda una foto de los cambios que ya existían. No reclama nada de lo que estaba antes.
2. Cada vez que la sesión principal termina de responder (`session.idle`), ejecuta `scan`. Si la sesión dejó cambios sin anotar o con la anotación desactualizada, le envía al agente un mensaje `[Codemap]` con la lista y le pide usar `codemap-annotate`. Esto incluye los cambios hechos con `bash` o por subagentes.
3. Los subagentes no reciben avisos. Hay como máximo 2 avisos por sesión y nunca dos por el mismo conjunto de cambios, para evitar bucles.

`CODEMAP_OPENCODE_DISABLE=1` lo desactiva. `CODEMAP_OPENCODE_LOG=<ruta>` registra en un archivo lo que hace
(útil para diagnosticar), y `CODEMAP_STORE` cambia la carpeta de anotaciones (lo usan los tests).

Notas de la prueba real con opencode 1.18:

- La primera vez, opencode pide permiso para ejecutar `codemap ...`. Elige **"always"** para no tener que confirmar cada anotación. Si tu agente restringe `bash` (como `orchestrator`), añade la regla `"codemap *": allow`.
- `opencode run` (modo no interactivo) termina antes de que el plugin reciba `session.idle`, así que el aviso solo funciona en la TUI o con `opencode serve`.

## Secciones

Se definen en `codemap.config.json`, en la raíz de cada repo. Si no existe, se usa la configuración genérica
[`codemap_core/defaults/generic.json`](codemap_core/defaults/generic.json). Para cada archivo se aplica la primera
sección cuyas reglas coinciden; los archivos que no coinciden con ninguna quedan en "Sin clasificar". Cada
sección tiene `nombre`, `descripcion` y estas reglas:

- `rutas`: globs; `**/` equivale a cualquier número de carpetas.
- `contenido`: expresiones regulares que se buscan en el contenido del archivo.

**Setup.** `codemap init` hace la parte determinista:

1. Parte de la configuración genérica.
2. Añade reglas según el stack que detecta (Django, Unity, Node…).
3. Crea una sección por cada carpeta de dominio, es decir, cada carpeta de primer nivel que no sea una capa técnica (`templates`, `static`, `docs`…) ni una app de Django.

La skill [`codemap-setup`](skills/codemap-setup/SKILL.md), que se lanza con `/codemap-setup`, hace que la IA
renombre esas secciones con conceptos del negocio y añada descripciones. Después comprueba con `codemap sections`
que no queden archivos sin clasificar. Un ejemplo completo hecho a mano está en
[`examples/neuroflex.config.json`](examples/neuroflex.config.json).

## Decisiones de diseño

1. **El parser da la verdad; el texto se deriva de él.** Cada resumen se construye solo con campos del modelo (símbolo, conteos, firma, decoradores, etiquetas). Ningún resumen menciona algo que no esté en el diff. Cuando llegue el LLM, solo reformulará esos datos (`resumen_origen` dirá `"llm"`).
2. **Siempre se puede ver el código.** Un resumen convincente pero falso es peor que no tener resumen, así que cada cambio enlaza a sus líneas.
3. **Se detectan los controles de acceso eliminados.** Quitar un `@login_required` es tan importante como añadir una llamada de red.
4. **Los identificadores son estables** (`archivo::símbolo`). Así, en la fase 6 se podrá comparar lo que la IA dice que hizo con lo que realmente cambió.
5. **Sin dependencias.** `ast` cubre Python con exactitud; HTML, JS y Markdown usan heurísticas. Para más lenguajes, tree-sitter se puede añadir en `symbols.py` sin tocar el resto.

## Estructura

```
codemap.py                # punto de entrada sin instalar (python codemap.py …)
pyproject.toml            # paquete: crea el comando `codemap` con pip install -e
codemap_core/
  cli.py                  # comandos
  projectinit.py          # init y sections: proponer y revisar secciones
  install.py              # instalación del comando, skills y plugin
  defaults/generic.json   # secciones genéricas
  gitsource.py            # llamadas a git (diff, archivos sin seguimiento, git show)
  diffparse.py            # parser de unified diff
  symbols.py              # funciones/clases (ast), bloques Django, funciones JS, apartados Markdown
  sections.py             # reglas de secciones
  tags.py                 # etiquetas de efectos secundarios
  moves.py                # archivos movidos (borrado + nuevo parecidos)
  analyze.py              # orquestador -> ChangeSet
  summarize.py            # plantillas de resumen simple / técnico
  model.py                # contrato de datos
  annotations.py          # anotaciones de la IA: guardar, fusionar, contrastar con el diff
  render.py, server.py, templates/report.html   # página local
skills/                   # skills codemap-annotate y codemap-setup (fuente; las instala `install`)
opencode/                 # plugin y comandos de opencode (fuente; los instala `install`)
examples/                 # configuraciones de ejemplo
tests/                    # unittest con repositorios git temporales
```

## Tests

```bash
python -m unittest discover -s tests
```

Los tests del plugin de opencode necesitan Node.js; sin él, se omiten.

## Hoja de ruta

| Fase | Qué falta | Dónde se integra |
|---|---|---|
| 3. Contexto + LLM | **En parte resuelta con las anotaciones de la IA.** Falta `context.md` (glosario, nivel del lector) para que la skill escriba con los términos del negocio, y un LLM externo para los cambios que no hizo un agente. | `SKILL.md` puede leer `context.md`; un LLM externo usaría el mismo `annotate`. |
| 4. Vigilancia de archivos + línea base | Guardar un commit o una copia del estado actual como "último revisado" y un botón **Marcar como revisado** que lo mueva. | `--base` ya acepta cualquier referencia; falta guardarla en `.git/codemap/` y un `POST` en `server.py`. |
| 5. Enganches | opencode, Cursor y nvim: abrir o actualizar la página cuando el agente termina. | Llamar a `serve` o a `/api/cambios`. |
| 6. Cambios no declarados | **Hecha con `annotate` + skill, y exigida en opencode con el plugin.** Falta el equivalente en Claude Code (un hook del evento `Stop`, que se ejecuta al terminar cada respuesta) y en Cursor. | Reutilizan `scan --compact` y `annotate`. |
| 7. Configuración interactiva | **Hecho para las secciones** (`codemap init` + `/codemap-setup`). Falta el `context.md` con el glosario y el nivel del lector. | La skill `codemap-setup` puede escribirlo junto a `codemap.config.json`. |

Antes de pasar a la fase 3, conviene medir el tiempo que lleva revisar un cambio real con `git diff` y con Codemap.

## Limitaciones conocidas

- En HTML, JS y Markdown los símbolos se detectan con heurísticas; un archivo que no se puede analizar se trata a nivel de archivo.
- Las etiquetas son patrones de texto: pueden dar falsos positivos (`.save(` de una imagen se marca como "base de datos") o pasar por alto llamadas indirectas.
- Si una función se mueve a otro archivo, aparece como eliminada en uno y nueva en el otro.
