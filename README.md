# Mapa de rutas de TransMilenio

Proyecto académico en Python con una aplicación de escritorio Tkinter, un motor independiente y un conversor de GTFS. Incluye una red de demostración con nombres de estaciones conocidos y rutas y horarios simulados.

## Estructura del repositorio

```
Proyecto_DA/
├── app.py               # Interfaz de escritorio (Tkinter)
├── mapa.py              # Dibujo esquemático del mapa
├── convertir_gtfs.py    # Conversor de GTFS a los tres CSV
├── motor/               # Motor independiente (código comentado línea a línea)
│   ├── estructuras.py   # Merge Sort, búsqueda binaria, lectura de CSV, horas
│   ├── red.py           # Clase Red: estaciones, rutas, viajes, ranking, deshacer
│   ├── simulacion.py    # Fila de abordaje (R10)
│   └── rendimiento.py   # Mediciones del panel de rendimiento (R11)
├── datos/real/          # estaciones.csv, rutas.csv, horarios.csv
└── pruebas/             # Pruebas automáticas (unittest)
```

**Orden sugerido para estudiar el motor:** `estructuras.py` → `red.py` → `simulacion.py` → `rendimiento.py`.

## Ejecutar

Necesitas Python 3.10 o posterior con Tkinter. Puedes comprobar que abre una ventana con `python3 -m tkinter`. Desde la carpeta del proyecto:

```sh
python3 app.py                       # usa datos/demo, o datos/real si no hay demo
python3 -m unittest discover -s pruebas -v
```

- **Viaje** permite elegir estaciones en el mapa o escribir sus nombres. El itinerario con menos paradas se resalta en amarillo e indica el punto de transbordo cuando corresponde.
- **Búsqueda** incluye consulta de estado por nombre exacto, sugerencias abiertas y rangos alfabéticos inclusivos. El diagnóstico exacto distingue «Cerrada» de «No existe». Las búsquedas de estaciones disponibles excluyen las cerradas.
- **Operador de red** usa las credenciales académicas `Pidove` y `Carracosta`. Las ediciones y el historial viven durante la sesión. Para insertar, indica el número de la parada anterior y el nombre de una estación existente. «Ver en sentido inverso» invierte la visualización del recorrido. Cada código tiene un único sentido de servicio.
- **Simular abordaje** admite una demanda inicial distinta por estación y una serie independiente de buses por fila. El primer bus sale en el minuto cero. Los pasajeros se numeran por llegada y el bus número *b* atiende consecutivamente desde `(b−1) × cupo + 1` hasta `b × cupo` o hasta agotar la fila.
- **Rendimiento** grafica medianas en microsegundos sobre 128, 512, 2048 y 8192 estaciones. Excluye la carga de datos y la preparación de cada muestra. Muestra por separado los aciertos de caché y la reconstrucción del ranking. Las cotas de peor caso pueden superar el crecimiento observado. Las muestras pequeñas incluyen el costo fijo de la llamada y del reloj.

## Contrato del motor

El script de calificación hace `from motor import Red, simular_fila` y usa estas llamadas, todas definidas en `motor/red.py` y `motor/simulacion.py`:

| Llamada | Req. | Qué hace por dentro |
| --- | --- | --- |
| `Red(carpeta)` | carga | Lee `estaciones.csv`, `rutas.csv` y `horarios.csv` de la carpeta |
| `red.estado(nombre)` | R1 | Devuelve `"Abierta"`, `"Cerrada"` o `"No existe"` |
| `red.autocompletar(prefijo, k)` | R2 | Usa `completar` |
| `red.rango(desde, hasta)` | R3 | Corte del arreglo de abiertas |
| `red.proximo_bus(estacion, ruta, hora)` | R4 | Minuto del siguiente bus o `None` |
| `red.viaje(origen, destino)` | R5 | Lista de tramos `(ruta, [estaciones])` |
| `red.ranking(k)` | R6 | Lista `(nombre, buses)` |
| `red.agregar_parada(ruta, nueva, despues_de)` | R7 | Busca `despues_de` en la ruta (búsqueda lineal, O(S)) y usa `insertar` |
| `red.quitar_parada(ruta, estacion)` | R7 | Busca la estación en la ruta y usa `quitar` |
| `red.recorrido(ruta, al_reves=False)` | R7 | Paradas en su sentido o al revés |
| `red.cerrar(nombre)`, `red.reabrir(nombre)` | R8 | Usan `alternar_estacion`; devuelven `False` si no había nada que cambiar |
| `red.deshacer()`, `red.rehacer()` | R9 | Dos pilas de cambios |
| `simular_fila(llegadas, frecuencia, capacidad)` | R10 | Cola FIFO con un arreglo y dos índices; devuelve `(minuto, suben, quedan)` por bus |

## Datos reales o red del profesor

Usa la fecha de servicio que cubra el ZIP suministrado por el curso. La fecha del ejemplo se puede reemplazar. El [catálogo de Datos Abiertos Bogotá](https://datosabiertos.bogota.gov.co/dataset/especificacion-gtfs-general-transport-feed-specification-sitp) publica el conjunto GTFS del SITP. La copia histórica de julio de 2021 no está incluida en este proyecto.

```sh
python3 convertir_gtfs.py /ruta/al/gtfs.zip datos/real --fecha 2021-07-14
python3 app.py --datos datos/real
```

El filtro opcional `--agencia ID` selecciona por `agency_id`. El conversor combina el calendario y sus excepciones para elegir los viajes de un día. Agrupa cada línea por sentido y secuencia de paradas, de modo que las variantes tengan identificadores distintos. Usa el nombre de la estación padre cuando existe y normaliza los nombres a mayúsculas sin acentos vocálicos, conservando la Ñ. Las frecuencias GTFS se expanden a salidas aproximadas al minuto. Si falta una hora en una parada, se conserva la parada en el itinerario y se omite su registro horario.

También puedes pasar directamente una carpeta con los CSV del profesor, en UTF-8 y con estas cabeceras:

| Archivo | Columnas |
| --- | --- |
| `estaciones.csv` | `nombre` |
| `rutas.csv` | `ruta,orden,estacion` |
| `horarios.csv` | `ruta,estacion,hora` |

`25:10` se conserva como hora extendida del mismo día de servicio. Al consultar puedes escribir horas extendidas. El horario de partida del planificador usa la hora local de Bogotá y la llegada suma la espera de cada bus y tres minutos estimados por segmento. Los CSV no vinculan los horarios a viajes individuales. La estimación de tres minutos por segmento sigue siendo aplicable después de editar una ruta. Agregar una parada habilita los horarios que ya existan para esa pareja ruta-estación. Si no hay, el motor puede encontrar el itinerario por paradas, pero no calcular la espera. Las estaciones cerradas se pueden atravesar en el mismo vehículo, aunque se excluyen como puntos de abordaje, descenso o transbordo. Los segmentos que se atraviesan siguen contando en la longitud del viaje. Si hay empate, se prefiere un viaje directo.

## Decisiones de R1 a R10

Dentro de `motor/` se usan arreglos, búsqueda binaria y ordenamiento por mezcla implementados en Python. Los recorridos guardan identificadores enteros de estaciones, con un índice inverso de apariciones por estación. En las cotas, `N` es el número de estaciones, `R` el número de rutas, `M` el total de apariciones de estaciones en rutas, `S` el tamaño del recorrido o el número de estaciones con horario en una ruta, `H` el tamaño del horario de una pareja ruta-estación y `D` el número de apariciones en rutas activas de la estación consultada. Se trata el tamaño de cada nombre como acotado.

| Req. | Estructura y algoritmo | Alternativa considerada | Tiempo |
| --- | --- | --- | --- |
| R1 | Búsqueda binaria sobre el arreglo ordenado de estaciones abiertas. El diagnóstico usa el catálogo ordenado completo. | Escanear todo en cada consulta haría lineal la operación más común. | O(log N) |
| R2 | Búsqueda del límite inferior y lectura consecutiva hasta agotar el prefijo o el cupo. | Un trie exige otra estructura para mantener las estaciones activas y la enumeración ordenada. | O(log N + k), con hasta `k` resultados |
| R3 | Dos búsquedas binarias y un corte del arreglo de abiertas. | Un escaneo completo revisaría estaciones fuera del rango. | O(log N + K), con `K` resultados |
| R4 | Índice de apariciones y horarios ordenados. Se encuentra la primera salida mayor o igual a la hora consultada. | Recorrer cada salida revisaría cientos de horarios en rutas frecuentes. | O(log N + log R + D + log S + log H) |
| R5 | Se recorren los sufijos desde el origen y los prefijos hasta el destino. En cada estación abierta se guardan los dos mejores primeros tramos de rutas distintas para comparar transbordos. | Probar todos los pares de recorridos repite trabajo en cada punto de intercambio. | O(log N + N + P), con `P` posiciones examinadas, incluidas las repetidas en distintos sufijos o prefijos |
| R6 | Conteo por estación usando los horarios activos y mezcla por cantidad descendente y nombre. El ranking se cachea hasta la próxima mutación. | Ordenar en cada consulta penaliza las lecturas frecuentes. | O(k) con caché. O(N + M log(S + 1) + N log N) al reconstruir |
| R7 | Inserción o eliminación posicional en el arreglo y reconstrucción del índice inverso. El recorrido inverso se genera al solicitarlo. | Una lista enlazada ahorra el desplazamiento después de hallar el nodo, pero complica el acceso por posición y sigue requiriendo actualizar el índice. | O(log N + log R + S + N + M) para insertar. Quitar omite log N. Ver cuesta O(log R + S) |
| R8 | Estado booleano por estación y modificación por búsqueda binaria y desplazamiento en el arreglo de abiertas. | Mantener cerradas en el arreglo de consultas obliga a saltarlas y puede degradar prefijos y rangos pequeños. | O(log N + N) |
| R9 | Dos pilas con comandos reversibles y la posición anterior de cada edición. Las nuevas ediciones descartan la pila de rehacer. | Las copias completas crecerían con toda la red por cada cambio. | O(N + S + M) al editar rutas, O(N) al cambiar el estado de una estación |
| R10 | Cola implícita por estación. Los intervalos de identificadores representan el orden FIFO y la división entera calcula cuántos buses alcanzan a abordar la fila. | Crear y desencolar un objeto por pasajero añade memoria y trabajo lineales en el número de personas. | O(F log N) con `F` filas, incluyendo validar sus estaciones. O(F) de memoria para los resultados |

El cierre de rutas del mapa mental es una operación adicional. Quita sus apariciones del índice público hasta la reapertura e invalida el ranking. El mapa es esquemático y usa únicamente los nodos y aristas de los CSV.
