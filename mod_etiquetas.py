import streamlit as st
import pandas as pd
import base64
import io
import os
import segno
import barcode
from barcode.writer import ImageWriter
from database import obtener_conexion

def renderizar_modulo_etiquetas():
    st.header("🖨️ Generador de Etiquetas Autoadhesivas TI")
    st.caption("Genere e imprima códigos identificatorios corporativos con Código de Barras y QR para el pegado físico en Notebooks, Tablets y cargadores.")

    # 1. Extracción de datos operativos desde la Base de Datos
    with obtener_conexion() as conn:
        try:
            df_computadores = pd.read_sql_query("""
                SELECT id_equipo AS id, tipo, marca, modelo,
                       tipo || ' - ' || marca || ' ' || modelo AS detalle,
                       num_documento AS factura, estado, ubicacion
                FROM equipos WHERE estado != 'De Baja'
            """, conn)
        except Exception:
            df_computadores = pd.DataFrame(columns=["id", "tipo", "marca", "modelo", "detalle", "factura", "estado", "ubicacion"])
            
        try:
            df_tablets = pd.read_sql_query("""
                SELECT id_tablet AS id, 'Tablet' AS tipo, marca, modelo,
                       nombre || ' (' || marca || ' ' || modelo || ')' AS detalle,
                       num_factura AS factura, estado, ubicacion
                FROM tablets WHERE estado != 'De Baja'
            """, conn)
        except Exception:
            df_tablets = pd.DataFrame(columns=["id", "tipo", "marca", "modelo", "detalle", "factura", "estado", "ubicacion"])

    if df_computadores.empty and df_tablets.empty:
        df_consolidado = pd.DataFrame(columns=["id", "tipo", "marca", "modelo", "detalle", "factura", "estado", "ubicacion"])
    else:
        df_consolidado = pd.concat([df_computadores, df_tablets], ignore_index=True)
    
    if df_consolidado.empty:
        st.info("📂 No se registran equipos operativos en el inventario para etiquetar.")
        return

    # 2. CONFIGURACIÓN DE LA HOJA Y CONTENIDO
    st.markdown("### ⚙️ Configuración de la Plantilla e Impresión")
    with st.expander("📐 Ajustar Dimensiones y Datos Visibles", expanded=False):
        col_ui1, col_ui2 = st.columns(2)
        with col_ui1:
            st.markdown("##### 📝 Datos Visibles")
            inc_factura = st.checkbox("Mostrar Nro. de Factura / Boleta", value=False)
            inc_estado = st.checkbox("Mostrar Estado Técnico", value=False)
            inc_ubicacion = st.checkbox("Mostrar Ubicación / Sala", value=False)
        with col_ui2:
            st.markdown("##### 📐 Formato de Tamaño")
            tamano_etiqueta = st.selectbox(
                "Dimensiones del Adhesivo:",
                ["Pequeño (38mm x 25mm)", "Estándar (50mm x 25mm)", "Grande (70mm x 35mm)"]
            )
            columnas_hoja = st.slider("Etiquetas simultáneas por fila en papel:", 1, 4, 2)

    # Motor de escala física adaptativa recalculado para albergar QR + Código de Barras
    if "38mm" in tamano_etiqueta:
        w_px, h_px, f_title, f_body, qr_size, bar_h = "420px", "180px", "12px", "10px", 55, 30
    elif "50mm" in tamano_etiqueta:
        w_px, h_px, f_title, f_body, qr_size, bar_h = "520px", "220px", "14px", "11px", 75, 40
    else:
        w_px, h_px, f_title, f_body, qr_size, bar_h = "640px", "290px", "18px", "13px", 100, 55
    # 3. FILTRADO MAESTRO POR TIPO, GRUPO O MASIVO
    st.markdown("---")
    st.markdown("### 🗂️ Selección de Activos para Impresión")
    
    tipos_disponibles = ["Todos los Tipos"] + sorted(df_consolidado["tipo"].unique().tolist())
    tipo_seleccionado = st.selectbox("🔍 Filtrar lista por Categoría de Hardware:", tipos_disponibles)
    
    df_base_f = df_consolidado if tipo_seleccionado == "Todos los Tipos" else df_consolidado[df_consolidado["tipo"] == tipo_seleccionado]
    modo_generacion = st.radio("Método de Selección de Etiquetas:", ["Selección Única", "Selección por Grupo / Casillas", "Todo el Tipo de Hardware Seleccionado"], horizontal=True)
    df_filtrado_lote = pd.DataFrame()

    if modo_generacion == "Selección Única" and not df_base_f.empty:
        lista_unicos = [f"{row['id']} - {row['detalle']}" for _, row in df_base_f.iterrows()]
        seleccion_unica = st.selectbox("Seleccione el Equipo Específico:", lista_unicos)
        id_real = seleccion_unica.split(" - ")[0].strip() if " - " in seleccion_unica else seleccion_unica
        df_filtrado_lote = df_base_f[df_base_f['id'] == id_real]

    elif modo_generacion == "Selección por Grupo / Casillas" and not df_base_f.empty:
        st.markdown("##### Marque los componentes que desea incorporar a la hoja de impresión:")
        cols_ticket = st.columns(3)
        items_seleccionados = []
        for idx, row in df_base_f.reset_index(drop=True).iterrows():
            with cols_ticket[idx % 3]:
                if st.checkbox(f"[{row['id']}] {row['marca']}", value=False, key=f"chk_et_lote_{row['id']}_{idx}"):
                    items_seleccionados.append(row['id'])
        if items_seleccionados:
            df_filtrado_lote = df_base_f[df_base_f['id'].isin(items_seleccionados)]
        else:
            st.info("💡 Marque las casillas superiores para compilar el grupo de impresión.")

    elif modo_generacion == "Todo el Tipo de Hardware Seleccionado":
        df_filtrado_lote = df_base_f
        st.success(f"🚀 Modo Masivo Activo: Se procesarán las {len(df_filtrado_lote)} unidades de la categoría '{tipo_seleccionado}'.")
    # 4. MOTOR DE RENDERIZADO Y CONSTRUCCIÓN DE MATRICES HTML
    if not df_filtrado_lote.empty:
        st.markdown("---")
        st.subheader("📋 Vista Previa de la Plantilla de Impresión")
        
        html_img_logo = ""
        ruta_logo_local = "logo_escuela.png"
        if os.path.exists(ruta_logo_local):
            try:
                with open(ruta_logo_local, "rb") as img_file:
                    encoded_logo = base64.b64encode(img_file.read()).decode('utf-8')
                logo_h = "18px" if "38mm" in tamano_etiqueta else ("24px" if "50mm" in tamano_etiqueta else "30px")
                html_img_logo = f'<img src="data:image/png;base64,{encoded_logo}" style="height: {logo_h}; width: auto; margin-right: 6px; object-fit: contain;">'
            except Exception:
                pass

        columnas_grilla = st.columns(columnas_hoja)
        html_consolidado_hoja = ""
        
        for idx, datos_fila in df_filtrado_lote.reset_index(drop=True).iterrows():
            id_act = str(datos_fila['id']).strip()
            det_act = str(datos_fila['detalle']).strip()
            fac_act = str(datos_fila['factura']).strip() if datos_fila['factura'] else "S/F"
            est_act = str(datos_fila['estado']).strip()
            ub_act = str(datos_fila['ubicacion']).strip()

            html_adicionales = ""
            if inc_factura: html_adicionales += f"<div style='font-size: 10px; color: #444444; margin-top: 1px;'><b>Doc:</b> {fac_act}</div>"
            if inc_estado: html_adicionales += f"<div style='font-size: 10px; color: #444444; margin-top: 1px;'><b>Est:</b> {est_act}</div>"
            if inc_ubicacion: html_adicionales += f"<div style='font-size: 10px; color: #444444; margin-top: 1px;'><b>📍 Ubic:</b> {ub_act}</div>"

                # 🛠️ GENERACIÓN DEL CÓDIGO DE BARRAS (CODE128) BLINDADO PARA SERVIDORES EN LA NUBE
                try:
                    code128_class = barcode.get_barcode_class('code128')
                    
                    # Forzamos al renderizador a trabajar de forma pura en memoria sin tocar jamás el disco
                    writer_instancia = ImageWriter()
                    encoder_barra = code128_class(id_act, writer=writer_instancia)
                    
                    buf_bar = io.BytesIO()
                    # El parámetro definitivo: pasamos el objeto buffer crudo directamente
                    encoder_barra.write(buf_bar, options={"write_text": False, "background": "white", "foreground": "black"})
                    
                    # Aseguramos la extracción de los bytes generados directamente de la memoria RAM
                    bar_b64 = base64.b64encode(buf_bar.getvalue()).decode()
                except Exception as e:
                    # En caso de cualquier percance menor en el servidor, dejamos registro en la barra lateral sin tumbar la app
                    st.sidebar.error(f"Error renderizado barras: {str(e)}")
                    bar_b64 = ""

            # CONCATENACIÓN ABSOLUTA PARA EL CONTENIDO INTERNO DEL CÓDIGO QR
            datos_qr = [f"ID:{id_act}", f"Det:{det_act}"]
            if inc_factura: datos_qr.append(f"Fact:{fac_act}")
            if inc_estado: datos_qr.append(f"Est:{est_act}")
            if inc_ubicacion: datos_qr.append(f"Ubic:{ub_act}")
            
            qr_local = segno.make_qr(" | ".join(datos_qr), error='m')
            buf_qr = io.BytesIO()
            qr_local.save(buf_qr, kind='png', scale=4, border=1)
            qr_b64 = base64.b64encode(buf_qr.getvalue()).decode()

            html_tarjeta_individual = f"""
            <div style="
                width: {w_px}; height: {h_px}; border: 2px dashed #333333; padding: 11px; 
                background-color: #ffffff; color: #000000; font-family: 'Arial', sans-serif; box-sizing: border-box;
                display: flex; flex-direction: column; justify-content: space-between; border-radius: 4px; margin: 5px; page-break-inside: avoid;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333333; padding-bottom: 4px;">
                    <div style="display: flex; align-items: center; text-align: left;">
                        {html_img_logo}
                        <span style="font-size: {f_body}; font-weight: bold; color: #111111; letter-spacing: 0.5px;">ESCUELA FELIPE CUBILLOS</span>
                    </div>
                    <span style="font-size: {f_body}; font-family: monospace; background-color: #eeeeee; padding: 1px 4px; border-radius: 2px; color: #000000;">TI-ACTIVO</span>
                </div>
                
                <div style="display: flex; align-items: center; justify-content: space-between; flex-grow: 1; margin: 5px 0;">
                    <div style="flex-grow: 1; padding-right: 8px; text-align: left; display: flex; flex-direction: column; justify-content: center;">
                        <div style="font-size: {f_title}; font-weight: bold; letter-spacing: 0.5px; color: #000000; word-break: break-all; margin-bottom: 2px;">{id_act}</div>
                        <div style="font-size: {f_body}; color: #333333; line-height: 1.2;">{det_act}</div>
                        {html_adicionales}
                        <div style="margin-top: 6px;">
                            <img src="data:image/png;base64,{bar_b64}" height="{bar_h}" style="display: block; width: 100%; max-width: 180px; object-fit: fill;">
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; justify-content: center; padding-left: 4px;">
                        <img src="data:image/png;base64,{qr_b64}" width="{qr_size}" height="{qr_size}" style="display: block;">
                    </div>
                </div>
                
                <div style="font-size: 9px; text-align: center; color: #555555; border-top: 1px dashed #999999; padding-top: 2px; font-style: italic;">
                    Inventario Control Reg. Interno - Felipe Cubillos
                </div>
            </div>
            """
            
            with columnas_grilla[idx % columnas_hoja]:
                st.html(html_tarjeta_individual)
            
            html_consolidado_hoja += html_tarjeta_individual

        # 5. ESTRUCTURA COMPLETA DE IMPRESIÓN ADAPTATIVA
        html_pagina_impresion = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Impresion de Etiquetas TI - Escuela Felipe Cubillos</title>
            <style>
                body {{ background: #ffffff; margin: 0; padding: 4mm; }}
                .grid-etiquetas {{ display: flex; flex-wrap: wrap; gap: 4mm; width: 100%; }}
                @media print {{ body {{ padding: 0; }} .grid-etiquetas {{ gap: 2mm; }} @page {{ margin: 4mm; size: auto; }} }}
            </style>
        </head>
        <body><div class="grid-etiquetas">{html_consolidado_hoja}</div>
            <script>window.onload = function() {{ setTimeout(function() {{ window.print(); }}, 350); }};</script>
        </body>
        </html>
        """

        html_escape_b64 = base64.b64encode(html_pagina_impresion.encode('utf-8')).decode('utf-8')

        st.markdown("---")
        col_acc1, col_acc2 = st.columns(2)
        
        with col_acc1:
            if st.button("🖨️ Abrir Ventana de Impresión", key="btn_forzar_impresion_definitiva_ti", use_container_width=True, type="primary"):
                js_bypass_sandbox = f"""
                <script>
                    var win = window.open();
                    if (win) {{
                        win.document.write(atob("{html_escape_b64}"));
                        win.document.close();
                    }} else {{
                        alert("⚠️ Navegador bloqueado: Habilite los permisos para ventanas emergentes (Pop-ups).");
                    }}
                </script>
                """
                st.components.v1.html(js_bypass_sandbox, height=0, width=0)
            
        with col_acc2:
            st.download_button(
                label="📥 Descargar Fichero HTML del Lote",
                data=html_pagina_impresion,
                file_name=f"lote_etiquetas_{tipo_seleccionado.lower().replace(' ', '_')}.html",
                mime="text/html",
                use_container_width=True,
                key="btn_dl_masivo_html_etiquetas"
            )
