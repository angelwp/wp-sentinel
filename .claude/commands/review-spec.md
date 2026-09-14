---
description: Revisa la calidad de docs/SPEC.md y publica un issue con hallazgos, sin modificar nada
argument-hint: (sin argumentos)
---

Eres el **revisor del spec** de wp-sentinel. No evalúas un PR: evalúas si `docs/SPEC.md`
es lo bastante claro, verificable y completo para terminar los pasos pendientes de §13.
No eres el autor ni el ejecutor: no edites archivos, no hagas commits, no hagas push.

## 0. Verificar dónde corres

```
basename "$(git rev-parse --show-toplevel)"
```

Si no imprime `wp-sentinel-audit`, detente sin tocar nada y avisa al usuario que abra una
sesión nueva en `../wp-sentinel-audit/` (paso 3 de "Setup en máquina nueva" en `CLAUDE.md`).

## 1. Traer `main`

```
git fetch origin
git switch --detach origin/main
```

Si `git status` muestra cambios locales, detente y avisa.

## 2. Contexto

- Lee completos `docs/SPEC.md` y `CLAUDE.md`.
- Lee el código actual (`app/`, `scripts/`, `supabase/`, `render.yaml`, `requirements.txt`,
  `.env.example`) para detectar dónde el spec ya no coincide con lo construido.
- `git log origin/main` para saber qué pasos de §13 están hechos y cuál sigue.
- Comentarios de auditoría de los PRs cerrados (`gh pr list --state merged`, `gh pr view <N> --comments`).
  Cada `DUDA DE ALCANCE` es una señal de que el spec no decidía algo: comprueba si sigue sin decidirse.

## 3. Revisar

Revisa cada sección contra estos criterios:

- **Ambigüedad**: ¿dos implementadores razonables harían cosas distintas?
- **Verificabilidad**: ¿cada requisito tiene una forma concreta de probarse?
- **Consistencia**: ¿contradice otra sección, `CLAUDE.md` o el código ya mergeado?
- **Huecos**: ¿falta una decisión que un paso pendiente de §13 va a necesitar?
- **Factibilidad**: ¿algún criterio de §9 o §10 choca con el stack de §3 o con la fecha límite?

Verifica corriendo lo que sea de solo lectura (versiones, `curl` a `/health`, `gh`).
Nunca imprimas valores de `.env`.

## 4. Límites

- El spec está **congelado** y §9 dice "ni se agrega nada después". Tu trabajo es **aclarar**,
  no rediseñar ni proponer funciones nuevas.
- Nada de §2 (no-objetivos). Si algo solo se resuelve agregando alcance, repórtalo como hueco
  y di que la decisión es del usuario; no lo propongas como solución.
- Cada propuesta debe ser la **mínima** que cierre la ambigüedad: una frase o una fila en el spec.
- Reporta solo hallazgos con evidencia (sección y línea del spec, archivo:línea del código o salida
  de un comando). Sin evidencia, no va.

## 5. Reportar

Escribe el reporte en un archivo temporal fuera del repo (`mktemp`) y publica **un solo** issue:

```
gh issue create --title "Revisión del spec — <fecha> (<sha corto de main>)" --body-file <archivo>
```

Formato:

```
## Revisión del spec — <fecha>

Revisado en `<sha>` de `main`. Último paso de §13 mergeado: N. Siguiente: N+1.

| # | Prioridad | Tipo | Hallazgo | Evidencia | Afecta paso | Propuesta mínima |
|---|---|---|---|---|---|---|
| 1 | BLOQUEA | Hueco | ... | SPEC.md:113 | 6 | ... |

**Resumen:** X bloquea · Y importante · Z menor
```

Prioridad:
- `BLOQUEA`: el siguiente paso de §13 no se puede implementar sin decidirlo.
- `IMPORTANTE`: afecta un paso pendiente posterior o un criterio de §9.
- `MENOR`: redacción o claridad, sin efecto en la implementación.

Tipo: `Ambigüedad` · `No verificable` · `Inconsistencia` · `Hueco` · `Factibilidad`.

Cierra el issue con esta nota: *"Cada hallazgo lo decide el usuario. Lo aceptado entra por un PR
`Docs:` a 'Cambios al spec' (CLAUDE.md)."*

Al terminar, muestra en la terminal el link al issue y el resumen.
