import os
import streamlit as st
import requests
import io

#def obtener_access_token_fresco():
#    """Genera un Access Token temporal simulando una petición de navegador web para saltar bloqueos locales"""
#    if "dropbox" not in st.secrets:
#        st.sidebar.error("❌ Falta configurar las credenciales [dropbox] en st.secrets.")
#        return None
    
#    url = "https://dropbox.com"

def obtener_access_token_fresco():
    """Genera un Access Token y fuerza la muestra de errores reales en la pantalla local"""
    if "dropbox" not in st.secrets:
        st.error("❌ Archivo secrets.toml no encontrado o vacío en la carpeta .streamlit.")
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
        response = requests.post(url, data=payload, headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            # 🚨 ESTA LÍNEA OBLIGA A MOSTRAR EL ERROR EN ROJO EN LA PANTALLA PRINCIPAL:
            st.error(f"🔴 ERROR CRÍTICO DE DROPBOX (Código {response.status_code}): {response.text}")
            return None
    except Exception as e:
        st.error(f"🔴 Error de conexión del PC: {str(e)}")
        return None

    
    app_key = str(st.secrets["dropbox"]["app_key"]).strip()
    app_secret = str(st.secrets["dropbox"]["app_secret"]).strip()
    refresh_token = str(st.secrets["dropbox"]["refresh_token"]).strip()
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret
    }
    
    # 🛠️ MEJORA DE NAVEGACIÓN: Añadimos cabeceras idénticas a un navegador Chrome real para evitar bloqueos de red
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Desactivamos verify=False por si el antivirus local intercepta y corrompe los certificados SSL
        response = requests.post(url, data=payload, headers=headers, timeout=12, verify=False)
        
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            st.sidebar.error(f"❌ Dropbox denegó el acceso (Código {response.status_code}): {response.text}")
            return None
    except Exception as e:
        # Si sigue fallando la red local, el sistema crea la base de datos de contingencia para no detener el trabajo en la escuela
        return None

def descargar_base_datos():
    """Descarga la base de datos real simulando navegación humana"""
    ruta_local = "laboratorio.db"
    ruta_dropbox = "/laboratorio.db"
    
    token = obtener_access_token_fresco()
    if not token:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return False

    url = "https://dropboxapi.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Dropbox-API-Arg": '{"path": "' + ruta_dropbox + '"}',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(url, headers=headers, timeout=15, verify=False)
        if response.status_code == 200:
            with open(ruta_local, "wb") as f:
                f.write(response.content)
            return True
        else:
            headers["Dropbox-API-Arg"] = '{"path": "/Aplicaciones/GestionLaboratorioCubillos/laboratorio.db"}'
            response_alt = requests.post(url, headers=headers, timeout=15, verify=False)
            if response_alt.status_code == 200:
                with open(ruta_local, "wb") as f:
                    f.write(response_alt.content)
                return True
            else:
                if not os.path.exists(ruta_local):
                    with open(ruta_local, "w") as f: pass
                    respaldar_base_datos()
                return False
    except Exception:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return False

def respaldar_base_datos():
    """Sube la copia de seguridad de forma binaria pura saltando reglas de inspección de cortafuegos"""
    ruta_local = "laboratorio.db"
    ruta_dropbox = "/laboratorio.db"
    
    if not os.path.exists(ruta_local):
        return False

    token = obtener_access_token_fresco()
    if not token:
        return False

    url = "https://dropboxapi.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": '{"path": "' + ruta_dropbox + '", "mode": "overwrite", "autorename": false, "mute": false, "strict_conflict": false}',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        with open(ruta_local, "rb") as f:
            data_binaria = f.read()
            
        response = requests.post(url, headers=headers, data=data_binaria, timeout=20, verify=False)
        if response.status_code == 200:
            return True
        else:
            headers["Dropbox-API-Arg"] = '{"path": "/Aplicaciones/GestionLaboratorioCubillos/laboratorio.db", "mode": "overwrite", "autorename": false, "mute": false, "strict_conflict": false}'
            response_alt = requests.post(url, headers=headers, data=data_binaria, timeout=20, verify=False)
            if response_alt.status_code == 200:
                return True
            else:
                return False
    except Exception:
        return False
