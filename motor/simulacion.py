"""R10: fila de abordaje en hora pico.

Hay dos funciones:
  - simular(): la que usa la app (pestaña "Simular abordaje").
  - simular_fila(): la que pide el contrato del profesor (diapositiva 10).
"""
from .estructuras import ordenar  # Merge Sort propio (el punto "." indica "de este mismo paquete").


def simular(red, filas, buses, cupo, intervalo):
    """Cada estación dispone de una serie independiente de salidas.

    Una fila contiene el nombre y su demanda inicial. Los pasajeros se
    identifican por su posición en la fila y se abordan por tramos FIFO.

    IDEA (cola implícita): no se crea un objeto por pasajero. Si hay 200.000
    personas, la persona número p es solo un número. El bus 1 lleva a las
    personas 1..cupo, el bus 2 a cupo+1..2*cupo, etc. (primero en llegar,
    primero en subir = FIFO). Con división entera se sabe cuántos buses se
    necesitan, sin recorrer persona por persona.

    Parámetros:
      - filas: lista de (nombre_estacion, personas_en_fila).
      - buses: cuántos buses salen de cada estación.
      - cupo: personas por bus.
      - intervalo: minutos entre un bus y el siguiente (el primero sale en el minuto 0).
    Devuelve, por estación:
      (nombre, personas, buses_usados, subieron, quedan, minuto_ultimo_bus,
       primera_persona_del_ultimo_bus)
    """
    if buses < 1 or cupo < 1 or intervalo < 1:  # Los tres parámetros deben ser al menos 1.
        raise ValueError("Buses, cupo e intervalo deben ser positivos.")
    resultado = []  # Aquí se acumula una tupla de resultados por cada estación.
    for nombre, pasajeros in filas:  # Cada fila es (nombre de estación, personas esperando).
        # Solo se puede abordar en una estación abierta (búsqueda binaria, O(log N)).
        if not red.buscar(nombre):  # buscar() es True solo si la estación existe Y está abierta.
            raise ValueError(f"{nombre}: selecciona una estación abierta.")
        if pasajeros < 0:  # No puede haber una cantidad negativa de personas.
            raise ValueError("La demanda debe ser cero o positiva.")
        # Buses necesarios = techo(pasajeros / cupo), hecho con división entera.
        # (Truco: sumar cupo-1 antes de dividir equivale a redondear hacia arriba.)
        necesarios = (pasajeros + cupo - 1) // cupo
        # No se pueden usar más buses de los que hay (se evita min()).
        usados = necesarios if necesarios < buses else buses  # Es el menor entre necesarios y disponibles.
        subieron = usados * cupo  # Si todos los buses usados van llenos, suben usados*cupo personas.
        if subieron > pasajeros:  # el último bus puede ir sin llenarse
            subieron = pasajeros  # Entonces suben solo las que había.
        # El bus número b sale en el minuto (b - 1) * intervalo.
        ultimo = (usados - 1) * intervalo if usados else None  # Minuto del último bus usado (None si no salió ninguno).
        # El último bus empieza a recoger desde la persona (usados - 1) * cupo + 1.
        primero_ultimo_bus = (usados - 1) * cupo + 1 if usados else None  # Número de la primera persona que subió al último bus.
        resultado.append((nombre, pasajeros, usados, subieron, pasajeros - subieron, ultimo, primero_ultimo_bus))  # pasajeros - subieron = los que quedan esperando.
    return resultado  # Lista con una tupla por estación.


def simular_fila(llegadas, frecuencia, capacidad):
    """R10 con la firma del contrato: simular_fila(llegadas, frecuencia, capacidad).

    ATENCIÓN: el enunciado dice exactamente qué recibe y qué devuelve esta
    función. Esta versión SUPONE lo siguiente (revisarlo con el enunciado):
      - llegadas: lista con el minuto en que llega cada pasajero a la fila.
      - frecuencia: cada cuántos minutos sale un bus (el primero en el minuto 0).
      - capacidad: cuántas personas caben en cada bus.
      - Devuelve una lista con un elemento por cada bus que se lleva gente:
        (minuto_de_salida, personas_que_suben, personas_que_quedan_en_fila).

    IDEA: cola FIFO hecha con un arreglo y dos índices (como en BFS):
      - 'fondo' avanza cuando una persona llega a la fila,
      - 'frente' avanza cuando una persona se sube a un bus.
    Nadie se crea ni se borra: cada persona es una posición del arreglo.
    Costo: O(P + B), con P = pasajeros y B = buses que salen con gente
    (más O(P log P) solo si las llegadas no vienen ordenadas).
    """
    if frecuencia < 1 or capacidad < 1:  # Ambos deben ser positivos.
        raise ValueError("La frecuencia y la capacidad deben ser positivas.")
    llegadas = list(llegadas)  # Copia en lista (así no se modifica lo que mandó quien llama).
    total = len(llegadas)  # Cantidad total de pasajeros.
    # Las personas suben en orden de llegada: se revisa si ya vienen ordenadas
    # (una sola pasada) y solo si no lo están se ordenan con Merge Sort.
    for i in range(1, total):  # Compara cada llegada con la anterior.
        if llegadas[i] < llegadas[i - 1]:  # Si alguna es menor que la anterior, la lista está desordenada.
            llegadas = ordenar(llegadas, lambda x: x)  # Se ordena por el minuto mismo.
            break  # Ya está ordenada; no hace falta seguir revisando.

    salidas = []  # Resultado: una tupla por cada bus que se lleva gente.
    frente = 0   # primera persona que todavía está en la fila
    fondo = 0    # cuántas personas han llegado hasta ahora
    minuto = 0   # hora de salida del bus actual
    while frente < total:  # Mientras falte alguien por subirse a un bus.
        # 1) Entran a la fila todos los que llegaron antes o justo cuando sale el bus.
        while fondo < total and llegadas[fondo] <= minuto:  # Avanza 'fondo' sobre los que ya llegaron.
            fondo += 1
        en_fila = fondo - frente  # Personas esperando ahora = llegadas acumuladas - las que ya subieron.
        if en_fila == 0:  # Nadie esperando en este momento:
            # Fila vacía: se salta directo al primer bus después de la próxima llegada
            # (así no se simulan miles de buses vacíos).
            siguiente = llegadas[fondo]  # Minuto de la próxima persona en llegar.
            minuto = ((siguiente + frecuencia - 1) // frecuencia) * frecuencia  # Redondea hacia arriba al siguiente múltiplo de la frecuencia (siguiente bus).
            continue  # Vuelve a empezar el ciclo con ese nuevo minuto.
        # 2) Suben los primeros de la fila, hasta llenar el bus.
        suben = capacidad if en_fila > capacidad else en_fila  # Suben a lo sumo 'capacidad' personas.
        frente += suben  # El frente de la cola avanza: esas personas ya se fueron.
        salidas.append((minuto, suben, en_fila - suben))  # Se anota: minuto, cuántos subieron y cuántos quedaron.
        # 3) Sale el siguiente bus.
        minuto += frecuencia  # El próximo bus sale 'frecuencia' minutos después.
    return salidas  # Lista de (minuto, suben, quedan) por cada bus con pasajeros.
