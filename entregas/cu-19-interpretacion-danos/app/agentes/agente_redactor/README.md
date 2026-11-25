# Agente 3 — Redactor del informe

Responsable: Víctor.

Junta los hallazgos del Agente 1 y los costes/cobertura del Agente 2 en un
informe de peritaje en markdown. Las cifras salen siempre del código a partir
de los JSON (nunca las escribe un LLM) y se comprueban automáticamente.

- Spec: [`specs/31-informe-peritaje.md`](../../../specs/31-informe-peritaje.md).
- Guía de partida: [`docs/guias/agente3-informe-guia.md`](../../../docs/guias/agente3-informe-guia.md).
- Datos de entrada de ejemplo: `../ejemplos_contrato/`.

## Uso

Necesita el paquete de la empresa extraído en la raíz del repo
(`piia2_paquete_datos/`, fuera de git) para los nombres de piezas, coches y
pólizas; no usa red ni API Key.

```python
from informe import comprobar_cifras, generar_informe

md = generar_informe(salida_agente1, salida_agente2, hoy="2026-10-14")  # markdown
assert comprobar_cifras(md, salida_agente2) == []  # ningún importe inventado
```

- `generar_informe` valida que las dos salidas son coherentes (mismo
  `image_id`, cada hallazgo en un único grupo, coche y piezas del catálogo) y,
  si no, lanza `ValueError` con el identificador.
- `comprobar_cifras` devuelve los importes en euros del informe que no están
  entre los campos monetarios del Agente 2 (claves `_eur`, `importe_eur` de las
  líneas y `desglose`).
- `diagnostico_rag` (#32) es opcional: con `parcial`, `sin_resultados` o
  `error` el informe se marca como preliminar y lista los temas sin fuentes.
- Los hallazgos fuera del coste sin pieza, sin severidad o sin regla de coste
  se listan aparte, bajo «Requieren revisión humana», y el «Resumen» dice
  cuántos son y si ningún hallazgo es presupuestable (#54, AC-003). La
  cabecera avisa de que solo se analizan los daños que encuentra el detector (#54, AC-011).
- Desde el plan v1.2 de la #54 (AC-014 a AC-019 y AC-021) el informe evita la jerga interna, explica las
  detecciones que descartó el filtro previo, agrupa las citas por fuente, dice «No aplica» en la cobertura
  cuando no hay nada que presupuestar y, si `contexto.vehiculo_origen` viene, dice de dónde sale el coche
  (spec 34 v1.7). Detalle en la sección «Ampliaciones de la #54» de la spec 31.
- La columna «Reparación» muestra la acción de la regla con la que el Agente 2
  presupuesta el daño. Es la propia o, si no la tiene, la de su equivalente,
  con la severidad mínima ([ADR 0008](../../../docs/adr/0008-equivalencias-reglas-coste.md),
  [spec 88](../../../specs/88-equivalencias-reglas-coste.md)). La columna «Daño» sigue
  mostrando la clase detectada, y el informe no menciona las equivalencias.
- `justificaciones` (#97) es opcional. Es el texto que un LLM redacta en el
  Agente 2 a partir de los pasajes del RAG ([ADR 0009](../../../docs/adr/0009-justificacion-llm-normativa.md),
  [spec 97](../../../specs/97-justificacion-llm-normativa.md)). El Agente 3 no llama a ningún
  modelo: solo lo muestra en «Fuentes consultadas».
  - Con `generada`, cada tema lleva su texto y, debajo, sus citas literales con su fuente.
  - Si alguna está `descartada` o `no_generada`, la cabecera lleva el aviso de
    informe preliminar de justificaciones, y el tema muestra sus pasajes y el motivo.
  - Sin el campo, el informe es el de siempre.
  - Un campo mal formado lanza `ValueError` con su nombre. Cuenta como mal formado
    un estado desconocido, un tema que falta o una `generada` con importes en el texto.

## Pruebas y ejemplo

Desde esta carpeta:

```bash
python probar_informe.py   # spec 31 (AC-001 a AC-009 y AC-011 a AC-015) y spec 97 (AC-008 a AC-010)
```

Para ver el informe del ejemplo:

```bash
python -c "import json; from informe import generar_informe; e='../ejemplos_contrato/'; print(generar_informe(json.load(open(e+'agente1_salida.json', encoding='utf-8')), json.load(open(e+'agente2_salida.json', encoding='utf-8'))))"
```
