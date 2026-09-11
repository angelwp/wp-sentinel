# 05 — Inyección en core, plugins y archivos sobrescritos

## Qué es

El atacante modifica archivos que WordPress carga en cada petición para que su código corra siempre. Tres formas observadas:

1. **Prepend en archivos de arranque:** `@include base64_decode("...")` como línea 1, o un bloque de código cerrado con `?><?php` antes del contenido original, en `index.php`, `wp-load.php`, `wp-blog-header.php`, `wp-settings.php`.
2. **Doorway ofuscado en `index.php`:** `goto <etiqueta>;` combinado con cadenas hex `\x..`.
3. **Sobrescritura completa:** el archivo legítimo (de core o de un plugin) reemplazado entero por otro contenido. Resultado: fatal de PHP.

Rasgos asociados: archivos core en permisos `444`, timestamps alterados. El atacante a veces pasa por un archivo, **toca permisos y timestamps, y no deja código**.

## Cómo se detecta

Inicio de los archivos de arranque:

```
head -c 300 <RUTA_SITIO>/index.php
```

`base64_decode` en la primera línea de cualquier PHP de la raíz:

```
for f in <RUTA_SITIO>/*.php; do head -n 1 "$f" | grep -q "base64_decode" && echo "$f"; done
```

Firma `goto` + hex:

```
grep -rlE --include="*.php" --exclude-dir=vendor 'goto [A-Za-z0-9_]{8,};.*\\x[0-9a-f]{2}' <RUTA_SITIO>/ 2>/dev/null | head -n 20
```

**El `error_log` como evidencia forense.** Leerlo antes de borrarlo:

- `PHP Fatal error: Label '<etiqueta>' already defined in index.php` = el inyector corrió **dos veces** y duplicó la etiqueta; el payload se rompió solo. La primera pasada no deja error, así que la inyección original es **anterior** a la primera línea de ese error.
- `fileperms(): stat failed` sobre `index.php` = el archivo no existía en ese momento (borrado y luego restaurado por alguien).
- `error_log` que deja de crecer en una fecha = algo restauró el archivo ese día (el escáner del hosting, un update, una persona). Anotarlo como pregunta abierta si no se puede confirmar.

## Cómo se confirma

**Opción A — WP-CLI** (requiere salida a `api.wordpress.org`):

```
<WP> core verify-checksums --path=<RUTA_SITIO>
```

Si el firewall saliente bloquea `api.wordpress.org`, este comando no funciona.

**Opción B — comparar contra core limpio de la MISMA versión.** Comparar contra un kit de otra versión no sirve: todo sale distinto. Por probar en entornos donde `downloads.wordpress.org` sí responde aunque `api.wordpress.org` no:

```
<WP> core version --path=<RUTA_SITIO>
```

Descargar `https://downloads.wordpress.org/release/wordpress-<VERSION>.zip`, descomprimir en `<KIT_CORE>` y:

```
diff -rq <KIT_CORE>/wp-includes <RUTA_SITIO>/wp-includes
```

Repetir con `wp-admin` y los `*.php` de la raíz. Líneas `Only in <RUTA_SITIO>` = archivos que no deberían existir; `differ` = modificados.

**Opción C — leer.** Para archivos puntuales, leerlos completos. Confirmado limpio por contenido, aunque tengan fecha del evento y permisos alterados.

## Cómo se remedia

Nunca "limpiar en sitio" línea por línea: reemplazar desde fuente limpia.

1. Quitar el bloqueo de escritura que puso el atacante:

```
chmod -R u+w <RUTA_SITIO>/wp-admin <RUTA_SITIO>/wp-includes
chmod u+w <RUTA_SITIO>/*.php
```

2. **Core:** reemplazar `wp-admin/` y `wp-includes/` completos y los `wp-*.php` + `index.php` de la raíz desde `<KIT_CORE>` de la misma versión. `wp-admin/` y `wp-includes/` no guardan nada propio del sitio; reemplazarlas enteras elimina también archivos plantados que un `cp` encima dejaría.
3. **`wp-config.php`:** no viene en el paquete; revisarlo a mano (inicio y final del archivo, `include`/`require` raros).
4. **Plugins:** reinstalar desde `https://downloads.wordpress.org/plugin/<SLUG>.zip` (o `<SLUG>.<VERSION>.zip`) o desde el ZIP del proveedor si es premium. Guardar los ZIPs en `<KIT_PLUGINS>`.
5. **Temas:** igual, desde el ZIP oficial. Si el tema está dañado sin forma de recuperar el ZIP original, migrar a otro tema es opción válida.
6. Validar: `php -l` sobre archivos editados a mano, `curl -sI https://<DOMINIO>/` en 200, navegar enlaces internos.

## Error que ya costó un sitio

Borrar archivos porque contienen una firma, cuando la firma está ahí porque el malware **sobrescribió** un archivo legítimo. Borrarlo cambia "archivo infectado" por "archivo faltante" = fatal. Si la ruta corresponde a core o a un plugin conocido, se **reemplaza**, no se borra.

## Falsos positivos

- **`goto` a secas es legítimo en core** (ej. `class-wp-html-processor.php`, `class-wp-html-doctype-info.php`, `class-wp-block-processor.php`, `compat-utf8.php`). La firma real es `goto` **+ hex**.
- `hello.php` sin header `Text Domain` (versiones viejas de Hello Dolly).
- Diferencias en `style.css` de temas default entre versiones.
- Archivos `.po`/`.mo`.
- `wp-content/` modificada recientemente: actualizaciones de plugins desde el panel.
- Core con fecha del evento y permisos `444` pero contenido idéntico al limpio: el atacante pasó, no dejó código. Restaurar permisos (`644`) y seguir.
