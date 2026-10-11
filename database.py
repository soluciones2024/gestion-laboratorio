import os
import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
import requests
import base64
import time

DB_PATH = "laboratorio.db"

# 🛡️ CLAVE DEL ÉXITO: Guardamos la función de conexión original de Python de respaldo
_sqlite3_connect_original = sqlite3.connect

def descargar_base_datos():
    """Descarga tu base de datos real con todos tus datos históricos desde GitHub"""
    if os.path.exists(DB_PATH):
        return True
    try:
        url = "https://githubusercontent.com"
        response = requests.get(url, timeout=12)
        if response.status_code != 200:  # Intento alternativo si la rama es main
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
    """Sube tu archivo .db sobreescribiendo internet detectando la rama correcta en segundo plano"""
    if not os.path.exists(DB_PATH):
        return False
    try:
        token = st.secrets["github"]["token"].strip()
        
        # 🚀 Probamos la rama master primero
        branch_actual = "master"
        url = f"https://github.com{branch_actual}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        
        res_get = requests.get(url, headers=headers, timeout=5)
        if res_get.status_code != 200:
            # 🚀 Si falla master, cambiamos de inmediato a la rama main
            branch_actual = "main"
            url = f"https://github.com{branch_actual}"
            res_get = requests.get(url, headers=headers, timeout=5)
            
        sha = res_get.json().get("sha") if res_get.status_code == 200 else None
        
        with open(DB_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
            
        url_put = "https://github.com"
        data = {
            "message": f"☁️ Sincronización Automática Escuela - {int(time.time())}",
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
    """Devuelve la conexión SQLite nativa usando la función original salvada"""
    descargar_base_datos()
    return _sqlite3_connect_original(DB_PATH, check_same_thread=False)

def inicializar_db():
    """Asegura la descarga inicial del archivo histórico en el arranque sin duplicar elementos"""
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
# 🚀 INTERCEPTOR EN SEGUNDO PLANO DE GUARDADO AUTOMÁTICO INMUNE
# =====================================================================
class SQLiteSincronizado:
    def __init__(self, conn_real):
        self.conn_real = conn_real
    def commit(self):
        self.conn_real.commit()
        # ☁️ CADA VEZ QUE TU APP HAGA COMMIT, SE SUBE A INTERNET DE FORMA INVISIBLE
        respaldar_base_datos()
    def __enter__(self): 
        return self
    def __exit__(self, exc_type, exc_val, exc_tb): 
        self.conn_real.close()
    def __getattr__(self, name): 
        return getattr(self.conn_real, name)

# Redirección en el motor de Python usando la conexión original salvada para evitar bucles
sqlite3.connect = lambda *args, **kwargs: SQLiteSincronizado(_sqlite3_connect_original(DB_PATH, check_same_thread=False))

# Ejecución automática al arranque
inicializar_db()
