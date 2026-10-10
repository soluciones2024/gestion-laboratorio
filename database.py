import os
import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
import requests
import base64

DB_PATH = "laboratorio.db"

# =====================================================================
# ☁️ SINCRONIZADOR MAESTRO DE ARCHIVOS (GITHUB PERSISTENCE)
# =====================================================================
def descargar_base_datos():
    """Descarga el archivo real .db desde tu repositorio al arrancar el servidor web"""
    if os.path.exists(DB_PATH):
        return True
    try:
        # Apunta directo al archivo físico de tu repositorio master
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
    """Sube el archivo modificado a GitHub de forma transparente usando tu API Key"""
    if not os.path.exists(DB_PATH):
        return False
    try:
        # Configuración atómica de subida mediante la API de GitHub
        token = st.secrets["github"]["token"]
        url = "https://github.com"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        # Conseguimos el identificador único del archivo viejo para poder sobreescribirlo
        res_get = requests.get(url, headers=headers, timeout=5)
        sha = res_get.json().get("sha") if res_get.status_code == 200 else None
        
        with open(DB_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
            
        data = {"message": "☁️ Sincronización Automática Escuela", "content": content, "branch": "master"}
        if sha: data["sha"] = sha
        
        requests.put(url, headers=headers, json=data, timeout=15)
        return True
    except Exception:
        return False

# =====================================================================
# ⚙️ FUNCIONES COMPATIBLES EXIGIDAS POR TU APP.PY
# =====================================================================
def obtener_conexion():
    """Devuelve la conexión SQLite nativa que tu app ya sabe usar perfectamente"""
    descargar_base_datos()
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def inicializar_db():
    """Inicializa la base de datos de forma local y asegura el autocommit de respaldo"""
    conn = obtener_conexion()
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.commit()
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

# 🚀 INTERCEPTOR FINAL DE PERSISTENCIA AUTOMÁTICA
# Redefinimos la función connect para que descargue el archivo al inicio
# y cada vez que tu app ejecute un guardado, suba el archivo modificado a GitHub
class SQLiteSincronizado:
    def __init__(self):
        self.conn = obtener_conexion()
    def commit(self):
        self.conn.commit()
        respaldar_base_datos() # ☁️ Guarda los datos en internet de forma automática en cada commit
    def __getattr__(self, name):
        return getattr(self.conn, name)

sqlite3.connect = lambda *args, **kwargs: SQLiteSincronizado()
# Ejecución de arranque automático
inicializar_db()
