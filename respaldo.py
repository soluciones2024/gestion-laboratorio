import os
import streamlit as st
import requests

def obtener_access_token_fresco():
    """Genera un Access Token temporal sólo si la aplicación está corriendo en internet"""
    # 🛠️ FILTRO MAESTRO DE ENTORNO LOCAL:
    # Si la app corre en tu PC (no existe /mount/src), cancelamos en silencio antes de pedir secretos
    es_nube = os.path.exists("/mount/src")
    if not es_nube:
        return None

    if "dropbox_token_cache" in st.session_state and st.session_state["dropbox_token_cache"]:
        return st.session_state["dropbox_token_cache"]

    if "dropbox" not in st.secrets:
        return None
    
    url = "https://dropbox.com"
    app_key = str(st.secrets["dropbox"]["app_key"]).strip()
    app_secret = str(st.secrets["dropbox"]["app_secret"]).strip()
    refresh_token = str(st.secrets["dropbox"]["refresh_token"]).strip()
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret
    }
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=10, verify=True)
        if response.status_code == 200:
            token_fresco = response.json().get("access_token")
            st.session_state["dropbox_token_cache"] = token_fresco
            return token_fresco
        else:
            return None
    except Exception:
        return None

def descargar_base_datos():
    """Descarga la base de datos real. En local se desactiva de forma automática en silencio"""
    es_nube = os.path.exists("/mount/src")
    ruta_local = "laboratorio.db"
    
    if not es_nube:
        # Si estás en tu computador, garantizamos la existencia del archivo local y cerramos en silencio
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return False
        
    ruta_dropbox = "/laboratorio.db"
    token = obtener_access_token_fresco()
    if not token:
        return False

    url = "https://dropboxapi.com"

    try:
        response = requests.post(url, headers={"Authorization": f"Bearer {token}", "Dropbox-API-Arg": '{"path":"' + ruta_dropbox + '"}'}, timeout=12, verify=True)
        if response.status_code == 200:
            with open(ruta_local, "wb") as f: f.write(response.content)
            return True
    except Exception:
        pass
    return False

def respaldar_base_datos():
    """Sube el archivo actual a Dropbox de forma atómica. En local se apaga en silencio"""
    es_nube = os.path.exists("/mount/src")
    if not es_nube:
        # Detiene la ejecución en tu casa sin mostrar alertas de error en la pantalla
        return True

    ruta_local = "laboratorio.db"
    if not os.path.exists(ruta_local):
        return False

    token = obtener_access_token_fresco()
    if not token:
        # En internet SÍ mostramos la alerta de diagnóstico si falla el secreto de la nube
        st.toast("⚠️ Error: No se pudo obtener el token de acceso a Dropbox.", icon="❌")
        return False

    url = "https://dropboxapi.com"

    try:
        with open(ruta_local, "rb") as f:
            data_binaria = f.read()
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": '{"path":"/laboratorio.db","mode":"overwrite","autorename":false,"mute":true,"strict_conflict":false}'
        }
        
        response = requests.post(url, headers=headers, data=data_binaria, timeout=20, verify=True)
        if response.status_code == 200:
            st.toast("☁️ ¡Archivo subido exitosamente a tu App Folder!", icon="✅")
            return True
    except Exception:
        pass
    return False
