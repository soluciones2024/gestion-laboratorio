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
    """Descarga la base de datos de la nube. Muestra alertas detalladas en pantalla"""
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
        st.toast("☁️ Base de datos histórica descargada desde Dropbox con éxito.")
    except Exception as e:
        # Asegurar archivo local limpio si no existe
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        
        # Reportar el error real en la interfaz de Streamlit si no es un simple "no encontrado"
        if "not_found" not in str(e) and "path" not in str(e):
            st.warning(f"⚠️ Alerta de conexión Dropbox (Descarga): {e}")

def respaldar_base_datos():
    """Sube y reemplaza la base de datos en la nube. Reporta fallos en la interfaz"""
    dbx = obtener_cliente_dropbox()
    if not dbx:
        st.warning("⚠️ El respaldo no se ejecutó: Revisa si la sección [dropbox] en tus Secrets de Streamlit está vacía o mal escrita.")
        return
        
    ruta_local = "database.db"
    ruta_nube = "/database.db"
    
    if os.path.exists(ruta_local):
        try:
            with open(ruta_local, "rb") as f:
                dbx.files_upload(f.read(), ruta_nube, mode=dropbox.files.WriteMode.overwrite)
            st.toast("✅ ¡Copia de seguridad sincronizada en Dropbox! ☁️")
        except Exception as e:
            # Pinta el error real en un recuadro amarillo para saber qué está fallando
            st.warning(f"⚠️ Error crítico al subir archivo a Dropbox: {e}")
