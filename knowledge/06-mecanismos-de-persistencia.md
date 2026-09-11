# 06 — Mecanismos de persistencia

## Qué es

Todo lo que permite al atacante **volver a entrar o volver a ejecutar código** después de que limpiaste. Mientras exista uno solo, cualquier limpieza de síntomas se revierte. Es la fase que se cierra antes que cualquier otra.

Heurística útil (inferencia, no regla): si lo borrado reaparece **al instante o con cada visita**, apunta a código que corre en cada petición (prepend, core inyectado, drop-in). Si reaparece **a intervalos**, apunta a cron. Si aparece en rutas **fuera del docroot**, apunta a acceso por shell/SSH.

Otra señal: si el generador crea carpetas y `.htaccess` **sin dejar PHP nuevo**, el código generador ya estaba en disco (o en la BD) antes de correr.

## Checklist

### 1. Llaves SSH plantadas — la más peligrosa

El atacante genera un keypair en el servidor y autoriza su propia llave. **Sobrevive a cualquier cambio de contraseña**: explica reinfecciones después de rotar credenciales.

```
ls -la --time-style=full-iso <HOME>/.ssh/
```

- **Confirmar:** `authorized_keys`, `authorized_keys2`, `id_rsa`, `id_rsa.pub` que nadie del equipo creó, con timestamps agrupados cerca de un evento de infección. OpenSSH lee `authorized_keys2` por defecto: no ignorarlo.
- **Remediar:** descargar copia como evidencia, borrar los cuatro, verificar que el directorio quede como debe.

### 2. Cron del sistema

```
crontab -l
```

También revisar la sección de Cron Jobs de cPanel. Vacío = descartado.

### 3. WP-Cron (vive en la BD)

```
<WP> cron event list --fields=hook,next_run_relative,recurrence --path=<RUTA_SITIO>
```

- **Confirmar:** cada hook debe pertenecer a core o a un plugin instalado. Hook desconocido → buscarlo en el código (`grep -rn "nombre_del_hook" <RUTA_SITIO>/wp-content/`).
- El escáner del hosting no toca la BD: un cron malicioso ahí sobrevive a todo escaneo de archivos.

### 4. `auto_prepend_file` / `auto_append_file`

Hace que PHP incluya un archivo **antes** de cualquier script, sin tocar WordPress.

```
find <HOME> -maxdepth 7 \( -name ".user.ini" -o -name "php.ini" \) 2>/dev/null
```

```
grep -rn --include=".user.ini" --include="php.ini" --include=".htaccess" -i "auto_prepend\|auto_append" <RUTA_SITIO>/ 2>/dev/null
```

- `.user.ini` aplica **en cascada por directorio**: puede estar en una subcarpeta intermedia, no solo en la raíz.
- `php -i` desde la terminal muestra la configuración del **PHP de CLI**, que puede ser otra versión y otra config que la del PHP web. Un "no value" en CLI no descarta nada del lado web.
- **Falso positivo:** Wordfence usa `auto_prepend_file` apuntando a `wordfence-waf.php` en la raíz. Legítimo.

### 5. Drop-ins y mu-plugins (se cargan solos)

```
ls -la <RUTA_SITIO>/wp-content/mu-plugins/ <RUTA_SITIO>/wp-content/advanced-cache.php <RUTA_SITIO>/wp-content/object-cache.php <RUTA_SITIO>/wp-content/db.php 2>/dev/null
```

Cada archivo debe corresponder a un plugin conocido (caché, hosting). **Falso positivo:** `endurance-page-cache.php` en mu-plugins, puesto por el hosting.

### 6. Tema activo y archivos principales de plugins

`functions.php` del tema activo y el archivo principal de cada plugin: ofuscación que evade el grep simple suele esconderse aquí. Leer el inicio y el final del archivo.

### 7. Perfil de shell

```
ls -la --time-style=full-iso <HOME>/.bashrc <HOME>/.bash_profile
```

Sin cambios desde la creación de la cuenta = descartado.

### 8. FTP y escritura anónima

- Cuentas FTP adicionales que nadie reconoce.
- `<HOME>/public_ftp/incoming/` en `777` = escritura anónima. Cambiar a `700` y verificar.

### 9. Usuarios y código en la BD

- Admins fantasma (`07-base-de-datos-comprometida.md`): con uno de ellos el atacante reinstala todo desde wp-admin.
- Plugins de snippets (WPCode y similares) guardan PHP en la BD y lo ejecutan en cada petición. Revisar la lista de snippets.

### 10. Credenciales filtradas

Si todo lo anterior está limpio y la reinfección sigue, el atacante puede estar entrando con una contraseña válida. Ver `08-credenciales-y-rotacion.md` y los logs de acceso del proveedor de identidad.

## Límites de la terminal compartida

Desde una jailshell no se ven procesos de otros usuarios del sistema (ej. el usuario del servidor web). Un generador corriendo como proceso del servidor web es invisible desde ahí. Si todas las rutas se agotaron, escalar (`01-metodologia-respuesta-incidentes.md`).

## Falsos positivos

- `wordfence-waf.php` vía `auto_prepend_file`. **Gotcha:** si ese archivo falta (migración, desinstalación sucia, o borrado por el atacante para cegar a Wordfence), cada petición da fatal / 500. Tras migrar de hosting, la ruta absoluta en `.user.ini` o `.htaccess` apunta al servidor viejo y tumba el sitio.
- Hooks de WP-Cron de core y plugins conocidos.
- mu-plugins del hosting.
- `.ftpquota` con owner numérico raro (ej. `65535`): lo escribe el demonio FTP.
- Grupo `nobody` en listados de archivos: configuración normal de cPanel. Lo que importa es el **owner**: `find <RUTA_SITIO> -maxdepth 8 ! -user <USUARIO_CPANEL>` debe dar vacío.
