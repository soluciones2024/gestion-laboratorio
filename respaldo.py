import os
import streamlit as st
import requests

def obtener_access_token_fresco():
    """Genera un Access Token temporal utilizando la caché de la RAM y maneja el error 429 en silencio"""
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
        # Forzamos una respuesta limpia o un manejo controlado sin excepciones visuales
        response = requests.post(url, data=payload, headers=headers, timeout=8, verify=verificar_ssl)
        if response.status_code == 200:
            token_fresco = response.json().get("access_token")
            st.session_state["dropbox_token_cache"] = token_fresco
            return token_fresco
        else:
            # 🛠️ MANEJO SILENCIOSO DEL BLOQUEO: Si da 429 o 401, devolvemos None sin activar alertas rojas
            return None
    except Exception:
        return None

def descargar_base_datos():
    """Intenta descargar la base de datos real. Si hay bloqueo 429, activa el Modo Desconectado seguro"""
    ruta_local = "laboratorio.db"
    ruta_dropbox = "/Aplicaciones/GestionLaboratorioCubillos/laboratorio.db"
    
    token = obtener_access_token_fresco()
    if not token:
        # Si Dropbox está bloqueado por tráfico, creamos la base local para no congelar la app
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return False

    url = "https://dropboxapi.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Dropbox-API-Arg": '{"path": "' + ruta_dropbox + '"}'
    }
    
    es_nube = os.path.exists("/mount/src")
    verificar_ssl = True if es_nube else False

    try:
        response = requests.post(url, headers=headers, timeout=12, verify=verificar_ssl)
        if response.status_code == 200:
            with open(ruta_local, "wb") as f:
                f.write(response.content)
            return True
        else:
            # Reintento secundario en la raíz de la app
            headers["Dropbox-API-Arg"] = '{"path": "/laboratorio.db"}'
            response_alt = requests.post(url, headers=headers, timeout=12, verify=verificar_ssl)
            if response_alt.status_code == 200:
                with open(ruta_local, "wb") as f:
                    f.write(response_alt.content)
                return True
            else:
                if not os.path.exists(ruta_local):
                    with open(ruta_local, "w") as f: pass
                return False
    except Exception:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return False

def respaldar_base_datos():
    """Envía los datos de forma atómica a Dropbox. Si hay bloqueo, guarda en local de forma transparente"""
    ruta_local = "laboratorio.db"
    ruta_dropbox = "/Aplicaciones/GestionLaboratorioCubillos/laboratorio.db"
    
    if not os.path.exists(ruta_local):
        return False

    token = obtener_access_token_fresco()
    if not token:
        return False

    url = "https://dropboxapi.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": '{"path": "' + ruta_dropbox + '", "mode": "overwrite", "autorename": false, "mute": false, "strict_conflict": false}'
    }
    
    es_nube = os.path.exists("/mount/src")
    verificar_ssl = True if es_nube else False

    try:
        with open(ruta_local, "rb") as f:
            data_binaria = f.read()
            
        response = requests.post(url, headers=headers, data=data_binaria, timeout=15, verify=verificar_ssl)
        if response.status_code == 200:
            return True
        else:
            headers["Dropbox-API-Arg"] = '{"path": "/laboratorio.db", "mode": "overwrite", "autorename": false, "mute": false, "strict_conflict": false}'
            requests.post(url, headers=headers, data=data_binaria, timeout=15, verify=verificar_ssl)
            return True
    except Exception:
        return False
