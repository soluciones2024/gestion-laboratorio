import streamlit as st
import dropbox
import os

def obtener_cliente_dropbox():
    """Genera una conexión segura a Dropbox usando el token de refresco de los Secrets"""
    try:
        dbx = dropbox.Dropbox(
            app_key=st.secrets["dropbox"]["app_key"],
            app_secret=st.secrets["dropbox"]["app_secret"],
            oauth2_refresh_token=st.secrets["dropbox"]["refresh_token"]
        )
        return dbx
    except Exception as e:
        st.error(f"❌ Error crítico de autenticación en la nube: {e}")
        return None

def descargar_base_datos():
    """Descarga la base de datos desde la nube al iniciar el servidor de Streamlit"""
    dbx = obtener_cliente_dropbox()
    if not dbx:
        return
        
    ruta_local = "database.db"
    ruta_nube = "/database.db"
    
    try:
        # Intentar descargar si el archivo ya existe en Dropbox
        with open(ruta_local, "wb") as f:
            metadata, res = dbx.files_download(path=ruta_nube)
            f.write(res.content)
    except dropbox.exceptions.ApiError as e:
        # Si el archivo no existe en la nube (primera vez), creamos una base de datos limpia local
        if "not_found" in str(e):
            if not os.path.exists(ruta_local):
                with open(ruta_local, "w") as f:
                    pass
        else:
            st.error(f"⚠️ Alerta en la nube: {e}")

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
                # El modo 'overwrite' reemplaza el archivo viejo por el nuevo de forma limpia
                dbx.files_upload(f.read(), ruta_nube, mode=dropbox.files.WriteMode.overwrite)
        except Exception as e:
            st.toast(f"⚠️ Error al sincronizar respaldo: {e}", icon="☁️")
