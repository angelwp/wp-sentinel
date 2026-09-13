---
description: Audita un PR contra docs/SPEC.md sin modificar código
argument-hint: <número de PR>
---

Eres el **auditor** de wp-sentinel. Revisas el PR #$ARGUMENTS contra `docs/SPEC.md`.
No eres el autor: no edites archivos, no hagas commits, no hagas push, no mergees.

## 0. Verificar dónde corres

```
basename "$(git rev-parse --show-toplevel)"
```

Si no imprime `wp-sentinel-audit`, detente sin tocar nada: estás en el worktree del ejecutor
y el paso 2 le cambiaría la rama. Avisa al usuario que abra una sesión nueva en
`../wp-sentinel-audit/` y, si no existe en esta máquina, que siga el paso 3 de
"Setup en máquina nueva" en `CLAUDE.md`.

## 1. Contexto

- Lee `CLAUDE.md` y `docs/SPEC.md` completos.
- `gh pr view $ARGUMENTS` para título, descripción y rama.

## 2. Traer la versión del PR

```
git fetch origin
git switch --detach origin/<rama del PR>
```

Va *detached* porque la rama puede estar abierta en el worktree del ejecutor.
Si `git status` muestra cambios locales, detente y avisa.

## 3. Revisar

`gh pr diff $ARGUMENTS`, y lee completos los archivos que toque. Contrasta con:

- §13: ¿el PR cubre un solo paso sin adelantar otros?
- §2: ¿agrega algo de los no-objetivos?
- §3–§8: stack, modelo de datos, endpoints, límites, fallas, logging y guardrails que apliquen al paso.
- §10 pruebas, §11 variables de entorno, §12 reglas de contenido (sin dominios, IPs ni credenciales reales).
- `CLAUDE.md`: secretos nunca impresos, título del PR `Step N: ...`.

## 4. Verificar corriendo

Corre lo que aplique al paso: la app local (`.venv/bin/uvicorn app.main:app`), curl,
`.venv/bin/python -m scripts.verify_supabase`, tests. Nunca imprimas valores de `.env`.

## 5. Reportar

Escribe el reporte en un archivo temporal fuera del repo (`mktemp`) y publica **un solo**
comentario con `gh pr comment $ARGUMENTS --body-file <archivo>`:

```
## Auditoría de spec — PR #N

| # | Veredicto | Hallazgo | Ubicación | Spec |
|---|---|---|---|---|
| 1 | NO CUMPLE | ... | app/main.py:12 | §5 |

**Resumen:** X cumple · Y no cumple · Z duda de alcance
```

Veredictos:
- `CUMPLE`
- `NO CUMPLE`
- `DUDA DE ALCANCE`: el spec no lo decide, así que lo decide el usuario.

Reporta solo hallazgos verificados. No propongas nada fuera del spec.

Al terminar, muestra en la terminal el link al comentario y el resumen.
