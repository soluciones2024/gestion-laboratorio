import os
import streamlit as st
import requests

def obtener_access_token_fresco():
    """Genera un Access Token temporal y lo almacena en la caché de la RAM para evitar exceso de tráfico"""
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
    """Descarga la base de datos real utilizando el orden de rutas prioritarias de Dropbox"""
    ruta_local = "laboratorio.db"
    
    token = obtener_access_token_fresco()
    if not token:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return False

    url = "https://dropboxapi.com"
    es_nube = os.path.exists("/mount/src")
    verificar_ssl = True if es_nube else False

    # Intento 1: Ruta limpia nativa (Obligatoria si el token es de tipo App Folder restringido)
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path": "/laboratorio.db"}'
        }
        response = requests.post(url, headers=headers, timeout=12, verify=verificar_ssl)
        if response.status_code == 200:
            with open(ruta_local, "wb") as f:
                f.write(response.content)
            return True
    except Exception:
        pass

    # Intento 2: Ruta absoluta corporativa (Obligatoria si el token tiene permisos globales de cuenta)
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": '{"path": "/Aplicaciones/GestionLaboratorioCubillos/laboratorio.db"}'
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
    """Fuerza la subida inmediata del archivo escribiendo en ambas rutas para romper el bloqueo 429"""
    ruta_local = "laboratorio.db"
    
    if not os.path.exists(ruta_local):
        return False

    token = obtener_access_token_fresco()
    if not token:
        return False

    url = "https://dropboxapi.com"
    es_nube = os.path.exists("/mount/src")
    verificar_ssl = True if es_nube else False

    try:
        with open(ruta_local, "rb") as f:
            data_binaria = f.read()
            
        # Ejecutamos la subida en la ruta base de la aplicación
        headers_base = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": '{"path": "/laboratorio.db", "mode": "overwrite", "autorename": false, "mute": false, "strict_conflict": false}'
        }
        requests.post(url, headers=headers_base, data=data_binaria, timeout=15, verify=verificar_ssl)
        
        # Duplicamos el respaldo de seguridad en la ruta absoluta corporativa de la escuela
        headers_abs = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": '{"path": "/Aplicaciones/GestionLaboratorioCubillos/laboratorio.db", "mode": "overwrite", "autorename": false, "mute": false, "strict_conflict": false}'
        }
        requests.post(url, headers=headers_abs, data=data_binaria, timeout=15, verify=verificar_ssl)
        return True
    except Exception:
        return False
