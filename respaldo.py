import os
import streamlit as st
import requests

def obtener_access_token_fresco():
    """Genera un Access Token temporal y lo almacena en la caché de la RAM"""
    if "dropbox_token_cache" in st.session_state and st.session_state["dropbox_token_cache"]:
        return st.session_state["dropbox_token_cache"]

    if "dropbox" not in st.secrets:
        return None
    
    url = "https://api.dropbox.com/oauth2/token"
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
    es_nube = os.path.exists("/mount/src")
    verificar_ssl = True if es_nube else False
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=10, verify=verificar_ssl)
        if response.status_code == 200:
            token_fresco = response.json().get("access_token")
            st.session_state["dropbox_token_cache"] = token_fresco
            return token_fresco
        else:
            return None
    except Exception:
        return None

def descargar_base_datos():
    """Descarga la base de datos real utilizando rutas simplificadas y directas"""
    ruta_local = "laboratorio.db"
    
    token = obtener_access_token_fresco()
    if not token:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return False

    url = "https://dropboxapi.com"
    es_nube = os.path.exists("/mount/src")
    verificar_ssl = True if es_nube else False

    # Intentar descargar desde la raíz por defecto
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path":"/laboratorio.db"}'
        }
        response = requests.post(url, headers=headers, timeout=12, verify=verificar_ssl)
        if response.status_code == 200:
            with open(ruta_local, "wb") as f:
                f.write(response.content)
            return True
    except Exception:
        pass
        
    if not os.path.exists(ruta_local):
        with open(ruta_local, "w") as f: pass
    return False

def respaldar_base_datos():
    """Sube el archivo actual de forma binaria pura e inyecta alertas de diagnóstico en tiempo real"""
    ruta_local = "laboratorio.db"
    
    if not os.path.exists(ruta_local):
        return False

    token = obtener_access_token_fresco()
    if not token:
        st.toast("⚠️ Error: No se pudo obtener el token de acceso a Dropbox.", icon="❌")
        return False

    url = "https://dropboxapi.com"
    es_nube = os.path.exists("/mount/src")
    verificar_ssl = True if es_nube else False

    try:
        with open(ruta_local, "rb") as f:
            data_binaria = f.read()
            
        # Cabeceras con JSON ultra compacto y plano (Sin espaciados accidentales)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": '{"path":"/laboratorio.db","mode":"overwrite","autorename":false,"mute":true,"strict_conflict":false}'
        }
        
        response = requests.post(url, headers=headers, data=data_binaria, timeout=20, verify=verificar_ssl)
        
        # 🚨 DIAGNÓSTICO EN TIEMPO REAL VISIBLE:
        if response.status_code == 200:
            st.toast("☁️ ¡Archivo subido exitosamente a la raíz de tu App Folder!", icon="✅")
            return True
        else:
            st.toast(f"❌ Error Dropbox ({response.status_code}): {response.text[:100]}", icon="🚨")
            return False
    except Exception as e:
        st.toast(f"❌ Error de conexión: {str(e)[:50]}", icon="🔌")
        return False
