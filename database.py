import os
import streamlit as st
import sqlite3
import pandas as pd
from io import BytesIO
import requests
import base64
import time

DB_PATH = "laboratorio.db"
_sqlite3_connect_original = sqlite3.connect

# =====================================================================
# ☁️ SINCRONIZADOR BINARIO INTELIGENTE (GITHUB API)
# =====================================================================
def descargar_base_datos():
    """Descarga tu base de datos real con todos tus datos históricos desde GitHub"""
    try:
        url = "https://githubusercontent.com"
        response = requests.get(url, timeout=12)
        if response.status_code != 200: # Intento alternativo si la rama es main
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
    """Sube tu archivo .db sobreescribiendo internet detectando la rama correcta"""
    if not os.path.exists(DB_PATH):
        return False
    try:
        token = st.secrets["github"]["token"].strip()
        
        # 🚀 Probamos master primero
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
            
        url_put = f"https://github.com"
        data = {
            "message": f"☁️ Sincronización Escuela - {int(time.time())}",
            "content": content,
            "branch": branch_actual
        }
        if sha: data["sha"] = sha
            
        res_put = requests.put(url_put, headers=headers, json=data, timeout=15)
        return res_put.status_code in [200, 201]
    except Exception:
        return False

# =====================================================================
# ⚙️ FUNCIONES DE INTERFAZ EXIGIDAS POR TU APP.PY
# =====================================================================
def obtener_conexion():
    if not os.path.exists(DB_PATH):
        descargar_base_datos()
    return _sqlite3_connect_original(DB_PATH, check_same_thread=False)

def inicializar_db():
    descargar_base_datos()
    
    # INTERFAZ UNIFICADA SIN BOTONES DUPLICADOS
    st.sidebar.write("---")
    st.sidebar.markdown("### ☁️ Nube de Respaldo")
    if st.sidebar.button("💾 GUARDAR CAMBIOS EN INTERNET", use_container_width=True, type="primary", key="btn_respaldo_unico"):
        with st.sidebar.spinner("Guardando en la nube de forma permanente..."):
            if respaldar_base_datos():
                st.sidebar.success("✅ ¡Guardado permanente exitoso!")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.error("❌ Error de permisos o de red.")

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

sqlite3.connect = lambda *args, **kwargs: _sqlite3_connect_original(DB_PATH, check_same_thread=False)
inicializar_db()
