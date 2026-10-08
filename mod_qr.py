import streamlit as st
import pandas as pd
import io
import zipfile
import base64
import os
import segno
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
        # Se simplifica el mapeo para evitar errores de split en cascada
        lista_opciones_qr = [f"{str(row['id_equipo']).strip()}" for _, row in df_base_f.iterrows()]
        seleccion_equipo = st.selectbox("Selecciona Equipo Específico:", lista_opciones_qr)
        if seleccion_equipo:
            df_filtrado_qr = df_base_f[df_base_f['id_equipo'] == seleccion_equipo.strip()]
            
    elif modo_generacion != "Selección Única" and not df_base_f.empty:
        if tipo_seleccionado == "Todos los Tipos":
            df_filtrado_qr = df_qr_equipos
        else:
            with st.expander("🗂️ Ver Casillas de Activos y Seleccionar", expanded=True):
                cols_ticket = st.columns(3)
                items_sel = []
                for idx, row in df_base_f.reset_index(drop=True).iterrows():
                    if cols_ticket[idx % 3].checkbox(f"[{row['id_equipo']}] {row['marca']}", value=False, key=f"chk_t_{row['id_equipo']}_{idx}"):
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
            inc_estado = col_d2.checkbox("Estado Técnico", value=True)
            inc_ubic = col_d2.checkbox("Ubicación / Sala", value=True)
            inc_factura = col_d3.checkbox("Nro. Factura", value=False)
            inc_costo = col_d3.checkbox("Costo ($)", value=False)

        # 🛠️ Carga y verificación binaria forzada del logotipo local
        html_img_logo = ""
        ruta_logo_local = "logo_escuela.png"
        if os.path.exists(ruta_logo_local):
            try:
                with open(ruta_logo_local, "rb") as img_file:
                    encoded_logo = base64.b64encode(img_file.read()).decode('utf-8')
                html_img_logo = f'<img src="data:image/png;base64,{encoded_logo}" style="height: 22px; width: auto; margin-right: 6px; display: inline-block; vertical-align: middle; object-fit: contain;">'
            except Exception:
                pass

        # MOTOR DE COMPILACIÓN DINÁMICA DE REQUISITOS DEL QR
        lista_bytes_qr = {}
        for idx, datos_fila in df_filtrado_qr.iterrows():
            txt = [f"ID: {datos_fila['id_equipo']}"]
            
            if inc_tipo: txt.append(f"Tipo: {datos_fila['tipo']}")
            if inc_marca: txt.append(f"Mod: {datos_fila['marca']} {datos_fila['modelo']}")
            if inc_estado: txt.append(f"Est: {datos_fila['estado']}")
            if inc_ubic: txt.append(f"Ubic: {datos_fila['ubicacion']}")
            if inc_factura: txt.append(f"Fact: {datos_fila['num_documento'] if datos_fila['num_documento'] else 'S/F'}")
            if inc_costo: 
                costo_val = datos_fila['costo_compra'] if datos_fila['costo_compra'] is not None else 0
                txt.append(f"Costo: ${costo_val:.0f}")
            
            qr_local = segno.make_qr(" | ".join(txt), error='m')
            buffer = io.BytesIO()
            qr_local.save(buffer, kind='png', scale=5, border=2)
            lista_bytes_qr[datos_fila['id_equipo']] = buffer.getvalue()

        st.markdown("### 📋 Vista Previa de la Plantilla")
        columnas_grilla = st.columns(columnas_hoja)
        html_consolidado_hoja = ""
        
        for idx, datos_fila in df_filtrado_qr.reset_index(drop=True).iterrows():
            id_actual = datos_fila['id_equipo']
            bytes_raw = lista_bytes_qr[id_actual]
            qr_b64_img = base64.b64encode(bytes_raw).decode('utf-8')
            
            border_style_dinamico = "2px dashed #333" if tamano_borde == "Línea Segmentada" else ("1px solid #333" if tamano_borde == "Línea Continua" else "none")
            bajada_txt_html = f"<p style='text-align:center; font-size:9px; font-style:italic; margin:4px 0 0 0; color:#555;'>Escanee para validar historial</p>" if incluir_bajada else ""

            # Maquetación integrada de la etiqueta QR individual
            html_tarjeta_individual = f"""
            <div style="
                border: {border_style_dinamico}; 
                padding: {padding_etiqueta}px; 
                text-align: center; 
                background-color: #ffffff; 
                margin: 5px; 
                border-radius: 4px;
                box-sizing: border-box;
                min-width: {ancho_etiqueta}px;
                max-width: {ancho_etiqueta}px;
                width: {ancho_etiqueta}px;
                color: #000000;
                font-family: 'Arial', sans-serif;
                page-break-inside: avoid;
            ">
                <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 6px; width: 100%;">
                    {html_img_logo}
                    <span style="font-size: 11px; font-weight: bold; text-transform: uppercase; color: #000000; letter-spacing: 0.3px; white-space: nowrap;">{nombre_institucion}</span>
                </div>
                <p style="text-align:center; font-family:monospace; font-size:13px; font-weight:bold; margin:2px 0 6px 0; color:#000000;">ID: {id_actual}</p>
                <div style="display: flex; justify-content: center; align-items: center; width: 100%;">
                    <img src="data:image/png;base64,{qr_b64_img}" style="width: calc(100% - 10px); max-width: {ancho_etiqueta - 20}px; height: auto; display: block;">
                </div>
                {bajada_txt_html}
            </div>
            """
            
            with columnas_grilla[idx % columnas_hoja]:
                st.html(html_tarjeta_individual)
                st.download_button(f"💾 Guardar QR {id_actual}", bytes_raw, f"QR_{id_actual}.png", "image/png", key=f"btn_dl_f_{id_actual}_{idx}", use_container_width=True)
            
            html_consolidado_hoja += html_tarjeta_individual

        # 5. ESTRUCTURA COMPLETA DE IMPRESIÓN ADAPTATIVA EN GRID
        html_pagina_impresion = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Impresion de QRs TI - Escuela Felipe Cubillos</title>
            <style>
                body {{
                    background: #ffffff;
                    margin: 0;
                    padding: 4mm;
                }}
                .grid-etiquetas {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 4mm;
                    width: 100%;
                }}
                @media print {{
                    body {{ padding: 0; }}
                    .grid-etiquetas {{ gap: 2mm; }}
                    @page {{ margin: 4mm; size: auto; }}
                }}
            </style>
        </head>
        <body>
            <div class="grid-etiquetas">
                {html_consolidado_hoja}
            </div>
            <script>
                window.onload = function() {{
                    setTimeout(function() {{
                        window.print();
                    }}, 350);
                }};
            </script>
        </body>
        </html>
        """

        # Codificación limpia en Base64 para el inyector del script
        html_escape_b64 = base64.b64encode(html_pagina_impresion.encode('utf-8')).decode('utf-8')

        # 6. INYECTOR PORTÁTIL EN COLUMNAS DE ACCIONES COLECTIVAS (IGUAL A GENERADOR DE ETIQUETAS)
        st.markdown("---")
        st.subheader("🛠️ Acciones Colectivas Masivas")
        col_acc1, col_acc2 = st.columns(2)
        
        with col_acc1:
            if st.button("🖨️ Abrir Ventana de Impresión", key="btn_forzar_impresion_qr_definitivo", use_container_width=True, type="primary"):
                js_bypass_sandbox = f"""
                <script>
                    var win = window.open();
                    if (win) {{
                        win.document.write(atob("{html_escape_b64}"));
                        win.document.close();
                    }} else {{
                        alert("⚠️ Navegador bloqueado: Habilite los permisos para ventanas emergentes (Pop-ups) in la barra de direcciones.");
                    }}
                </script>
                """
                st.components.v1.html(js_bypass_sandbox, height=0, width=0)
            
        with col_acc2:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for id_eq, bytes_img in lista_bytes_qr.items():
                    zip_file.writestr(f"QR_{id_eq}.png", bytes_img)
            st.download_button(f"📥 Descargar Lote de QRs ({len(df_filtrado_qr)} unidades) en .ZIP", zip_buffer.getvalue(), "lote_qr.zip", "application/zip", use_container_width=True)
