# 01 — Metodología de respuesta a incidentes en hosting compartido

## Qué es el problema

En una cuenta cPanel compartida, todos los sitios corren bajo el **mismo usuario Unix**. Un sitio comprometido equivale a la cuenta completa comprometida: el atacante puede escribir en cualquier sitio, en el correo, en `~/etc/`, en `~/.ssh/`. Limpiar sitio por sitio sin esa visión garantiza reinfección.

La trampa más cara: **limpiar síntomas mientras el mecanismo de persistencia sigue vivo**. Todo lo que se limpie antes de matar la persistencia se vuelve a llenar.

## Fases (en orden, no saltarse ninguna)

1. **Respaldo.** Home completo + cada base de datos por separado. Contar sitios activos vs. dumps de BD descargados; deben coincidir. Las BD también pueden estar infectadas: respaldarlas no significa que estén limpias.
2. **Inventario.** Mapear todo lo que corre, no solo lo que crees que corre (ver abajo).
3. **Persistencia.** Encontrar y cerrar todo mecanismo que re-ejecute o re-abra acceso (`06-mecanismos-de-persistencia.md`).
4. **Síntomas.** Shells, `.htaccess`, carpetas spam, core inyectado. Primero lo que tiene contenido, después los cascarones vacíos.
5. **Verificación.** Detectores de reinfección en `0` en toda la cuenta.
6. **Credenciales.** Rotación completa (`08-credenciales-y-rotacion.md`).
7. **Base de datos.** Admins fantasma, `options`, posts, Search Console (`07-base-de-datos-comprometida.md`).
8. **Hardening y monitoreo.** Cerrar vectores, correr detectores periódicamente.

## Inventario: lo que no está en la lista también está infectado

Sitios de producción aparecieron **fuera del docroot** (colgados directo del home) y subdominios con WordPress activo que nunca se inventariaron. Ninguno estaba en los barridos.

```
find <HOME> -maxdepth 5 -name wp-config.php 2>/dev/null
```

- WordPress permite `wp-config.php` un nivel arriba de la raíz; una ruta sin `wp-config.php` al lado de `wp-load.php` no significa que no sea WordPress.
- Estructura `wp-admin/ wp-content/ wp-includes/` **sin** `wp-config.php` en ningún nivel = cascarón (sitio huérfano o plantado). Investigar.
- Apps PHP a medida (no WordPress) también son superficie: inventariarlas aparte.
- Si el cliente tiene varias cuentas cPanel, cada una es un filesystem aparte: la que no tiene escáner ni auditoría es el punto ciego más grande.

## Principios

- **Backdoor antes que credenciales.** Rotar con persistencia viva es trabajo perdido. Excepción válida: si la persistencia que justificaba esperar ya se eliminó (ej. llave SSH borrada), rotar el acceso principal antes está bien.
- **Evidencia, no inferencia.** "Directorio no vacío" no es "payload". Descartar tres hipótesis no confirma la cuarta. La investigación sigue abierta hasta ver el inyector en evidencia.
- **Timestamps no bastan.** Se falsifican (`touch`). Sirven para agrupar eventos (muchos archivos con el mismo segundo = evento masivo), no para descartar archivos. Descartar solo por contenido.
- **Contenido antes que cascarones.** En cada zona: primero `! -empty` (puede haber payload vivo), después barrer vacías.
- **Leer antes de borrar.** Logs, archivos sospechosos, directorios. Un `rm` reescribe el mtime del directorio padre y destruye la pista de "qué pasó aquí y cuándo". Registrar `stat` o `ls -la --time-style=full-iso` antes.
- **Simular antes de borrar.** Listar, revisar, luego borrar. Excepción: archivos con hash o firma confirmada.
- **Sin exclusiones globales de "zonas seguras".** Excluir una app completa por generar falsos positivos ocultó una infección activa durante meses. Excluir solo `vendor/`; los falsos positivos se descartan leyendo, no excluyendo.
- **"Sin malware conocido" ≠ "auditado".** El escaneo por firma solo encuentra lo conocido. Un shell escrito a mano sin ofuscación pasa limpio. Reportar el estado real.
- **Verificar después de cada cambio** a `.htaccess` o `wp-config.php`: `curl -sI https://<DOMINIO>/` debe seguir en 200.

## Manejo de evidencia

- Antes de borrar un shell: ruta, tamaño, MD5, mtime, owner/permisos. Anotarlo en el handoff.
- Evidencia sensible (llaves, `wp-config`) se copia **fuera del docroot** o se descarga; nunca como `.bak` dentro de `public_html`.
- Cada sesión cierra con un documento de handoff: qué se hizo, qué se verificó, qué quedó abierto, firmas nuevas, falsos positivos nuevos. Es la fuente de verdad del estado del servidor.

## Reconstrucción de la línea de tiempo

- Agrupar por mtime idéntico entre muchos archivos: revela oleadas de infección que no se ven sitio por sitio.
- Drops en zonas **no alcanzables por HTTP** (`~/etc/`, `~/ssl/keys/`, `~/mail/`, `~/bin/`) prueban acceso a nivel shell/SSH, no solo un webshell.
- `error_log` congelado en una fecha, o con errores repetidos del payload, da una **cota** del evento (ver `05-inyeccion-en-core.md`).
- Pedidos a intervalo regular exacto (ej. cada ~60 s) no son humanos: monitor, beacon o bot. Solo se resuelven con logs de acceso con IP; esos logs rotan rápido, descargarlos al inicio.

## Cuándo escalar

- La reinfección sigue **después** de cerrar persistencia conocida, y las rutas desde terminal se agotaron (ej. un proceso corriendo como el usuario del servidor web, invisible desde la jailshell).
- Opciones: servicio especializado (Sucuri, MalCare) o soporte del hosting con acceso root. No es rendirse, es la herramienta correcta.
- **Ojo (inferencia a verificar por proveedor):** en hosting compartido, un ticket formal de "malware" puede disparar suspensión automática de la cuenta y tumbar todos los sitios. Revisar la política del proveedor antes de abrirlo; pedir accesos técnicos (shell, logs) como soporte técnico, no como incidente.
