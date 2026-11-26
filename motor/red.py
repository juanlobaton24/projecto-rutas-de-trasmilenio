"""La red de TransMilenio: estaciones, rutas, horarios y todas las operaciones R1 a R9.

IDEA GENERAL DE LAS ESTRUCTURAS (todo con listas usadas como arreglos):
  - self.nombres     -> arreglo ORDENADO con TODAS las estaciones. La posición de
                        una estación en este arreglo es su "id" (un número entero).
  - self.abiertas    -> arreglo de booleanos: self.abiertas[id] dice si está abierta.
  - self._abiertas   -> arreglo ORDENADO solo con los nombres de estaciones abiertas.
                        Sirve para R1, R2 y R3 con búsqueda binaria.
  - self.rutas       -> arreglo de objetos Ruta, ordenado por código de ruta.
  - self._codigos    -> los códigos de ruta en el mismo orden (para búsqueda binaria).
  - self._pasos      -> "índice inverso": self._pasos[id] = lista de (ruta, posición)
                        con todas las rutas ACTIVAS que pasan por esa estación.
  - self._hechos / self._pendientes -> dos pilas para deshacer y rehacer (R9).
"""
from .estructuras import clave, inferior, leer, minutos, ordenar  # Herramientas básicas del otro archivo.


class Ruta:
    """Una ruta en UN solo sentido (por ejemplo "B14-1")."""

    def __init__(self, codigo, paradas):
        self.codigo = codigo  # Nombre/código de la ruta, p. ej. "B14-1".
        # paradas: lista de ids de estación en el orden del recorrido.
        self.paradas = paradas
        # activa: False si un operador cerró la ruta completa.
        self.activa = True  # Al crearse, toda ruta está activa.
        # horarios: lista ORDENADA por estación de parejas (id_estacion, [horas]).
        # Las horas están en minutos y también van ordenadas.
        self.horarios = []  # Se llena después, al leer horarios.csv.


class Red:
    def __init__(self, estaciones, rutas=None, horarios=()):
        """Crea la red.

        Se puede usar de dos formas:
          1) Red(carpeta)  -> forma que exige el profesor: lee los tres CSV
             (estaciones.csv, rutas.csv, horarios.csv) de esa carpeta.
          2) Red(estaciones, rutas, horarios) -> se le pasan los datos ya leídos
             (la usan las pruebas y el panel de rendimiento).
        """
        if rutas is None:  # Si no se pasaron rutas, se entiende que el 1.er argumento es una carpeta.
            # Forma 1: el primer parámetro es la carpeta.
            carpeta = estaciones  # Se renombra para que se entienda.
            estaciones = (nombre for nombre, in leer(carpeta, "estaciones.csv", ("nombre",)))  # Generador de nombres (la coma tras 'nombre' desempaqueta la fila de 1 columna).
            rutas = leer(carpeta, "rutas.csv", ("ruta", "orden", "estacion"))  # Filas [ruta, orden, estacion].
            horarios = leer(carpeta, "horarios.csv", ("ruta", "estacion", "hora"))  # Filas [ruta, estacion, hora].

        # --- Estaciones -------------------------------------------------
        # Se normalizan los nombres y se ordenan alfabéticamente con Merge Sort.
        self.nombres = ordenar([clave(nombre) for nombre in estaciones], lambda x: x)  # Arreglo ordenado: la posición = id de la estación.
        # Como quedan ordenadas, dos repetidas quedan juntas: basta comparar con la anterior.
        for i, nombre in enumerate(self.nombres):  # Recorre todas las estaciones.
            if not nombre or (i and nombre == self.nombres[i - 1]):  # Nombre vacío, o igual al anterior (i != 0).
                raise ValueError(f"Estación vacía o repetida: {nombre}")
        # Al inicio todas las estaciones están abiertas.
        self.abiertas = [True for _ in self.nombres]  # Un True por estación (indexado por id).
        self._abiertas = self.nombres[:]  # copia del arreglo ordenado (solo nombres abiertos; irá cambiando).

        # --- Rutas ------------------------------------------------------
        self.rutas = []  # Aquí se guardarán los objetos Ruta.
        # Se ordenan las filas por (código de ruta, orden de parada).
        # Así todas las paradas de una ruta quedan juntas y en orden.
        filas = ordenar([(codigo, int(orden), estacion) for codigo, orden, estacion in rutas],  # 'orden' llega como texto: se pasa a entero.
                        lambda fila: (fila[0], fila[1]))  # Se compara por la tupla (código, orden).
        for codigo, orden, estacion in filas:  # Recorre fila por fila, ya ordenadas.
            if not self.rutas or self.rutas[-1].codigo != codigo:  # ¿Es la primera ruta o cambió el código?
                # Empieza una ruta nueva.
                self.rutas.append(Ruta(codigo, []))  # Crea la ruta con lista de paradas vacía.
            elif orden == anterior:  # Misma ruta y mismo número de orden que la fila anterior.
                # Dos paradas con el mismo número de orden en la misma ruta: error de datos.
                raise ValueError(f"Orden de parada repetido en {codigo}: {orden}")
            # Se guarda el id (entero) de la estación, no su nombre.
            self.rutas[-1].paradas.append(self._estacion(estacion))  # Se agrega a la última ruta creada.
            anterior = orden  # Se recuerda el orden para comparar con la siguiente fila.
        # Arreglo paralelo con los códigos (ya quedó ordenado) para buscar rutas rápido.
        self._codigos = [ruta.codigo for ruta in self.rutas]

        # --- Horarios ---------------------------------------------------
        # Cada fila (ruta, estación, hora) se convierte a (código, id, minutos)
        # y se ordena todo. Así quedan agrupadas por ruta, luego por estación,
        # y las horas de cada pareja ruta-estación quedan de menor a mayor.
        grupos = ordenar([(codigo, self._estacion(estacion), minutos(hora))  # Texto de estación -> id; "HH:MM" -> minutos.
                          for codigo, estacion, hora in horarios], lambda fila: fila)  # Se ordena por la tupla completa.
        for codigo, estacion, hora in grupos:  # Recorre los horarios ya ordenados.
            ruta = self._ruta(codigo)  # Busca el objeto Ruta (búsqueda binaria).
            if not ruta.horarios or ruta.horarios[-1][0] != estacion:  # ¿Primera estación de esta ruta o cambió la estación?
                ruta.horarios.append((estacion, []))  # nueva estación en esta ruta (con lista de horas vacía)
            ruta.horarios[-1][1].append(hora)  # Agrega la hora a la lista de la última estación.

        # --- Historial y caché -----------------------------------------
        self._hechos = []       # pila de cambios hechos (para deshacer)
        self._pendientes = []   # pila de cambios deshechos (para rehacer)
        self._ranking = None    # caché del ranking R6 (None = hay que recalcular)
        self._indexar()         # construye self._pasos

    @classmethod
    def cargar(cls, carpeta):
        """Igual a Red(carpeta). Se deja porque la app y las pruebas lo usan."""
        return cls(carpeta)  # Crea una Red leyendo la carpeta.

    # ------------------------------------------------------------------
    # Funciones de apoyo (privadas: empiezan con _)
    # ------------------------------------------------------------------

    def _estacion(self, nombre):
        """Devuelve el id de una estación (abierta o cerrada) usando búsqueda binaria."""
        nombre = clave(nombre)  # Normaliza el nombre (mayúsculas, sin tildes).
        i = inferior(self.nombres, nombre)  # Primera posición con valor >= nombre.
        if i == len(self.nombres) or self.nombres[i] != nombre:  # Se pasó del final o lo encontrado no es igual:
            raise ValueError(f"Estación desconocida: {nombre}")  # la estación no existe.
        return i  # La posición es el id.

    def _ruta(self, codigo):
        """Devuelve el objeto Ruta de un código usando búsqueda binaria."""
        codigo = codigo.strip()  # Quita espacios de los bordes.
        i = inferior(self._codigos, codigo)  # Busca en el arreglo ordenado de códigos.
        if i == len(self.rutas) or self._codigos[i] != codigo:  # No está.
            raise ValueError(f"Ruta desconocida: {codigo}")
        return self.rutas[i]  # El objeto Ruta está en la misma posición.

    def _indexar(self):
        """Reconstruye el índice inverso self._pasos.

        self._pasos[id] = [(ruta, posición), ...] para cada ruta ACTIVA que pasa
        por la estación id. Así no hay que recorrer todas las rutas para saber
        qué buses pasan por una estación. Costo: O(N + M), con M = total de
        paradas sumando todas las rutas.
        """
        self._pasos = [[] for _ in self.nombres]  # Una lista vacía por estación.
        for ruta in self.rutas:  # Recorre todas las rutas.
            if ruta.activa:  # Las rutas cerradas no se indexan (por eso "desaparecen" de las consultas).
                for posicion, estacion in enumerate(ruta.paradas):  # Cada parada con su posición en la ruta.
                    self._pasos[estacion].append((ruta, posicion))  # "Por la estación X pasa esta ruta en esta posición".

    # ------------------------------------------------------------------
    # R1, R2 y R3: consultar estaciones
    # ------------------------------------------------------------------

    def buscar(self, nombre):
        """True si la estación existe Y está abierta. Búsqueda binaria: O(log N)."""
        nombre = clave(nombre)  # Normaliza.
        i = inferior(self._abiertas, nombre)  # Busca solo entre las abiertas.
        return i < len(self._abiertas) and self._abiertas[i] == nombre  # True si cayó dentro del arreglo y es exactamente ese nombre.

    def estado(self, nombre):
        """R1. Devuelve "No existe", "Abierta" o "Cerrada". O(log N).

        Busca en el catálogo completo (self.nombres) para poder distinguir
        una estación cerrada de una que no existe.
        """
        nombre = clave(nombre)  # Normaliza.
        i = inferior(self.nombres, nombre)  # Busca entre TODAS las estaciones.
        if i == len(self.nombres) or self.nombres[i] != nombre:  # No aparece en el catálogo.
            return "No existe"
        return "Abierta" if self.abiertas[i] else "Cerrada"  # Existe: se mira su bandera booleana.

    def completar(self, prefijo, k=8):
        """R2. Hasta k estaciones abiertas que empiezan por el prefijo. O(log N + k).

        Como el arreglo está ordenado, todas las que empiezan por "CAL" están
        juntas. Se busca con búsqueda binaria la primera y se leen las siguientes.
        """
        prefijo = clave(prefijo)  # Normaliza lo que escribió el usuario.
        i = inferior(self._abiertas, prefijo)  # Primera estación abierta >= prefijo (aquí empiezan las que coinciden).
        salida = []  # Sugerencias encontradas.
        while len(salida) < k and i < len(self._abiertas) and self._abiertas[i].startswith(prefijo):  # Hasta k, sin pasarse del final y mientras sigan empezando por el prefijo.
            salida.append(self._abiertas[i])  # Agrega la sugerencia.
            i += 1  # Pasa a la siguiente estación (están contiguas por estar ordenadas).
        return salida

    def rango(self, inicio, fin):
        """R3. Estaciones abiertas entre inicio y fin (ambas incluidas). O(log N + K)."""
        inicio, fin = clave(inicio), clave(fin)  # Normaliza los dos límites.
        if inicio > fin:  # Comparación alfabética de textos.
            raise ValueError("El límite inicial debe preceder al final.")
        i = inferior(self._abiertas, inicio)  # primera >= inicio
        j = inferior(self._abiertas, fin)     # primera >= fin
        # Si fin existe, se incluye moviendo j una posición.
        if j < len(self._abiertas) and self._abiertas[j] == fin:  # El corte [i:j] excluye j, así que se suma 1 para incluir 'fin'.
            j += 1
        return self._abiertas[i:j]  # Corte (slice) del arreglo ordenado.

    # ------------------------------------------------------------------
    # R4: próximo bus
    # ------------------------------------------------------------------

    def _horario(self, ruta, estacion):
        """Lista ordenada de horas (en minutos) de una ruta en una estación.

        Se busca la estación con búsqueda binaria dentro de ruta.horarios.
        """
        i = inferior(ruta.horarios, estacion, lambda fila: fila[0])  # Busca por el id de estación (primer elemento de cada pareja).
        if i < len(ruta.horarios) and ruta.horarios[i][0] == estacion:  # La encontró exactamente.
            return ruta.horarios[i][1]  # Devuelve su lista de horas.
        return []  # Esa ruta no tiene horarios en esa estación.

    def _siguiente(self, ruta, estacion, desde):
        """Primera hora >= desde (búsqueda binaria). None si ya no hay más buses."""
        horas = self._horario(ruta, estacion)  # Horas (ordenadas) de la ruta en esa estación.
        i = inferior(horas, desde)  # Primera hora >= desde.
        return horas[i] if i < len(horas) else None  # Si se pasó del final, ya no hay más buses.

    def proximo_bus(self, nombre, codigo, hora):
        """R4. Minuto en que pasa el siguiente bus de esa ruta, o None.

        Devuelve None si la estación está cerrada, si la ruta está cerrada o
        si la ruta ya no pasa por esa estación (por ejemplo, tras quitar la parada).
        """
        estacion, ruta = self._estacion(nombre), self._ruta(codigo)  # Convierte nombre -> id y código -> objeto Ruta.
        desde = minutos(hora)  # "HH:MM" -> minutos.
        if self.abiertas[estacion]:  # Solo si la estación está abierta.
            # Se revisa en el índice inverso que la ruta (activa) pase por aquí.
            for candidata, _ in self._pasos[estacion]:  # Rutas activas que pasan por la estación.
                if candidata is ruta:  # 'is' compara que sea el MISMO objeto.
                    return self._siguiente(ruta, estacion, desde)  # Minuto del próximo bus (o None).
        return None  # Estación cerrada o la ruta no pasa (o está cerrada).

    # ------------------------------------------------------------------
    # R5: planear un viaje (directo o con un transbordo, menos paradas)
    # ------------------------------------------------------------------

    def viaje(self, origen, destino):
        """R5. Devuelve una lista de tramos [(código, [estaciones...]), ...].

        - None  -> no hay viaje directo ni con un transbordo (o alguna está cerrada).
        - []    -> origen y destino son la misma estación.
        - 1 tramo  -> viaje directo.
        - 2 tramos -> viaje con un transbordo (el cambio es la última estación del
                      primer tramo).

        IDEA:
          Paso 1: desde el origen se recorren hacia adelante todas las rutas que
                  pasan por él. Así se sabe a qué estaciones se llega sin
                  transbordo y con cuántas paradas. Si se llega al destino, es
                  un candidato a viaje directo.
          Paso 2: desde el destino se miran hacia atrás las rutas que llegan a él.
                  Para cada estación anterior se mira si se llegó a ella en el
                  paso 1 con OTRA ruta. Si sí, ahí se puede transbordar.
          Se queda el viaje con menos paradas en total.
        """
        a, b = self._estacion(origen), self._estacion(destino)  # ids de origen (a) y destino (b).
        # Nadie sube ni baja en una estación cerrada.
        if not self.abiertas[a] or not self.abiertas[b]:
            return None
        if a == b:  # Mismo lugar: no hay que viajar.
            return []
        # primeras[id] = las 2 mejores formas (de rutas distintas) de llegar a la
        # estación id desde el origen: (paradas, ruta, posición_salida, posición_llegada).
        primeras = [[] for _ in self.nombres]
        mejor = None            # mejor viaje encontrado
        costo = float("inf")    # paradas del mejor viaje (infinito al inicio)

        # Paso 1: rutas que salen del origen.
        for ruta, salida in self._pasos[a]:  # Cada ruta activa que pasa por el origen, con la posición donde pasa.
            for llegada in range(salida + 1, len(ruta.paradas)):  # Cada parada posterior (solo hacia adelante: un sentido).
                estacion = ruta.paradas[llegada]  # id de la estación a la que se llega.
                pasos = llegada - salida  # Cantidad de segmentos recorridos.
                # ¿Viaje directo al destino?
                if estacion == b and pasos < costo:  # Llegó al destino y es mejor que lo que había.
                    mejor, costo = [(ruta, salida, llegada)], pasos  # Se guarda como mejor viaje (1 tramo).
                # Solo se puede transbordar en estaciones abiertas.
                if self.abiertas[estacion]:
                    # Las dos mejores rutas distintas permiten descartar la del segundo tramo.
                    # (Si el segundo tramo usa la misma ruta del mejor primer tramo,
                    # se usa la segunda mejor, que es de otra ruta.)
                    opciones = primeras[estacion]  # Opciones ya guardadas para llegar a esta estación.
                    for i, opcion in enumerate(opciones):
                        if opcion[1] is ruta:  # opcion[1] es la ruta de esa opción.
                            # Ya había una opción con esta misma ruta: se queda la más corta.
                            if pasos >= opcion[0]:  # La que ya estaba es igual o mejor:
                                break  # no se hace nada.
                            opciones.pop(i)  # La nueva es mejor: se quita la vieja
                            opciones.append((pasos, ruta, salida, llegada))  # y se agrega la nueva.
                            break
                    else:  # Ninguna opción guardada usa esta ruta (el for terminó sin break):
                        opciones.append((pasos, ruta, salida, llegada))  # se agrega como opción nueva.
                    # Se ordenan por número de paradas y se dejan solo las 2 mejores.
                    primeras[estacion] = ordenar(opciones, lambda opcion: opcion[0])[:2]

        # Paso 2: rutas que llegan al destino; se busca dónde transbordar.
        for ruta, llegada in self._pasos[b]:  # Cada ruta activa que pasa por el destino.
            for salida in range(llegada):  # Cada parada ANTERIOR al destino en esa ruta: posible punto de transbordo.
                # Opciones para llegar a ruta.paradas[salida] desde el origen.
                for pasos, anterior, inicio, cambio in primeras[ruta.paradas[salida]]:  # Formas de llegar a esa estación desde el origen.
                    if anterior is not ruta:  # tiene que ser un cambio de ruta
                        # "<" estricto: si empata con el directo, se prefiere el directo.
                        if pasos + llegada - salida < costo:  # Total = tramo 1 + tramo 2; ¿mejora el mejor actual?
                            costo = pasos + llegada - salida  # Nuevo mejor costo.
                            mejor = [(anterior, inicio, cambio), (ruta, salida, llegada)]  # Dos tramos.
                        break  # la primera opción válida ya es la mejor (están ordenadas)
        if mejor is None:  # No se encontró ni directo ni con un transbordo.
            return None
        # Se pasa de ids a nombres para devolver algo fácil de leer.
        return [(ruta.codigo, [self.nombres[i] for i in ruta.paradas[salida:llegada + 1]])  # Código de ruta y nombres de las estaciones del tramo (incluye ambos extremos).
                for ruta, salida, llegada in mejor]

    @staticmethod
    def duracion_tramo(paradas):
        """Estimación: 3 minutos por cada segmento entre paradas."""
        return 3 * (len(paradas) - 1)  # N paradas = N-1 segmentos.

    def estimar(self, viaje, hora):
        """Hora estimada de llegada (en minutos) de un viaje que sale a 'hora'.

        Para cada tramo: se espera el próximo bus y se suman 3 min por segmento.
        Devuelve None si algún tramo no tiene buses después de esa hora.
        """
        if viaje is None:  # No había viaje posible.
            return None
        llegada = minutos(hora)  # Se parte de la hora de salida, en minutos.
        for codigo, paradas in viaje:  # Cada tramo del viaje.
            ruta = self._ruta(codigo)  # Objeto Ruta del tramo.
            bus = self._siguiente(ruta, self._estacion(paradas[0]), llegada)  # Próximo bus en la estación de abordaje.
            if bus is None:  # Ya no pasan más buses ese día.
                return None
            llegada = bus + self.duracion_tramo(paradas)  # Hora del bus + tiempo de viaje = llegada del tramo (y salida para el siguiente).
        return llegada  # Minuto de llegada final.

    # ------------------------------------------------------------------
    # R6: ranking de estaciones con más buses
    # ------------------------------------------------------------------

    def ranking(self, k):
        """R6. Las k estaciones abiertas por donde pasan más buses al día.

        Devuelve [(nombre, total_buses), ...]. Si hay empate, orden alfabético.
        Usa CACHÉ: el ranking se calcula una vez y se guarda en self._ranking.
        Solo se vuelve a calcular cuando algo cambia (cerrar, reabrir, editar),
        porque _aplicar() pone self._ranking = None.
        Con caché: O(k). Al reconstruir: conteo + Merge Sort O(N log N).
        """
        if self._ranking is None:  # No hay caché válida: hay que calcular.
            filas = []  # Lista de (nombre, total de buses).
            for i, nombre in enumerate(self.nombres):  # Cada estación.
                if self.abiertas[i]:  # Las cerradas no entran al ranking.
                    total = 0  # Contador de buses al día en esta estación.
                    anterior = None  # Última ruta contada (para no contarla dos veces).
                    for ruta, _ in self._pasos[i]:  # Rutas activas que pasan por la estación.
                        # Si una ruta pasa dos veces por la estación, se cuenta una sola vez.
                        if ruta is not anterior:
                            total += len(self._horario(ruta, i))  # Suma la cantidad de horarios de esa ruta aquí.
                            anterior = ruta
                    filas.append((nombre, total))
            # Mayor total primero (por eso el signo menos) y luego por nombre.
            self._ranking = ordenar(filas, lambda fila: (-fila[1], fila[0]))  # Se guarda en la caché.
        return self._ranking[:k] if k > 0 else []  # Devuelve solo los k primeros.

    # ------------------------------------------------------------------
    # R7: editar rutas
    # ------------------------------------------------------------------

    def ruta_activa(self, codigo):
        return self._ruta(codigo).activa  # True si la ruta no está cerrada.

    def recorrido(self, codigo, al_reves=False):
        """R7. Nombres de las paradas de una ruta, en su sentido o al revés."""
        paradas = self._ruta(codigo).paradas  # ids de las paradas de la ruta.
        indices = reversed(paradas) if al_reves else paradas  # reversed() las recorre de atrás hacia adelante sin copiar.
        return [self.nombres[i] for i in indices]  # Convierte ids a nombres.

    def insertar(self, codigo, despues, nombre):
        """Inserta la estación 'nombre' después de la parada número 'despues' (desde 1).

        Solo se permite entre dos paradas existentes (no al final).
        """
        ruta = self._ruta(codigo)  # Objeto Ruta.
        estacion = self._estacion(nombre)  # id de la estación a insertar.
        if not 1 <= despues < len(ruta.paradas):  # Debe estar entre 1 y (última - 1).
            raise ValueError("Indica el número de una parada anterior a la última.")
        # Como 'despues' cuenta desde 1, la nueva parada queda en la posición 'despues'.
        self._cambio(("insertar", ruta, despues, estacion))  # Se aplica y se guarda para poder deshacer.

    def quitar(self, codigo, numero):
        """Quita la parada número 'numero' (desde 1). La ruta debe quedar con al menos una."""
        ruta = self._ruta(codigo)
        if len(ruta.paradas) <= 1 or not 1 <= numero <= len(ruta.paradas):  # No dejar la ruta vacía; número válido.
            raise ValueError("Selecciona una parada válida. La ruta requiere al menos una.")
        # Se guarda qué estación había, para poder volver a ponerla al deshacer.
        self._cambio(("quitar", ruta, numero - 1, ruta.paradas[numero - 1]))  # numero - 1: de base 1 a base 0.

    # ------------------------------------------------------------------
    # R8: cerrar y reabrir (y cerrar rutas completas, que es un extra)
    # ------------------------------------------------------------------

    def alternar_estacion(self, nombre):
        """Si está abierta la cierra; si está cerrada la abre."""
        self._cambio(("estacion", None, self._estacion(nombre), None))  # (acción, ruta, id de estación, estación)

    def alternar_ruta(self, codigo):
        """Extra: cierra o abre una ruta completa."""
        self._cambio(("ruta", self._ruta(codigo), None, None))

    # ------------------------------------------------------------------
    # R9: deshacer y rehacer
    # ------------------------------------------------------------------
    # Cada cambio se guarda como una tupla (accion, ruta, posicion, estacion).
    # Todos los cambios son "reversibles":
    #   - "estacion" y "ruta" son interruptores: aplicarlos dos veces deja todo igual.
    #   - "insertar" se deshace quitando, y "quitar" se deshace insertando.

    def _aplicar(self, cambio, inverso=False):
        """Aplica un cambio. Con inverso=True hace lo contrario (para deshacer)."""
        accion, ruta, posicion, estacion = cambio  # Desempaqueta la tupla.
        if accion == "estacion":  # Abrir/cerrar una estación.
            nombre = self.nombres[posicion]  # Aquí 'posicion' es el id de la estación.
            # Dónde está (o dónde debería estar) en el arreglo ordenado de abiertas.
            i = inferior(self._abiertas, nombre)
            self.abiertas[posicion] = not self.abiertas[posicion]  # Invierte la bandera.
            if self.abiertas[posicion]:  # Quedó abierta:
                self._abiertas.insert(i, nombre)  # se reabre: se mete en su lugar
            else:  # Quedó cerrada:
                self._abiertas.pop(i)             # se cierra: se saca del arreglo
            # No hace falta reconstruir el índice: viaje() y proximo_bus()
            # revisan self.abiertas directamente.
        else:  # Cambios sobre rutas.
            if accion == "ruta":  # Cerrar/abrir ruta completa.
                ruta.activa = not ruta.activa  # Invierte el estado.
            # (accion == "insertar") != inverso es un "o exclusivo":
            #   insertar normal  -> inserta
            #   quitar al deshacer -> inserta (vuelve a poner la estación)
            elif (accion == "insertar") != inverso:
                ruta.paradas.insert(posicion, estacion)  # Mete la estación en esa posición.
            else:
                #   quitar normal     -> quita
                #   insertar al deshacer -> quita
                ruta.paradas.pop(posicion)  # Saca la parada de esa posición.
            self._indexar()  # las rutas cambiaron: se rehace el índice inverso
        self._ranking = None  # cualquier cambio invalida la caché del ranking

    def _cambio(self, cambio):
        """Aplica un cambio nuevo y lo guarda en la pila de deshacer."""
        self._aplicar(cambio)  # Lo ejecuta.
        self._hechos.append(cambio)  # Lo apila en "hechos".
        # Un cambio nuevo borra todo lo que había para rehacer.
        self._pendientes.clear()

    def deshacer(self):
        """R9. Deshace el último cambio. Devuelve False si no hay nada que deshacer."""
        if not self._hechos:  # Pila vacía.
            return False
        cambio = self._hechos.pop()            # sacar de la pila de hechos
        self._aplicar(cambio, inverso=True)    # hacer lo contrario
        self._pendientes.append(cambio)        # guardarlo por si se quiere rehacer
        return True

    def rehacer(self):
        """R9. Vuelve a aplicar el último cambio deshecho. False si no hay nada."""
        if not self._pendientes:  # Nada para rehacer.
            return False
        cambio = self._pendientes.pop()  # Saca el último deshecho.
        self._aplicar(cambio)  # Lo vuelve a aplicar normalmente.
        self._hechos.append(cambio)  # Vuelve a quedar como "hecho".
        return True

    # ------------------------------------------------------------------
    # CONTRATO DEL PROFESOR (diapositiva 10)
    # El script de calificación llama EXACTAMENTE estos nombres. Por dentro
    # solo reutilizan las funciones de arriba; no cambian la lógica.
    # OJO: los valores que devuelve cada una deben coincidir con el enunciado.
    # ------------------------------------------------------------------

    def autocompletar(self, prefijo, k):
        """R2 con el nombre del contrato."""
        return self.completar(prefijo, k)  # Solo cambia el nombre.

    def _posicion(self, ruta, nombre):
        """Posición (desde 0) de la primera aparición de una estación en una ruta.

        Búsqueda lineal hecha a mano (no se puede usar .index()). O(S).
        """
        estacion = self._estacion(nombre)  # id de la estación.
        for posicion, actual in enumerate(ruta.paradas):  # Recorre las paradas de una en una.
            if actual == estacion:  # La encontró.
                return posicion
        raise ValueError(f"La ruta {ruta.codigo} no pasa por {clave(nombre)}.")  # Recorrió todo y no estaba.

    def agregar_parada(self, ruta, nueva, despues_de):
        """R7. Agrega la estación 'nueva' justo después de la estación 'despues_de'."""
        posicion = self._posicion(self._ruta(ruta), despues_de)  # Posición (base 0) de 'despues_de'.
        self.insertar(ruta, posicion + 1, nueva)  # insertar() cuenta desde 1

    def quitar_parada(self, ruta, estacion):
        """R7. Quita la estación indicada de la ruta."""
        posicion = self._posicion(self._ruta(ruta), estacion)  # Posición (base 0).
        self.quitar(ruta, posicion + 1)           # quitar() cuenta desde 1

    def cerrar(self, nombre):
        """R8. Cierra la estación. Devuelve False si ya estaba cerrada."""
        if not self.abiertas[self._estacion(nombre)]:  # Ya estaba cerrada: nada que hacer.
            return False
        self.alternar_estacion(nombre)  # La cierra (y queda registrada para deshacer).
        return True

    def reabrir(self, nombre):
        """R8. Reabre la estación. Devuelve False si ya estaba abierta."""
        if self.abiertas[self._estacion(nombre)]:  # Ya estaba abierta.
            return False
        self.alternar_estacion(nombre)  # La reabre.
        return True
