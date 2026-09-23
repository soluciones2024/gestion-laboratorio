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

def buscar_archivo_en_drive(service, folder_id):
    """Busca si el archivo database.db ya existe estrictamente dentro de la carpeta asignada"""
    try:
        query = f"name = 'database.db' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        return files[0]["id"] if files else None
    except Exception:
        return None

def descargar_base_datos():
    """Descarga la base de datos de Drive al iniciar el servidor"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    if not res:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass
        return
        
    service, folder_id = res
    file_id = buscar_archivo_en_drive(service, folder_id)
    
    if file_id:
        try:
            request = service.files().get_media(fileId=file_id)
            with open(ruta_local, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
        except Exception:
            if not os.path.exists(ruta_local):
                with open(ruta_local, "w") as f: pass
    else:
        if not os.path.exists(ruta_local):
            with open(ruta_local, "w") as f: pass

def respaldar_base_datos():
    """Sube y actualiza el archivo database.db en Google Drive usando el método de carga binaria correcto"""
    ruta_local = "database.db"
    res = obtener_servicio_drive()
    
    if not res:
        st.info("💡 Nota: El sistema está operando en modo local o procesando la sincronización de credenciales con Google Drive.")
        return
        
    service, folder_id = res
    file_id = buscar_archivo_en_drive(service, folder_id)
    
    if os.path.exists(ruta_local):
        try:
            # CORRECCIÓN DE ERROR 404: Se define el cuerpo del archivo binario y el cargador de medios por separado
            media = MediaFileUpload(ruta_local, mimetype="application/x-sqlite3", resumable=True)
            
            if file_id:
                # Actualizar archivo existente pasando los parámetros correctos de la API v3
                service.files().update(fileId=file_id, media_body=media).execute()
            else:
                # Crear archivo nuevo dentro de la carpeta parents asignada
                file_metadata = {"name": "database.db", "parents": [folder_id]}
                service.files().create(body=file_metadata, media_body=media, fields="id").execute()
                
            st.success("☁️ ¡Copia de seguridad unificada y guardada en Google Drive con éxito!")
        except Exception as e:
            st.error(f"❌ Error crítico de comunicación Google Drive API: {e}")

