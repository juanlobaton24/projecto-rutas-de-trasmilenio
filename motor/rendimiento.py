"""R11: mediciones para el panel de rendimiento.

Método (el mismo del Taller 1): se crean redes falsas cada vez más grandes
(128, 512, 2048 y 8192 estaciones), se corre cada operación y se mide cuánto
tarda. Si al crecer la red el tiempo crece como dice la O grande esperada,
la implementación es coherente.
"""
from time import perf_counter_ns  # reloj de alta precisión (en nanosegundos)

from .estructuras import ordenar, reloj  # Merge Sort propio y conversor minutos -> "HH:MM".
from .red import Red  # La clase principal que se va a medir.
from .simulacion import simular  # La simulación de filas (R10).


def medir():
    """Devuelve una lista: (nombre, complejidad_esperada, nota, [(n, microsegundos), ...])."""
    # Cada operación con la O grande que se espera y una nota que explica la medición.
    operaciones = [
        ("R1 · Búsqueda", "O(log N)", "Las muestras pueden verse planas por el costo fijo de la llamada."),
        ("R2 · Prefijo", "O(log N + k)", "Se limita la salida a 8 nombres."),
        ("R3 · Rango", "O(log N + K)", "El rango medido devuelve todas las estaciones."),
        ("R4 · Próximo bus", "O(log N + log R + D + log S + log H)", "Se mantiene una sola ruta por estación y crecen las paradas y los horarios."),
        ("R5 · Viaje", "O(log N + N + P)", "La ruta larga hace que el planificador recorra una cantidad lineal de paradas."),
        ("R6 · Ranking en caché", "O(k)", "Se copian 8 resultados. La reconstrucción se mide por separado."),
        ("R6 · Reconstrucción", "O(N + M log S + N log N)", "Es una cota superior. En esta muestra los conteos son casi iguales."),
        ("R7 · Insertar parada", "O(log N + log R + S + N + M)", "Se reconstruye el índice de la red."),
        ("R7 · Quitar parada", "O(log R + S + N + M)", "Se quita la primera parada y se reconstruye el índice."),
        ("R8 · Cerrar estación", "O(log N + N)", "Se cierra la primera estación para medir el desplazamiento del arreglo."),
        ("R8 · Reabrir estación", "O(log N + N)", "Se inserta la primera estación en el arreglo ordenado."),
        ("R9 · Deshacer", "O(N + M + S) para editar ruta", "Se deshace una edición. Deshacer un cierre cuesta O(N)."),
        ("R9 · Rehacer", "O(N + M + S) para editar ruta", "Se reaplica una edición de ruta."),
        ("R10 · Filas FIFO", "O(F log N)", "Crecen las filas. Cada fila representa 200.000 personas sin instanciarlas."),
    ]
    # A cada operación se le agrega una lista vacía donde irán los puntos medidos.
    resultados = [(nombre, cota, nota, []) for nombre, cota, nota in operaciones]
    for n in (128, 512, 2048, 8192):  # cada tamaño es 4 veces el anterior
        # Red sintética: n estaciones, una sola ruta "A" que pasa por todas,
        # y n horarios en la primera estación.
        nombres = [f"ESTACION {i:05d}" for i in range(n)]  # "ESTACION 00000", "ESTACION 00001", ... (con ceros para que el orden alfabético sea el numérico).
        red = Red(nombres, [("A", i, nombre) for i, nombre in enumerate(nombres)],  # Ruta "A": (código, orden, estación) para cada estación.
                  [("A", nombres[0], reloj(i)) for i in range(n)])  # n horarios en la primera estación: minutos 0..n-1 como "HH:MM".
        primero, ultimo = nombres[0], nombres[-1]  # Extremos de la ruta, usados como origen/destino en las pruebas.
        filas = [(nombre, 200_000) for nombre in nombres]  # una fila por estación (R10), con 200.000 personas cada una
        red.ranking(8)  # se llena la caché antes de medir "ranking en caché"

        def preparar_rehacer():
            # Deja un cambio listo en la pila de rehacer.
            red.insertar("A", 1, ultimo)  # Hace un cambio...
            red.deshacer()  # ...y lo deshace: queda pendiente para rehacer.

        # Cada prueba es (acción a medir, preparación antes, limpieza después).
        # La preparación y la limpieza NO se miden; solo la acción.
        # El orden de esta lista coincide con el de 'operaciones' (R1, R2, R3...).
        pruebas = [
            (lambda: red.buscar(ultimo), None, None),  # R1: buscar una estación.
            (lambda: red.completar("ESTACION", 8), None, None),  # R2: autocompletar con prefijo, máximo 8.
            (lambda: red.rango(primero, ultimo), None, None),  # R3: rango completo.
            (lambda: red.proximo_bus(primero, "A", reloj(n // 2)), None, None),  # R4: próximo bus a media jornada.
            (lambda: red.viaje(primero, ultimo), None, None),  # R5: viaje de punta a punta.
            (lambda: red.ranking(8), None, None),  # R6: ranking con caché ya llena.
            # Para medir la reconstrucción se invalida la caché cerrando una estación.
            (lambda: red.ranking(8), lambda: red.alternar_estacion(ultimo), red.deshacer),  # R6: preparar = cerrar (invalida la caché); limpiar = deshacer.
            (lambda: red.insertar("A", 1, ultimo), None, red.deshacer),  # R7: insertar parada; luego se deshace.
            (lambda: red.quitar("A", 1), None, red.deshacer),  # R7: quitar parada; luego se deshace.
            (lambda: red.alternar_estacion(primero), None, red.deshacer),  # R8: cerrar estación.
            (lambda: red.alternar_estacion(primero), lambda: red.alternar_estacion(primero), None),  # R8: reabrir (antes se cierra para poder reabrir).
            (red.deshacer, lambda: red.insertar("A", 1, ultimo), None),  # R9: deshacer (antes se hace un cambio).
            (red.rehacer, preparar_rehacer, red.deshacer),  # R9: rehacer (antes se deja un cambio pendiente).
            (lambda: simular(red, filas, 100, 160, 4), None, None),  # R10: 100 buses, cupo 160, uno cada 4 minutos.
        ]
        for i, (accion, preparar, limpiar) in enumerate(pruebas):  # i = número de la prueba (= posición en 'resultados').
            muestras = []  # Tiempos medidos de esta prueba.
            for _ in range(7):  # se repite 7 veces cada medición
                if preparar:  # Si hay preparación, se hace SIN medir.
                    preparar()
                inicio = perf_counter_ns()  # Marca de tiempo antes de la acción.
                accion()  # La operación que se mide.
                muestras.append(perf_counter_ns() - inicio)  # Tiempo transcurrido en nanosegundos.
                if limpiar:  # Deja la red como estaba, SIN medir.
                    limpiar()
            # Mediana: se ordenan las 7 muestras y se toma la del medio (posición 3).
            # La mediana no se daña con una medición rara. /1000 pasa a microsegundos.
            resultados[i][3].append((n, ordenar(muestras, lambda x: x)[3] / 1000))  # Guarda el punto (tamaño, tiempo) de esta operación.
    return resultados  # Una entrada por operación con sus 4 puntos medidos.
