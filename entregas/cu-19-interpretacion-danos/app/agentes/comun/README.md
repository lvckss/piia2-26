# Módulo común: equivalencias de reglas de coste

Lo consumen los tres agentes. Solo usa la biblioteca estándar. Decisión: [ADR 0008](../../../docs/adr/0008-equivalencias-reglas-coste.md); plan: [spec 88](../../../specs/88-equivalencias-reglas-coste.md).

| Fichero | Qué hace |
|---|---|
| `equivalencias_reglas.csv` | La tabla, en UTF-8: columnas `clase_origen`, `zona_tipo`, `clase_destino`, `severidad_minima` (vacía si no hay) y `motivo`. Las cuatro equivalencias iniciales y sus motivos están en el [README del Agente 1](../agente_multimodal/README.md#equivalencias-de-reglas-de-coste). |
| `equivalencias.py` | `cargar_equivalencias(ruta=None)` lee y valida la tabla: si falta, está incompleta, tiene una severidad desconocida o una fila duplicada, falla con la ruta y la fila; nunca se ignora en silencio. `regla_efectiva(clase, zona_tipo, severidad, reglas, equivalencias)` devuelve `(clase, severidad)` si hay regla propia, `(clase_destino, severidad_efectiva)` si hay una equivalencia cuyo destino existe, y `None` («sin regla») en cualquier otro caso. |
| `probar_equivalencias.py` | Siete pruebas, citando AC-001, AC-002 y AC-009 de la spec 88. Se ejecuta con `python probar_equivalencias.py` desde esta carpeta. La de AC-001 usa `reglas_dano.csv` del paquete de la empresa y se salta con un aviso si falta. |

## Cómo se importa

El repositorio no usa paquetes Python: se añade esta carpeta a `sys.path` y se importa por nombre. Lo hace `catalogo.py` del Agente 1; los demás agentes pueden hacer lo mismo:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "comun"))
from equivalencias import cargar_equivalencias, regla_efectiva
```
