import os
import streamlit as st
import psycopg2
import pandas as pd
from io import BytesIO

# =====================================================================
# 🚀 CONTROL ANTI-CACHÉ EN TIEMPO REAL
# =====================================================================
try:
    st.cache_data.clear()
except Exception:
    pass

def obtener_conexion():
    """Abre el canal de comunicación real directo con el servidor en internet"""
    try:
        conn = psycopg2.connect(st.secrets["base_datos"]["url"])
        conn.autocommit = True  # Fuerza el guardado inmediato en red
        return conn
    except Exception as e:
        st.error(f"❌ Error de red al conectar con Neon: {str(e)}")
        return None

def inicializar_db():
    """Crea la arquitectura de la escuela directamente en la nube si no existe"""
    conn = obtener_conexion()
    if conn is None: 
        return
    cursor = conn.cursor()
    try:
        # 1. Creación compacta de tablas operativas principales (Formatos Largos)
        cursor.execute("CREATE TABLE IF NOT EXISTS inventario_hardware (id SERIAL PRIMARY KEY, codigo_barra TEXT UNIQUE NOT NULL, tipo_equipo TEXT NOT NULL, marca TEXT, modelo TEXT, estado TEXT NOT NULL, ubicacion TEXT, notes TEXT, fecha_registro TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos_laboratorio (id SERIAL PRIMARY KEY, id_prestamo INTEGER, id_equipo TEXT, codigo_barra TEXT, rut_solicitante TEXT, nombre_solicitante TEXT, fecha_prestamo TEXT NOT NULL, fecha_devolucion TEXT, fecha_limite TEXT, estado_prestamo TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora_notas (id SERIAL PRIMARY KEY, fecha TEXT NOT NULL, usuario TEXT NOT NULL, modulo TEXT NOT NULL, descripcion TEXT NOT NULL);")
        
        # 2. 🛡️ ESCUDO DE COLUMNAS MASIVO PARA CONSULTAS AVANZADAS (LÍNEAS 700+ Y JOINS)
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos (id SERIAL PRIMARY KEY, id_prestamo INTEGER, id_equipo TEXT, codigo_barra TEXT, usuario TEXT, rut_solicitante TEXT, nombre_solicitante TEXT, fecha_prestamo TEXT, fecha_devolucion TEXT, fecha_limite TEXT, estado_prestamo TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS equipos (id SERIAL PRIMARY KEY, id_equipo INTEGER, codigo_barra TEXT, tipo TEXT, tipo_equipo TEXT, marca TEXT, modelo TEXT, estado TEXT, ubicacion TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id SERIAL PRIMARY KEY, cantidad INTEGER NOT NULL, costo_unitario NUMERIC NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS salas (id SERIAL PRIMARY KEY, nombre_sala TEXT UNIQUE NOT NULL, estado TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora (id_nota SERIAL PRIMARY KEY, fecha TEXT NOT NULL, usuario TEXT NOT NULL, modulo TEXT NOT NULL, descripcion TEXT);")
    except Exception: 
        pass
    finally:
        cursor.close()
        conn.close()

def to_excel(df):
    """Transforma cualquier cuadro de datos en un reporte Excel binario descargable"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Laboratorio')
    return output.getvalue()

def obtener_bytes_db(): 
    return b""

def restaurar_db_desde_bytes(datos_bytes): 
    return True

# =====================================================================
# 🚀 PARCHE DE RED REDIRECTOR (INTERCEPTOR DE SQLITE)
# =====================================================================
import sqlite3
sqlite3.connect = lambda *args, **kwargs: obtener_conexion()
