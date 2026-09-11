# 02 — `.htaccess` malicioso (kit AnonymousFox)

## Qué es

El kit AnonymousFox siembra `.htaccess` en cientos o miles de directorios por sitio. Objetivo: **bloquear la ejecución de cualquier PHP excepto el suyo**, para que limpiadores, plugins de seguridad y otros atacantes no puedan correr código, mientras sus shells siguen funcionando.

Anatomía típica:

- Un `<FilesMatch>` con variantes de mayúsculas de la extensión PHP (`php|PHP|pHP7|PHP7|PhP`, a veces `py|exe`) + `Order allow,deny` / `Deny from all`.
- Un segundo `<FilesMatch>` con `Allow from all` que autoriza archivos legítimos de WordPress **y una lista de ~25 nombres de shells**: `adminfuns.php`, `cjfuns.php`, `classsmtps.php`, `gdftps.php`, `copypaths.php`, `delpaths.php`, `qfunctions.php`, `tempfuns.php`, `lock360.php`, `radio.php`, `about.php`, entre otros.
- Permisos `444` (o `555` en el raíz) para que nadie los reescriba.
- Es una **plantilla idéntica** soltada en toda la cuenta: aparece con reglas de WordPress incluso en sitios que no son WordPress. Eso prueba despliegue masivo, no ataque dirigido al sitio.

Variante 2 observada: `.htaccess` con un `RewriteRule . index.php` genérico, permisos `444` y timestamp del evento.

Ubicaciones típicas: `.well-known/`, `.well-known/acme-challenge/`, `images/`, `wp-admin/`, `wp-includes/`, carpetas de temas, plugins y uploads.

## Cómo se detecta

Conteo a nivel cuenta (debe dar `0` tras la limpieza):

```
grep -rl --include=".htaccess" "pHP7" <HOME>/ 2>/dev/null | wc -l
```

Si la terminal aborta, correrlo por sitio con `<RUTA_SITIO>` en vez de `<HOME>`.

Por permisos (variante 2 y complementos):

```
find <RUTA_SITIO> -maxdepth 6 -name ".htaccess" -perm 444 2>/dev/null
```

**Síntoma en navegador que engaña:** si la página muestra como texto `Order allow,deny` / `Deny from all` (las etiquetas `<FilesMatch>` no se ven porque el navegador las interpreta como HTML), **eso no es Apache**. Apache responde 500 ante una directiva que no entiende; nunca vuelca el `.htaccess` como texto. Lo que ves es un **PHP imprimiendo ese contenido**: un file manager malicioso servido como `index.php`, o un archivo incluido antes de WordPress. Borrar los `.htaccess` no arregla ese síntoma; hay que encontrar el PHP (ver `04-web-shells.md` y `06-mecanismos-de-persistencia.md`).

## Cómo se confirma

- `cat` de uno completo: `FilesMatch` con variantes `pHP7` + whitelist con nombres de shells = confirmado.
- La whitelist es una lista de IOCs: buscar si esos archivos existen en la cuenta.

```
find <HOME> -maxdepth 7 -type f \( -name lock360.php -o -name radio.php -o -name adminfuns.php -o -name cjfuns.php -o -name classsmtps.php -o -name gdftps.php \) 2>/dev/null
```

`about.php` y `radio.php` pueden existir legítimamente en algunos temas o plugins: confirmar por contenido.

## Cómo se remedia

1. **Borrar restringido a `.htaccess`.** Nunca un grep de la firma sin `--include`:

```
grep -rl --include=".htaccess" "pHP7" <RUTA_SITIO> 2>/dev/null | while read -r f; do rm -f "$f"; done
```

2. Si un directorio está en `555`, `rm` falla: `chmod u+w` sobre el directorio primero.
3. **Revisar el `.htaccess` raíz a mano.** Si trae la firma, reemplazarlo; si trae reglas legítimas (caché, redirecciones, Wordfence, forzado HTTPS), quitar solo los bloques maliciosos.
4. Si falta el raíz, recrearlo con `printf` (los heredocs pegados en la terminal web colapsan saltos de línea y un `.htaccess` en una línea tumba el sitio con 500):

```
printf '%s\n' '<IfModule mod_rewrite.c>' 'RewriteEngine On' 'RewriteBase /' 'RewriteRule ^index\.php$ - [L]' 'RewriteCond %{REQUEST_FILENAME} !-f' 'RewriteCond %{REQUEST_FILENAME} !-d' 'RewriteRule . /index.php [L]' '</IfModule>' > <RUTA_SITIO>/.htaccess
```

Supuestos: WordPress instalado en la raíz del dominio (si está en subcarpeta, cambia `RewriteBase` y la última regla). Omite las líneas de comentario `BEGIN/END WordPress`; WordPress las agrega si reescribe permalinks.

5. Validar: `cat -A <RUTA_SITIO>/.htaccess` (cada línea debe terminar en `$`) y `curl -sI https://<DOMINIO>/` en 200.
6. Re-correr el conteo a nivel cuenta: `0`.

## Error que ya costó un sitio

Un grep de `pHP7|PHP7` **sin** `--include=".htaccess"` borró también archivos `.php` legítimos que el malware había **sobrescrito completos** con el contenido del `.htaccess` (un archivo de plugin SEO, la clase principal de Wordfence y `wp-includes/pluggable.php`). El sitio cayó con fatales. Regla: si un `.php` contiene la firma, **se reemplaza desde fuente limpia**, no se borra (ver `05-inyeccion-en-core.md`).

## Impacto colateral

- **Inferencia:** los `.htaccess` en `.well-known/acme-challenge/` pueden interferir con la validación de SSL (AutoSSL / Let's Encrypt) según la variante. Borrarlos no hace daño; si una renovación falla, verificar con `curl` a un archivo de prueba en esa carpeta.

## Falsos positivos

WordPress core **no trae ningún `.htaccess`**. En `wp-admin/`, `wp-includes/` y carpetas de temas, uno en subcarpeta es anómalo por definición.

Pero varios plugins crean `.htaccess` legítimos para proteger sus carpetas (normalmente un `Deny from all` simple, **sin** `pHP7` ni whitelist de shells):

- Wordfence: `wp-content/wflogs/`
- Contact Form 7: `uploads/wpcf7_uploads/`
- File managers: `fm_backup/`
- En general plugins de formularios, backups y tiendas que guardan archivos en uploads.

Borrarlos no rompe el sitio, pero deja expuestos archivos subidos por usuarios hasta que el plugin lo regenere. Por eso la regla operativa es **borrar por firma, no por ubicación**.
