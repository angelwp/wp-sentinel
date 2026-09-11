# 07 — Base de datos comprometida

## Qué es

La infección no vive solo en archivos. En la BD de WordPress el atacante deja: usuarios administradores propios, código en opciones, spam en posts, eventos de cron y verificaciones de Search Console. **Los escáneres de archivos (incluido el del hosting) no tocan la BD**, así que todo esto sobrevive a una limpieza de archivos perfecta.

Respaldar antes de tocar:

```
<WP> db export <HOME>/respaldo_<SITIO>.sql --path=<RUTA_SITIO>
```

El respaldo va fuera del docroot.

## 1. Admins fantasma

**Detección:**

```
<WP> user list --role=administrator --fields=ID,user_login,user_email,user_registered --path=<RUTA_SITIO>
```

**Confirmación — señales combinadas:**

- Login genérico (`administrator`, `user`, `admin`).
- Sin email, o email que nadie reconoce.
- Fecha de registro dentro de la ventana del ataque, **repetida en varios sitios** de la misma cuenta.

**Remediación:**

```
<WP> user delete <ID> --reassign=<ID_ADMIN_LEGITIMO> --path=<RUTA_SITIO>
```

Anotar la fila (login, email, fecha) antes de borrar. Revisar también usuarios con otros roles creados en la misma fecha.

**Falso positivo:** admins legítimos del equipo con `<CORREO_ADMIN>` o del cliente. Confirmar con quien corresponda, no por intuición.

## 2. `options` secuestradas

```
<WP> option get siteurl --path=<RUTA_SITIO>
<WP> option get home --path=<RUTA_SITIO>
```

Deben ser el dominio propio. Si redirigen a otro, están secuestradas.

Código en opciones (el prefijo de tablas sale de `<WP> db prefix`):

```
<WP> db query "SELECT option_name, LENGTH(option_value) FROM <PREFIJO>options WHERE option_value LIKE '%base64_decode%' OR option_value LIKE '%eval(%'" --path=<RUTA_SITIO>
```

Supuesto: los comandos `<WP> db` necesitan el cliente `mysql` disponible en el servidor. Si no está, usar phpMyAdmin con la misma consulta.

**Falsos positivos:** plugins de snippets y de headers/footers guardan código legítimo en opciones. Revisar qué plugin es dueño de la opción.

## 3. Spam en posts

Truco para sitios en español: buscar un carácter japonés muy común. Cualquier coincidencia es sospechosa.

```
<WP> db search 'の' --all-tables --path=<RUTA_SITIO>
```

También: `<script` con dominios externos desconocidos, posts o páginas creados en la ventana del ataque.

## 4. Cron y código ejecutable

- WP-Cron: ver `06-mecanismos-de-persistencia.md`.
- Snippets (WPCode y similares): revisar la lista en wp-admin; desactivar lo que nadie reconozca.
- `Cron ... could not be saved` en logs es común y casi siempre benigno, pero vive en `options`, territorio que el escáner de archivos no toca: no darlo por descartado sin mirar la lista de eventos.

## 5. Verificación falsa de Google Search Console y sitemaps spam

**Qué es:** el atacante sube `google<hash>.html` a la raíz (o mete una meta `google-site-verification` en el tema/BD), se verifica como propietario del dominio en Search Console y envía sitemaps con sus doorways para acelerar la indexación.

**Detección:**

```
ls <RUTA_SITIO>/google*.html
<WP> db search 'google-site-verification' --all-tables --path=<RUTA_SITIO>
```

Sitemaps XML en la raíz que no genera el plugin SEO del sitio.

**Remediación:**

1. Confirmar con el equipo cuál verificación es la legítima (puede haber una real).
2. Borrar el archivo o meta falsos.
3. En Search Console, quitar al propietario desconocido de la propiedad (borrar el token no siempre lo desverifica de inmediato) y eliminar los sitemaps que no sean tuyos.
4. Que las URLs doorway respondan 404/410 para que Google las saque del índice.

## Orden

La limpieza de BD va **después** de cerrar persistencia y rotar credenciales. Excepción: admins fantasma se borran en cuanto se confirman, porque son acceso activo.

## Falsos positivos (resumen)

- Admins legítimos del equipo o cliente.
- Opciones con código de plugins de snippets / headers.
- Hooks de cron de core y plugins.
- Bloques `wp_scraping_result` en `debug.log`: chequeo post-actualización de core, no ataque.
