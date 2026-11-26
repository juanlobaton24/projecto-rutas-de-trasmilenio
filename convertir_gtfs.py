"""Convierte un ZIP GTFS estático de un día de servicio a los tres CSV.

Uso:
    python3 convertir_gtfs.py /ruta/al/gtfs.zip datos/real --fecha 2021-07-14

Este archivo está FUERA de motor/, así que aquí sí se puede usar cualquier
librería (dict, set, sqlite3, etc.). El motor solo lee los tres CSV que salen de aquí:
    estaciones.csv (nombre)
    rutas.csv      (ruta, orden, estacion)
    horarios.csv   (ruta, estacion, hora)

Archivos del GTFS que se usan:
    calendar.txt / calendar_dates.txt -> qué servicios funcionan ese día
    routes.txt  -> las líneas (B14, K3...)
    trips.txt   -> cada viaje de un bus y a qué línea y sentido pertenece
    stops.txt   -> las paradas y su estación "padre"
    stop_times.txt -> a qué hora pasa cada viaje por cada parada
    frequencies.txt -> viajes que se repiten cada X segundos (opcional)
"""
import argparse
import csv
import io
from itertools import groupby
from collections import defaultdict
from contextlib import closing
from datetime import date
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unicodedata
from zipfile import ZipFile


def normalizar(nombre):
    """Mayúsculas y sin tildes, pero conservando la Ñ. "Nariño" -> "NARIÑO".

    Truco: se cambia la Ñ por un carácter raro (\\x00), se quitan todas las
    tildes y luego se vuelve a poner la Ñ.
    """
    # NFD separa cada letra de su tilde: "á" queda como "a" + "´".
    texto = unicodedata.normalize("NFD", nombre.upper().replace("Ñ", "\x00"))
    # Se botan las marcas de tilde (combining).
    limpio = "".join(letra for letra in texto if not unicodedata.combining(letra))
    # Se devuelve la Ñ y se dejan los espacios sencillos.
    return " ".join(limpio.replace("\x00", "Ñ").split())


def segundos(valor):
    """"HH:MM:SS" -> segundos desde la medianoche. Acepta horas >= 24 (ej. 25:10:00)."""
    horas, minutos, segundos = map(int, valor.split(":"))
    return (horas * 60 + minutos) * 60 + segundos


def convertir(origen, salida, fecha, agencia=None):
    """Lee el ZIP 'origen' y escribe los tres CSV en la carpeta 'salida'.

    - fecha: día de servicio (date) que se quiere convertir.
    - agencia: si se da, solo se usan las rutas de ese agency_id.
    """
    with ZipFile(origen) as archivo, TemporaryDirectory() as temporal:
        # Mapa nombre_de_archivo -> ruta dentro del ZIP (por si vienen dentro de una carpeta).
        archivos = {Path(ruta).name: ruta for ruta in archivo.namelist()}

        def leer(nombre):
            """Entrega cada fila de un .txt del GTFS como diccionario. Si no existe, no entrega nada."""
            if nombre in archivos:
                with archivo.open(archivos[nombre]) as datos:
                    yield from csv.DictReader(io.TextIOWrapper(datos, encoding="utf-8-sig"))

        # ---- 1. Servicios activos ese día ----------------------------------
        dia = fecha.strftime("%Y%m%d")  # formato del GTFS: 20210714
        semana = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        # Del calendario normal: servicios vigentes en la fecha que funcionan ese día de la semana.
        servicios = {
            fila["service_id"] for fila in leer("calendar.txt")
            if fila["start_date"] <= dia <= fila["end_date"] and fila[semana[fecha.weekday()]] == "1"
        }
        # Excepciones: tipo 1 = se agrega el servicio ese día; tipo 2 = se quita.
        for fila in leer("calendar_dates.txt"):
            if fila["date"] == dia:
                if fila["exception_type"] == "1":
                    servicios.add(fila["service_id"])
                else:
                    servicios.discard(fila["service_id"])

        # ---- 2. Rutas y viajes ----------------------------------------------
        # rutas: route_id -> nombre corto (ej. "B14"); si no tiene, se usa el id.
        rutas = {}
        for fila in leer("routes.txt"):
            if agencia is None or fila.get("agency_id") == agencia:
                rutas[fila["route_id"]] = fila["route_short_name"].strip() or fila["route_id"]
        # viajes: trip_id -> (route_id, sentido). Solo los viajes activos ese día.
        viajes = {
            fila["trip_id"]: (fila["route_id"], fila.get("direction_id") or "0")
            for fila in leer("trips.txt")
            if fila["service_id"] in servicios and fila["route_id"] in rutas
        }
        if not viajes:
            raise ValueError("La fecha y el filtro no tienen viajes activos en el GTFS.")

        # ---- 3. Nombres de estación -----------------------------------------
        # Un andén ("Andén 1") pertenece a una estación padre. Se usa el nombre del padre
        # para que todos los andenes de una estación cuenten como la misma estación.
        paradas = {fila["stop_id"]: fila for fila in leer("stops.txt")}
        nombres = {}
        for identificador, fila in paradas.items():
            padre = paradas.get(fila.get("parent_station"), fila)  # si no tiene padre, es ella misma
            nombres[identificador] = normalizar(padre["stop_name"])

        # ---- 4. Frecuencias (viajes que se repiten) -------------------------
        # frecuencias[trip_id] = [(inicio, fin, cada_cuantos_segundos), ...]
        frecuencias = defaultdict(list)
        for fila in leer("frequencies.txt"):
            if fila["trip_id"] in viajes:
                frecuencias[fila["trip_id"]].append(
                    (segundos(fila["start_time"]), segundos(fila["end_time"]), int(fila["headway_secs"]))
                )

        def tiempos():
            """Entrega (viaje, secuencia, nombre_estacion, segundos) de cada fila útil de stop_times."""
            for fila in leer("stop_times.txt"):
                viaje = fila["trip_id"]
                if viaje in viajes:
                    hora = fila["departure_time"] or fila["arrival_time"]
                    yield viaje, int(fila["stop_sequence"]), nombres[fila["stop_id"]], segundos(hora) if hora else None

        salida.mkdir(parents=True, exist_ok=True)
        codigos = {}      # (ruta, sentido, patrón de paradas) -> código final, ej. "B14-0-1"
        usados = set()    # códigos ya asignados
        estaciones = set()  # estaciones que aparecen en alguna ruta
        # ---- 5. Ordenar stop_times con SQLite --------------------------------
        # stop_times.txt es enorme; se guarda en una base temporal SQLite para
        # poder ordenarlo por viaje y secuencia sin cargar todo en memoria.
        with closing(sqlite3.connect(Path(temporal) / "gtfs.db")) as base, (
            salida / "rutas.csv"
        ).open("w", newline="", encoding="utf-8") as rutas_csv, (
            salida / "horarios.csv"
        ).open("w", newline="", encoding="utf-8") as horarios_csv:
            base.execute("CREATE TABLE tiempos (viaje TEXT, secuencia INTEGER, nombre TEXT, hora INTEGER)")
            base.executemany("INSERT INTO tiempos VALUES (?, ?, ?, ?)", tiempos())
            filas = base.execute("SELECT viaje, nombre, hora FROM tiempos ORDER BY viaje, secuencia")
            escritor_rutas, escritor_horas = csv.writer(rutas_csv), csv.writer(horarios_csv)
            escritor_rutas.writerow(("ruta", "orden", "estacion"))
            escritor_horas.writerow(("ruta", "estacion", "hora"))
            # groupby junta las filas consecutivas del mismo viaje.
            for viaje, filas_viaje in groupby(filas, key=lambda fila: fila[0]):
                # secuencia = [(estacion, hora), ...] del viaje, sin repetir estaciones seguidas
                # (dos andenes de la misma estación seguidos cuentan como una parada).
                secuencia = []
                for _, nombre, hora in filas_viaje:
                    if secuencia and secuencia[-1][0] == nombre:
                        if hora is not None:
                            secuencia[-1] = nombre, hora
                    else:
                        secuencia.append((nombre, hora))
                patron = tuple(nombre for nombre, _ in secuencia)
                if not patron:
                    continue
                ruta, sentido = viajes[viaje]
                # Cada combinación línea + sentido + recorrido exacto es una "ruta" del CSV.
                # Así cada código va en un solo sentido, como pide el enunciado.
                llave = ruta, sentido, patron
                if llave not in codigos:
                    # Código nuevo: nombre-sentido-número (ej. "B14-0-1", "B14-0-2"...).
                    prefijo = f"{rutas[ruta]}-{sentido}"
                    numero = 1
                    codigo = f"{prefijo}-{numero}"
                    while codigo in usados:
                        numero += 1
                        codigo = f"{prefijo}-{numero}"
                    codigos[llave] = codigo
                    usados.add(codigo)
                    estaciones.update(patron)
                    # Se escriben sus paradas en rutas.csv con el orden desde 1.
                    escritor_rutas.writerows((codigo, i, nombre) for i, nombre in enumerate(patron, 1))
                codigo = codigos[llave]
                # ---- 6. Horarios ------------------------------------------------
                if viaje in frecuencias:
                    # Viaje por frecuencia: se repite cada 'paso' segundos entre inicio y fin.
                    # Se calcula cuánto hay que correr (desfase) el viaje modelo en cada salida.
                    referencia = next((hora for _, hora in secuencia if hora is not None), None)
                    if referencia is None:
                        continue
                    desfases = (
                        segundo - referencia
                        for inicio, fin, paso in frecuencias[viaje]
                        for segundo in range(inicio, fin, paso)
                    )
                else:
                    desfases = (0,)  # viaje normal: una sola salida, tal cual
                for desfase in desfases:
                    for nombre, hora in secuencia:
                        if hora is not None:
                            # Segundos -> HH:MM. Las horas >= 24 se dejan así (ej. 25:10)
                            # porque pertenecen al mismo día de servicio.
                            h, m = divmod((hora + desfase) // 60, 60)
                            escritor_horas.writerow((codigo, nombre, f"{h:02d}:{m:02d}"))

        # ---- 7. estaciones.csv (ordenadas alfabéticamente, sin repetir) --------
        with (salida / "estaciones.csv").open("w", newline="", encoding="utf-8") as archivo_csv:
            escritor = csv.writer(archivo_csv)
            escritor.writerow(("nombre",))
            escritor.writerows((nombre,) for nombre in sorted(estaciones))


if __name__ == "__main__":
    # Lectura de los argumentos de la terminal.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("salida", type=Path)
    parser.add_argument("--fecha", required=True, type=date.fromisoformat)
    parser.add_argument("--agencia", help="Filtra por agency_id")
    args = parser.parse_args()
    try:
        convertir(args.zip, args.salida, args.fecha, args.agencia)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f"Error: {error}\n")
