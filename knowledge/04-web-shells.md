# 04 — Web shells y file managers maliciosos

## Qué es

Un PHP que da control remoto del servidor: navegar el filesystem, subir archivos, editar, cambiar permisos, ejecutar comandos. Es la herramienta con la que el atacante vuelve a entrar y a sembrar todo lo demás. En hosting compartido, un shell en un sitio controla **todos** los sitios de la cuenta.

Tipos observados:

| Tipo | Rasgos | Ubicación típica |
|---|---|---|
| Shell `wk/index.php` | 56,749 bytes exactos, MD5 `c1db092890378513b65609a45f636f43` | Carpetas `wk/`, incluso dentro de `~/mail/` (buzones de clientes) |
| File manager "Sind3" | `index.php` de ~56 KB, doble `eval`, clave XOR `XyZ@2024` | Carpetas hex en la raíz del sitio; a veces servido como home del sitio |
| Shell con funciones en caracteres coreanos / bengalíes | Marcador `a22bcS0vMzEJElwPNAQA`, clase `fa-fluidicon`, `move_uploaded_file` | Temas, plugins, uploads |
| Shell AES | `$_REQUEST["k"]` + `openssl_decrypt` AES-256-CBC: ejecuta lo que llega cifrado en el parámetro | Archivos sueltos o inyectado en archivos existentes |
| Nombres de la whitelist AnonymousFox | `lock360.php`, `radio.php`, `adminfuns.php`, `cjfuns.php`, etc. | Cualquier directorio (ver `02-...`) |

Los shells fuera del docroot (ej. en `~/mail/`) **no se ejecutan por HTTP**: son copias de respaldo del atacante para re-sembrar. Sobreviven meses porque ni el escáner del hosting ni Wordfence revisan esas rutas.

## Cómo se detecta

Barrido por firmas de contenido:

```
grep -rlE --include="*.php" --exclude-dir=vendor "a22bcS0vMzEJElwPNAQA|_REQUEST\[.k.\]|@include *base64_decode|eval *\( *(base64_decode|gzinflate|str_rot13)" <RUTA_SITIO>/ 2>/dev/null | head -n 20
```

Por tamaño exacto + hash en toda la cuenta (rápido, porque `-size` filtra antes de hashear):

```
find <HOME> -maxdepth 8 -type f -size 56749c -exec md5sum {} + 2>/dev/null | grep c1db092890378513b65609a45f636f43
```

PHP fuera del docroot (hay legítimos; revisar la lista, no borrarla):

```
find <HOME> -maxdepth 6 -type f -name "*.php" -not -path "<DOCROOT>/*" 2>/dev/null | head -n 50
```

Ampliar el grep de ofuscación cuando el básico sale limpio: `gzuncompress`, `assert(`, `create_function`, `preg_replace` con modificador `/e`, variables llamadas como función (`$f(`), cadenas hex largas.

## Cómo se confirma

- **Hash idéntico** a una firma conocida = malware confirmado. Borrado directo, sin simulacro.
- Leer sin ejecutar: `head -c 3000 archivo.php`. Nunca abrirlo por el navegador.
- Funcionalidad de file manager (listar directorios, subir, `chmod`) sin autenticación, en una carpeta con nombre aleatorio = shell.

## Cómo se remedia

1. **Antes de borrar, registrar el directorio:** `ls -la --time-style=full-iso <carpeta>` y `stat` del archivo. El `rm` reescribe el mtime del directorio padre; si ese mtime era la pista (algo tocó esa carpeta a una hora concreta), se pierde para siempre.
2. Anotar ruta, tamaño, MD5, mtime en el handoff.
3. Borrar.
4. **Barrer la cuenta completa por el mismo hash o firma.** Donde hay uno, suele haber más.
5. Si el shell estaba **inyectado dentro de un archivo legítimo**, no borrar el archivo: reemplazarlo desde fuente limpia (`05-inyeccion-en-core.md`).
6. Si el sitio mostraba texto raro en vez de HTML (ej. `Order allow,deny`), verificar con `curl -s https://<DOMINIO>/ | head -5` que ya sirve el `index.php` correcto.
7. Extremo cuidado en `~/mail/` y `~/etc/`: un borrado mal apuntado destruye correo de clientes y no hay deshacer. Borrar solo el archivo confirmado, nunca carpetas completas del buzón.

## Falsos positivos

Funciones "peligrosas" con uso legítimo:

- phpseclib (`EvalBarrett`, `Blowfish` y similares), sodium_compat.
- `class-wpcode-snippet-execute.php` de WPCode: ejecuta snippets por diseño. Legítimo, pero es un vector a auditar en la BD.
- `Chain.php` de WPForms con `str_rot13` en un método/PHPDoc, no en ejecución.
- Archivos del propio scanner de Wordfence (contienen firmas de malware como datos).
- JS minificado (patrones parecidos a ofuscación).
- Apps a medida con `base64_decode` o `move_uploaded_file` para formularios de carga.
- Plugins de file manager legítimos (ej. WP File Manager): no son malware, pero son un riesgo real; desinstalar si no se usan.

Regla: un falso positivo se descarta **leyendo el archivo**, nunca excluyendo la carpeta de los barridos. La única exclusión permanente es `vendor/`.
