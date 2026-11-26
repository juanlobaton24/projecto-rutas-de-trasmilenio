"""Pruebas automáticas del proyecto.

Se corren desde la carpeta del proyecto con:
    python3 -m unittest discover -s pruebas -v

Cada método que empieza por test_ es una prueba. assertEqual(a, b) falla si
a y b son distintos; assertTrue / assertFalse / assertIsNone revisan condiciones.
"""
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from convertir_gtfs import convertir
from motor import Red, simular_fila
from motor.rendimiento import medir
from motor.simulacion import simular


class PruebasRed(unittest.TestCase):
    def setUp(self):
        """Red pequeña que se crea de nuevo antes de CADA prueba.

        Rutas:  A: NORTE -> CALLE 26 -> SUR
                B: SUR -> CALLE 45 -> CALLE 80
                C: NORTE -> CALLE 80
        Horarios: A en NORTE a las 08:00 y 25:10, A en CALLE 26 a las 08:03,
                  B en SUR a las 08:07.
        """
        self.red = Red(
            ["CALLE 26", "CALLE 45", "CALLE 80", "NORTE", "SUR"],
            [
                ("A", 1, "NORTE"), ("A", 2, "CALLE 26"), ("A", 3, "SUR"),
                ("B", 1, "SUR"), ("B", 2, "CALLE 45"), ("B", 3, "CALLE 80"),
                ("C", 1, "NORTE"), ("C", 2, "CALLE 80"),
            ],
            [("A", "NORTE", "25:10"), ("A", "NORTE", "08:00"),
             ("A", "CALLE 26", "08:03"), ("B", "SUR", "08:07")],
        )

    def test_busquedas_y_cierre(self):
        """R1, R2, R3 y R8: búsquedas antes y después de cerrar una estación."""
        red = self.red
        self.assertTrue(red.buscar(" calle 26 "))  # no importan mayúsculas ni espacios
        self.assertEqual(red.completar("cal", 2), ["CALLE 26", "CALLE 45"])
        self.assertEqual(red.rango("CALLE 26", "CALLE 80"), ["CALLE 26", "CALLE 45", "CALLE 80"])
        red.alternar_estacion("CALLE 26")  # se cierra
        self.assertEqual(red.estado("CALLE 26"), "Cerrada")
        self.assertFalse(red.buscar("CALLE 26"))
        self.assertEqual(red.completar("CAL", 8), ["CALLE 45", "CALLE 80"])
        self.assertEqual(red.rango("CALLE 26", "CALLE 80"), ["CALLE 45", "CALLE 80"])
        self.assertIsNone(red.proximo_bus("CALLE 26", "A", "08:00"))  # cerrada: no hay bus

    def test_bus_y_viaje(self):
        """R4 y R5, incluyendo horas extendidas y transbordos."""
        red = self.red
        self.assertEqual(red.proximo_bus("NORTE", "A", "08:00"), 480)   # 08:00 = 480 min
        self.assertEqual(red.proximo_bus("NORTE", "A", "08:01"), 1510)  # el siguiente es 25:10
        self.assertIsNone(red.proximo_bus("NORTE", "A", "25:11"))       # ya no hay más
        self.assertEqual(red.viaje("NORTE", "CALLE 80"), [("C", ["NORTE", "CALLE 80"])])  # directo
        self.assertIsNone(red.viaje("CALLE 80", "NORTE"))  # las rutas van en un solo sentido
        red.alternar_ruta("C")  # sin la ruta C toca transbordar en SUR
        viaje = red.viaje("NORTE", "CALLE 80")
        self.assertEqual(viaje, [("A", ["NORTE", "CALLE 26", "SUR"]), ("B", ["SUR", "CALLE 45", "CALLE 80"])])
        # Sale 07:58 -> bus A 08:00 -> +6 min = 08:06 -> bus B 08:07 -> +6 min = 08:13 (493).
        self.assertEqual(red.estimar(viaje, "07:58"), 493)
        red.alternar_estacion("CALLE 26")  # se puede ATRAVESAR una estación cerrada
        self.assertEqual(red.viaje("NORTE", "CALLE 80"), viaje)
        red.alternar_estacion("SUR")  # pero NO transbordar en una cerrada
        self.assertIsNone(red.viaje("NORTE", "CALLE 80"))

    def test_ranking_ediciones_e_historial(self):
        """R6, R7 y R9: el ranking cambia al editar, y deshacer/rehacer funcionan."""
        red = self.red
        self.assertEqual(red.ranking(2), [("NORTE", 2), ("CALLE 26", 1)])
        red.quitar("A", 2)  # se quita CALLE 26 de la ruta A
        self.assertEqual(red.ranking(2), [("NORTE", 2), ("SUR", 1)])
        red.deshacer()
        self.assertEqual(red.recorrido("A", True), ["SUR", "CALLE 26", "NORTE"])
        red.rehacer()
        self.assertIsNone(red.proximo_bus("CALLE 26", "A", "08:00"))
        red.deshacer()
        red.insertar("A", 1, "CALLE 45")
        self.assertFalse(red.rehacer())  # un cambio nuevo borra lo que había para rehacer
        self.assertEqual(red.recorrido("A"), ["NORTE", "CALLE 45", "CALLE 26", "SUR"])

    def test_fifo(self):
        """R10 (versión de la app): 200.000 personas, 100 buses de 160 cada 4 minutos."""
        filas = [("NORTE", 200_000), ("SUR", 161)]
        self.assertEqual(simular(self.red, filas, 100, 160, 4),
                         [("NORTE", 200_000, 100, 16_000, 184_000, 396, 15_841),
                          ("SUR", 161, 2, 161, 0, 4, 161)])

    def test_rendimiento(self):
        """R11: el panel mide los 4 tamaños y todos los tiempos son positivos."""
        for _, _, _, puntos in medir():
            self.assertEqual([n for n, _ in puntos], [128, 512, 2048, 8192])
            self.assertTrue(all(tiempo > 0 for _, tiempo in puntos))


class PruebasContrato(unittest.TestCase):
    """Usa EXACTAMENTE los nombres de la diapositiva 10 (los que llama el profesor)."""

    def setUp(self):
        # Se escriben tres CSV en una carpeta temporal y se carga con Red(carpeta).
        self.carpeta = TemporaryDirectory()
        raiz = Path(self.carpeta.name)
        (raiz / "estaciones.csv").write_text("nombre\nCALLE 26\nCALLE 45\nCALLE 80\nNORTE\nSUR\n", encoding="utf-8")
        (raiz / "rutas.csv").write_text(
            "ruta,orden,estacion\nA,1,NORTE\nA,2,CALLE 26\nA,3,SUR\nB,1,SUR\nB,2,CALLE 45\nB,3,CALLE 80\n",
            encoding="utf-8")
        (raiz / "horarios.csv").write_text("ruta,estacion,hora\nA,NORTE,08:00\n", encoding="utf-8")
        self.red = Red(str(raiz))  # el profesor puede pasar un texto, no un Path

    def tearDown(self):
        self.carpeta.cleanup()

    def test_llamadas_del_contrato(self):
        red = self.red
        self.assertEqual(red.estado("NORTE"), "Abierta")
        self.assertEqual(red.autocompletar("CAL", 2), ["CALLE 26", "CALLE 45"])
        self.assertEqual(red.rango("CALLE 26", "CALLE 45"), ["CALLE 26", "CALLE 45"])
        self.assertEqual(red.proximo_bus("NORTE", "A", "07:00"), 480)
        self.assertEqual(red.recorrido("A", al_reves=True), ["SUR", "CALLE 26", "NORTE"])
        red.agregar_parada("A", "CALLE 80", "NORTE")
        self.assertEqual(red.recorrido("A"), ["NORTE", "CALLE 80", "CALLE 26", "SUR"])
        red.quitar_parada("A", "CALLE 26")
        self.assertEqual(red.recorrido("A"), ["NORTE", "CALLE 80", "SUR"])
        self.assertTrue(red.cerrar("SUR"))
        self.assertFalse(red.cerrar("SUR"))  # ya estaba cerrada
        self.assertEqual(red.estado("SUR"), "Cerrada")
        self.assertTrue(red.reabrir("SUR"))
        # Deshacer en orden: reabrir, cerrar, quitar parada, agregar parada.
        for _ in range(4):
            self.assertTrue(red.deshacer())
        self.assertEqual(red.recorrido("A"), ["NORTE", "CALLE 26", "SUR"])
        self.assertTrue(red.rehacer())
        self.assertEqual(red.recorrido("A"), ["NORTE", "CALLE 80", "CALLE 26", "SUR"])

    def test_simular_fila(self):
        # Llegan 5 personas en el minuto 0 y 1 en el minuto 9; bus cada 4 min con cupo 2.
        # Minuto 0: suben 2 (quedan 3); minuto 4: suben 2 (queda 1); minuto 8: sube 1;
        # minuto 12: sube la que llegó en el 9.
        self.assertEqual(simular_fila([0, 0, 0, 0, 0, 9], 4, 2),
                         [(0, 2, 3), (4, 2, 1), (8, 1, 0), (12, 1, 0)])


class PruebaConversion(unittest.TestCase):
    def test_calendario_sentidos_horas_extendidas_y_carga(self):
        """Arma un GTFS mínimo en un ZIP, lo convierte y lo carga en el motor."""
        with TemporaryDirectory() as carpeta:
            raiz = Path(carpeta)
            origen = raiz / "gtfs.zip"
            with ZipFile(origen, "w") as zip_gtfs:
                # El servicio S funciona el 14 de julio de 2021 (el T no).
                zip_gtfs.writestr("calendar_dates.txt", "service_id,date,exception_type\nS,20210714,1\n")
                zip_gtfs.writestr("routes.txt", "route_id,route_short_name\nX,K3\n")
                # V y W son de la misma línea pero en sentidos distintos; Y no funciona ese día.
                zip_gtfs.writestr("trips.txt", "route_id,service_id,trip_id,direction_id\nX,S,V,0\nX,S,W,1\nX,T,Y,0\n")
                # "Andén 1" (stop 3) pertenece a la estación padre 1 ("Universidádes").
                zip_gtfs.writestr("stops.txt", "stop_id,stop_name,parent_station\n1,Universidádes,\n2,Nórte,\n3,Andén 1,1\n")
                zip_gtfs.writestr(
                    "stop_times.txt",
                    "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
                    "V,25:14:00,25:14:00,2,2\nW,08:00:00,08:00:00,2,1\n"
                    "V,25:10:30,25:10:30,3,1\nW,08:05:00,08:05:00,1,2\nY,06:00:00,06:00:00,1,1\n",
                )
            salida = raiz / "datos"
            convertir(origen, salida, date(2021, 7, 14))
            red = Red.cargar(salida)
            self.assertEqual(red.nombres, ["NORTE", "UNIVERSIDADES"])  # sin tildes
            self.assertEqual(red.recorrido("K3-0-1"), ["UNIVERSIDADES", "NORTE"])
            self.assertEqual(red.recorrido("K3-1-1"), ["NORTE", "UNIVERSIDADES"])
            self.assertEqual(red.proximo_bus("UNIVERSIDADES", "K3-0-1", "25:09"), 1510)
            self.assertEqual(red.ranking(2), [("NORTE", 2), ("UNIVERSIDADES", 2)])
