# 08 — Credenciales y rotación

## Qué es el problema

Tras un compromiso hay que asumir que el atacante leyó todo lo legible: `wp-config.php` de cada sitio, archivos `.env`, tokens en código, contraseñas guardadas. Rotar es obligatorio. Rotar **demasiado pronto** es inútil: si hay persistencia viva (llave SSH, shell, admin fantasma), el atacante vuelve a leer las nuevas.

## Cuándo rotar

- **Regla general:** después de cerrar toda persistencia (`06-...`).
- **Excepción razonada:** si la persistencia que justificaba esperar ya se eliminó (ej. la llave SSH plantada, que sobrevivía a cambios de contraseña), rotar el acceso principal (cPanel) antes es correcto. El resto (BD, admins WP) espera al cierre completo.

## Qué rotar (inventario completo)

| Credencial | Notas |
|---|---|
| cPanel | En algunos proveedores solo se cambia desde el portal de cliente, no desde cPanel. El reset suele arrastrar la **cuenta FTP por defecto**. |
| Cuentas FTP adicionales | Listar en cPanel. Las cuentas especiales del sistema (`<USUARIO_CPANEL>`, `<USUARIO_CPANEL>_logs`, `anonymous@<DOMINIO>`, `ftp@<DOMINIO>`) no se pueden borrar; no son del atacante. |
| Usuario de BD de cada sitio | El script de rotación **debe actualizar el `wp-config.php` de cada sitio** o tumba sitios. Leerlo antes de correrlo y verificar que cubra los `wp-config.php` fuera del docroot. |
| Admins de WordPress | Todos los sitios. |
| Salts de WordPress | Invalida sesiones abiertas (incluidas cookies robadas). `<WP> config shuffle-salts --path=<RUTA_SITIO>`; puede fallar si el servidor no sale a `api.wordpress.org`, en ese caso generarlas y editarlas a mano. |
| Secretos de apps | `.env` (SMTP, APIs), tokens hardcodeados en código (ej. almacenamiento en la nube). Se rotan **en el proveedor del servicio**, no solo en el archivo. |
| Cuenta de identidad del admin | Si el acceso al hosting es por SSO (Google, etc.), esa cuenta es la llave maestra: 2FA obligatorio y revisar sus logs. |

## Secretos expuestos: la protección no es retroactiva

Si un `.env` o un archivo con tokens estuvo accesible por HTTP durante la ventana del ataque, **asumir que se leyó**. Bloquearlo ahora (403) protege hacia adelante, no hacia atrás. Rotar.

## Logs del proveedor de identidad — con fecha de caducidad

Para buscar accesos no autorizados a la cuenta de administración:

- Google Workspace: Admin console → Reporting → Audit and investigation → **User log events**. Filtrar por la cuenta admin y la ventana del ataque; revisar IPs y ubicaciones.
- Retención: Google Workspace guarda la mayoría de logs de auditoría **alrededor de 6 meses** y no se puede extender desde la consola. Revisarlos antes de que la ventana del ataque se purgue. Para conservarlos más tiempo, exportarlos.

## Reglas de manejo

- **Respaldos de `wp-config.php` nunca como `.bak` dentro del docroot.** Apache lo sirve como texto plano y expone las credenciales de BD. Van fuera de `public_html`.
- **No crear credenciales que no se van a usar.** Una contraseña de respaldo para un portal al que se entra por SSO es superficie extra sin beneficio.
- Mostrar nombres de archivo, no contenido, cuando se busca en archivos con credenciales (`grep -l` en vez de `grep`), para no volcar contraseñas en pantalla ni en logs.
- 2FA en toda cuenta con privilegio (identidad, portal del hosting, admins WP).

## Falsos positivos

- Cuentas FTP especiales del sistema listadas en cPanel.
- Admins legítimos del equipo que comparten un correo de sistemas: no son fantasma, pero sí son una credencial compartida entre todos los sitios. Si se filtra, abre todos; considerar credenciales distintas por sitio.
