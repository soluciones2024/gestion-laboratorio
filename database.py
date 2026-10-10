import os
import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
import requests
import base64

DB_PATH = "laboratorio.db"

# Guardamos la función de conexión original de Python de respaldo
_sqlite3_connect_original = sqlite3.connect

def descargar_base_datos():
    """Descarga tu base de datos real con todos tus datos históricos al arrancar el servidor web"""
    if os.path.exists(DB_PATH):
        try: os.remove(DB_PATH) # Limpia cualquier residuo viejo del inicio
        except: pass
    try:
        # Descarga directa en texto binario desde tu repositorio master en GitHub
        url = "https://githubusercontent.com"
        response = requests.get(url, timeout=12)
        if response.status_code == 200:
            with open(DB_PATH, "wb") as f:
                f.write(response.content)
            return True
    except Exception:
        pass
    return False

def respaldar_base_datos():
    """Sube tu archivo .db modificado directamente a GitHub usando tu API de seguridad"""
    if not os.path.exists(DB_PATH):
        return False
    try:
        token = st.secrets["github"]["token"]
        url = "https://github.com"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Obtenemos el identificador único del archivo en la nube para poder sobreescribirlo
        res_get = requests.get(url, headers=headers, timeout=5)
        sha = res_get.json().get("sha") if res_get.status_code == 200 else None
        
        with open(DB_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
            
        data = {
            "message": "☁️ Sincronización Automática Escuela",
            "content": content,
            "branch": "master"
        }
        if sha: 
            data["sha"] = sha
            
        requests.put(url, headers=headers, json=data, timeout=15)
        return True
    except Exception:
        return False

# =====================================================================
# ⚙️ FUNCIONES DE INTERFAZ EXIGIDAS POR TU APP.PY
# =====================================================================
def obtener_conexion():
    """Devuelve la conexión SQLite nativa que tu app ya sabe usar perfectamente"""
    return _sqlite3_connect_original(DB_PATH, check_same_thread=False)

def inicializar_db():
    """Asegura la descarga inicial del archivo histórico en el arranque"""
    descargar_base_datos()

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
# 🚀 INTERCEPTOR DE GUARDADO AUTOMÁTICO (EMULADOR SIN MORDERSE LA COLA)
# =====================================================================
class SQLiteSincronizado:
    def __init__(self, conn_real):
        self.conn_real = conn_real
    def commit(self):
        self.conn_real.commit()
        respaldar_base_datos() # 🔥 GRABADO INDESTRUCTIBLE: Sube el archivo modificado a GitHub en cada commit
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.conn_real.close()
    def __getattr__(self, name): return getattr(self.conn_real, name)

# Redirección atómica en el motor de Python
sqlite3.connect = lambda *args, **kwargs: SQLiteSincronizado(_sqlite3_connect_original(DB_PATH, check_same_thread=False))

# Descarga el archivo con tus datos apenas se enciende internet
inicializar_db()
