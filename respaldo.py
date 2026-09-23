import streamlit as st
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

def obtener_servicio_drive():
    """Conecta con Google Drive leyendo el archivo JSON local y reparando su estructura interna"""
    ruta_json = "claves_google.json"
    
    try:
        folder_id = st.secrets["google_drive"]["folder_id"]
    except Exception:
        folder_id = "1i32pLPXc0pl2Tthf5eL3lki8F-BCYAlc"
        
    if not os.path.exists(ruta_json):
        return None
        
    try:
        # ARREGLO CRÍTICO: Leer el JSON de GitHub y forzar el reemplazo de los saltos de línea en memoria
        with open(ruta_json, "r") as f:
            cred_info = json.load(f)
            
        if "private_key" in cred_info:
            cred_info["private_key"] = cred_info["private_key"].replace("\\n", "\n")
            
        credentials = service_account.Credentials.from_service_account_info(
            cred_info, scopes=["https://googleapis.com"]
        )
        
        # Conexión explícita al servicio de archivos de Google v3
        service = build("drive", "v3", credentials=credentials)
        return service, folder_id
    except Exception:
        return None

def descargar_base_datos():
    """Descarga la base de datos de Drive al iniciar el servidor (Solo en Internet)"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    if not res:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return
        
    service, folder_id = res
    try:
        query = f"name = 'database.db' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id)", spaces="drive").execute()
        files = results.get("files", [])
        if files:
            file_id = files[0]["id"]  # Corrección de índice para extraer el ID del archivo
            request = service.files().get_media(fileId=file_id)
            with open(ruta_local, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
    except Exception:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass

def respaldar_base_datos():
    """Sube y actualiza el archivo database.db en Google Drive usando el cargador de medios correcto"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    
    if not res:
        return
        
    service, folder_id = res
    if os.path.exists(ruta_local):
        try:
            # Buscamos si ya existe el archivo en tu carpeta usando el buscador nativo
            query = f"name = 'database.db' and '{folder_id}' in parents and trashed = false"
            results = service.files().list(q=query, fields="files(id)", spaces="drive").execute()
            files = results.get("files", [])
            
            # Formato de transmisión binario nativo exigido por Google v3
            media = MediaFileUpload(ruta_local, mimetype="application/x-sqlite3", resumable=True)
            
            if files:
                file_id = files[0]["id"]  # Extrae de forma segura el ID del archivo existente
                service.files().update(fileId=file_id, media_body=media).execute()
            else:
                # Si es la primera vez, crea el archivo vinculándolo a tu carpeta parents
                file_metadata = {"name": "database.db", "parents": [folder_id]}
                service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                
            st.success("☁️ ¡Copia de seguridad sincronizada en Google Drive con éxito!")
        except Exception as e:
            st.error(f"❌ Error al subir a Google Drive: {e}")
