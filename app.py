"""Aplicación de escritorio para consultar y operar la red.

Este es el FRONT. La regla del proyecto: aquí NO va lógica del sistema,
solo se llama al motor (motor/red.py) y se muestran los resultados.

Cómo arrancar:
    python3 app.py                     -> usa datos/demo (o datos/real si no hay demo)
    python3 app.py --datos datos/real  -> usa otra carpeta con los tres CSV
"""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from mapa import Mapa
from motor import Red
from motor.estructuras import clave, reloj
from motor.rendimiento import medir
from motor.simulacion import simular


class Aplicacion:
    def __init__(self, ventana, red, demo):
        """Arma la ventana: encabezado, menú de botones, mapa a la izquierda y panel lateral."""
        self.ventana = ventana
        self.red = red
        self.operador = False  # False = usuario normal; True = operador de red
        self.seccion = ""      # vista abierta en este momento
        ventana.title("Mapa de rutas · TransMilenio")
        ventana.geometry("1230x760")
        ventana.minsize(900, 620)
        # Estilos (colores y letras) de los widgets ttk.
        estilo = ttk.Style(ventana)
        estilo.theme_use("clam")
        estilo.configure("TFrame", background="#edf2f8")
        estilo.configure("TLabel", background="#edf2f8", foreground="#19283b")
        estilo.configure("Titulo.TLabel", font=("TkDefaultFont", 23, "bold"))
        estilo.configure("Subtitulo.TLabel", font=("TkDefaultFont", 15, "bold"))
        estilo.configure("TButton", padding=(9, 6))

        marco = ttk.Frame(ventana, padding=16)
        marco.pack(fill="both", expand=True)
        encabezado = ttk.Frame(marco)
        encabezado.pack(fill="x", pady=(0, 12))
        self.titulo = ttk.Label(encabezado, text="Mapa de rutas de TransMilenio", style="Titulo.TLabel")
        self.titulo.pack(anchor="w")
        etiqueta = "RED DE DEMOSTRACIÓN · HORARIOS SIMULADOS" if demo else "RED IMPORTADA · DÍA DE SERVICIO"
        ttk.Label(encabezado, text=etiqueta).pack(anchor="w", pady=(3, 0))
        self.menu = ttk.Frame(marco)  # aquí van los botones de las vistas
        self.menu.pack(fill="x", pady=(0, 12))
        cuerpo = ttk.Frame(marco)
        cuerpo.pack(fill="both", expand=True)
        # El mapa recibe la red y la función que se llama al hacer clic en una estación.
        self.mapa = Mapa(cuerpo, red, self.elegir_en_mapa)
        self.mapa.pack(side="left", fill="both", expand=True)
        self.lateral = ttk.Frame(cuerpo, width=340)  # panel derecho con los formularios
        self.lateral.pack(side="right", fill="y", padx=(16, 0))
        self.lateral.pack_propagate(False)  # que el panel no cambie de ancho
        ttk.Label(marco, text="● Estación    ◉ Intercambio    ━ Ruta    ━ Viaje seleccionado en amarillo").pack(anchor="w", pady=(9, 0))
        self.configurar_menu()
        self.abrir("Planear viaje")  # vista inicial

    def configurar_menu(self):
        """Crea los botones del menú. Cambian según si es usuario o operador."""
        for widget in self.menu.winfo_children():
            widget.destroy()
        vistas = ["Planear viaje", "Búsqueda", "Filtro", "Próximo bus", "Ranking", "Rendimiento"]
        if self.operador:
            vistas = ["Editar rutas", "Simular abordaje", "Planear viaje", "Filtro", "Rendimiento"]
        for vista in vistas:
            # v=vista guarda el valor actual (si no, todos los botones abrirían la última vista).
            ttk.Button(self.menu, text=vista, command=lambda v=vista: self.abrir(v)).pack(side="left", padx=(0, 5))
        ttk.Button(self.menu, text="Salir de operación" if self.operador else "Operador de red",
                   command=self.acceso).pack(side="right")

    def abrir(self, vista):
        """Limpia el panel lateral y muestra la vista elegida."""
        self.seccion = vista
        for widget in self.lateral.winfo_children():
            widget.destroy()
        self.mapa.viaje = []
        self.mapa.dibujar()
        ttk.Label(self.lateral, text=vista, style="Subtitulo.TLabel").pack(anchor="w", pady=(2, 12))
        # Se busca en el diccionario la función de la vista y se llama.
        {
            "Planear viaje": self.planear, "Búsqueda": self.busqueda, "Filtro": self.filtro,
            "Próximo bus": self.proximo, "Ranking": self.ranking, "Editar rutas": self.editar,
            "Simular abordaje": self.simulacion, "Rendimiento": self.rendimiento,
        }[vista]()

    # ------------------------------------------------------------------
    # Ayudas para crear widgets
    # ------------------------------------------------------------------

    def campo(self, etiqueta, valor="", opciones=None, padre=None, ancho=24):
        """Crea una etiqueta + caja de texto (o lista desplegable si hay opciones).

        Devuelve (variable, widget). Con variable.get() se lee lo que escribió el usuario.
        """
        padre = padre or self.lateral
        ttk.Label(padre, text=etiqueta).pack(anchor="w", pady=(5, 3))
        variable = tk.StringVar(value=valor)
        if opciones is None:
            widget = ttk.Entry(padre, textvariable=variable, width=ancho)
        else:
            widget = ttk.Combobox(padre, textvariable=variable, values=opciones, width=ancho, state="readonly")
        widget.pack(fill="x", pady=(0, 5))
        return variable, widget

    def boton(self, etiqueta, accion, padre=None):
        ttk.Button(padre or self.lateral, text=etiqueta, command=accion).pack(anchor="w", pady=(4, 4))

    def salida(self):
        """Crea una caja de texto de solo lectura y devuelve una función para escribir en ella."""
        marco = ttk.Frame(self.lateral)
        marco.pack(fill="both", expand=True, pady=(10, 0))
        texto = tk.Text(marco, wrap="word", height=4, bg="#f9fbfe", fg="#19283b",
                        relief="flat", padx=10, pady=8)
        barra = ttk.Scrollbar(marco, orient="vertical", command=texto.yview)
        texto.configure(yscrollcommand=barra.set, state="disabled")
        barra.pack(side="right", fill="y")
        texto.pack(fill="both", expand=True)

        def mostrar(mensaje):
            # Hay que habilitar la caja un momento para poder escribir en ella.
            texto.configure(state="normal")
            texto.delete("1.0", "end")
            texto.insert("1.0", mensaje)
            texto.configure(state="disabled")
        return mostrar

    def ejecutar(self, accion, mostrar):
        """Corre una acción y muestra su resultado. Si el motor lanza ValueError, muestra el mensaje."""
        try:
            mostrar(accion())
        except ValueError as error:
            mostrar(str(error))

    def elegir_en_mapa(self, nombre):
        """Al hacer clic en una estación del mapa, se pone su nombre en el campo que toque."""
        if self.seccion == "Planear viaje":
            # Primer clic llena el origen; el segundo, el destino.
            (self.origen if not self.origen.get() else self.destino).set(nombre)
        elif self.seccion in ("Búsqueda", "Filtro", "Próximo bus", "Editar rutas", "Simular abordaje"):
            self.estacion.set(nombre)

    # ------------------------------------------------------------------
    # Vistas del usuario
    # ------------------------------------------------------------------

    def planear(self):
        """Vista R5: planear un viaje y resaltarlo en el mapa."""
        self.origen, _ = self.campo("Estación de origen")
        self.destino, _ = self.campo("Estación de destino")
        ttk.Label(self.lateral, text="Puedes seleccionar estaciones en el mapa.", wraplength=300).pack(anchor="w", pady=5)

        def calcular():
            self.mapa.viaje = []
            self.mapa.dibujar()
            viaje = self.red.viaje(self.origen.get(), self.destino.get())  # llamada al motor
            if viaje is None:
                return "No hay un viaje directo ni con un solo transbordo entre estas estaciones abiertas."
            if not viaje:
                return "Ya estás en la estación de destino."
            self.mapa.filtro_ruta = self.mapa.filtro_estacion = ""
            self.mapa.viaje = viaje  # el mapa lo pinta en amarillo
            self.mapa.dibujar()
            # Hora actual de Bogotá (UTC-5) para estimar la llegada.
            ahora = datetime.now(timezone(timedelta(hours=-5)))
            hora = f"{ahora.hour:02d}:{ahora.minute:02d}"
            llegada = self.red.estimar(viaje, hora)
            tramos = [f"Toma {ruta} en {paradas[0]} y baja en {paradas[-1]} ({len(paradas)-1} paradas)."
                      for ruta, paradas in viaje]
            duracion = sum(self.red.duracion_tramo(paradas) for _, paradas in viaje)
            estimacion = (f"{duracion} min de recorrido estimado. Sin horario para calcular la espera."
                          if llegada is None else f"Hora estimada de llegada: {reloj(llegada)} · Bogotá")
            return "\n\n".join([estimacion, *tramos])

        self.boton("Calcular viaje", lambda: self.ejecutar(calcular, mostrar))
        mostrar = self.salida()

    def busqueda(self):
        """Vista R1 (estado), R2 (autocompletar mientras se escribe) y R3 (rango)."""
        self.estacion, entrada = self.campo("Nombre exacto")
        k, _ = self.campo("Máximo de sugerencias", "8")
        opciones = tk.Listbox(self.lateral, height=5, exportselection=False)
        opciones.pack(fill="x", pady=(0, 6))

        def actualizar(*_):
            # Se llama cada vez que cambia el texto: muestra las sugerencias (R2).
            opciones.delete(0, "end")
            if self.estacion.get().strip():
                try:
                    for nombre in self.red.completar(self.estacion.get(), int(k.get())):
                        opciones.insert("end", nombre)
                except ValueError:
                    pass  # si k no es un número, simplemente no se muestran sugerencias

        def seleccionar(_):
            # Al elegir una sugerencia, se copia al campo y se consulta.
            if opciones.curselection():
                self.estacion.set(opciones.get(opciones.curselection()[0]))
                consultar()

        def consultar():
            mostrar(self.red.estado(self.estacion.get()))  # R1

        # trace_add("write", ...) = "avísame cada vez que cambie el valor".
        self.estacion.trace_add("write", actualizar)
        k.trace_add("write", actualizar)
        opciones.bind("<<ListboxSelect>>", seleccionar)
        entrada.bind("<Return>", lambda _: consultar())  # Enter también consulta
        self.boton("Consultar estado", consultar)
        inicio, _ = self.campo("Rango alfabético · desde", "CALLE 26")
        fin, _ = self.campo("Hasta", "CALLE 80")
        self.boton("Listar abiertas", lambda: self.ejecutar(
            lambda: "\n".join(self.red.rango(inicio.get(), fin.get())) or "Sin coincidencias.", mostrar))
        mostrar = self.salida()

    def codigos(self):
        """Códigos de ruta que se muestran en las listas (el operador ve también las cerradas)."""
        return [ruta.codigo for ruta in self.red.rutas if self.operador or ruta.activa]

    def filtro(self):
        """Vista para dibujar solo una ruta o solo las rutas de una estación."""
        ruta, _ = self.campo("Ruta", self.mapa.filtro_ruta, ["", *self.codigos()])
        self.estacion, _ = self.campo("Estación", self.mapa.filtro_estacion)

        def aplicar():
            nombre = self.estacion.get().strip()
            if nombre:
                nombre = clave(nombre)
                estado = self.red.estado(nombre)
                if estado == "No existe" or (not self.operador and estado == "Cerrada"):
                    return "Selecciona una estación disponible."
            self.mapa.filtro_ruta, self.mapa.filtro_estacion = ruta.get(), nombre
            self.mapa.dibujar()
            return "Mapa actualizado."

        def limpiar():
            ruta.set("")
            self.estacion.set("")
            self.ejecutar(aplicar, mostrar)

        self.boton("Aplicar filtro", lambda: self.ejecutar(aplicar, mostrar))
        self.boton("Mostrar toda la red", limpiar)
        mostrar = self.salida()

    def proximo(self):
        """Vista R4: próximo bus de una ruta en una estación."""
        self.estacion, _ = self.campo("Estación")
        codigos = self.codigos()
        ruta, _ = self.campo("Ruta", codigos[0] if codigos else "", codigos)
        ahora = datetime.now(timezone(timedelta(hours=-5)))  # hora de Bogotá por defecto
        hora, _ = self.campo("Hora de consulta (HH:MM)", ahora.strftime("%H:%M"))

        def consultar():
            bus = self.red.proximo_bus(self.estacion.get(), ruta.get(), hora.get())
            return f"Próximo bus a las {reloj(bus)}." if bus is not None else "Sin servicio disponible desde esa hora."

        self.boton("Consultar", lambda: self.ejecutar(consultar, mostrar))
        mostrar = self.salida()

    def ranking(self):
        """Vista R6: estaciones con más buses."""
        k, _ = self.campo("Número de estaciones", "8")

        def consultar():
            return "\n".join(f"{i}. {nombre} · {total} buses"
                             for i, (nombre, total) in enumerate(self.red.ranking(int(k.get())), 1)) or "Sin resultados."

        self.boton("Ver ranking", lambda: self.ejecutar(consultar, mostrar))
        mostrar = self.salida()
        self.ejecutar(consultar, mostrar)  # se muestra apenas se abre la vista

    # ------------------------------------------------------------------
    # Modo operador
    # ------------------------------------------------------------------

    def acceso(self):
        """Ventana de usuario y contraseña para entrar como operador (o salir del modo)."""
        if self.operador:
            self.cambiar_modo(False)
            return
        dialogo = tk.Toplevel(self.ventana)
        dialogo.title("Acceso de operador")
        dialogo.transient(self.ventana)
        dialogo.grab_set()  # bloquea la ventana principal mientras está abierta
        marco = ttk.Frame(dialogo, padding=20)
        marco.pack(fill="both", expand=True)
        usuario, entrada = self.campo("Usuario", padre=marco)
        clave, secreta = self.campo("Contraseña", padre=marco)
        secreta.configure(show="•")  # oculta lo que se escribe
        aviso = ttk.Label(marco, text="")
        aviso.pack(anchor="w")

        def entrar():
            # Credenciales académicas fijas (ver README).
            if (usuario.get(), clave.get()) == ("Pidove", "Carracosta"):
                dialogo.destroy()
                self.cambiar_modo(True)
            else:
                aviso.configure(text="Credenciales incorrectas.")

        dialogo.bind("<Return>", lambda _: entrar())
        self.boton("Ingresar", entrar, marco)
        entrada.focus_set()

    def cambiar_modo(self, operador):
        """Pasa de usuario a operador o al revés y actualiza menú, título y mapa."""
        self.operador = self.mapa.operador = operador
        self.mapa.filtro_ruta = self.mapa.filtro_estacion = ""
        self.titulo.configure(text="Mapa editable de TransMilenio" if operador else "Mapa de rutas de TransMilenio")
        self.configurar_menu()
        self.abrir("Editar rutas" if operador else "Planear viaje")

    def editar(self):
        """Vista R7, R8 y R9: editar rutas, cerrar/abrir estaciones, deshacer y rehacer."""
        codigos = self.codigos()
        ruta, selector = self.campo("Ruta", codigos[0] if codigos else "", codigos)
        self.estacion, _ = self.campo("Estación")
        numero, _ = self.campo("Número de parada (desde 1)", "1")

        def recorrido(inverso=False):
            # Lista numerada de las paradas, marcando las cerradas.
            paradas = self.red.recorrido(ruta.get(), inverso)
            estado = "Abierta" if self.red.ruta_activa(ruta.get()) else "Cerrada"
            return f"{ruta.get()} · {estado}\n\n" + "\n".join(
                f"{i}. {nombre}" + (" (cerrada)" if not self.red.buscar(nombre) else "")
                for i, nombre in enumerate(paradas, 1)
            )

        def cambiar(accion, mensaje):
            # Ejecuta un cambio en el motor, redibuja el mapa y muestra el recorrido actualizado.
            resultado = accion()
            self.mapa.viaje = []
            self.mapa.dibujar()
            if resultado is False:  # deshacer/rehacer devuelven False si no había nada
                return "No hay cambios disponibles."
            return mensaje + ("\n\n" + recorrido() if ruta.get() else "")

        # (texto del botón, función que se ejecuta)
        botones = (
            ("Ver recorrido", recorrido),
            ("Ver en sentido inverso", lambda: recorrido(True)),
            ("Insertar después del número", lambda: cambiar(
                lambda: self.red.insertar(ruta.get(), int(numero.get()), self.estacion.get()), "Parada insertada.")),
            ("Quitar parada numerada", lambda: cambiar(
                lambda: self.red.quitar(ruta.get(), int(numero.get())), "Parada eliminada.")),
            ("Abrir o cerrar estación", lambda: cambiar(
                lambda: self.red.alternar_estacion(self.estacion.get()), "Estado de la estación actualizado.")),
            ("Abrir o cerrar ruta", lambda: cambiar(
                lambda: self.red.alternar_ruta(ruta.get()), "Estado de la ruta actualizado.")),
            ("← Deshacer", lambda: cambiar(self.red.deshacer, "Cambio deshecho.")),
            ("Rehacer →", lambda: cambiar(self.red.rehacer, "Cambio rehecho.")),
        )
        acciones = ttk.Frame(self.lateral)
        acciones.pack(fill="x")
        # Botones en dos columnas: fila = i // 2, columna = i % 2.
        for i, (nombre, accion) in enumerate(botones):
            ttk.Button(acciones, text=nombre, command=lambda a=accion: self.ejecutar(a, mostrar)).grid(
                row=i // 2, column=i % 2, sticky="ew", pady=2)
        mostrar = self.salida()
        # Al cambiar de ruta en la lista, se muestra su recorrido.
        selector.bind("<<ComboboxSelected>>", lambda _: self.ejecutar(recorrido, mostrar))
        if codigos:
            self.ejecutar(recorrido, mostrar)

    def simulacion(self):
        """Vista R10: armar filas de personas por estación y simular el abordaje."""
        self.estacion, _ = self.campo("Estación")
        pasajeros, _ = self.campo("Personas en la fila", "200000")
        filas = {}  # estación -> personas en la fila (en el front sí se puede usar dict)
        buses, _ = self.campo("Buses por estación", "100")
        cupo, _ = self.campo("Cupo por bus", "160")
        intervalo, _ = self.campo("Intervalo en minutos", "4")

        def agregar():
            nombre = clave(self.estacion.get())
            personas = int(pasajeros.get())
            if not self.red.buscar(nombre) or personas < 0:
                raise ValueError("Selecciona una estación abierta y una demanda de cero o más.")
            filas[nombre] = personas
            return "\n".join(f"{estacion}: {total:,} personas" for estacion, total in filas.items())

        def correr():
            capacidad = int(cupo.get())
            resultados = simular(self.red, filas.items(), int(buses.get()), capacidad, int(intervalo.get()))
            return "\n\n".join(
                f"{nombre}\n{abordaron:,} abordaron en {usados} buses.\n"
                f"{pendientes:,} en espera de {total:,}.\n"
                + (f"Último abordaje en el minuto {ultimo}. Suben las personas "
                   f"{primero:,} a {abordaron:,} de la fila."
                   if ultimo is not None else "Sin abordajes.")
                for nombre, total, usados, abordaron, pendientes, ultimo, primero in resultados
            ) or "Agrega al menos una estación."

        self.boton("Agregar o actualizar fila", lambda: self.ejecutar(agregar, mostrar))
        self.boton("Simular", lambda: self.ejecutar(correr, mostrar))
        mostrar = self.salida()

    # ------------------------------------------------------------------
    # R11: panel de rendimiento
    # ------------------------------------------------------------------

    def rendimiento(self):
        ttk.Label(self.lateral, text="Mide cada requisito sobre redes sintéticas crecientes. El gráfico usa la mediana de siete ejecuciones.",
                  wraplength=290).pack(anchor="w")
        self.boton("Ejecutar mediciones", self.graficar)

    def graficar(self):
        """Corre las mediciones del motor y las dibuja en una ventana nueva."""
        datos = medir()
        ventana = tk.Toplevel(self.ventana)
        ventana.title("Panel de rendimiento")
        marco = ttk.Frame(ventana, padding=16)
        marco.pack(fill="both", expand=True)
        opcion, selector = self.campo("Operación", datos[0][0], [fila[0] for fila in datos], padre=marco)
        grafico = tk.Canvas(marco, width=650, height=290, bg="#101c2b", highlightthickness=0)
        grafico.pack(pady=10)
        nota = ttk.Label(marco, wraplength=650, justify="left")
        nota.pack(anchor="w")

        def dibujar(_=None):
            # Gráfico de líneas: eje x = tamaño de la red, eje y = tiempo (escalado al máximo).
            nombre, cota, detalle, puntos = datos[selector.current()]
            grafico.delete("all")
            pico = max(tiempo for _, tiempo in puntos) or 1
            grafico.create_text(14, 16, text="Tiempo (µs)", anchor="w", fill="#fff")
            grafico.create_line(60, 35, 60, 235, 625, 235, fill="#8594aa")  # ejes
            coordenadas = []
            for i, (n, tiempo) in enumerate(puntos):
                x, y = 108 + 160 * i, 235 - 169 * tiempo / pico
                coordenadas.extend((x, y))
                grafico.create_text(x, 253, text=f"N = {n:,}", fill="#fff")
            grafico.create_line(*coordenadas, width=3, fill="#29bbf5")
            for i, (_, tiempo) in enumerate(puntos):
                x, y = coordenadas[2*i:2*i+2]
                grafico.create_oval(x-4, y-4, x+4, y+4, fill="#ffe371", outline="")
                grafico.create_text(x, y-15, text=f"{tiempo:.2f}", fill="#fff")
            # Cuántas veces creció el tiempo entre la red más pequeña y la más grande.
            razon = puntos[-1][1] / puntos[0][1] if puntos[0][1] else 0
            nota.configure(text=f"{nombre}\nComplejidad esperada: {cota}\n{detalle}\n"
                                f"La última red tiene 64 veces más estaciones. El tiempo observado varió por un factor de {razon:.2f}.")

        selector.bind("<<ComboboxSelected>>", dibujar)
        dibujar()


def main():
    """Punto de entrada: lee --datos, carga la red y abre la ventana."""
    base = Path(__file__).resolve().parent / "datos"
    demo = base / "demo"
    # Si no existe la red de demostración, se usa la real por defecto.
    defecto = demo if demo.exists() else base / "real"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=defecto, help="Carpeta con los tres CSV")
    args = parser.parse_args()
    try:
        red = Red(args.datos)  # forma del contrato: Red(carpeta)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Error al cargar la red: {error}\n")
    ventana = tk.Tk()
    Aplicacion(ventana, red, args.datos.resolve() == demo)
    ventana.mainloop()  # se queda esperando clics hasta que se cierre la ventana


if __name__ == "__main__":
    main()
