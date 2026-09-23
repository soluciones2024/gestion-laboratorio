import streamlit as st
import dropbox
import os

def obtener_cliente_dropbox():
    """Genera una conexión segura a Dropbox validando la existencia de los Secrets"""
    # Validación de seguridad: Comprobar si la llave 'dropbox' existe en st.secrets
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
    """Descarga la base de datos de la nube. Si falla, asegura la creación del archivo local"""
    ruta_local = "database.db"
    ruta_nube = "/database.db"
    
    dbx = obtener_cliente_dropbox()
    
    # Si no hay conexión a la nube, creamos el archivo local vacío para que la app no se caiga
    if not dbx:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f:
                pass
        return

    try:
        with open(ruta_local, "wb") as f:
            metadata, res = dbx.files_download(path=ruta_nube)
            f.write(res.content)
    except Exception:
        # Si el archivo no existe en la nube, asegurar archivo local limpio
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f:
                pass

def respaldar_base_datos():
    """Sube y reemplaza la base de datos en la nube inmediatamente tras un cambio"""
    dbx = obtener_cliente_dropbox()
    if not dbx:
        return
        
    ruta_local = "database.db"
    ruta_nube = "/database.db"
    
    if os.path.exists(ruta_local):
        try:
            with open(ruta_local, "rb") as f:
                dbx.files_upload(f.read(), ruta_nube, mode=dropbox.files.WriteMode.overwrite)
        except Exception:
            pass
