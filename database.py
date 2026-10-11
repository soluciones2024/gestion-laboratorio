import os
import sqlite3
import pandas as pd
from io import BytesIO

DB_PATH = "laboratorio.db"

def obtener_conexion():
    """Abre el archivo SQLite local de forma rápida y nativa"""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    """Crea las tablas de la escuela en el disco duro si el archivo no existe"""
    conn = obtener_conexion()
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS inventario_hardware (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo_barra TEXT UNIQUE NOT NULL, tipo_equipo TEXT NOT NULL, marca TEXT, modelo TEXT, estado TEXT NOT NULL, ubicacion TEXT, notes TEXT, fecha_registro TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos_laboratorio (id INTEGER PRIMARY KEY AUTOINCREMENT, id_prestamo INTEGER, id_equipo TEXT, codigo_barra TEXT, rut_solicitante TEXT, nombre_solicitante TEXT, fecha_prestamo TEXT NOT NULL, fecha_devolucion TEXT, fecha_limite TEXT, estado_prestamo TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora_notas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, usuario TEXT NOT NULL, modulo TEXT NOT NULL, descripcion TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_prestamo INTEGER, id_equipo TEXT, codigo_barra TEXT, usuario TEXT, rut_solicitante TEXT, nombre_solicitante TEXT, fecha_prestamo TEXT, fecha_devolucion TEXT, fecha_limite TEXT, estado_prestamo TEXT, observaciones TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS equipos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_equipo INTEGER, codigo_barra TEXT, tipo TEXT, tipo_equipo TEXT, marca TEXT, modelo TEXT, estado TEXT, ubicacion TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id INTEGER PRIMARY KEY AUTOINCREMENT, cantidad INTEGER NOT NULL, costo_unitario NUMERIC NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS salas (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_sala TEXT UNIQUE NOT NULL, estado TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora (id_nota INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, usuario TEXT NOT NULL, modulo TEXT NOT NULL, descripcion TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_usuario TEXT UNIQUE NOT NULL, clave TEXT NOT NULL, rol TEXT NOT NULL, correo TEXT, nombre TEXT, fecha_creacion TEXT, usuario_creador TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS cuentas_secundarias (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_usuario TEXT UNIQUE NOT NULL, clave TEXT NOT NULL, rol TEXT NOT NULL, correo TEXT, nombre TEXT, fecha_creacion TEXT, usuario_creador TEXT);")
        conn.commit()
    except Exception:
        pass
    finally:
        cursor.close()
        conn.close()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Laboratorio')
    return output.getvalue()

def obtener_bytes_db():
    try:
        with open(DB_PATH, "rb") as f: return f.read()
    except Exception: return b""

def restaurar_db_desde_bytes(datos_bytes):
    try:
        with open(DB_PATH, "wb") as f: f.write(datos_bytes)
        return True
    except Exception: return False

inicializar_db()
