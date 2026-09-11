# 03 — Carpetas spam, doorways y esqueletos (Japanese keyword hack)

## Qué es

El atacante usa el dominio de la víctima para posicionar spam (típicamente en japonés) en Google. Para eso crea **doorways**: carpetas con un `index.php` que sirve contenido spam o redirige.

Patrones observados:

- Nombres fijos: `wk`, `656070`.
- Nombres hex aleatorios de 5–6 caracteres (`25fd7e`, `babad`, `1957d`) o con prefijo numérico (`3477_<hash>`).
- Nombres que imitan carpetas legítimas: `images`, `cgi-bin`, `wp`.
- Anidamiento: `wk/wk/wk/`, y dentro de carpetas core (`wp-admin/css/css/`, `wp-includes/blocks/columns/columns/`).
- `index.php` cargador con `require base64_decode(...)` que incluye un **archivo "multimedia" falso** (`.jpx`, `.m4a`, `.bmp`) que en realidad es PHP.
- Payload típico `cache.php`, a veces protegido por un `.htaccess` con `FilesMatch` sobre `cache.php`.
- Sabotaje: renombra `wp-content/plugins/` a `pluginsX/` (WordPress deja de cargar plugins, incluidos los de seguridad) o vacía el `index.php` raíz.
- Archivo de verificación falsa de Google Search Console en la raíz (`google<hash>.html`) para controlar el sitio en Search Console y enviar sitemaps spam.

Drops en rutas **no alcanzables por HTTP** (`~/mail/`, `~/etc/`, `~/ssl/keys/`, `~/bin/`, `~/perl5/`, `~/backups/`, `~/public_ftp/`) no sirven para SEO: son evidencia de que el atacante tiene shell en la cuenta.

## Cómo se detecta

**Detector de reinfección** (tras la limpieza debe dar `0`; cualquier resultado es drop nuevo):

```
find <HOME> -maxdepth 7 -type d \( -name wk -o -name 656070 \) 2>/dev/null | wc -l
```

Primero las que tienen contenido (payload vivo posible):

```
find <RUTA_SITIO> -maxdepth 7 -type d \( -name wk -o -name 656070 \) ! -empty 2>/dev/null
```

Carpetas hex (ruidoso, revisar a mano):

```
find <RUTA_SITIO> -maxdepth 6 -type d -regextype posix-extended -regex '.*/[0-9a-f]{5,6}' 2>/dev/null
```

"Multimedia" que contiene PHP:

```
find <RUTA_SITIO> -maxdepth 8 -type f \( -name "*.jpx" -o -name "*.m4a" -o -name "*.bmp" \) -exec grep -l "<?php" {} + 2>/dev/null
```

Desde fuera: búsqueda `site:<DOMINIO>` en Google con resultados en japonés, o páginas indexadas desconocidas en Search Console.

## Cómo se confirma

- Leer el `index.php` de la carpeta: `base64_decode` + include de un archivo multimedia = doorway confirmado.
- Carpeta dentro de core que no existe en el core limpio: `ls <KIT_CORE>/wp-admin/css/` vs. el sitio.
- Un archivo `.jpx`/`.m4a`/`.bmp` que empieza con `<?php` es PHP disfrazado, sin discusión.

## Cómo se remedia

1. Matar la persistencia primero (`06-mecanismos-de-persistencia.md`). Si no, se regeneran.
2. Carpetas con contenido: leer, confirmar, borrar.
3. **Guardar la lista antes de borrar esqueletos:**

```
find <HOME> -maxdepth 7 -type d \( -name wk -o -name 656070 \) -empty 2>/dev/null > <HOME>/lista_esqueletos.txt
```

4. Borrar solo vacías (falla si hay algo dentro, así que es simulacro y borrado en un paso):

```
find <HOME> -maxdepth 7 -type d \( -name wk -o -name 656070 \) -empty -delete 2>/dev/null
```

Si hay anidamiento, repetir hasta que el conteo no baje; `-delete` implica `-depth`, así que normalmente resuelve la cadena en una pasada.

5. Restaurar `index.php` raíz desde `<KIT_CORE>` si fue vaciado; renombrar `pluginsX/` → `plugins/` solo tras verificar su contenido (o reinstalar plugins limpios).
6. Borrar `google<hash>.html` falso y quitar al propietario desconocido en Search Console (ver `07-base-de-datos-comprometida.md`).
7. Re-correr el detector: `0`.

## Por qué barrer los esqueletos

El escáner del hosting borra el PHP malicioso pero **deja la estructura de carpetas**. Cientos de carpetas `wk` vacías hacen imposible distinguir un drop nuevo de un residuo viejo. Con los esqueletos barridos, el detector en `0` se vuelve una señal limpia: cualquier aparición futura es reinfección confirmada.

## Falsos positivos

- **`firmas`, `images`, `cgi-bin`, `wp`:** nombres usados legítimamente (por el propio equipo para assets de clientes, por plugins, por el hosting). El atacante los imita justamente por eso. **Nunca borrar por nombre**; verificar contenido. Una carpeta `firmas` con un logo de años atrás es trabajo legítimo.
- Carpetas `wp` dentro de plugins reales (ej. `wp-mail-smtp`, plugins SEO) con sus archivos normales.
- Carpetas hash de Forminator en uploads, `.tmb/` (miniaturas de file managers), carpetas de caché.
- `readme.<hash>.html` en la raíz: el readme de WordPress renombrado por un plugin de hardening.
- `upgrade-temp-backup/`: respaldo temporal de WordPress durante actualizaciones; debería autoborrarse, su presencia es menor.
- Solo `wk` y `656070` son firmas de nombre inequívocas. Todo lo demás se decide por contenido.
