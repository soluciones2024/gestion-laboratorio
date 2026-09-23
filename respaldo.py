import streamlit as st
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

def obtener_servicio_drive():
    """Conecta con Google Drive leyendo el archivo JSON de claves de forma directa"""
    ruta_json = "claves_google.json"
    
    try:
        folder_id = st.secrets["google_drive"]["folder_id"]
    except Exception:
        folder_id = "1i32pLPXc0pl2Tthf5eL3lki8F-BCYAlc"
        
    if not os.path.exists(ruta_json):
        return None
        
    try:
        credentials = service_account.Credentials.from_service_account_file(
            ruta_json, scopes=["https://googleapis.com"]
        )
        service = build("drive", "v3", credentials=credentials)
        return service, folder_id
    except Exception:
        return None

def descargar_base_datos():
    """Descarga la base de datos desde Google Drive de forma ultra-acotada al arrancar"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    if not res:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return
        
    service, folder_id = res
    try:
        # Búsqueda protegida: Solo escanea dentro del parents (tu carpeta) evitando el error 404
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
    """Sube y actualiza la base de datos directo al endpoint de Google Drive"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    
    if not res:
        return
        
    service, folder_id = res
    if os.path.exists(ruta_local):
        try:
            # Buscamos si ya existe el archivo dentro de tu carpeta específica
            query = f"name = 'database.db' and '{folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, fields="files(id)", spaces="drive").execute()
            files = results.get("files", [])
            
            media = MediaFileUpload(ruta_local, mimetype="application/x-sqlite3", resumable=True)
            
            if files:
                file_id = files[0]["id"]
                # Modificación limpia usando el identificador único del archivo
                service.files().update(fileId=file_id, media_body=media).execute()
            else:
                # Creación inicial inyectando la metadata de la carpeta contenedora
                file_metadata = {"name": "database.db", "parents": [folder_id]}
                service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                
            st.success("☁️ ¡Copia de seguridad sincronizada en Google Drive con éxito!")
        except Exception as e:
            st.error(f"❌ Error de permisos o comunicación con Google: {e}")
