---
name: nexus-setup
description: Configura Nexus-diff en el repositorio actual. Genera y adapta nexus-diff.config.json para que los cambios se agrupen en secciones con nombres del negocio. Úsala cuando el usuario pida "/nexus-setup", "configura nexus-diff", "prepara nexus-diff para este proyecto" o cuando Nexus-diff avise de que usa secciones genéricas.
---

# Configurar Nexus-diff en este proyecto

Nexus-diff agrupa cada cambio del repositorio en **secciones** (UI, Backend, Datos…) definidas en
`nexus-diff.config.json`, en la raíz del repo. Tu trabajo es dejar ese archivo con secciones que la persona
reconozca: nombres en lenguaje de negocio, una descripción corta y reglas que clasifiquen bien los archivos.

Comando de Nexus-diff: `{{NEXUS}}` (ejecútalo desde la raíz del repositorio).

## Pasos

1. **Genera la propuesta inicial:**
   ```bash
   {{NEXUS}} init --repo .
   ```
   Detecta el stack y crea una sección por cada carpeta de dominio. Si `nexus-diff.config.json` ya existe, no lo
   sobrescribas: revísalo desde el paso 2. Usa `init --force` solo si el usuario quiere empezar de cero.

2. **Mira cómo quedan clasificados los archivos:**
   ```bash
   {{NEXUS}} sections --repo . --json
   ```
   Para cada sección verás cuántos archivos tiene y algunos ejemplos; además, `sin_clasificar` y
   `logica_generica` listan los archivos que no encajan en ninguna sección concreta.

3. **Entiende el proyecto lo justo:** lee el README y los archivos de instrucciones (`AGENTS.md`,
   `CLAUDE.md`…) y echa un vistazo a las carpetas principales. No hace falta leer todo el código.

4. **Edita `nexus-diff.config.json`:**
   - Renombra las secciones de carpeta (las que dicen "pendiente de describir") con el concepto de negocio que
     representan (por ejemplo, `ml/` → "Modelo predictivo"; `accounts/` → "Usuarios y permisos") y escribe una
     descripción de una línea.
   - Si conviene, junta carpetas en una misma sección, añade rutas a secciones existentes o crea secciones
     nuevas. Mantén entre 5 y 12 secciones: más que eso no ayuda a revisar.
   - Añade a `excluir` lo generado automáticamente (builds, cachés, archivos de bloqueo enormes, binarios de
     terceros).
   - Reglas del formato: cada sección tiene `nombre`, `descripcion` y `rutas` (globs; `**/` = cualquier
     número de carpetas). Opcionalmente `contenido`: expresiones regulares que se buscan en el archivo. **Gana
     la primera sección cuyas reglas coincidan**, así que pon las específicas antes que las genéricas
     ("Tests" y "Configuración" suelen ir primero; "Lógica de aplicación" al final).
   - Conserva la clave `proyecto` y actualiza `proyecto.stack` si detectas algo que `init` no vio.

5. **Comprueba el resultado** con `{{NEXUS}} sections --repo .` y repite el paso 4 hasta que
   `sin_clasificar` esté vacío o solo tenga archivos que de verdad no importan.

6. **Pregunta solo lo que no puedas deducir** (por ejemplo, qué representa una carpeta con un nombre ambiguo).
   Una o dos preguntas como máximo; lo demás, decídelo tú y explícalo.

7. **Resume al usuario** las secciones finales (nombre → qué agrupa) y recuérdale que `nexus-diff.config.json`
   se puede commitear para compartirlo con el equipo y editar a mano cuando quiera.

## Qué no hacer

- No inventes secciones para carpetas que no existen.
- No borres la sección "Tests" ni "Configuración" aunque estén vacías: servirán cuando aparezcan esos archivos.
- No modifiques otros archivos del proyecto: esta skill solo toca `nexus-diff.config.json`.
