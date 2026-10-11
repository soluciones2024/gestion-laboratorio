import sqlite3
import streamlit as st  
import io
import os

DB_NAME = "laboratorio.db"

def obtener_conexion():
    """Retorna una conexión limpia a la base de datos."""
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def inicializar_db():
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS equipos (id_equipo TEXT PRIMARY KEY, tipo TEXT, marca TEXT, modelo TEXT, estado TEXT, ubicacion TEXT, fecha_cambio TEXT, num_documento TEXT, proveedor_origen TEXT, costo_compra REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id_compra INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, cantidad INTEGER, costo_unitario REAL, proveedor TEXT, fecha TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos (id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT, id_equipo TEXT, usuario TEXT, rut TEXT, fecha_prestamo TEXT, fecha_limite TEXT, fecha_devolucion TEXT, estado_prestamo TEXT, observaciones TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS infraestructura (id_item INTEGER PRIMARY KEY AUTOINCREMENT, elemento TEXT, ubicacion TEXT, estado TEXT, observaciones TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (rut TEXT PRIMARY KEY, nombre TEXT, correo TEXT, tipo_usuario TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora (id_nota INTEGER PRIMARY KEY AUTOINCREMENT, nota TEXT, fecha TEXT, hora TEXT, estado_nota TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS salas (id_sala INTEGER PRIMARY KEY AUTOINCREMENT, nombre_sala TEXT UNIQUE, encargado TEXT, capacidad INTEGER)")
        
        # LÍNEA INYECTADA: Crea de forma automatizada la tabla para el mantenedor de cuentas
        cursor.execute("CREATE TABLE IF NOT EXISTS cuentas_acceso (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE, password TEXT, rol TEXT, modulos TEXT)")
        
        columnas_nuevas = [("num_documento", "TEXT"), ("proveedor_origen", "TEXT"), ("costo_compra", "REAL")]
        for col, tipo in columnas_nuevas:
            try:
                cursor.execute(f"ALTER TABLE equipos ADD COLUMN {col} {tipo}")
            except sqlite3.OperationalError:
                pass
                
        try:
            cursor.execute("ALTER TABLE bitacora ADD COLUMN estado_nota TEXT")
        except sqlite3.OperationalError:
            pass
            
        conn.commit()

def to_excel(df):
    output = io.BytesIO()
    import pandas as pd  
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

def obtener_bytes_db():
    if os.path.exists(DB_NAME):
        try:
            with open(DB_NAME, "rb") as f:
                return f.read()
        except Exception:
            return None
    return None

def restaurar_db_desde_bytes(datos_bytes):
    with open(DB_NAME, "wb") as f:
        f.write(datos_bytes)
