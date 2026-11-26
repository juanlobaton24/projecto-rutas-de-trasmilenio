# Este archivo convierte la carpeta motor/ en un "paquete" de Python.
# Gracias a estas líneas se puede escribir:  from motor import Red, simular_fila
# (que es exactamente lo que hace el script de calificación del profesor).
from .red import Red
from .simulacion import simular, simular_fila
