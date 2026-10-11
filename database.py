import os
import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
import requests
import base64

DB_PATH = "laboratorio.db"

# 🛡️ CLAVE DE LA VICTORIA: Guardamos la función de conexión original de Python
# antes de hacer cualquier cambio para evitar bucles infinitos (RecursionError)
_sqlite3_connect_original = sqlite3.connect

def descargar_base_datos():
    """Descarga tu base de datos real con todos tus datos históricos desde GitHub"""
    try:
        url = "https://githubusercontent.com"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(DB_PATH, "wb") as f:
                f.write(response.content)
            return True
    except Exception:
        pass
    return False

def respaldar_base_datos():
    """Sube tu archivo .db modificado directamente a GitHub de forma transparente"""
    if not os.path.exists(DB_PATH):
        return False
    try:
        token = st.secrets["github"]["token"]
        url = "https://github.com"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Obtenemos el identificador único del archivo en la nube para sobreescribirlo
        res_get = requests.get(url, headers=headers, timeout=5)
        sha = res_get.json().get("sha") if res_get.status_code == 200 else None
        
        with open(DB_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
            
        data = {
            "message": "☁️ Sincronización Automática Escuela",
            "content": content,
            "branch": "master"
        }
        if sha: data["sha"] = sha
            
        requests.put(url, headers=headers, json=data, timeout=15)
        return True
    except Exception:
        return False

# =====================================================================
# ⚙️ FUNCIONES DE INTERFAZ EXIGIDAS POR TU APP.PY
# =====================================================================
def obtener_conexion():
    """Devuelve la conexión SQLite nativa usando la función original salvada"""
    if not os.path.exists(DB_PATH):
        descargar_base_datos()
    return _sqlite3_connect_original(DB_PATH, check_same_thread=False)

def inicializar_db():
    """Asegura la descarga inicial y crea las tablas base si el archivo viene vacío"""
    descargar_base_datos()
    conn = _sqlite3_connect_original(DB_PATH, check_same_thread=False)
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
        respaldar_base_datos()
        return True
    except Exception: return False

# =====================================================================
# 🚀 INTERCEPTOR DE GUARDADO AUTOMÁTICO SEGURO
# =====================================================================
class SQLiteSincronizado:
    def __init__(self, conn_real):
        self.conn_real = conn_real
    def commit(self):
        self.conn_real.commit()
        respaldar_base_datos()  # 🔥 Sube el archivo modificado a GitHub automáticamente en cada commit
    def __enter__(self): 
        return self
    def __exit__(self, exc_type, exc_val, exc_tb): 
        self.conn_real.close()
    def __getattr__(self, name): 
        return getattr(self.conn_real, name)

# Redirección en el motor de Python usando la función original guardada
sqlite3.connect = lambda *args, **kwargs: SQLiteSincronizado(_sqlite3_connect_original(DB_PATH, check_same_thread=False))

# Descarga el archivo e inicializa al encender internet
inicializar_db()
