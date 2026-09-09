import streamlit as st
import pandas as pd
import io
import zipfile
import segno
from datetime import datetime
from database import obtener_conexion

def renderizar_modulo_qr(nombre_institucion):
    with obtener_conexion() as conn:
        df_qr_equipos = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, estado, ubicacion, num_documento, proveedor_origen, costo_compra FROM equipos", conn)
    
    st.markdown("### ⚙️ Configuración Física de la Hoja de Etiquetas")
    with st.expander("📐 Ajustar Dimensiones de la Plantilla de Impresión", expanded=False):
        col_c1, col_c2, col_c3 = st.columns(3)
        columnas_hoja = col_c1.slider("Columnas por fila:", 2, 5, 3)
        ancho_etiqueta = col_c2.slider("Ancho (px):", 120, 300, 180)
        padding_etiqueta = col_c3.slider("Padding (px):", 5, 25, 10)
        col_c4, col_c5 = st.columns(2)
        tamano_borde = col_c4.selectbox("Borde:", ["Línea Segmentada", "Línea Continua", "Sin Borde"])
        estilo_borde_css = "2px dashed #000" if tamano_borde == "Línea Segmentada" else ("1px solid #000" if tamano_borde == "Línea Continua" else "none")
        incluir_bajada = col_c5.checkbox("Incluir texto aclaratorio inferior", value=True)

    st.markdown("---")
    modo_generacion = st.radio("Método de Generación:", ["Selección Única", "Selección Masiva por Ticket / Auto"], horizontal=True)
    df_filtrado_qr = pd.DataFrame()
    
    if df_qr_equipos.empty:
        st.warning("⚠️ El inventario está vacío.")
        return

    tipos_disp = ["Todos los Tipos"] + sorted(df_qr_equipos["tipo"].unique().tolist())
    tipo_seleccionado = st.selectbox("🔍 Filtrar por Tipo de Equipo:", tipos_disp)
    df_base_f = df_qr_equipos if tipo_seleccionado == "Todos los Tipos" else df_qr_equipos[df_qr_equipos["tipo"] == tipo_seleccionado]
    
    if modo_generacion == "Selección Única" and not df_base_f.empty:
        lista_opciones_qr = [f"{row['id_equipo']} - {row['tipo']}" for _, row in df_base_f.iterrows()]
        seleccion_equipo = st.selectbox("Selecciona Equipo Específico:", lista_opciones_qr)
        df_filtrado_qr = df_base_f[df_base_f['id_equipo'] == seleccion_equipo.split(" - ")[0].strip()]
    elif modo_generacion != "Selección Única" and not df_base_f.empty:
        if tipo_seleccionado == "Todos los Tipos":
            st.success(f"🚀 Modo Auto-Generación Activo: {len(df_qr_equipos)} equipos listos.")
            df_filtrado_qr = df_qr_equipos
        else:
            with st.expander("🗂️ Ver Casillas de Activos y Seleccionar", expanded=True):
                cols_ticket = st.columns(3)
                items_sel = []
                for idx, row in df_base_f.reset_index(drop=True).iterrows():
                    if cols_ticket[idx % 3].checkbox(f"[{row['id_equipo']}] {row['tipo']}", value=False, key=f"chk_t_{row['id_equipo']}_{idx}"):
                        items_sel.append(row['id_equipo'])
            if items_sel:
                df_filtrado_qr = df_base_f[df_base_f['id_equipo'].isin(items_sel)]

    if not df_filtrado_qr.empty:
        st.markdown("---")
        st.markdown("### 📊 Contenido Interno del Código QR")
        with st.expander("📝 Selecciona los datos que se guardarán DENTRO del código", expanded=True):
            col_d1, col_d2, col_d3 = st.columns(3)
            inc_tipo = col_d1.checkbox("Tipo de Hardware", value=True)
            inc_marca = col_d1.checkbox("Marca y Modelo", value=True)
            inc_estado = col_d2.checkbox("Estado Técnico", value=False)
            inc_ubic = col_d2.checkbox("Ubicación / Sala", value=True)
            inc_factura = col_d3.checkbox("Nro. Factura", value=False)
            inc_costo = col_d3.checkbox("Costo ($)", value=False)

        lista_bytes_qr = {}
        for idx, datos_fila in df_filtrado_qr.iterrows():
            txt = [f"ID: {datos_fila['id_equipo']}"]
            if inc_tipo: txt.append(f"Tipo: {datos_fila['tipo']}")
            if inc_marca: txt.append(f"Mod: {datos_fila['marca']} {datos_fila['modelo']}")
            if inc_estado: txt.append(f"Est: {datos_fila['estado']}")
            if inc_ubic: txt.append(f"Ubic: {datos_fila['ubicacion']}")
            if inc_factura: txt.append(f"Fact: {datos_fila['num_documento']}")
            if inc_costo: txt.append(f"Costo: ${datos_fila['costo_compra'] if datos_fila['costo_compra'] is not None else 0:.0f}")
            
            qr_local = segno.make_qr(" | ".join(txt), error='m')
            buffer = io.BytesIO()
            qr_local.save(buffer, kind='png', scale=5, border=2)
            lista_bytes_qr[datos_fila['id_equipo']] = buffer.getvalue()

        st.markdown(f"""
            <style>
            @media print {{
                div[data-testid="stSidebar"], header, footer, div[data-testid="stHeader"], 
                div[class*="stRadio"], div[class*="stSelectbox"], div[class*="stTextInput"], 
                div[class*="stForm"], div.stAlert, div.stButton, .stDownloadButton, 
                [data-testid="stExpander"], h1, h2, h3, hr, p:not(.txt-eq), span:not(.txt-eq) {{ display: none !important; }}
                div[data-testid="stHorizontalBlock"] {{ display: flex !important; flex-direction: row !important; flex-wrap: wrap !important; width: 100% !important; gap: 5mm !important; }}
                div[data-testid="stColumn"] {{ min-width: {ancho_etiqueta}px !important; max-width: {ancho_etiqueta}px !important; width: {ancho_etiqueta}px !important; margin: 2mm !important; page-break-inside: avoid !important; display: block !important; }}
                .main, .main .block-container, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{ padding: 0mm !important; margin: 0mm !important; padding-top: 0mm !important; margin-top: 0mm !important; max-width: 100% !important; display: block !important; height: auto !important; }}
                div[data-testid="stImage"], div[data-testid="stImage"] img {{ display: block !important; width: 100% !important; height: auto !important; }}
                * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                @page {{ margin: 6mm !important; size: auto; }}
            }}
            </style>
        """, unsafe_allow_html=True)

        if len(df_filtrado_qr) > 1:
            st.subheader("🛠️ Acciones Colectivas Masivas")
            col_masiva1, col_masiva2 = st.columns(2)
            with col_masiva1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for id_eq, bytes_img in lista_bytes_qr.items():
                        zip_file.writestr(f"QR_{id_eq}.png", bytes_img)
                st.download_button(f"📥 Descargar {len(df_filtrado_qr)} QRs (.ZIP)", zip_buffer.getvalue(), "lote.zip", "application/zip", use_container_width=True)
            with col_masiva2:
                if st.button("🖨️ Preparar Hoja para Imprimir (Ctrl + P)", use_container_width=True):
                    st.info("Presiona Ctrl + P en tu teclado.")

        st.markdown("### 📋 Vista Previa de la Plantilla")
        columnas_grilla = st.columns(columnas_hoja)
        for idx, datos_fila in df_filtrado_qr.reset_index(drop=True).iterrows():
            id_actual = datos_fila['id_equipo']
            bytes_raw = lista_bytes_qr[id_actual]
            with columnas_grilla[idx % columnas_hoja]:
                with st.container(border=True if tamano_borde != "Sin Borde" else False):
                    st.markdown(f"<p class='txt-eq' style='text-align:center; font-size:11px; font-weight:bold; margin:0; text-transform:uppercase; color:#000;'>{nombre_institucion}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='txt-eq' style='text-align:center; font-family:monospace; font-size:13px; font-weight:bold; margin:2px 0; color:#000;'>ID: {id_actual}</p>", unsafe_allow_html=True)
                    st.image(bytes_raw, width=ancho_etiqueta - 20 if ancho_etiqueta > 40 else 100)
                    if incluir_bajada:
                        st.markdown("<p class='txt-eq' style='text-align:center; font-size:9px; font-style:italic; margin:0; color:#555;'>Escanee para validar historial</p>", unsafe_allow_html=True)
                st.download_button(f"💾 Guardar {id_actual}", bytes_raw, f"QR_{id_actual}.png", "image/png", key=f"btn_dl_f_{id_actual}_{idx}", use_container_width=True)
