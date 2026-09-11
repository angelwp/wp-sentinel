# 11 — Operación segura en la terminal web de cPanel

## Qué es el problema

La remediación se hace en producción, a veces sin SSH, desde la terminal web de cPanel (jailshell). Ahí un comando mal pegado o mal apuntado hace más daño que el malware: tumba sitios, borra correo de clientes o destruye evidencia. Esta es la disciplina que evita eso.

## Particularidades de la terminal web

- **`Ctrl+U` antes de pegar** para limpiar la línea; si no, el pegado se concatena con lo que había.
- **Sin comentarios `#`** en lo que se pega. Pegar solo el comando.
- **Pegado multilínea corrompe saltos de línea.** Un heredoc puede terminar como una sola línea; en un `.htaccess` eso da 500. Para escribir archivos usar `printf '%s\n' 'línea1' 'línea2' > archivo`.
- **Validar lo escrito:** `cat -A archivo` (cada línea termina en `$`) y `php -l archivo.php` para PHP.
- **Comandos pesados abortan** (`ABORTED`): acotar por sitio y con `find -maxdepth` (4–7 según la zona), no sobre todo el home de golpe.
- **SSH externo** en hosting compartido puede requerir que soporte lo habilite; no asumir que existe.
- **PHP de CLI ≠ PHP web** (versión y configuración distintas).
- **WP-CLI** puede requerir ruta completa del binario y `--allow-root`.
- El firewall saliente puede bloquear `api.wordpress.org` y permitir `downloads.wordpress.org`.

## Disciplina de comandos

1. **Un comando a la vez.** Leer el output real antes de decidir el siguiente.
2. **Control positivo** cuando un resultado vacío importa: correr el comando contra algo que sí debería coincidir. Vacío por comando roto se ve igual que vacío por limpio.
3. **Listar antes de borrar** (simulacro). Guardar la lista a archivo si son muchos:

```
find <RUTA> ... > <HOME>/lista_a_borrar.txt
```

4. **Preferir borrados que fallan si hay contenido:** `rmdir` y `find ... -empty -delete` sobre `rm -rf`. Son simulacro y borrado en un paso.
5. **Registrar antes de tocar:** `ls -la --time-style=full-iso` del directorio. Un `rm` reescribe el mtime del padre.
6. **Leer logs antes de borrarlos.** No vuelven.
7. **Verificar después de tocar `.htaccess` o `wp-config.php`:** `curl -sI https://<DOMINIO>/` en 200.
8. **Excepciones al simulacro:** solo archivos con hash o firma confirmada.

## Trampas de shell ya pisadas

- **`~` no se expande dentro de comillas simples.** En `sed -i 'Nr ~/archivo' destino`, sed busca un archivo llamado literalmente `~/archivo`. Usar ruta absoluta.
- **Espacio faltante** entre opción y argumento (`head -c 12"$f"`) produce un comando que no hace lo que crees y puede devolver vacío.
- **Grep sin `--include`** sobre una firma de `.htaccess` también encuentra `.php` sobrescritos con esa firma; si el siguiente paso es `rm`, se lleva archivos legítimos.
- **`chmod`**: el atacante deja archivos en `444` y directorios en `555`. `chmod u+w` antes de editar o borrar; no `777`.
- **Owner vs grupo:** en listados de cPanel el grupo `nobody` es normal. Para buscar archivos de otro dueño: `find <RUTA> -maxdepth 8 ! -user <USUARIO_CPANEL>`.

## Zonas de cuidado extremo

- `<HOME>/mail/` — correo de clientes. Borrar solo el archivo confirmado, nunca carpetas de buzón.
- `<HOME>/etc/` — configuración de correo y dominios de la cuenta.
- Sitios en producción colgados fuera del docroot: se ven como "carpetas raras" en el home y no lo son.
- Kits de reparación propios (`<KIT_CORE>`, `<KIT_PLUGINS>`) y carpetas de cuarentena propias: marcarlos con nombres claros para que ningún barrido los trate como sospechosos.

## Continuidad entre sesiones

Cerrar cada sesión con un handoff: estado del servidor, qué se borró (con respaldos de listas), qué quedó abierto, firmas y falsos positivos nuevos, correcciones al método. La siguiente sesión arranca de ese documento, no de la memoria.

## Falsos positivos

- Grupo `nobody` en listados.
- `.ftpquota` con owner numérico.
- Resultados vacíos de un comando mal escrito (no son "limpio"; ver control positivo).
