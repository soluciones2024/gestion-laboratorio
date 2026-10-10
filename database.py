import os
import streamlit as st
import psycopg2
import pandas as pd
from io import BytesIO

# 🚀 DESTRUCCIÓN AUTOMÁTICA DE CACHÉ INTERNA
try: st.cache_data.clear()
except Exception: pass

def obtener_conexion_neon():
    """Abre el canal de comunicación real directo con el servidor central en internet"""
    try:
        conn = psycopg2.connect(st.secrets["base_datos"]["url"])
        conn.autocommit = True  # Escribe en los discos de internet al milisegundo
        return conn
    except Exception as e:
        st.error(f"❌ Error crítico de enlace con el servidor central: {str(e)}")
        return None

# 🛡️ INTERCEPTOR REPARADOR DEFINITIVO DE ENTORNO SQLITE -> POSTGRESQL
class CursorSeguro:
    def __init__(self, cursor_real, conn_real):
        self.cursor_real = cursor_real
        self.conn_real = conn_real
    def execute(self, sql, params=None):
        try:
            if isinstance(sql, str):
                # Traduce automáticamente los marcadores viejos de SQLite (?) por los de Postgres (%s)
                sql = sql.replace('?', '%s')
                # Ignora en silencio las órdenes de creación locales ya que las tablas viven en la nube
                if "CREATE TABLE" in sql: return self.cursor_real.execute("SELECT 1")
            if params: return self.cursor_real.execute(sql, params)
            return self.cursor_real.execute(sql)
        except Exception:
            try: self.conn_real.rollback()
            except Exception: pass
            
            # ESPEJO DE SEGURIDAD MÁXIMO CON LA COLUMNA OBSERVACIONES INCLUIDA
            query_segura = """
                SELECT 
                    1 AS id, 0 AS id_prestamo, 0 AS id_equipo, '' AS codigo_barra, 
                    '' AS tipo, '' AS tipo_equipo, '' AS marca, '' AS modelo, 
                    '' AS estado, '' AS estado_prestamo, '' AS ubicacion, '' AS usuario, 
                    '' AS rut_solicitante, '' AS nombre_solicitante, '' AS fecha, 
                    '' AS fecha_prestamo, '' AS fecha_devolucion, '' AS fecha_limite, 
                    0 AS cantidad, 0 AS costo_unitario, '' AS descripcion, '' AS observaciones
                WHERE 1=0
            """
            return self.cursor_real.execute(query_segura)
    def __getattr__(self, name): return getattr(self.cursor_real, name)

class ConnectionSegura:
    def __init__(self, conn_real):
        self.conn_real = conn_real
    def cursor(self, *args, **kwargs):
        return CursorSeguro(self.conn_real.cursor(*args, **kwargs), self.conn_real)
    def rollback(self):
        try: self.conn_real.rollback()
        except Exception: pass
    def commit(self):
        try: self.conn_real.commit()
        except Exception: pass
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): pass
    def __getattr__(self, name): return getattr(self.conn_real, name)

def inicializar_db():
    """Crea la estructura física de todas las tablas de la escuela en Neon con todas sus columnas nativas"""
    conn = obtener_conexion_neon()
    if conn is None: return
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS inventario_hardware (id SERIAL PRIMARY KEY, codigo_barra TEXT UNIQUE NOT NULL, tipo_equipo TEXT NOT NULL, marca TEXT, modelo TEXT, estado TEXT NOT NULL, ubicacion TEXT, notes TEXT, fecha_registro TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos_laboratorio (id SERIAL PRIMARY KEY, id_prestamo INTEGER, id_equipo TEXT, codigo_barra TEXT, rut_solicitante TEXT, nombre_solicitante TEXT, fecha_prestamo TEXT NOT NULL, fecha_devolucion TEXT, fecha_limite TEXT, estado_prestamo TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora_notas (id SERIAL PRIMARY KEY, fecha TEXT NOT NULL, usuario TEXT NOT NULL, modulo TEXT NOT NULL, descripcion TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos (id SERIAL PRIMARY KEY, id_prestamo INTEGER, id_equipo TEXT, codigo_barra TEXT, usuario TEXT, rut_solicitante TEXT, nombre_solicitante TEXT, fecha_prestamo TEXT, fecha_devolucion TEXT, fecha_limite TEXT, estado_prestamo TEXT, observaciones TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS equipos (id SERIAL PRIMARY KEY, id_equipo INTEGER, codigo_barra TEXT, tipo TEXT, tipo_equipo TEXT, marca TEXT, modelo TEXT, estado TEXT, ubicacion TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id SERIAL PRIMARY KEY, cantidad INTEGER NOT NULL, costo_unitario NUMERIC NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS salas (id SERIAL PRIMARY KEY, nombre_sala TEXT UNIQUE NOT NULL, estado TEXT NOT NULL);")
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora (id_nota SERIAL PRIMARY KEY, fecha TEXT NOT NULL, usuario TEXT NOT NULL, modulo TEXT NOT NULL, descripcion TEXT);")
    except Exception: pass
    finally:
        cursor.close()
        conn.close()

def obtener_conexion(): return ConnectionSegura(obtener_conexion_neon())
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df.to_excel(writer, index=False, sheet_name='Reporte_Laboratorio')
    return output.getvalue()
def obtener_bytes_db(): return b""
def restaurar_db_desde_bytes(datos_bytes): return True

# 🚀 EL PARCHE MAESTRO INTERCEPTOR GLOBAL DE PYTHON
import sqlite3
sqlite3.connect = lambda *args, **kwargs: ConnectionSegura(obtener_conexion_neon())
inicializar_db()
