# Interpretación de daños a partir de una imagen

## Qué construir

Se construirá un flujo que reciba una imagen de un vehículo y devuelva una lista
estructurada de daños visibles. Para cada resultado deberá proporcionar, cuando
sea posible:

- tipo de daño;
- región o parte del vehículo afectada;
- máscara o caja delimitadora;
- nivel de confianza;
- explicación breve basada en la evidencia visual disponible.

La salida deberá poder consumirse desde una API y visualizarse sobre la imagen
original en una interfaz de demostración. El sistema deberá permitir también
una respuesta sin daños o no concluyente cuando la evidencia no sea suficiente.

## Por qué

Las máscaras de segmentación son útiles para evaluar un modelo, pero por sí
solas no ofrecen una interpretación completa para una persona usuaria. Esta
funcionalidad convierte la salida visual del pipeline en información legible,
localizada y revisable, manteniendo un vínculo directo con la evidencia que
originó cada conclusión.

## Restricciones y supuestos

- La entrada será una única imagen en un formato admitido y con dimensiones
  válidas.
- La interpretación se limitará a daños visualmente observables.
- Cada afirmación deberá estar asociada a una región de la imagen o marcarse
  explícitamente como no concluyente.
- El sistema no identificará personas, propietarios ni matrículas.
- Una respuesta con baja confianza no se presentará como una conclusión segura.
- Los modelos y versiones utilizados deberán quedar registrados junto al
  resultado.
- Los fallos de validación o inferencia deberán comunicarse sin exponer rutas,
  credenciales ni detalles internos del servidor.

## Criterios de aceptación

1. Una imagen JPEG o PNG válida produce una respuesta estructurada o una lista
   vacía de daños, sin requerir intervención manual durante el procesamiento.
2. Un fichero vacío, corrupto o que no sea una imagen se rechaza con un error de
   validación comprensible.
3. Cada daño devuelto contiene como mínimo una categoría, una confianza y una
   región expresada como máscara o caja delimitadora.
4. Las regiones devueltas se encuentran dentro de las dimensiones de la imagen
   de entrada.
5. La interfaz puede superponer los resultados sobre la imagen y permite
   distinguir visualmente las detecciones individuales.
6. Cuando ninguna predicción supera los umbrales configurados, la respuesta no
   inventa daños y representa explícitamente que no hay resultados concluyentes.
7. La respuesta registra la versión de la estrategia y la configuración mínima
   necesaria para reproducir la ejecución.
