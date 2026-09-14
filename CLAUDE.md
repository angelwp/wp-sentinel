# wp-sentinel

Spec driven development. La fuente de verdad del proyecto es [docs/SPEC.md](docs/SPEC.md) — congelado en v1.1.
Cualquier cambio de alcance, arquitectura o criterios de aceptación se anota ahí, en "Cambios al spec", no en otro lado.

- `docs/SPEC.md` — especificación completa: objetivo, stack, arquitectura, endpoints, límites, pruebas mínimas, variables de entorno.
- `knowledge/` — corpus de conocimiento operativo (seguridad WordPress / hosting compartido) que se carga completo al `system` prompt. No editar sin revisar §12 del spec (reglas de contenido: cero dominios reales, IPs, credenciales o material identificable de clientes).
- Antes de implementar cualquier paso, revisar §13 del spec (orden de trabajo) y no saltarse pasos.
- No-objetivos (§2) son definitivos para esta versión: no agregar login, RAG, panel admin, etc. sin que el usuario cambie el spec primero.
- Secretos: `.env` nunca se commitea y sus valores nunca se imprimen en output, logs ni tests.
- Verificar conexión a Supabase: `.venv/bin/python -m scripts.verify_supabase`
- Commits: un paso de §13 = un PR = un commit squash en `main`, prefijado con el número (`Step 3: ...`), para que el avance sea legible desde `git log`. Si un paso ya mergeado necesita corrección, entra en otro PR con el mismo prefijo (`Step 4:`), así que un paso puede tener más de un commit. Lo que no es un paso de §13 usa `Setup:` o `Docs:`.

## Flujo con agentes

- Cada paso de §13 va en su rama `step-N-slug` y entra a `main` por PR con merge **squash**, titulado `Step N: ...`. Cada PR deja un solo commit en `main`. `main` es producción: Render la despliega.
- **Ejecutor**: Claude en `wp-sentinel/`. Crea la rama, implementa y abre el PR. No mergea sin OK del usuario.
- **Auditor**: Claude en `../wp-sentinel-audit/` (worktree), siempre en sesión nueva, vía `/audit-spec <PR>`. Solo comenta en el PR; nunca edita.
- **Revisor del spec**: Claude en `../wp-sentinel-audit/`, en sesión nueva, vía `/review-spec`. Revisa la calidad de `docs/SPEC.md` contra `main` (ambigüedades, huecos, inconsistencias) y abre un issue; nunca edita. Se corre antes de empezar un paso cuando las auditorías acumulan dudas de alcance. Lo que el usuario acepte entra por un PR `Docs:` a "Cambios al spec".
- Los agentes no se comunican entre sí: el código viaja por git, los hallazgos por comentarios del PR o issues, y el usuario da la señal.
- No implementar el paso N+1 hasta que el PR del paso N esté mergeado (§13).

### Retroalimentación del ejecutor al auditor

Tras corregir los hallazgos de una auditoría, el ejecutor comenta en el PR (no edita el reporte del auditor) una tabla `Hallazgo → Qué se hizo` antes de pedir re-auditoría. Si el ejecutor no está de acuerdo con un hallazgo, lo dice ahí — con su razón — en vez de ignorarlo en silencio. Cierra el ciclo: el auditor no tiene forma de saber si su comentario se leyó hasta que ve un commit nuevo o esta respuesta.

### Mensaje del commit al mergear

El commit squash en `main` es el registro permanente; el chat no se conserva. Nada decidido en el chat queda solo en el chat.

```
gh pr merge <N> --squash --subject "<título del PR> (#N)" --body-file <archivo temporal>
```

El cuerpo lleva, en este orden:

1. **Qué cambió**: una línea por archivo o grupo de archivos.
2. **Auditoría**: SHA revisado y conteo (`X cumple · Y no cumple · Z duda de alcance`). Si no hubo auditoría, decirlo.
3. **Verificación**: qué se corrió y su resultado.
4. **Decisiones del usuario**: cada `DUDA DE ALCANCE` con lo decidido y por qué. Si cambia el spec, también va en "Cambios al spec".
5. **Correcciones**: lo que la descripción del PR dijo mal.
6. Líneas de atribución.

Se omite la sección que no aplique. Nunca van secretos ni valores de `.env`.

## Render

- El servicio se creó **a mano** en el panel de Render (§13 paso 3, primer deploy `46c3e43`). Hace auto-deploy desde `main`.
- Variables capturadas a mano en Render → Environment:
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (12 sep 2026). Faltaban, y por eso fallaron los deploys de `5559c4a` y `4c3448b`: la app exige ambas al importar (§11). La clave de servicio se rotó ese mismo día.
  - `IP_HASH_SALT` (13 sep 2026, paso 5). Confirmada porque el deploy de `8550e6f` arrancó y la app no arranca sin ella. Puede ser distinta de la local.
  - Cada variable nueva de §11 se captura ahí antes de mergear el paso que la usa.
- `render.yaml` está versionado pero **no aplicado**: un servicio creado a mano no lo lee. No crear un Blueprint con él hasta que `/health` deje de llamar a Supabase al importar (`app/main.py`); con `healthCheckPath`, cualquier falla de credenciales tumbaría el deploy, y §5 dice que `/health` no toca la base.
- `/health` responde igual en todos los commits: un 200 no prueba qué commit está vivo. Eso se confirma en Render → Deploys.
- **Una instancia, un worker de uvicorn.** El lock de `app/sessions.py`, que evita pasar el límite de sesiones por IP con peticiones simultáneas, solo protege dentro de un proceso. Antes de subir instancias en Render o agregar `--workers`, mover ese conteo a Postgres. Durante un deploy conviven unos segundos la instancia vieja y la nueva; se acepta.

## Setup en máquina nueva

1. `.env`: lo crea el usuario a mano (nunca por chat ni por git).
2. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
3. Worktree del auditor, una vez por máquina:
   ```
   git worktree add --detach ../wp-sentinel-audit origin/main
   cd ../wp-sentinel-audit
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   cp ../wp-sentinel/.env .env
   cp .claude/auditor-settings.json .claude/settings.local.json
   ```
   El último `cp` agrega una **segunda capa**, no un sandbox. En ese directorio, Claude Code niega las herramientas `Edit` y `Write`, y los comandos de la lista `deny` de `.claude/auditor-settings.json`: commits, push, merge, cambios de archivos con git y `gh api`, entre otros. No bloquea toda escritura posible: un redirect de shell (`>`) o un comando que no esté en la lista todavía podría escribir. La primera capa sigue siendo la instrucción "el auditor nunca edita". `settings.local.json` está en `.gitignore`, así que no ensucia el `git status` que revisa `/audit-spec`. Si el auditor necesita un comando nuevo, se ajusta la plantilla por PR.

## Seguimiento y retomar trabajo

El chat no se conserva. Todo el contexto para seguir, desde cualquier máquina o persona, vive en GitHub:

| Pregunta | Dónde |
|---|---|
| Qué se construye | `docs/SPEC.md` |
| Cómo se trabaja | este archivo |
| Qué está en curso y qué falta | PRs abiertos (descripción + último comentario `## Estado`) e issues abiertos (revisiones del spec con hallazgos sin decidir) |
| Qué se decidió y por qué | Si cambia alcance, arquitectura o criterios de aceptación: "Cambios al spec" en `docs/SPEC.md`. Todo lo demás, y el registro de cada merge: cuerpo de los commits squash en `main` |

- **Al retomar:** `git fetch`, `gh pr list` y `gh issue list`. Lee el último comentario `## Estado` de cada PR abierto y el último comentario de cada issue abierto. Si un hallazgo sin decidir afecta el siguiente paso, se decide antes de implementarlo. Si no hay PRs abiertos, busca el último commit `Step N:` en `git log main`; el siguiente es el paso N+1. Los pasos 1 y 2 (`3f2e997`, `46c3e43`) y parte del 4 (`5559c4a`, `4c3448b`) son anteriores a la convención y no llevan el prefijo.
- **Al pausar:** el ejecutor deja en cada PR abierto un comentario `## Estado — <fecha>` con los pendientes en orden, cada uno con su responsable (usuario, ejecutor o auditor). En cada issue abierto, el último comentario dice qué hallazgos siguen sin decidir. Nunca secretos.
- No se mantiene un archivo de estado aparte: se desactualiza y duplica lo que ya dicen los PRs.
