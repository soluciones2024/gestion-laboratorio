# =====================================================================
# 🌐 MOTOR SECUNDARIO DE RED (DATABASE.PY) - REFRESH TOTAL ANTI-CACHÉ
# =====================================================================
import os
import streamlit as st
import psycopg2
import pandas as pd
from io import BytesIO

# 🚀 TRUCO MAESTRO DE INYECCIÓN DE CONTROL:
# Limpiamos físicamente toda la caché de datos de Streamlit en cada carga
# de página para evitar que Pandas retenga tablas simuladas viejas.
try:
    st.cache_data.clear()
except Exception:
    pass

def obtener_conexion():
    """Abre el canal de comunicación real directo con el servidor en internet"""
    try:
        db_url = st.secrets["base_datos"]["url"]
        conn = psycopg2.connect(db_url)
        conn.autocommit = True  # Fuerza el guardado inmediato en red
        return conn
    except Exception as e:
        st.error(f"❌ Error de red en database.py: {str(e)}")
        return None

def inicializar_db():
    """Crea la arquitectura de la escuela directamente en la nube si no existe"""
    conn = obtener_conexion()
    if conn is None:
        return
        
    cursor = conn.cursor()
    try:
        # Creamos las tablas físicas oficiales en tu servidor central de Neon
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventario_hardware (
                id SERIAL PRIMARY KEY,
                codigo_barra TEXT UNIQUE NOT NULL,
                tipo_equipo TEXT NOT NULL,
                marca TEXT,
                modelo TEXT,
                estado TEXT NOT NULL,
                ubicacion TEXT,
                notes TEXT,
                fecha_registro TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prestamos_laboratorio (
                id SERIAL PRIMARY KEY,
                codigo_barra TEXT NOT NULL,
                rut_solicitante TEXT NOT NULL,
                nombre_solicitante TEXT NOT NULL,
                fecha_prestamo TEXT NOT NULL,
                fecha_devolucion TEXT,
                estado_prestamo TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prestamos (
                id SERIAL PRIMARY KEY,
                id_equipo TEXT NOT NULL,
                usuario TEXT NOT NULL,
                fecha_limite TEXT NOT NULL,
                estado_prestamo TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bitacora (
                id_nota SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                usuario TEXT NOT NULL,
                modulo TEXT NOT NULL,
                descripcion TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bitacora_notas (
                id SERIAL PRIMARY KEY,
                fecha TEXT NOT NULL,
                usuario TEXT NOT NULL,
                modulo TEXT NOT NULL,
                descripcion TEXT NOT NULL
            );
        """)
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

# 🚀 PARCHE DE RED REDIRECTOR:
# Capturamos en silencio cualquier llamado antiguo a SQLite que venga de tu app.py
# y lo obligamos a viajar por internet directo a la nube relacional de Neon.
import sqlite3
conn_global = obtener_conexion()
sqlite3.connect = lambda *args, **kwargs: conn_global
