# coding=utf-8
import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import base64
import os
from database import obtener_conexion, to_excel  

def inicializar_db_tablets():
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tablets (
                id_tablet TEXT PRIMARY KEY,
                nombre TEXT DEFAULT 'Tablet Institucional',
                marca TEXT,
                modelo TEXT,
                numero_serie TEXT,
                num_factura TEXT DEFAULT 'S/F',
                estado TEXT DEFAULT 'Disponible',
                ubicacion TEXT DEFAULT 'Bodega TI',
                fecha_cambio TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tablets_prestamos (
                id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT,
                ids_tablets TEXT, 
                usuario TEXT,
                rut TEXT,
                fecha_prestamo TEXT,
                fecha_limite TEXT,
                fecha_devolucion TEXT DEFAULT 'Pendiente',
                estado_prestamo TEXT DEFAULT 'Activo',
                observaciones TEXT,
                retorno_bateria INTEGER DEFAULT 100,
                retorno_cargador TEXT DEFAULT 'No Aplica',
                retorno_carcasa TEXT DEFAULT 'Conforme'
            )
        """)
        conn.commit()
def renderizar_modulo_tablets(nombre_institucion):
    inicializar_db_tablets()
    st.header("Gestion y Control de Tablets Institucionales")
    
    with obtener_conexion() as conn:
        df_all = pd.read_sql_query("SELECT id_tablet, nombre, marca, modelo, numero_serie, num_factura, estado, ubicacion FROM tablets ORDER BY id_tablet ASC", conn)
        df_usuarios = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
        df_prestamos_activos = pd.read_sql_query("SELECT id_prestamo, ids_tablets, usuario, fecha_prestamo FROM tablets_prestamos WHERE estado_prestamo='Activo' ORDER BY id_prestamo DESC", conn)
        
    lista_tablets_combo = [f"{r['id_tablet']} - {r['nombre']} ({r['marca']} {r['modelo']})" for _, r in df_all.iterrows()]
    lista_tablets_disponibles = [f"{r['id_tablet']} - {r['nombre']} ({r['marca']} {r['modelo']})" for _, r in df_all.iterrows() if r['estado'] == 'Disponible']
    lista_usuarios_combo = [f"{r['rut']} | {r['nombre']}" for _, r in df_usuarios.iterrows()] if not df_usuarios.empty else ["No hay Usuarios Registrados"]

    hoy_actual = date.today().isoformat()
    ahora_hora = datetime.now().strftime("%H:%M")
    
    bloques_termino = {
        "1 Modulo (08:30 - 10:00)": "10:00", "2 Modulo (10:15 - 11:45)": "11:45",
        "3 Modulo (12:00 - 13:30)": "13:30", "4 Modulo (14:30 - 16:00)": "16:00",
        "5 Modulo (16:15 - 17:45)": "17:45"
    }
    
    profesores_bloqueados_global = set()
    with obtener_conexion() as conn:
        df_alertas_mora = pd.read_sql_query("SELECT ids_tablets, usuario, fecha_prestamo FROM tablets_prestamos WHERE estado_prestamo = 'Activo' AND fecha_prestamo <= ?", conn, params=(hoy_actual,))
    
    if not df_alertas_mora.empty:
        for _, fila_a in df_alertas_mora.iterrows():
            profesores_bloqueados_global.add(str(fila_a['usuario']).strip().lower())
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Inventario y Mantenedor", "Solicitar / Prestar", "Devoluciones", "Bajas Tecnicas", "Listado e Historial", "Carga Masiva (Excel)"])

    with tab1:
        st.subheader("Registro de Nuevas Tablets")
        if st.session_state.get("rol") == "Administrador":
            with st.form("form_nueva_tablet_sistema_factura", clear_on_submit=True):
                col1, col2 = st.columns(2)
                id_tab = col1.text_input("ID / Codigo Unico (ej: TAB-01):")
                nombre_tab = col2.text_input("Nombre / Alias Identificatorio:", placeholder="ej: Tablet Alumno 01")
                marca_tab = col1.text_input("Marca:", value="Samsung")
                modelo_tab = col2.text_input("Modelo:", value="Galaxy Tab S9")
                num_serie = col1.text_input("Numero de Serie (S/N):")
                factura_tab = col2.text_input("Nro. Factura / Boleta Contable:")
                
                if st.form_submit_button("Guardar Tablet en Inventario"):
                    if id_tab.strip() and num_serie.strip():
                        try:
                            with obtener_conexion() as conn:
                                conn.cursor().execute("INSERT INTO tablets VALUES (?, ?, ?, ?, ?, ?, 'Disponible', 'Bodega TI', ?)",
                                               (id_tab.strip().upper(), nombre_tab.strip() if nombre_tab.strip() else "Tablet Institucional", marca_tab.strip(), modelo_tab.strip(), num_serie.strip().upper(), factura_tab.strip().upper() if factura_tab.strip() else "S/F", date.today().isoformat()))
                                conn.commit()
                            st.success("Tablet incorporada con exito.")
                            st.rerun()
                        except sqlite3.IntegrityError: st.error("El ID de esta Tablet ya se encuentra registrado.")
                    else: st.warning("El ID y el Numero de Serie son obligatorios.")
        else: st.warning("Acceso exclusivo para perfiles Administradores.")
            
        st.markdown("---")
        if not df_all.empty:
            st.dataframe(df_all, use_container_width=True, hide_index=True)
    with tab2:
        st.subheader("Agendamiento y Reserva Futura de Tablets")
        if df_usuarios.empty or "No hay" in lista_usuarios_combo[0]: 
            st.error("Registre usuarios antes de operar este modulo.")
        else:
            col_ag1, col_ag2 = st.columns(2)
            fecha_agenda = col_ag1.date_input("Fecha para la clase:", value=date.today())
            modulo_horario = col_ag2.selectbox("Bloque Horario:", list(bloques_termino.keys()))
            profesor_sel = st.selectbox("Profesor Responsable:", lista_usuarios_combo)
            
            partes_p = profesor_sel.split(" | ")
            profesor_rut_sel = partes_p[0].strip() if len(partes_p) > 1 else profesor_sel.strip()
            profesor_nombre_sel = partes_p[1].strip() if len(partes_p) > 1 else profesor_sel.strip()
            
            esta_bloqueado = profesor_nombre_sel.lower() in profesores_bloqueados_global
            if esta_bloqueado: 
                st.error("ACCESO BLOQUEADO: El docente registra deudas o atrasos activos.")
            
            with st.form("form_prestamo_masivo_tablets_agenda"):
                cantidad_solicitada = st.number_input("Cantidad requerida:", min_value=1, max_value=30, value=1, step=1)
                obs_p = st.text_input("Observaciones:", value=f"Entregado conforme para {modulo_horario}")
                
                if st.form_submit_button("Procesar Reserva", disabled=esta_bloqueado):
                    with obtener_conexion() as conn:
                        tablets_candidatas = pd.read_sql_query("SELECT id_tablet FROM tablets WHERE estado='Disponible' LIMIT ?", conn, params=(int(cantidad_solicitada),))
                    if len(tablets_candidatas) < int(cantidad_solicitada):
                        st.error("No hay suficiente stock de tablets disponibles.")
                    else:
                        lista_ids = tablets_candidatas['id_tablet'].tolist()
                        ids_p_str = ", ".join(lista_ids)
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO tablets_prestamos (ids_tablets, usuario, rut, fecha_prestamo, fecha_limite, observaciones) VALUES (?, ?, ?, ?, ?, ?)", (ids_p_str, profesor_nombre_sel, profesor_rut_sel, fecha_agenda.isoformat(), fecha_agenda.isoformat(), obs_p.strip()))
                            id_gen = cursor.lastrowid
                            for id_t in lista_ids:
                                cursor.execute("UPDATE tablets SET estado='Prestada', fecha_cambio=? WHERE id_tablet=?", (fecha_agenda.isoformat(), id_t))
                            conn.commit()
                        st.session_state["acta_tablet_entrega"] = {"id": id_gen, "tablets": ids_p_str, "cantidad": cantidad_solicitada, "usuario": profesor_nombre_sel, "rut": profesor_rut_sel, "fecha": fecha_agenda.isoformat(), "modulo": str(modulo_horario), "obs": obs_p.strip()}
                        st.session_state["mostrar_acta_fullscreen"] = True
                        st.rerun()

    with tab3:
        st.subheader("Retorno y Recepcion de Dispositivos")
        if df_prestamos_activos.empty: st.info("No hay tablets bajo prestamos activos.")
        else:
            lista_dev_combo = [f"ID:{row['id_prestamo']} | Responsable: {row['usuario']} | Equipos: {row['ids_tablets']}" for _, row in df_prestamos_activos.iterrows()]
            with st.form("form_devolucion_tablets_final"):
                pres_sel = st.selectbox("Selecciona la transaccion a cerrar:", lista_dev_combo)
                v_bateria = st.slider("Porcentaje de Bateria Restante (%):", 0, 100, 80, step=5)
                obs_dev = st.text_input("Condicion fisica general:", value="Lote recibido para revision estandar.")
                
                if st.form_submit_button("Procesar Retorno"):
                    id_p_real = int(pres_sel.split(" | ")[0].split(":")[1].strip())
                    fila_p = df_prestamos_activos[df_prestamos_activos['id_prestamo'] == id_p_real].iloc[0]
                    hoy_str = date.today().isoformat()
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE tablets_prestamos SET fecha_devolucion = ?, estado_prestamo = 'Devuelto', observaciones = ? WHERE id_prestamo = ?", (hoy_str, obs_dev.strip(), id_p_real))
                        for t_id in str(fila_p['ids_tablets']).split(","):
                            cursor.execute("UPDATE tablets SET estado = 'Disponible', ubicacion = 'Bodega TI', fecha_cambio = ? WHERE id_tablet = ?", (hoy_str, t_id.strip()))
                        conn.commit()
                    st.session_state["acta_tablet_recepcion"] = {"id": id_p_real, "tablets": fila_p['ids_tablets'], "usuario": fila_p['usuario'], "fecha_r": hoy_str, "bateria": v_bateria, "obs": obs_dev.strip()}
                    st.session_state["mostrar_acta_recepcion_fullscreen"] = True
                    st.rerun()

    with tab4:
        st.subheader("Proceso de Baja Tecnica Definitiva (Tablets)")
        if st.session_state.get("rol") == "Administrador":
            lista_tablets_operativas = [f"{r['id_tablet']}" for _, r in df_all.iterrows() if r['estado'] != 'De Baja']
            if not lista_tablets_operativas: st.info("No hay tablets operativas para descarte.")
            else:
                with st.form("form_baja_tablet"):
                    tab_baja = st.selectbox("Selecciona Tablet a retirar:", lista_tablets_operativas)
                    motivo_b = st.text_input("Motivo tecnico del descarte:")
                    if st.form_submit_button("Confirmar Baja Administrativa"):
                        if motivo_b.strip():
                            hoy_str = date.today().isoformat()
                            with obtener_conexion() as conn:
                                conn.cursor().execute("UPDATE tablets SET estado='De Baja', ubicacion='Casillero Desecho RAEE', fecha_cambio=? WHERE id_tablet=?", (hoy_str, tab_baja))
                                conn.commit()
                            st.session_state["acta_tablet_baja"] = {"id_tablet": tab_baja, "motivo": motivo_b.strip(), "fecha": hoy_str, "autoriza": st.session_state.get("usuario", "Encargado TI")}
                            st.session_state["mostrar_acta_baja_fullscreen"] = True
                            st.rerun()
        else: st.warning("Modulo restringido a Administradores.")

    with tab5:
        st.subheader("📆 Calendario de Disponibilidad e Historial")
        
        # 1. Extracción de los flujos de reservas activos
        with obtener_conexion() as conn:
            df_historial = pd.read_sql_query("""
                SELECT id_prestamo, ids_tablets, usuario, fecha_prestamo, estado_prestamo, observaciones
                FROM tablets_prestamos 
                ORDER BY id_prestamo DESC
            """, conn)

        # =========================================================================
        # 📆 MATRIX INTERACTIVA: MAPA DE CALOR SEMANAL DE BLOQUES
        # =========================================================================
        st.markdown("#### ⏰ Ocupación del Laboratorio de Tablets Móviles")
        st.caption("Consulte qué bloques horarios se encuentran reservados según la planificación escolar.")
        
        # Crear la estructura de bloques fijos de la escuela
        lista_bloques_fijos = [
            "1 Modulo (08:30 - 10:00)", 
            "2 Modulo (10:15 - 11:45)",
            "3 Modulo (12:00 - 13:30)", 
            "4 Modulo (14:30 - 16:00)",
            "5 Modulo (16:15 - 17:45)"
        ]
        
        # Selector de fecha para auditar la semana
        fecha_pivote = st.date_input("📅 Seleccione Fecha para verificar ocupación:", date.today(), key="calendar_date_picker")
        fecha_pivote_str = fecha_pivote.isoformat()
        
        # Filtrar las solicitudes asignadas a ese día exacto
        df_dia_actual = df_historial[(df_historial["fecha_prestamo"] == fecha_pivote_str) & (df_historial["estado_prestamo"] == "Activo")]
        
        matriz_horaria = []
        for bloque in lista_bloques_fijos:
            # Buscar si el bloque está tomado en las observaciones o texto de la reserva
            reserva_bloque = df_dia_actual[df_dia_actual["observaciones"].str.contains(bloque, na=False, case=False)]
            
            if not reserva_bloque.empty:
                fila_r = reserva_bloque.iloc[0]
                estado_celda = f"🔴 Reservado por: {fila_r['usuario']}"
                valor_numerico = 1  # Ocupado
            else:
                estado_celda = "🟢 Disponible para Aula"
                valor_numerico = 0  # Libre
                
            matriz_horaria.append({
                "Bloque Horario": bloque,
                "Estado de Agenda": estado_celda,
                "Control": valor_numerico
            })
            
        df_agenda_visual = pd.DataFrame(matriz_horaria)
        
        # Renderizado estético usando la configuración de columnas de Streamlit
        st.dataframe(
            df_agenda_visual,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Bloque Horario": st.column_config.TextColumn("Horario"),
                "Estado de Agenda": st.column_config.TextColumn("Disponibilidad del Día"),
                "Control": st.column_config.ProgressColumn(
                    "Ocupación Física", 
                    help="Barra indicadora de uso", 
                    format="", 
                    min_value=0, 
                    max_value=1
                )
            }
        )
        
        st.markdown("---")
        st.markdown("#### 📋 Bitácora Histórica de Transacciones")
        if not df_historial.empty:
            df_historial_fmt = df_historial.rename(columns={
                "id_prestamo": "ID Ficha",
                "ids_tablets": "Lote Tablets",
                "usuario": "Docente Responsable",
                "fecha_prestamo": "Fecha Reserva",
                "estado_prestamo": "Condición Actual"
            })
            st.dataframe(df_historial_fmt[["ID Ficha", "Lote Tablets", "Docente Responsable", "Fecha Reserva", "Condición Actual"]], use_container_width=True, hide_index=True)
        else:
            st.info("No se registran movimientos ni arriendos históricos de tablets.")

    with tab6:
        st.subheader("Carga Masiva de Tablets desde Excel")
        archivo_tablets = st.file_uploader("Seleccione archivo Excel de Tablets:", type=["xlsx"], key="uploader_tablets_masivo_final")
        if archivo_tablets is not None:
            try:
                df_excel_tab = pd.read_excel(archivo_tablets)
                if st.button("Confirmar Carga Inmediata y Sincronizar", use_container_width=True):
                    hoy_str = date.today().isoformat()
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        for _, fila in df_excel_tab.iterrows():
                            try:
                                cursor.execute("""
                                    INSERT INTO tablets (id_tablet, nombre, marca, modelo, numero_serie, num_factura, estado, ubicacion, fecha_cambio) 
                                    VALUES (?, ?, ?, ?, ?, ?, 'Disponible', 'Bodega TI', ?)
                                """, (str(fila["ID Tablet"]).strip().upper(), str(fila["Nombre"]).strip(), str(fila["Marca"]).strip(), str(fila["Modelo"]).strip(), str(fila["Numero Serie"]).strip().upper(), str(fila["Nro Factura"]).strip().upper(), hoy_str))
                            except: pass
                        conn.commit()
                    st.success("Importacion masiva de tablets finalizada correctamente.")
                    st.rerun()
            except Exception as e: st.error(f"Error al procesar la planilla: {e}")
    mostrar_entrega = st.session_state.get("mostrar_acta_fullscreen", False) and "acta_tablet_entrega" in st.session_state
    mostrar_recepcion = st.session_state.get("mostrar_acta_recepcion_fullscreen", False) and "acta_tablet_recepcion" in st.session_state
    mostrar_baja = st.session_state.get("mostrar_acta_baja_fullscreen", False) and "acta_tablet_baja" in st.session_state

    @st.dialog("Documento Oficial Emitido", width="large")
    def popup_maestro_actas_tablets(tipo_documento):
        imagen_logo = ""
        if os.path.exists("logo_escuela.png"):
            try:
                encoded_string = base64.b64encode(open("logo_escuela.png", "rb").read()).decode()                            
                imagen_logo = f"<img class='print-txt' src='data:image/png;base64,{encoded_string}' style='height: 75px; width: auto; object-fit: contain;'>"                        
            except Exception: pass

        st.markdown("""
            <style>
            @media print {
                div[data-testid="stSidebar"], header, footer, div[data-testid="stHeader"],
                div.stAlert, div.stButton, button, .stDownloadButton, [data-testid="stExpander"], 
                h1, h2, h3, hr, p:not(.print-txt), span:not(.print-txt), div:not(.zona-print-tablet) { 
                    display: none !important; 
                }
                .main, .main .block-container, [data-testid="stAppViewContainer"], html, body {
                    padding: 0mm !important; margin: 0mm !important; max-width: 100% !important; background-color: #fff !important; color: #000 !important;
                }
                .zona-print-tablet {
                    display: block !important; padding: 10mm !important; font-family: 'Arial', sans-serif !important; color: #000 !important; background: #fff !important; line-height: 1.5 !important; border: none !important;
                }
                * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                @page { margin: 15mm !important; size: letter; }
            }
            </style>
        """, unsafe_allow_html=True)

        if tipo_documento == "ENTREGA":
            act = st.session_state["acta_tablet_entrega"]
            html_acta = f"""
            <div class="zona-print-tablet" style="padding: 25px; border: 1px solid #ccc; background-color: #fafafa; border-radius: 6px; color: #000; font-family: Arial, sans-serif;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
                    {imagen_logo}
                    <div style="text-align: right;">
                        <h3 class="print-txt" style="margin: 0; color: #111; font-size: 18px; font-weight: bold;">ACTA DE COMODATO Y ASIGNACION DE TABLETS</h3>
                        <p class="print-txt" style="margin: 3px 0 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase; color: #333;">{nombre_institucion}</p>
                        <p class="print-txt" style="margin: 2px 0 0 0; font-size: 11px; color: #555; font-family: monospace;">Ref: REG-TAB-COM-{act.get('id', 'N/A')}</p>
                    </div>
                </div>
                <hr style="border: 1px solid #000; margin-bottom: 20px;">
                <table class="print-txt" style="width:100%; border-collapse: collapse; margin: 20px 0; font-size:14px; color: #000;">
                    <tr style="background-color:#eee;"><th style="border:1px solid #999; padding:8px; text-align:left; width:34%;">Concepto</th><th style="border:1px solid #999; padding:8px; text-align:left;">Detalle</th></tr>
                    <tr><td><b>Lote Tablets:</b></td><td>{act.get('tablets', 'N/A')}</td></tr>
                    <tr><td><b>Docente:</b></td><td>{act.get('usuario', 'N/A')}</td></tr>
                    <tr><td><b>Bloque:</b></td><td>{act.get('modulo', 'N/A')}</td></tr>
                </table>
                <div class="print-txt" style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 13px;">
                    <div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Profesor Custodio</b></div>
                    <div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Encargado TI</b></div>
                </div>
            </div>
            """
            st.markdown(html_acta, unsafe_allow_html=True)
            col_pop1, col_pop2 = st.columns(2)
            with col_pop1:
                st.markdown('<button onclick="window.print()" style="width: 100%; background-color: #22c55e; color: white; border: none; padding: 0.5rem; font-weight: bold; border-radius: 0.375rem; cursor: pointer;">Imprimir / Guardar PDF</button>', unsafe_allow_html=True)
            with col_pop2:
                if st.button("Concluir Operacion", use_container_width=True):
                    st.session_state["mostrar_acta_fullscreen"] = False
                    del st.session_state["acta_tablet_entrega"]
                    st.rerun()

        elif tipo_documento == "RECEPCION":
            act_r = st.session_state["acta_tablet_recepcion"]
            html_acta_r = f"""
            <div class="zona-print-tablet" style="padding: 25px; border: 1px solid #ccc; background-color: #fafafa; border-radius: 6px; color: #000; font-family: Arial, sans-serif;">
                <h3>ACTA DE RECEPCION Y CONFORMIDAD</h3>
                <p><b>Lote Reintegrado:</b> [{act_r.get('tablets', 'N/A')}]</p>
                <p><b>Bateria Promedio:</b> {act_r.get('bateria', 100)}%</p>
                <div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 13px;">
                    <div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Docente</b></div>
                    <div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Receptor TI</b></div>
                </div>
            </div>
            """
            st.markdown(html_acta_r, unsafe_allow_html=True)
            if st.button("Concluir Retorno", use_container_width=True):
                st.session_state["mostrar_acta_recepcion_fullscreen"] = False
                del st.session_state["acta_tablet_recepcion"]
                st.rerun()

    if mostrar_entrega: popup_maestro_actas_tablets("ENTREGA")
    elif mostrar_recepcion: popup_maestro_actas_tablets("RECEPCION")
