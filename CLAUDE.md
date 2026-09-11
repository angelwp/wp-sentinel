# wp-sentinel

Spec driven development. La fuente de verdad del proyecto es [docs/SPEC.md](docs/SPEC.md) — congelado en v1.1.
Cualquier cambio de alcance, arquitectura o criterios de aceptación se anota ahí, en "Cambios al spec", no en otro lado.

- `docs/SPEC.md` — especificación completa: objetivo, stack, arquitectura, endpoints, límites, pruebas mínimas, variables de entorno.
- `knowledge/` — corpus de conocimiento operativo (seguridad WordPress / hosting compartido) que se carga completo al `system` prompt. No editar sin revisar §12 del spec (reglas de contenido: cero dominios reales, IPs, credenciales o material identificable de clientes).
- Antes de implementar cualquier paso, revisar §13 del spec (orden de trabajo) y no saltarse pasos.
- No-objetivos (§2) son definitivos para esta versión: no agregar login, RAG, panel admin, etc. sin que el usuario cambie el spec primero.
