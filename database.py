import os
import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
import requests
import base64
import time

DB_PATH = "laboratorio.db"

# 🛡️ CLAVE DE LA VICTORIA: Guardamos la función de conexión original de Python
# antes de hacer cualquier cambio para evitar que se muerda la cola
_sqlite3_connect_original = sqlite3.connect

def descargar_base_datos_fija():
    """Descarga tu archivo real .db con todos tus datos históricos desde GitHub al arrancar"""
    try:
        url = "https://githubusercontent.com"
        response = requests.get(url, timeout=12)
        if response.status_code != 200:
            url = "https://githubusercontent.com"
            response = requests.get(url, timeout=12)
        if response.status_code == 200:
            with open(DB_PATH, "wb") as f:
                f.write(response.content)
            return True
    except Exception:
        pass
    return False

def respaldar_base_datos_fija():
    """Sube tu archivo .db modificado directamente a GitHub de forma transparente e inmune"""
    if not os.path.exists(DB_PATH):
        return False
    try:
        token = st.secrets["github"]["token"].strip()
        branch_actual = "master"
        url = f"https://github.com{branch_actual}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        res_get = requests.get(url, headers=headers, timeout=5)
        if res_get.status_code != 200:
            branch_actual = "main"
            url = f"https://github.com{branch_actual}"
            res_get = requests.get(url, headers=headers, timeout=5)
            
        sha = res_get.json().get("sha") if res_get.status_code == 200 else None
        
        with open(DB_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
            
        url_put = "https://github.com"
        data = {
            "message": f"☁️ Sincronización Escuela - {int(time.time())}",
            "content": content,
            "branch": branch_actual
        }
        if sha: data["sha"] = sha
            
        requests.put(url_put, headers=headers, json=data, timeout=15)
        return True
    except Exception:
        return False

# =====================================================================
# ⚙️ FUNCIONES DE INTERFAZ EXIGIDAS POR TU APP.PY
# =====================================================================
def obtener_conexion():
    """Devuelve la conexión SQLite nativa rápida utilizando la función original salvada"""
    if not os.path.exists(DB_PATH):
        descargar_base_datos_fija()
    return _sqlite3_connect_original(DB_PATH, check_same_thread=False)

def inicializar_db():
    """Asegura la descarga inicial del archivo histórico en el arranque sin duplicar elementos"""
    descargar_base_datos_fija()

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
        respaldar_base_datos_fija()
        return True
    except Exception: return False

# =====================================================================
# 🚀 INTERCEPTOR AISLADO DE GUARDADO AUTOMÁTICO INMUNE
# =====================================================================
class ConnectionSincronizada:
    def __init__(self, conn_real):
        self.conn_real = conn_real
    def commit(self):
        self.conn_real.commit()
        # El respaldo se ejecuta de forma externa y aislada de los hilos de Pandas
        respaldar_base_datos_fija()
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.conn_real.close()
    def __getattr__(self, name): return getattr(self.conn_real, name)

# Sobreescribimos el motor de conexión de Python apuntando a la función limpia original
sqlite3.connect = lambda *args, **kwargs: ConnectionSincronizada(_sqlite3_connect_original(DB_PATH, check_same_thread=False))

# Ejecución automática al arranque
inicializar_db()
