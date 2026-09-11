# 09 — Vectores de entrada y hardening

## Qué es el problema

La persistencia explica cómo el atacante **se queda**; el vector explica cómo **entró**. Son cosas distintas: una llave SSH plantada es persistencia, no entrada. Si no se cierra el vector, el mismo atacante (o el siguiente bot) vuelve a entrar por ahí.

## Vectores observados y candidatos

| Vector | Nivel de certeza en el caso | Cómo cerrarlo |
|---|---|---|
| Tema premium desactualizado / nulled en un dominio **reconectado** tras años sin DNS | Confirmado como origen | Al reactivar un sitio viejo: actualizar o reemplazar el tema **antes** de apuntar DNS. La ventana entre reconexión y actualización es la que se explota. |
| Contaminación cruzada entre sitios del mismo usuario Unix | Confirmado | No se cierra en hosting compartido; se mitiga con menos sitios por cuenta, sitios huérfanos borrados y detectores periódicos. |
| SQL injection en app PHP a medida | Confirmado como vulnerabilidad; no confirmado como entrada | Ver abajo. |
| FTP anónimo con carpeta `incoming/` en `777` | Candidato viable, no confirmado | Permisos `700` y desactivar FTP anónimo. |
| Contraseña filtrada | Sin evidencia a favor ni en contra | Rotación + 2FA + revisar logs de identidad. |

Una licencia legítima y al día del mismo tema en otro sitio **no** es sospechosa por sí sola: el problema es la versión vieja o la copia nulled.

## SQL injection en apps a medida

**Patrón:** parámetros de `$_GET` concatenados directo en `mysqli_query`. Pasarlos por `base64` no sanitiza nada, solo ofusca el payload en la URL.

**Remedio:**

- Valores → sentencias preparadas (`mysqli_prepare` + `bind_param`, o PDO).
- **Nombres de tabla o columna no se pueden parametrizar:** validarlos contra una lista blanca fija en el código.
- Código de desarrollo en producción (rutas `C:/...`, tokens hardcodeados, scripts rotos) se retira. Si no funciona en producción, solo aporta superficie.

## Hardening — checklist

**Archivos sensibles fuera del docroot**
- `.env`, respaldos (`.bak`, `.sql`, `.zip`), llaves, exportaciones. Mientras no se puedan mover, bloquearlos:

```
printf '%s\n' '<Files .env>' 'Require all denied' '</Files>' >> <RUTA_SITIO>/.htaccess
```

- Verificar: `curl -sI https://<DOMINIO>/.env` debe dar **403**. Un **406** es el WAF del hosting (mod_security), no un control tuyo: puede cambiar sin aviso, no contar con él.

**Debug apagado**
- `WP_DEBUG` y `WP_DEBUG_LOG` en `false` en producción. `wp-content/debug.log` es público por defecto y filtra rutas y errores.
- Leer el `debug.log` antes de borrarlo: puede tener evidencia (o puro ruido de auto-updates).

**Permisos**
- Directorios `755`, archivos `644`. Nunca `777`.
- Tras la limpieza, buscar lo que el atacante dejó en solo-lectura para proteger sus archivos:

```
find <RUTA_SITIO> -maxdepth 6 \( -perm 444 -o -perm 555 \) 2>/dev/null | head -n 50
```

**WordPress**
- `define('DISALLOW_FILE_EDIT', true);` en `wp-config.php` (quita el editor de temas/plugins de wp-admin).
- Borrar temas y plugins inactivos; borrar sitios y BD huérfanos. Todo lo que no se usa es superficie sin dueño.
- Plugins premium solo desde el proveedor oficial, nunca nulled.
- Plugins de file manager: desinstalar si no se usan.
- 2FA para admins.

**Cuenta**
- Inventario completo de todo lo que corre (`01-...`), incluidos sitios fuera del docroot y subdominios.
- Detectores de reinfección (`02-...`, `03-...`) corridos periódicamente.
- Escáner de archivos activo en **todas** las cuentas del cliente, no solo en una.

## Falsos positivos

- Apps a medida con `base64_decode`, `move_uploaded_file`, `eval` de librerías (PDF, QR): legítimo si se lee y se entiende. No es motivo para excluir la app de los barridos.
- Temas premium licenciados y al día.
