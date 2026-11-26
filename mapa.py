"""Lienzo desplazable para la red y los viajes.

Este archivo es parte del FRONT (la app), no del motor. Solo dibuja: no decide
nada de la lógica. Lee los datos de la red (red.nombres, red.rutas, red.abiertas)
y los pinta en un Canvas de Tkinter.

El mapa es esquemático: no usa coordenadas reales. Si hay pocas estaciones
(<= 18) las pone en un círculo; si hay muchas, las pone en una cuadrícula.
"""
import colorsys  # para generar colores distintos para cada estación
import math
import tkinter as tk
from tkinter import ttk


class Mapa(ttk.Frame):
    FONDO = "#101c2b"
    # Colores que se van turnando para las rutas.
    RUTAS = ("#29bbf5", "#a98cff", "#20d6aa", "#ffab61", "#f781b7")

    def __init__(self, padre, red, al_elegir):
        """
        - padre: el contenedor de Tkinter donde va el mapa.
        - red: el objeto Red del motor.
        - al_elegir: función que se llama con el nombre de la estación al hacer clic.
        """
        super().__init__(padre)
        self.red = red
        self.al_elegir = al_elegir
        self.filtro_ruta = ""      # si no está vacío, solo se dibuja esa ruta
        self.filtro_estacion = ""  # si no está vacío, solo rutas que pasan por esa estación
        self.viaje = []            # viaje a resaltar en amarillo: [(ruta, [estaciones]), ...]
        self.operador = False      # el operador también ve lo que está cerrado
        # Canvas con barras de desplazamiento horizontal y vertical.
        self.lienzo = tk.Canvas(self, bg=self.FONDO, highlightthickness=0, width=780, height=490)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.lienzo.xview)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        self.lienzo.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        self.lienzo.grid(row=0, column=0, sticky="nsew")
        horizontal.grid(row=1, column=0, sticky="ew")
        vertical.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        # Cada vez que cambia el tamaño de la ventana, se vuelve a dibujar.
        self.lienzo.bind("<Configure>", lambda _: self.dibujar())

    def dibujar(self):
        """Borra todo y vuelve a dibujar el mapa según los filtros y el viaje actual."""
        c = self.lienzo
        c.delete("all")
        red = self.red
        # 1) Qué rutas se dibujan: (posición, ruta) que cumplen los filtros.
        #    El usuario normal no ve rutas cerradas; el operador sí.
        rutas = [
            (i, ruta) for i, ruta in enumerate(red.rutas)
            if (self.operador or ruta.activa)
            and (not self.filtro_ruta or ruta.codigo == self.filtro_ruta)
            and (not self.filtro_estacion or any(
                self.filtro_estacion == red.nombres[j] for j in ruta.paradas
            ))
        ]
        filtrado = self.filtro_ruta or self.filtro_estacion
        # 2) Qué estaciones se ven: las de esas rutas (dict.fromkeys quita repetidas
        #    y conserva el orden; aquí está permitido porque esto NO es el motor).
        visibles = dict.fromkeys(i for _, ruta in rutas for i in ruta.paradas)
        if not filtrado:
            visibles.update(dict.fromkeys(range(len(red.nombres))))  # sin filtro: todas
        visibles = [i for i in visibles if self.operador or red.abiertas[i]]
        n = len(visibles)
        ancho, alto = max(450, c.winfo_width()), max(360, c.winfo_height())
        posiciones = {}  # id de estación -> (x, y) en pantalla
        if n <= 18:
            # Pocas estaciones: en círculo (elipse). CALLE 26 va en el centro si está.
            centro = next((i for i in visibles if red.nombres[i] == "CALLE 26"), None)
            anillo = [i for i in visibles if i != centro]
            for indice, estacion in enumerate(anillo):
                # Se reparte el círculo en partes iguales, empezando arriba (-90°).
                angulo = -math.pi / 2 + math.tau * indice / len(anillo)
                posiciones[estacion] = ancho / 2 + (ancho / 2 - 125) * math.cos(angulo), alto / 2 + (alto / 2 - 65) * math.sin(angulo)
            if centro is not None:
                posiciones[centro] = ancho / 2, alto / 2
        else:
            # Muchas estaciones: cuadrícula de columnas de 175 px y filas de 66 px.
            columnas = max(3, ancho // 175)
            for indice, estacion in enumerate(visibles):
                fila, columna = divmod(indice, columnas)
                posiciones[estacion] = 85 + 175 * columna, 50 + 66 * fila
            alto = max(alto, 80 + 66 * ((n - 1) // columnas))
        c.configure(scrollregion=(0, 0, ancho, alto))  # área que se puede desplazar
        if not visibles:
            c.create_text(ancho / 2, alto / 2, text="Sin estaciones para este filtro", fill="#c2cede", font=("TkDefaultFont", 15))
            return

        def linea(a, b, color, grosor, guiones=None):
            """Dibuja una línea entre dos estaciones si ambas están en pantalla."""
            if a in posiciones and b in posiciones:
                c.create_line(*posiciones[a], *posiciones[b], fill=color, width=grosor, dash=guiones)

        # 3) Líneas de las rutas. Las cerradas van grises y punteadas.
        conexiones = {i: set() for i in visibles}  # estación -> rutas que pasan
        for indice, ruta in rutas:
            color = self.RUTAS[indice % len(self.RUTAS)] if ruta.activa else "#536276"
            paradas = [i for i in ruta.paradas if i in posiciones]
            for a, b in zip(paradas, paradas[1:]):  # parejas de paradas seguidas
                linea(a, b, color, 2, (4, 4) if not ruta.activa else None)
            for i in paradas:
                conexiones[i].add(ruta.codigo)

        # 4) El viaje seleccionado, encima, en amarillo y más grueso.
        destacadas = set()
        ids = {nombre: i for i, nombre in enumerate(red.nombres)}
        for _, paradas in self.viaje:
            puntos = [ids[nombre] for nombre in paradas if ids[nombre] in posiciones]
            destacadas.update(puntos)
            for a, b in zip(puntos, puntos[1:]):
                linea(a, b, "#ffe371", 5)
        # 5) Círculos y nombres de las estaciones.
        for i, (x, y) in posiciones.items():
            tag = f"estacion{i}"  # etiqueta para saber a qué estación se le hizo clic
            clave = len(conexiones[i]) > 2  # más de 2 rutas = intercambio (círculo grande)
            radio = 8 if clave else 5
            # Color distinto por estación usando la razón áurea para repartir los tonos.
            rgb = colorsys.hsv_to_rgb(i * 0.61803398875 % 1, 0.55, 1)
            color = "#%02x%02x%02x" % tuple(int(v * 255) for v in rgb)
            if not red.abiertas[i]:
                color = "#68768a"  # cerrada = gris
            c.create_oval(x-radio, y-radio, x+radio, y+radio, fill=color,
                          outline="#ffe371" if i in destacadas else "#ffffff", width=2, tags=tag)
            c.create_text(x, y+19, text=red.nombres[i], fill="#e5edf7", width=160,
                          font=("TkDefaultFont", 9, "bold" if clave else "normal"), tags=tag)
            # Clic en la estación -> se avisa a la app con su nombre.
            c.tag_bind(tag, "<Button-1>", lambda _, nombre=red.nombres[i]: self.al_elegir(nombre))
