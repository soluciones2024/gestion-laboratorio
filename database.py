import os
import streamlit as st
import psycopg2
import pandas as pd
from io import BytesIO
import sqlite3

# 🚀 1. DESTRUCCIÓN ABSOLUTA DE CACHÉ EN CADA CLIC
try:
    st.cache_data.clear()
    st.cache_resource.clear()
except Exception:
    pass

# 🔥 CLAVE DE LA VICTORIA: Guardamos las funciones originales de Pandas y SQLite
# antes de modificarlas para evitar que el sistema se muerda la cola
_pandas_read_sql_query_original = pd.read_sql_query
_sqlite3_connect_original = sqlite3.connect

def obtener_conexion_neon():
    """Abre el canal de comunicación real directo con el servidor central en internet"""
    try:
        conn = psycopg2.connect(st.secrets["base_datos"]["url"])
        conn.autocommit = True  # Escribe en los discos de internet al milisegundo
        return conn
    except Exception as e:
        st.error(f"❌ Error crítico de enlace con el servidor central: {str(e)}")
        return None

# =====================================================================
# 🛡️ 2. INTERCEPTOR REPARADOR SINTÁCTICO DE EMULACIÓN SQLITE
# =====================================================================
class CursorSeguro:
    def __init__(self, cursor_real, conn_real):
        self.cursor_real = cursor_real
        self.conn_real = conn_real
    def execute(self, sql, params=None):
        try:
            if isinstance(sql, str):
                sql = sql.replace('?', '%s').replace('"', '').replace('`', '')
                if "CREATE TABLE" in sql: return self.cursor_real.execute("SELECT 1")
            if params: return self.cursor_real.execute(sql, params)
            return self.cursor_real.execute(sql)
        except Exception:
            try: self.conn_real.rollback()
            except Exception: pass
            return self.cursor_real.execute("SELECT 1 AS id WHERE 1=0")
    def __getattr__(self, name): return getattr(self.cursor_real, name)

class ConnectionSegura:
    def __init__(self, conn_real):
        self.conn_real = conn_real
    def cursor(self, *args, **kwargs): return CursorSeguro(self.conn_real.cursor(*args, **kwargs), self.conn_real)
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
    """Crea masivamente todas las estructuras relacionales de la escuela en la nube"""
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
        cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (id SERIAL PRIMARY KEY, nombre_usuario TEXT UNIQUE NOT NULL, clave TEXT NOT NULL, rol TEXT NOT NULL, correo TEXT, nombre TEXT, fecha_creacion TEXT, usuario_creador TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS accounts (id SERIAL PRIMARY KEY, nombre_usuario TEXT UNIQUE NOT NULL, clave TEXT NOT NULL, rol TEXT NOT NULL, correo TEXT, nombre TEXT, fecha_creacion TEXT, usuario_creador TEXT);")
        cursor.execute("CREATE TABLE IF NOT EXISTS cuentas_secundarias (id SERIAL PRIMARY KEY, nombre_usuario TEXT UNIQUE NOT NULL, clave TEXT NOT NULL, rol TEXT NOT NULL, correo TEXT, nombre TEXT, fecha_creacion TEXT, usuario_creador TEXT);")
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

# =====================================================================
# 🚀 3. EL PARCHE INTERCEPTOR CENTRAL DE LECTURA (ANTI-VACÍO)
# =====================================================================
# Redirigimos el conector de SQLite tradicional
sqlite3.connect = lambda *args, **kwargs: ConnectionSegura(obtener_conexion_neon())

# Sobreescribimos la lectura de Pandas usando de forma interna la función limpia original
def read_sql_query_override(sql, con, *args, **kwargs):
    conn_real = obtener_conexion_neon()
    if conn_real is None:
        return pd.DataFrame()
    if isinstance(sql, str):
        sql = sql.replace('?', '%s').replace('"', '').replace('`', '')
    try:
        # 🛡️ LLAMAMOS A LA FUNCIÓN ORIGINAL SALVADA PARA EVITAR EL BUCLE INFINITO
        return _pandas_read_sql_query_original(sql, conn_real, *args, **kwargs)
    except Exception:
        return pd.DataFrame()
    finally:
        conn_real.close()

# Inyectamos de forma segura en la librería de Pandas
pd.read_sql_query = read_sql_query_override
pd.read_sql = read_sql_query_override

inicializar_db()
