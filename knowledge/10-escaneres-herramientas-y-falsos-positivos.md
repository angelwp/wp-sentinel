# 10 — Escáneres, herramientas y catálogo de falsos positivos

## Qué es el problema

Cada herramienta tiene un alcance y puntos ciegos. Tratar un "limpio" de una herramienta como "limpio" del sistema es cómo el malware sobrevive meses.

## Qué cubre y qué no cada herramienta

### Escáner del hosting (tipo Monarx)

- **Hace:** borra PHP malicioso conocido en segundos.
- **No hace:**
  - Borrar la estructura: deja carpetas vacías ("esqueletos") que ensucian la detección de reinfección.
  - Tocar la BD: admins fantasma, cron, opciones, spam en posts quedan intactos.
  - Llegar a la persistencia activa (llaves SSH, código en BD, código generador).
  - Escanear `~/mail/`: se encontraron shells vivos ahí meses después.
  - Cubrir cuentas cPanel donde no está contratado.
- Sus conteos de "amenazas" varían entre reportes; no usarlos como métrica de avance.
- Su **log de detecciones** es evidencia forense: puede explicar qué tocó una carpeta a una hora concreta.

### Wordfence (Free)

- Escaneo por firma dentro de la instalación WordPress. Útil como **verificación final**, no como limpiador principal.
- No ve fuera de la raíz del sitio.
- Su WAF depende de `wordfence-waf.php` vía `auto_prepend_file` (ver `06-...`).
- Sin salida a internet genera avisos como `Failed to retrieve cookie redaction patterns`: ruido, no ataque.

### WP-CLI

- `core verify-checksums`: la mejor verificación de core, pero **requiere `api.wordpress.org`**. Si el firewall saliente lo bloquea, no funciona; usar comparación contra core de la misma versión (`05-...`).
- `user list`, `cron event list`, `option get`, `db search`, `db export`: auditoría de BD sin phpMyAdmin.
- La terminal puede correr otra versión de PHP que los sitios; para WP-CLI no suele importar, para diagnosticar configuración de PHP web sí.

### grep / find por firma

- Encuentran **solo lo conocido**. Un shell escrito a mano sin ofuscación pasa limpio. Reportar "sin malware conocido", no "limpio".
- En terminales con timeout: acotar por sitio y con `-maxdepth`.
- Exclusión permanente solo `vendor/`.
- **Control positivo:** antes de confiar en un resultado vacío, correr el mismo comando contra un archivo que sí tiene la firma. Un comando mal escrito (ej. un espacio faltante) también devuelve vacío y parece "limpio".

### Logs

- `error_log` de cada sitio: línea de tiempo del payload (ver `05-...`). Leer antes de borrar.
- Logs de acceso: únicos que dan IP y patrón de peticiones. **Rotan rápido**: descargarlos al inicio del incidente.
- `debug.log`: normalmente ruido de actualizaciones; leerlo una vez antes de borrarlo.

### curl

- `curl -sI https://<DOMINIO>/` → código de estado tras cada cambio.
- `curl -s https://<DOMINIO>/ | head -5` → detecta si el sitio sirve texto raro en vez de HTML.
- `403` en un recurso bloqueado = tu control. `406` = WAF del hosting.

## Firmas de malware (resumen)

| Firma | Dónde | Archivo |
|---|---|---|
| `pHP7\|PHP7` + whitelist de shells | `.htaccess` | `02` |
| Carpetas `wk`, `656070` | Cualquier ruta | `03` |
| Carpetas hex aleatorias (`25fd7e`, `3477_<hash>`) | Raíz de sitios | `03` |
| `require base64_decode` + include de `.jpx`/`.m4a`/`.bmp` | Doorways | `03` |
| `wk/index.php` MD5 `c1db092890378513b65609a45f636f43` | `wk/`, `~/mail/` | `04` |
| `a22bcS0vMzEJElwPNAQA` | Shells | `04` |
| `$_REQUEST["k"]` + AES-256-CBC | Shells | `04` |
| Doble `eval` + XOR `XyZ@2024` | File manager en carpeta hex | `04` |
| `@include base64_decode` en línea 1 | Core | `05` |
| `?><?php` al inicio de archivos raíz | Core | `05` |
| `goto` + hex `\x..` | `index.php` | `05` |
| `pluginsX/` | `wp-content` | `03` |
| `google<hash>.html` no reconocido | Raíz | `07` |
| Permisos `444`/`555` en `.htaccess` y core | Cualquier ruta | `09` |

## Catálogo de falsos positivos

**Código**
- phpseclib (`EvalBarrett`, `Blowfish`), sodium_compat.
- `class-wpcode-snippet-execute.php` (WPCode).
- `Chain.php` de WPForms con `str_rot13` en PHPDoc.
- `goto` a secas en core de WordPress (`class-wp-html-processor.php`, `class-wp-html-doctype-info.php`, `class-wp-block-processor.php`, `compat-utf8.php`).
- Archivos del scanner de Wordfence.
- JS minificado.
- `hello.php` sin `Text Domain`.
- Diferencias de `style.css` en temas default.
- Tests de Symfony y READMEs de Guzzle dentro de `vendor/`.
- Apps a medida con `base64_decode` / `move_uploaded_file` legítimos.

**Archivos y carpetas**
- `.po` / `.mo`.
- Carpetas hash de Forminator en uploads; caché de WPForms; logs de WP-Optimize.
- `wflogs/` de Wordfence.
- `.tmb/` de file managers.
- `endurance-page-cache.php` en mu-plugins (del hosting).
- `readme.<hash>.html` (readme renombrado por plugin de hardening).
- `upgrade-temp-backup/` (respaldo temporal de updates).
- `.htaccess` de protección en `wpcf7_uploads/`, `fm_backup/`, `wflogs/` (simples, sin firma).
- Carpetas `firmas`, `images`, `cgi-bin`, `wp` con contenido legítimo.

**Sistema**
- Grupo `nobody` en listados de cPanel (normal; importa el owner).
- `.ftpquota` con owner `65535` (demonio FTP).
- Cuentas FTP especiales del sistema.
- `wordfence-waf.php` en `auto_prepend_file`.

**Logs**
- `wp_scraping_result` en `debug.log` (chequeo post-update de core).
- Warnings de PHP 8 en temas propios (`Attempt to read property ... on array`).
- `Failed to retrieve cookie redaction patterns` (Wordfence sin salida).
- `Cron ... could not be saved` (casi siempre benigno; revisar la lista de cron igual).
