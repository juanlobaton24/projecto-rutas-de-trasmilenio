"""Ordenamiento y búsqueda sobre arreglos.

Este archivo tiene las "herramientas básicas" que usa todo el motor:
  - clave(): deja un nombre de estación en un formato único (mayúsculas, sin tildes).
  - ordenar(): Merge Sort hecho a mano (no se puede usar sorted ni .sort()).
  - inferior(): búsqueda binaria hecha a mano (no se puede usar bisect).
  - leer(): lee un CSV y devuelve solo las columnas pedidas.
  - minutos() y reloj(): pasan de "HH:MM" a minutos y de minutos a "HH:MM".
"""
import csv  # Módulo estándar para leer archivos CSV. Permitido dentro de motor/.


def clave(nombre):
    """Normaliza un nombre para poder compararlo.

    Ejemplo: "  calle   26 " -> "CALLE 26"   y   "Ricaurté" -> "RICAURTE".
    Se usa .replace() (método de str, permitido) para quitar las tildes.
    La Ñ no se toca, así que "NARIÑO" sigue siendo "NARIÑO".
    """
    texto = nombre.upper()  # Pasa todo a mayúsculas: "calle 26" -> "CALLE 26".
    texto = texto.replace("Á", "A").replace("É", "E").replace("Í", "I")  # Quita tildes de A, E, I.
    texto = texto.replace("Ó", "O").replace("Ú", "U").replace("Ü", "U")  # Quita tildes de O, U y la diéresis.
    # .split() parte por espacios (quita los repetidos y los de los bordes)
    # y " ".join(...) vuelve a unir las palabras con un solo espacio.
    return " ".join(texto.split())  # Devuelve el nombre limpio y con espacios simples.


def ordenar(elementos, llave):
    """Merge Sort (divide y vencerás). Devuelve una lista NUEVA ordenada.

    - elementos: la lista que se quiere ordenar.
    - llave: función que dice por qué valor se compara cada elemento
      (por ejemplo lambda fila: fila[0] para ordenar por la primera columna).
    Complejidad: O(n log n). Es estable: si dos elementos empatan,
    se queda primero el que venía primero (por eso se usa <= abajo).
    """
    # Caso base: una lista de 0 o 1 elementos ya está ordenada.
    if len(elementos) < 2:  # Con 0 o 1 elemento no hay nada que ordenar.
        return elementos[:]  # [:] hace una copia (así siempre se devuelve una lista nueva).
    # Dividir: partir la lista en dos mitades.
    mitad = len(elementos) // 2  # Posición central (división entera).
    # Resolver: ordenar cada mitad con recursión.
    izquierda = ordenar(elementos[:mitad], llave)  # Ordena la primera mitad.
    derecha = ordenar(elementos[mitad:], llave)    # Ordena la segunda mitad.
    # Combinar (mezclar): ir tomando el menor de las dos mitades.
    resultado = []  # Aquí se va armando la lista ya ordenada.
    i = j = 0  # i recorre la izquierda, j recorre la derecha (ambos empiezan en 0).
    while i < len(izquierda) and j < len(derecha):  # Mientras queden elementos en AMBAS mitades.
        if llave(izquierda[i]) <= llave(derecha[j]):  # <= (y no <) mantiene la estabilidad ante empates.
            resultado.append(izquierda[i])  # El de la izquierda es menor o igual: pasa primero.
            i += 1                          # Se avanza en la izquierda.
        else:
            resultado.append(derecha[j])    # El de la derecha es menor: pasa primero.
            j += 1                          # Se avanza en la derecha.
    # Lo que sobre de alguna mitad ya está ordenado: se pega al final.
    resultado.extend(izquierda[i:])  # Si sobraron elementos a la izquierda, se agregan.
    resultado.extend(derecha[j:])    # Si sobraron a la derecha, se agregan (solo una de las dos tiene algo).
    return resultado  # Lista nueva, ordenada.


def inferior(arreglo, valor, llave=lambda x: x):
    """Búsqueda binaria del "límite inferior" (lower bound).

    Devuelve la PRIMERA posición del arreglo ordenado cuyo valor es >= valor.
    - Si el valor existe, devuelve su posición.
    - Si no existe, devuelve dónde habría que insertarlo para no dañar el orden.
    - Si todos son menores, devuelve len(arreglo).
    Complejidad: O(log n), porque en cada vuelta se descarta la mitad.
    """
    inicio, fin = 0, len(arreglo)  # Se busca en el intervalo [inicio, fin): fin NO se incluye.
    while inicio < fin:  # Mientras el intervalo tenga al menos un elemento.
        medio = (inicio + fin) // 2  # Posición central del intervalo.
        if llave(arreglo[medio]) < valor:  # El elemento central es MENOR que lo buscado:
            inicio = medio + 1  # la respuesta está a la derecha de medio (medio no sirve).
        else:  # El central es >= valor:
            fin = medio         # medio puede ser la respuesta; se busca a la izquierda (incluyéndolo).
    return inicio  # Cuando inicio == fin, esa es la primera posición con valor >= buscado.


def leer(carpeta, archivo, columnas):
    """Lee un CSV y va entregando (yield) cada fila con las columnas pedidas.

    - carpeta: ruta de la carpeta (sirve tanto un texto como un Path).
    - archivo: nombre del CSV, por ejemplo "rutas.csv".
    - columnas: tupla con los nombres de las columnas que se necesitan,
      en el orden en que se quieren recibir.
    Lanza ValueError si falta una columna o si una fila viene incompleta.
    """
    # f"{carpeta}/{archivo}" funciona con texto y con Path (también en Windows).
    # encoding="utf-8-sig" ignora el BOM que a veces pone Excel al inicio.
    with open(f"{carpeta}/{archivo}", newline="", encoding="utf-8-sig") as entrada:  # Abre el CSV (se cierra solo al salir del with).
        filas = csv.reader(entrada)  # Lector que convierte cada línea en una lista de textos.
        # Primera fila = cabecera. Se le quitan espacios a cada nombre.
        cabecera = [col.strip() for col in next(filas, [])]  # next(...) toma la 1.ª fila; [] si el archivo está vacío.
        # posiciones[k] = número de columna (en el CSV) de columnas[k].
        posiciones = []  # Aquí se guarda en qué columna del CSV está cada columna pedida.
        for columna in columnas:  # Por cada columna que el programa necesita...
            # La cabecera original puede venir en cualquier orden.
            for i, nombre in enumerate(cabecera):  # ...se busca su posición en la cabecera.
                if nombre == columna:  # ¿Es esta la columna pedida?
                    posiciones.append(i)  # Sí: se guarda su posición.
                    break  # Ya se encontró; se deja de buscar.
            else:  # este else es del for: se ejecuta si NO hubo break
                raise ValueError(f"{archivo}: falta la columna {columna}")  # La columna no existe en el CSV.
        # enumerate(filas, 2): la numeración empieza en 2 porque la fila 1 es la cabecera.
        for numero, fila in enumerate(filas, 2):  # Recorre el resto del archivo (los datos).
            if fila:  # se saltan las filas vacías
                if len(fila) != len(cabecera):  # Una fila con distinta cantidad de columnas está dañada.
                    raise ValueError(f"{archivo}: fila {numero} incompleta")  # Se avisa en qué fila está el error.
                yield [fila[i].strip() for i in posiciones]  # Entrega solo las columnas pedidas, sin espacios. yield = generador (lee de a una fila, sin cargar todo en memoria).


def minutos(hora):
    """Convierte "HH:MM" en minutos desde la medianoche. Ej.: "08:30" -> 510.

    Acepta horas extendidas del GTFS (como "25:10" = 1:10 a. m. del día
    siguiente, pero dentro del mismo día de servicio) -> 1510.
    """
    partes = hora.strip().split(":")  # "08:30" -> ["08", "30"] (quitando espacios de los bordes).
    # Debe haber exactamente dos partes, ambas con dígitos, y los minutos con 2 cifras.
    if len(partes) != 2 or not partes[0].isdigit() or len(partes[1]) != 2 or not partes[1].isdigit():
        raise ValueError("Escribe una hora en formato HH:MM.")  # Formato inválido.
    h, m = int(partes[0]), int(partes[1])  # Convierte los textos a números enteros.
    if m >= 60:  # Los minutos solo pueden ir de 00 a 59.
        raise ValueError("Los minutos deben estar entre 00 y 59.")
    return h * 60 + m  # Horas a minutos + minutos. No se limita h a 23: por eso acepta "25:10".


def reloj(valor):
    """Lo contrario de minutos(): 510 -> "08:30"; 1510 -> "25:10"."""
    return f"{valor // 60:02d}:{valor % 60:02d}"  # // da las horas, % da los minutos; :02d rellena con cero a 2 dígitos.
