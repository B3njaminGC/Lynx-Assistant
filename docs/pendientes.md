# Pendientes: notas técnicas

Función "pendientes al arrancar" de Lynx. Esta página explica cómo está armada; para usarla, mirá el README.

## Estado

| Parte | Qué hace | Estado |
| --- | --- | --- |
| 1 | Archivo de pendientes y parser de órdenes | hecha |
| 2 | Lectura al arrancar y "qué tengo pendiente" | hecha |
| 3 | Agregar, terminar y borrar por voz | hecha |
| 4 | Modo insistente y posponer | hecha |
| 5 | Pestaña "Pendientes", respaldo, versión 1.6 | pendiente |

## Archivos

- `pendientes.py`: guarda y busca. No sabe nada de voz ni de ventanas.
- `pendientes_voz.py`: convierte lo que dijiste en una `Orden` (acción, texto, hora). No toca archivos.
- `pendientes_servicio.py`: el puente con Lynx. Decide cuándo leerlos (5 segundos después de que el micrófono está
  listo, una vez por arranque, y no más de una vez cada 10 minutos aunque Lynx se reinicie) y atiende "qué tengo
  pendiente". No habla si Lynx está despierto, pausado o respondiendo al celular. Sin pendientes, al arrancar calla.
- Las frases fijas ("Tenés estos pendientes.") se pueden preparar con la voz de personaje; el texto de cada pendiente
  siempre suena con una voz de Windows (la de personaje solo sabe frases ya preparadas).
- Mientras Lynx está despierto solo entiende frases fijas, así que el texto libre se pide en dos pasos: decís
  "agregá un pendiente", Lynx pregunta "¿Qué anoto?" y entonces dictás (usa el reconocedor libre). Si decís todo
  junto ("Lynx, agregá pendiente comprar pan") lo toma de una. Para terminar o borrar lo más seguro es el número
  ("terminé el dos") después de que Lynx los leyó.
- Si dos pendientes se parecen, Lynx los dice numerados y pregunta cuál; si no queda claro, no toca nada.
  Borrar siempre pide confirmación (sí/no). Por Telegram no pregunta: el texto va en el mismo mensaje.
- Modo insistente (`pendientes_insistir`, apagado por defecto): cada `pendientes_cada_min` minutos (mínimo 5) vuelve
  a leer los que siguen sin hacer. No habla si Lynx está despierto, pausado o atendiendo al celular, ni lee los
  pospuestos hasta que venza su hora. "Posponé comprar pan una hora" los deja callados; si no decís el tiempo,
  Lynx pregunta "¿Por cuánto tiempo?".
- Lo que dijiste tiene prioridad: tus comandos de `comandos.json` se prueban primero; los pendientes solo
  responden si ninguno coincide.
- `tests/test_pendientes*.py`: pruebas de cada parte.

## Formato de `pendientes.json`

```json
{
  "version": 1,
  "ultimo_id": 3,
  "pendientes": [
    {"id": 3, "texto": "comprar pan", "hecho": false, "creado": "2026-11-19T15:50:00",
     "hecho_en": null, "posponer_hasta": null}
  ]
}
```

- Se guarda escribiendo un archivo nuevo y reemplazando el anterior, así no queda a medias si se corta la luz.
- Si el archivo está dañado, no se pisa: se renombra a `pendientes.roto-AAAAMMDD-HHMMSS.json` y se empieza vacío.
- Los hechos se guardan 30 días y después se limpian.
- Los ids no se reutilizan, aunque borres el último.

## Cómo se busca un pendiente

Lo que dijiste se compara con cada pendiente abierto (sin tildes, sin "el", "de", etc.). El puntaje mezcla cuántas
de tus palabras aparecen (aunque estén un poco mal reconocidas) y qué tan parecido es el texto entero.

- Ninguno llega a 0,55: no hay coincidencia.
- Hay uno claramente mejor: es ese.
- Hay varios casi iguales: Lynx pregunta cuál (hasta tres).
- Si dijiste un número ("el dos"), se usa la lista tal como se leyó en voz alta.

## Órdenes que entiende el parser

| Dicho | Acción |
| --- | --- |
| "terminé comprar pan", "ya hice ...", "marcá como hecho ..." | terminar |
| "agregá pendiente comprar pan", "anotá un pendiente de ..." | agregar |
| "borrá pendiente comprar pan" | borrar |
| "qué tengo pendiente", "leeme mis pendientes" | listar |
| "posponé comprar pan una hora" (también media hora, N minutos, mañana a las 9:00) | posponer |

Si una orden no trae el texto ("terminé"), el parser devuelve la acción con el texto vacío y el motor preguntará cuál.
