import streamlit as st
import dropbox
import os

def obtener_cliente_dropbox():
    """Genera una conexión segura a Dropbox validando la existencia de los Secrets"""
    if "dropbox" not in st.secrets:
        return None
    try:
        dbx = dropbox.Dropbox(
            app_key=st.secrets["dropbox"]["app_key"],
            app_secret=st.secrets["dropbox"]["app_secret"],
            oauth2_refresh_token=st.secrets["dropbox"]["refresh_token"]
        )
        return dbx
    except Exception:
        return None

def descargar_base_datos():
    """Descarga la base de datos de la nube al arrancar"""
    ruta_local = "database.db"
    ruta_nube = "/database.db"
    
    dbx = obtener_cliente_dropbox()
    if not dbx:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return

    try:
        with open(ruta_local, "wb") as f:
            metadata, res = dbx.files_download(path=ruta_nube)
            f.write(res.content)
    except Exception:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass

def respaldar_base_datos():
    """Sube el archivo a la nube y fuerza una alerta visual gigante en la pantalla web de Streamlit"""
    ruta_local = "database.db"
    ruta_nube = "/database.db"
    
    dbx = obtener_cliente_dropbox()
    
    # ALERTA 1: Si no detecta los Secrets en la nube
    if not dbx:
        st.error("❌ RESPALDO APAGADO: Esta copia se está ejecutando de forma local (en tu PC) o los Secrets en Streamlit Cloud están vacíos.")
        return
        
    if os.path.exists(ruta_local):
        try:
            with open(ruta_local, "rb") as f:
                dbx.files_upload(f.read(), ruta_nube, mode=dropbox.files.WriteMode.overwrite)
            # ALERTA 2: Letrero verde gigante de éxito total
            st.success("☁️ ¡SINCRO COMPLETA! El archivo 'database.db' fue enviado y guardado con éxito en la nube de Dropbox.")
        except Exception as e:
            st.error(f"❌ Error al subir a Dropbox: {e}")