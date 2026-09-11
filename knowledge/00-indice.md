# Seguridad WordPress en hosting compartido — base de conocimiento

Conocimiento reusable extraído de una respuesta a incidentes (DFIR) real contra una infección persistente tipo AnonymousFox / Japanese keyword hack en una cuenta cPanel compartida con decenas de sitios WordPress.

Cada archivo sigue la misma estructura: qué es, cómo se detecta, cómo se confirma, cómo se remedia, falsos positivos y errores que ya costaron caro.

## Archivos

| # | Archivo | Tema |
|---|---|---|
| 01 | `01-metodologia-respuesta-incidentes.md` | Fases, principios, inventario, evidencia, cuándo escalar |
| 02 | `02-htaccess-malicioso-anonymousfox.md` | `.htaccess` sembrados por el kit AnonymousFox |
| 03 | `03-carpetas-spam-y-doorways.md` | Carpetas `wk`, `656070`, hex; doorways de SEO spam; esqueletos |
| 04 | `04-web-shells.md` | Shells, file managers maliciosos, confirmación por hash |
| 05 | `05-inyeccion-en-core.md` | Core y plugins inyectados o sobrescritos; restauración |
| 06 | `06-mecanismos-de-persistencia.md` | SSH, cron, WP-Cron, `auto_prepend_file`, drop-ins, FTP |
| 07 | `07-base-de-datos-comprometida.md` | Admins fantasma, `options`, spam en posts, Search Console |
| 08 | `08-credenciales-y-rotacion.md` | Qué rotar, en qué orden, secretos de apps, logs de identidad |
| 09 | `09-vectores-de-entrada-y-hardening.md` | Cómo entran y cómo cerrar la superficie |
| 10 | `10-escaneres-herramientas-y-falsos-positivos.md` | Qué cubre cada herramienta y catálogo de falsos positivos |
| 11 | `11-operacion-segura-en-terminal-cpanel.md` | Disciplina de comandos en la terminal web de cPanel |

## Marcadores

Todo dato identificable está sustituido. Reemplázalos antes de correr cualquier comando.

| Marcador | Significado |
|---|---|
| `<HOME>` | Home de la cuenta cPanel (ej. `/homeN/usuario`) |
| `<DOCROOT>` | `public_html` de la cuenta |
| `<RUTA_SITIO>` | Raíz de una instalación WordPress (donde está `wp-load.php`) |
| `<DOMINIO>` | Dominio de un sitio |
| `<USUARIO_CPANEL>` | Usuario Unix / cPanel |
| `<CORREO_ADMIN>` | Correo de la cuenta admin legítima |
| `<WP>` | Binario de WP-CLI (`wp`, o ruta completa + `--allow-root` si el entorno lo exige) |
| `<KIT_CORE>` | Carpeta con core WordPress limpio **de la misma versión** que el sitio |
| `<KIT_PLUGINS>` | Carpeta con ZIPs limpios de plugins |
| `<HASH>` | Hash MD5 de un archivo |
| `<ID>` / `<ID_ADMIN_LEGITIMO>` | ID numérico de usuario o post |
| `<SITIO>` | Nombre corto del sitio (para nombrar archivos) |
| `<PREFIJO>` | Prefijo de tablas de la BD (`<WP> db prefix`) |
| `<VERSION>` | Versión de WordPress del sitio (`<WP> core version`) |
| `<SLUG>` | Slug de un plugin en wordpress.org |

## Niveles de certeza usados

- **Confirmado:** visto en evidencia (contenido, hash, output real).
- **Inferencia:** consistente con la evidencia, no probado.
- **Por probar:** técnica razonable que aún no se validó en campo.
