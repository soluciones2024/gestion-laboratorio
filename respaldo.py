import streamlit as st
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

def obtener_servicio_drive():
    """Conecta con Google Drive leyendo los secretos de forma segura"""
    if not hasattr(st, "secrets") or "google_drive" not in st.secrets:
        return None
        
    try:
        cred_dict = {}
        for key, value in st.secrets["google_drive"].items():
            cred_dict[key] = value
            
        folder_id = cred_dict.pop("folder_id", None)
        
        if "private_key" in cred_dict:
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            
        credentials = service_account.Credentials.from_service_account_info(
            cred_dict, scopes=["https://googleapis.com"]
        )
        service = build("drive", "v3", credentials=credentials)
        return service, folder_id
    except Exception:
        return None

def descargar_base_datos():
    """Descarga la base de datos de Drive al iniciar el servidor buscando el archivo de forma segura"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    if not res:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return
        
    service, folder_id = res
    
    try:
        # Búsqueda ultra-acotada usando el endpoint correcto de v3
        query = f"name = 'database.db' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id)", spaces="drive").execute()
        files = results.get("files", [])
        
        if files:
            file_id = files[0]["id"]
            request = service.files().get_media(fileId=file_id)
            with open(ruta_local, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
        else:
            if not os.path.exists(ruta_local):
                with open(ruta_local, "w") as f: pass
    except Exception:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass

def respaldar_base_datos():
    """Sube y actualiza la base de datos directo al endpoint de subida de Google Drive"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    
    if not res:
        return
        
    service, folder_id = res
    
    if os.path.exists(ruta_local):
        try:
            # Determinamos si el archivo ya existe para actualizarlo o crearlo nuevo
            query = f"name = 'database.db' and '{folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, fields="files(id)", spaces="drive").execute()
            files = results.get("files", [])
            
            # Forzamos el uso del tipo de medio correcto para bases de datos SQLite
            media = MediaFileUpload(ruta_local, mimetype="application/x-sqlite3", resumable=True)
            
            if files:
                file_id = files[0]["id"]
                # Actualización limpia usando la API v3 oficial de Google
                service.files().update(fileId=file_id, media_body=media).execute()
            else:
                # Creación inicial asignando la carpeta contenedora en los metadatos
                file_metadata = {"name": "database.db", "parents": [folder_id]}
                service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                
            st.success("☁️ ¡Copia de seguridad sincronizada en Google Drive con éxito!")
        except Exception as e:
            st.error(f"❌ Error de permisos o comunicación con Google: {e}")

