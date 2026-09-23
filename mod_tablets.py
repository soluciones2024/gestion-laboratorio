import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import base64
import os
import plotly.express as px
from database import obtener_conexion, to_excel  

def inicializar_db_tablets():
    """Asegura la migración, existencia de las tablas y migración de nuevas columnas"""
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        # 1. Tabla maestra de Tablets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tablets (
                id_tablet TEXT PRIMARY KEY,
                marca TEXT,
                modelo TEXT,
                numero_serie TEXT,
                estado TEXT DEFAULT 'Disponible',
                ubicacion TEXT DEFAULT 'Bodega TI',
                fecha_cambio TEXT
            )
        """)
        # Patches de migración segura para la tabla maestra de tablets
        try:
            cursor.execute("ALTER TABLE tablets ADD COLUMN nombre TEXT DEFAULT 'Tablet Institucional'")
            conn.commit()
        except sqlite3.OperationalError: pass

        try:
            cursor.execute("ALTER TABLE tablets ADD COLUMN num_factura TEXT DEFAULT 'S/F'")
            conn.commit()
        except sqlite3.OperationalError: pass

        # 2. Tabla de Préstamos de Tablets
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
                observaciones TEXT
            )
        """)
        conn.commit()
        # Patches de migración segura para la tabla de préstamos (Control Clínico)
        try:
            cursor.execute("ALTER TABLE tablets_prestamos ADD COLUMN retorno_bateria INTEGER DEFAULT 100")
            conn.commit()
        except sqlite3.OperationalError: pass

        try:
            cursor.execute("ALTER TABLE tablets_prestamos ADD COLUMN retorno_cargador TEXT DEFAULT 'No Aplica'")
            conn.commit()
        except sqlite3.OperationalError: pass

        try:
            cursor.execute("ALTER TABLE tablets_prestamos ADD COLUMN retorno_carcasa TEXT DEFAULT 'Conforme'")
            conn.commit()
        except sqlite3.OperationalError: pass
def renderizar_modulo_tablets(nombre_institucion):
    inicializar_db_tablets()
    st.header("📱 Gestión y Control de Tablets Institucionales")
    
    # Carga de datos inicial para los formularios de Streamlit
    with obtener_conexion() as conn:
        df_all = pd.read_sql_query("SELECT id_tablet, nombre, marca, modelo, numero_serie, num_factura, estado, ubicacion FROM tablets ORDER BY id_tablet ASC", conn)
        df_usuarios = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
        df_prestamos_activos = pd.read_sql_query("SELECT id_prestamo, ids_tablets, usuario, fecha_prestamo FROM tablets_prestamos WHERE estado_prestamo='Activo' ORDER BY id_prestamo DESC", conn)
        
    lista_tablets_combo = [f"{r['id_tablet']} - {r['nombre']} ({r['marca']} {r['modelo']})" for _, r in df_all.iterrows()]
    lista_tablets_disponibles = [f"{r['id_tablet']} - {r['nombre']} ({r['marca']} {r['modelo']})" for _, r in df_all.iterrows() if r['estado'] == 'Disponible']
    lista_usuarios_combo = [f"{r['rut']} | {r['nombre']}" for _, r in df_usuarios.iterrows()] if not df_usuarios.empty else ["⚠️ No hay Usuarios Registrados"]
    # =========================================================================
    # 🚨 MOTOR DE DETECCIÓN DE TABLETS EN MORA (NOTIFICACIÓN EN PANTALLA)
    # =========================================================================
    hoy_actual = date.today().isoformat()
    ahora_hora = datetime.now().strftime("%H:%M")
    
    bloques_termino = {
        "1° Módulo (08:30 - 10:00)": "10:00", "2° Módulo (10:15 - 11:45)": "11:45",
        "3° Módulo (12:00 - 13:30)": "13:30", "4° Módulo (14:30 - 16:00)": "16:00",
        "5° Módulo (16:15 - 17:45)": "17:45"
    }
    
    with obtener_conexion() as conn:
        df_alertas_mora = pd.read_sql_query("SELECT id_prestamo, ids_tablets, usuario, fecha_prestamo, observaciones FROM tablets_prestamos WHERE estado_prestamo = 'Activo' AND fecha_prestamo <= ?", conn, params=(hoy_actual,))
        
    alertas_visibles = []
    if not df_alertas_mora.empty:
        for _, fila_a in df_alertas_mora.iterrows():
            obs_texto, fecha_p = str(fila_a['observaciones']), str(fila_a['fecha_prestamo'])
            modulo_detectado = None
            for b_nombre in bloques_termino.keys():
                if b_nombre in obs_texto:
                    modulo_detectado = b_nombre
                    break
            if modulo_detectado:
                hora_limite = bloques_termino[modulo_detectado]
                if fecha_p < hoy_actual or (fecha_p == hoy_actual and ahora_hora > hora_limite):
                    alertas_visibles.append({"id": fila_a['id_prestamo'], "profesor": fila_a['usuario'], "tablets": fila_a['ids_tablets'], "modulo": modulo_detectado, "fecha": fecha_p})

    if alertas_visibles:
        st.error(f"🚨 **ALERTA DE CONTROL TI:** Se detectan **{len(alertas_visibles)} préstamos de tablets con retraso** de entrega.")
        for al in alertas_visibles:
            st.markdown(f"❌ **[TAB-PRES-{al['id']}]** El profesor **{al['profesor']}** aún no devuelve el lote `{al['tablets']}` correspondiente al **{al['modulo']}** con fecha **{al['fecha']}**.")
        st.markdown("---")

    # Instanciación de las 5 Pestañas de Trabajo
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Inventario y Mantenedor", "🤝 Solicitar / Prestar", "🔙 Devoluciones", "❌ Bajas Técnicas", "📊 Listado e Historial"])
    # --- PESTAÑA 1: MANTENEDOR (INGRESAR CON ALIAS Y FACTURA) ---
    with tab1:
        st.subheader("➕ Registro de Nuevas Tablets")
        if st.session_state.get("rol") == "Administrador":
            with st.form("form_nueva_tablet_sistema_factura", clear_on_submit=True):
                col1, col2 = st.columns(2)
                id_tab = col1.text_input("ID / Código Único (ej: TAB-01):", key="txt_id_tablet_registro_maestro")
                nombre_tab = col2.text_input("Nombre / Alias Identificatorio:", placeholder="ej: Tablet Alumno 01", key="txt_alias_tablet_registro_maestro")
                marca_tab = col1.text_input("Marca:", value="Samsung", key="txt_marca_tablet_registro_maestro")
                modelo_tab = col2.text_input("Modelo:", value="Galaxy Tab S9", key="txt_modelo_tablet_registro_maestro")
                num_serie = col1.text_input("Número de Serie (S/N):", key="txt_serial_tablet_registro_maestro")
                factura_tab = col2.text_input("Nro. Factura / Boleta Contable:", placeholder="ej: FAC-45812", key="txt_factura_tablet_registro_maestro")
                
                if st.form_submit_button("Guardar Tablet en Inventario"):
                    if id_tab.strip() and num_serie.strip():
                        try:
                            with obtener_conexion() as conn:
                                conn.cursor().execute("INSERT INTO tablets (id_tablet, nombre, marca, modelo, numero_serie, num_factura, estado, ubicacion, fecha_cambio) VALUES (?, ?, ?, ?, ?, ?, 'Disponible', 'Bodega TI', ?)",
                                               (id_tab.strip().upper(), nombre_tab.strip() if nombre_tab.strip() else "Tablet Institucional", marca_tab.strip(), modelo_tab.strip(), num_serie.strip().upper(), factura_tab.strip().upper() if factura_tab.strip() else "S/F", date.today().isoformat()))
                                conn.commit()
                            st.success(f"✅ Tablet {id_tab.upper()} incorporada con éxito al inventario.")
                            st.rerun()
                        except sqlite3.IntegrityError: st.error("⛔ El ID de esta Tablet ya se encuentra registrado.")
                    else: st.warning("⚠️ El ID y el Número de Serie son obligatorios.")
        else: st.warning("🔒 Acceso exclusivo para perfiles Administradores.")
            
        st.markdown("---")
        st.subheader("📋 Catálogo Actual de Tablets")
        if not df_all.empty:
            df_mostrar = df_all[["id_tablet", "nombre", "marca", "modelo", "numero_serie", "num_factura", "estado", "ubicacion"]]
            df_mostrar.columns = ["ID Tablet", "Alias Identificatorio", "Marca", "Modelo", "Nro. Serie", "Nro. Factura", "Estado Técnico", "Ubicación"]
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
            st.download_button(label="📥 Descargar Inventario Tablets (Excel)", data=to_excel(df_all), file_name="inventario_tablets.xlsx", key="btn_download_excel_inventario_tablets_factura", use_container_width=True)
        else: st.info("No hay tablets registradas en el sistema.")

    # --- PESTAÑA 2: AGENDAMIENTO PEDAGÓGICO FUTURO BLINDADO (CON SELECCIÓN EN LOTE) ---
    with tab2:
        st.subheader("📅 Agendamiento y Reserva Futura de Tablets")
        st.caption("Planifique sus clases reservando un modelo específico. Puede ingresar una cantidad exacta o solicitar el stock completo disponible para esa jornada.")
        
        if df_usuarios.empty: 
            st.error("❌ Registra usuarios/profesores antes de operar este módulo.")
        else:
            col_ag1, col_ag2 = st.columns(2)
            fecha_agenda = col_ag1.date_input("1. Seleccione Fecha para la clase:", value=date.today(), key="date_input_agenda_tablets_futura")
            modulo_horario = col_ag2.selectbox("2. Seleccione Bloque Horario Escolar:", ["1° Módulo (08:30 - 10:00)", "2° Módulo (10:15 - 11:45)", "3° Módulo (12:00 - 13:30)", "4° Módulo (14:30 - 16:00)", "5° Módulo (16:15 - 17:45)", "Jornada Completa Diaria"], key="sb_modulo_horario_agenda_tablets_futura")
            fecha_agenda_str = fecha_agenda.isoformat()
            
            with obtener_conexion() as conn:
                df_ocupadas_bloque = pd.read_sql_query("SELECT ids_tablets FROM tablets_prestamos WHERE estado_prestamo = 'Activo' AND fecha_prestamo = ? AND observaciones LIKE ?", conn, params=(fecha_agenda_str, f"%{modulo_horario}%"))
            set_ids_ocupados = set()
            if not df_ocupadas_bloque.empty:
                for _, fila_o in df_ocupadas_bloque.iterrows():
                    for id_t in str(fila_o['ids_tablets']).split(","):
                        if id_t.strip(): set_ids_ocupados.add(id_t.strip())
            
            df_stock_neto_futuro = df_all[(df_all['estado'] != 'De Baja') & (~df_all['id_tablet'].isin(set_ids_ocupados))]
            
            if df_stock_neto_futuro.empty: 
                st.warning(f"⚠️ No hay stock disponible de tablets para el bloque {modulo_horario} en la fecha {fecha_agenda_str}.")
            else:
                df_conteo_futuro = df_stock_neto_futuro.groupby(['nombre', 'marca', 'modelo']).size().reset_index(name='disponibles')
                lista_modelos_disponibles = [f"{row['nombre']} | {row['marca']} {row['modelo']} ({row['disponibles']} libres)" for _, row in df_conteo_futuro.iterrows()]

                with st.form("form_prestamo_masivo_tablets_final_agenda_nueva", clear_on_submit=False):
                    col_form1, col_form2 = st.columns(2)
                    modelo_seleccionado_txt = col_form1.selectbox("Modelo de Tablet requerido:", lista_modelos_disponibles, key="sb_modelo_tablet_form_agenda")
                    
                    # NUEVA MEJORA: Switch para llevarse el stock total o un número fijo
                    modo_seleccion_stock = col_form2.radio("Modalidad de Retiro:", ["Cantidad Específica", "Llevar TODAS las Unidades Libres"], horizontal=True, key="radio_modo_seleccion_stock_tablets")
                    
                    # Extraer matemáticamente el stock máximo disponible del modelo elegido
                    texto_modelo_aislado = modelo_seleccionado_txt.split(" | ")[0].strip()
                    max_unidades_libres = int(df_conteo_futuro[df_conteo_futuro['nombre'] == texto_modelo_aislado]['disponibles'].iloc[0])
                    
                    # Control condicional del cuadro numérico según la modalidad seleccionada
                    if modo_seleccion_stock == "Llevar TODAS las Unidades Libres":
                        cantidad_solicitada = col_form1.number_input("Cantidad de unidades requeridas:", min_value=max_unidades_libres, max_value=max_unidades_libres, value=max_unidades_libres, disabled=True, key="num_disabled_max_stock")
                        st.caption(f"💡 Se seleccionaron automáticamente las **{max_unidades_libres}** tablets del modelo `{texto_modelo_aislado}` disponibles en bodega.")
                    else:
                        cantidad_solicitada = col_form1.number_input("Cantidad de unidades requeridas:", min_value=1, max_value=max_unidades_libres, value=1, step=1, key="num_enabled_manual_stock")
                    
                    profesor_sel = col_form2.selectbox("Profesor / Custodio Responsable:", lista_usuarios_combo, key="sb_profesor_form_agenda")
                    curso_clase = col_form2.selectbox("Curso de destino:", ["Primero Básico", "Segundo Básico", "Tercero Básico", "Cuarto Básico", "Quinto Básico", "Sexto Básico", "Séptimo Básico", "Octavo Básico", "Kinder", "Pre-Kinder", "Otro"], key="sb_curso_form_agenda")
                    asignatura_clase = col_form1.selectbox("Asignatura / Taller:", ["Lenguaje", "Matemáticas", "Ciencias Naturales", "Historia", "Inglés", "Artes Visuales", "Educación Física", "Música", "Tecnología", "Otro"], key="sb_asig_form_agenda")
                    obs_p = col_form2.text_input("Observaciones adicionales:", value="Entregado conforme en contenedor institucional.")
                    
                    nombre_profesor_limpio = profesor_sel.split(" | ")[1].strip() if " | " in profesor_sel else profesor_sel
                    esta_bloqueado = any(al['profesor'] == nombre_profesor_limpio for al in alertas_visibles)
                    if esta_bloqueado: 
                        st.markdown(f"<div style='padding:10px; background-color:#ffcccc; color:#cc0000; border-radius:4px; font-weight:bold; margin-bottom:15px;'>⛔ ACCESO BLOQUEADO: El docente {nombre_profesor_limpio} registra deudas vigentes de tablets en mora.</div>", unsafe_allow_html=True)
                    
                    if st.form_submit_button("🚀 Procesar Reserva y Emitir Acta de Entrega", disabled=esta_bloqueado):
                        texto_modelo_limpio = modelo_seleccionado_txt.split(" | ")[0].strip()
                        tablets_candidatas = df_stock_neto_futuro[df_stock_neto_futuro['nombre'] == texto_modelo_limpio].head(int(cantidad_solicitada))
                        
                        if len(tablets_candidatas) < cantidad_solicitada: 
                            st.error(f"⛔ Error: No hay suficientes unidades libres.")
                        else:
                            partes_us = profesor_sel.split(" | ")
                            rut_r, nom_r = partes_us[0].strip(), partes_us[1].strip()
                            lista_ids_asignados = tablets_candidatas['id_tablet'].tolist()
                            ids_p_str = ", ".join(lista_ids_asignados)
                            destino_estructurado = f"Bloque: {modulo_horario} | Clase: {asignatura_clase} en {curso_clase}."
                            if obs_p.strip(): destino_estructurado += f" Obs: {obs_p.strip()}"
                            
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute("INSERT INTO tablets_prestamos (ids_tablets, usuario, rut, fecha_prestamo, fecha_limite, observaciones) VALUES (?, ?, ?, ?, ?, ?)", (ids_p_str, nom_r, rut_r, fecha_agenda_str, fecha_agenda_str, destino_estructurado))
                                id_generado = cursor.lastrowid
                                if fecha_agenda_str == date.today().isoformat():
                                    for id_t_real in lista_ids_asignados: 
                                        cursor.execute("UPDATE tablets SET estado='Prestada', fecha_cambio=? WHERE id_tablet=?", (fecha_agenda_str, id_t_real))
                                conn.commit()
                                
                            modelo_txt_limpio = modelo_seleccionado_txt.split(" | ")[1].split(" (")[0].strip()
                            
                            st.session_state["acta_tablet_entrega"] = {"id": id_generado, "tablets": ids_p_str, "modelo_txt": f"{texto_modelo_limpio} ({modelo_txt_limpio})", "cantidad": cantidad_solicitada, "usuario": nom_r, "rut": rut_r, "fecha": fecha_agenda_str, "modulo": str(modulo_horario), "curso": str(curso_clase), "asignatura": str(advanced_asig:=asignatura_clase), "obs": obs_p.strip()}
                            st.session_state["mostrar_acta_fullscreen"] = True
                            st.rerun()
                                                     
                            
    # --- PESTAÑA 3: DEVOLUCIONES CON CONTROL CLÍNICO Y RETORNO SEGURO ---
    with tab3:
        st.subheader("🔙 Retorno y Recepción de Dispositivos")
        if df_prestamos_activos.empty: st.info("🤝 No hay tablets bajo préstamos activos en este momento.")
        else:
            lista_dev_combo = [f"ID:{row['id_prestamo']} | Responsable: {row['usuario']} | Equipos: {row['ids_tablets']}" for _, row in df_prestamos_activos.iterrows()]
            with st.form("form_devolucion_tablets_sistema_nuevo_talca_clinico_final", clear_on_submit=False):
                st.subheader("🔙 Registrar Retorno Físico de Lote")
                pres_sel = st.selectbox("Selecciona la transacción a cerrar:", lista_dev_combo, key="sb_devolucion_tablets_maestro_final_v2")
                col_c1, col_c2, col_c3 = st.columns(3)
                v_bateria = col_c1.slider("Porcentaje de Batería Restante (%):", 0, 100, 80, step=5, key="slider_bateria_retorno_tablets")
                v_cargador = col_c2.selectbox("Estado de Cargadores / Cables:", ["Conforme", "Faltante / Extraviado", "Dañado Técnicamente"], key="sb_cargador_retorno_tablets")
                v_carcasa = col_c3.selectbox("Estado de Carcasas Antigolpes:", ["Conforme", "Dañado Estructuralmente"], key="sb_carcasa_retorno_tablets")
                obs_dev = st.text_input("Condición física general u observaciones:", value="Lote recibido para revisión estándar.", key="txt_obs_devolucion_tablets_final_v2")
                
                if st.form_submit_button("📥 Procesar Retorno y Emitir Acta de Recepción", use_container_width=True):
                    partes_glosa = pres_sel.split(" | ")
                    id_p_real = int(partes_glosa[0].split(":")[1].strip())
                    fila_p = df_prestamos_activos[df_prestamos_activos['id_prestamo'] == id_p_real].iloc[0]
                    hoy_str = date.today().isoformat()
                    
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE tablets_prestamos SET fecha_devolucion = ?, estado_prestamo = 'Devuelto', observaciones = ?, retorno_bateria = ?, retorno_cargador = ?, retorno_carcasa = ? WHERE id_prestamo = ?", (hoy_str, obs_dev.strip(), v_bateria, v_cargador, v_carcasa, id_p_real))
                        for t_id in fila_p['ids_tablets'].split(","):
                            id_t_limpio = t_id.strip()
                            nuevo_estado_hardware = "En Carga" if v_bateria <= 20 else "Disponible"
                            nueva_ub_hardware = "Estación de Carga Carro TI" if v_bateria <= 20 else "Bodega TI"
                            cursor.execute("UPDATE tablets SET estado = ?, ubicacion = ?, fecha_cambio = ? WHERE id_tablet = ?", (nuevo_estado_hardware, nueva_ub_hardware, hoy_str, id_t_limpio))
                        conn.commit()
                        
                    st.session_state["acta_tablet_recepcion"] = {"id": id_p_real, "tablets": fila_p['ids_tablets'], "usuario": fila_p['usuario'], "fecha_r": hoy_str, "bateria": v_bateria, "cargador": v_cargador, "carcasa": v_carcasa, "obs": obs_dev.strip()}
                    st.session_state["mostrar_acta_recepcion_fullscreen"] = True
                    st.rerun()

    # --- PESTAÑA 4: BAJAS TÉCNICAS DEFINITIVAS ---
    with tab4:
        st.subheader("❌ Proceso de Baja Técnica Definitiva (Tablets)")
        if st.session_state.get("rol") == "Administrador":
            lista_tablets_operativas = [f"{r['id_tablet']} - {r['marca']} {r['modelo']}" for _, r in df_all.iterrows() if r['estado'] != 'De Baja']
            if not lista_tablets_operativas: st.info("No hay tablets operativas de descarte.")
            else:
                with st.form("form_baja_tablet_dispositivos_exclusivo_nueva", clear_on_submit=True):
                    tab_baja = st.selectbox("Selecciona Tablet a retirar del sistema:", lista_tablets_operativas, key="sb_baja_tablets_maestro_v2")
                    motivo_b = st.text_input("Motivo técnico del descarte definitivo:", placeholder="ej: Batería inflada...", key="txt_motivo_baja_tablet_real_v2")
                    if st.form_submit_button("🚨 Confirmar Destrucción / Baja Administrativa"):
                        if motivo_b.strip():
                            id_t_baja = tab_baja.split(" - ")[0].strip()
                            hoy_str = date.today().isoformat()
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE tablets SET estado='De Baja', ubicacion='Casillero Desecho RAEE', fecha_cambio=? WHERE id_tablet=?", (hoy_str, id_t_baja))
                                cursor.execute("INSERT INTO historial_mantenimiento (id_equipo, fecha_ingreso, fecha_salida, detalle_reparacion, costo_repuestos) VALUES (?, ?, ?, ?, 0.0)", (id_t_baja, hoy_str, hoy_str, f"❌ [BAJA TABLET] Motivo: {motivo_b.strip()}"))
                                conn.commit()
                            st.success(f"Tablet {id_t_baja} registrada de baja técnica.")
                            st.rerun()
                        else: st.error("Debe detallar el informe técnico.")
        else: st.warning("🔒 Módulo restringido a Administradores.")
    # --- PESTAÑA 5: LISTADO E HISTORIAL DE MOVIMIENTOS Y GRÁFICOS ---
    with tab5:
        st.subheader("📊 Historial de Trazabilidad y Uso de Tablets")
        with obtener_conexion() as conn:
            df_historial_tablets = pd.read_sql_query("SELECT id_prestamo AS 'ID Mov.', fecha_prestamo AS 'Fecha Entrega', ids_tablets AS 'Lote Tablets', usuario AS 'Profesor Encargado', rut AS 'RUT', fecha_devolucion AS 'Fecha Retorno', estado_prestamo AS 'Estado Actual', observaciones AS 'Detalle Pedagógico / Horario' FROM tablets_prestamos ORDER BY id_prestamo DESC", conn)
            
        if df_historial_tablets.empty: st.info("📂 No se registran movimientos históricos todavía.")
        else:
            total_movimientos, lotes_activos = len(df_historial_tablets), len(df_historial_tablets[df_historial_tablets['Estado Actual'] == 'Activo'])
            lotes_devueltos = len(df_historial_tablets[df_historial_tablets['Estado Actual'] == 'Devuelto'])
            col_h1, col_h2, col_h3 = st.columns(3)
            col_h1.metric("Total Solicitudes Históricas", f"{total_movimientos} clases")
            col_h2.metric("Préstamos Vigentes (En Aula)", f"{lotes_activos} lotes", delta_color="inverse")
            col_h3.metric("Retornos Concluidos (En Bodega)", f"{lotes_devueltos} devueltos")
            
            st.markdown("---")
            col_graf_t1, col_graf_t2 = st.columns(2)
            lista_asignaturas_conteo, lista_cursos_conteo = [], []
            lista_asig_fijas = ["Lenguaje", "Matemáticas", "Ciencias Naturales", "Historia", "Inglés", "Artes Visuales", "Educación Física", "Música", "Tecnología"]
            lista_cursos_fijos = ["Primero Básico", "Segundo Básico", "Tercero Básico", "Cuarto Básico", "Quinto Básico", "Sexto Básico", "Séptimo Básico", "Octavo Básico", "Kinder", "Pre-Kinder"]
            
            for _, fila_h in df_historial_tablets.iterrows():
                glosa_obs = str(fila_h['Detalle Pedagógico / Horario'])
                for asig in lista_asig_fijas:
                    if f"Clase: {asig}" in glosa_obs: lista_asignaturas_conteo.append(asig)
                for curso in lista_cursos_fijos:
                    if f"en {curso}" in glosa_obs: lista_cursos_conteo.append(curso)
            
            with col_graf_t1:
                st.markdown("##### 📚 Frecuencia por Asignatura")
                if lista_asignaturas_conteo:
                    df_graf_asig_tabs = pd.DataFrame(lista_asignaturas_conteo, columns=['Asignatura']).value_counts().reset_index(name='Cantidad Préstamos')
                    fig_asig_tabs = px.bar(df_graf_asig_tabs.head(5), x='Cantidad Préstamos', y='Asignatura', orientation='h', color='Asignatura', color_discrete_sequence=px.colors.qualitative.Set2, labels={'Cantidad Préstamos': 'Clases', 'Asignatura': ''})
                    fig_asig_tabs.update_layout(showlegend=False, height=220, margin=dict(l=0, r=0, t=10, b=10))
                    st.plotly_chart(fig_asig_tabs, use_container_width=True, key="grafico_demanda_tablets_asig_p5_final")
                else: st.info("Sin datos.")
            
            with col_graf_t2:
                st.markdown("##### 🏫 Ocupación por Cursos")
                if lista_cursos_conteo:
                    df_graf_cursos_tabs = pd.DataFrame(lista_cursos_conteo, columns=['Curso']).value_counts().reset_index(name='Cantidad Préstamos')
                    fig_cursos_tabs = px.bar(df_graf_cursos_tabs.head(5), x='Cantidad Préstamos', y='Curso', orientation='h', color='Curso', color_discrete_sequence=px.colors.qualitative.Pastel, labels={'Cantidad Préstamos': 'Clases', 'Curso': ''})
                    fig_cursos_tabs.update_layout(showlegend=False, height=220, margin=dict(l=0, r=0, t=10, b=10))
                    st.plotly_chart(fig_cursos_tabs, use_container_width=True, key="grafico_demanda_tablets_cursos_p5_final")
                else: st.info("Sin datos.")
            
            st.markdown("---")
            col_filtro_txt, col_filtro_est = st.columns([0.7, 0.3])
            buscar_h_txt = col_filtro_txt.text_input("Filtrar historial:", key="txt_buscar_historial_tablets_exclusivo_v2")
            estado_filtro = col_filtro_est.selectbox("Condición:", ["Todos", "Activo", "Devuelto"], key="sb_filtro_estado_historial_tablets_v2")
            
            df_resultado_h = df_historial_tablets.copy()
            if estado_filtro != "Todos": df_resultado_h = df_resultado_h[df_resultado_h['Estado Actual'] == estado_filtro]
            if buscar_h_txt.strip():
                term_h = buscar_h_txt.strip().lower()
                df_resultado_h = df_resultado_h[df_resultado_h['Profesor Encargado'].astype(str).str.lower().str.contains(term_h) | df_resultado_h['Lote Tablets'].astype(str).str.lower().str.contains(term_h)]
            st.dataframe(df_resultado_h, use_container_width=True, hide_index=True)
    # =========================================================================
    # 🖨️ MOTOR UNIFICADO DE VENTANAS EMERGENTES (FIN DEL ARCHIVO MAESTRO)
    # =========================================================================
    mostrar_entrega = st.session_state.get("mostrar_acta_fullscreen", False) and "acta_tablet_entrega" in st.session_state
    mostrar_recepcion = st.session_state.get("mostrar_acta_recepcion_fullscreen", False) and "acta_tablet_recepcion" in st.session_state

    if mostrar_entrega or mostrar_recepcion:
        @st.dialog("📄 Documento Oficial Emitido", width="large")
        def popup_maestro_actas_tablets(tipo_documento):
            imagen_logo = ""
            if os.path.exists("logo_escuela.png"):
                try:
                    encoded_string = base64.b64encode(open("logo_escuela.png", "rb").read()).decode()                            
                    imagen_logo = f"<img src='data:image/png;base64,{encoded_string}' style='height: 70px; width: auto;'>"                        
                except Exception: pass

            if tipo_documento == "ENTREGA":
                act = st.session_state["acta_tablet_entrega"]
                html_acta = f"""<div style="padding: 25px; border: 1px solid #111; background-color: #ffffff; color: #000; font-family: 'Arial', sans-serif; line-height: 1.6;"><div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">{imagen_logo}<div style="text-align: right;"><h3 style="margin: 0; color: #000; font-size: 18px; font-weight: bold;">ACTA DE COMODATO Y ASIGNACIÓN DE TABLETS</h3><p style="margin: 3px 0 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">{nombre_institucion}</p><p style="margin: 2px 0 0 0; font-size: 11px; color: #444; font-family: monospace;">Ref: REG-TAB-COM-{act.get('id', 'N/A')}</p></div></div><hr style="border: 1px solid #000; margin-bottom: 20px;"><p style="font-size: 14px; text-align: justify; color: #000;">Por medio del presente documento, se deja constancia de la entrega en calidad de préstamo/comodato del siguiente lote de activos tecnológicos destinados a labores pedagógicas en aula:</p><table style="width:100%; border-collapse: collapse; margin: 20px 0; font-size:14px; color: #000; background-color: #fff;"><tr style="background-color:#eee;"><th style="border:1px solid #999; padding:8px; text-align:left; width:30%;">Concepto / Ítem</th><th style="border:1px solid #999; padding:8px; text-align:left;">Detalle de Asignación</th></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Lote Equipos Asignados:</b></td><td style="border:1px solid #999; padding:8px; font-family:monospace; font-weight:bold;">{act.get('tablets', 'N/A')}</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Modelo Hardware Lote:</b></td><td style="border:1px solid #999; padding:8px;">{act.get('modelo_txt', 'N/A')}</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Total Unidades:</b></td><td style="border:1px solid #999; padding:8px; font-weight:bold; color:#00f;">{act.get('cantidad', 0)} dispositivos</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Custodio Responsable:</b></td><td style="border:1px solid #999; padding:8px;">{act.get('usuario', 'N/A')}</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>RUT Custodio:</b></td><td style="border:1px solid #999; padding:8px;">{act.get('rut', 'N/A')}</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Curso de Destino:</b></td><td style="border:1px solid #999; padding:8px; font-weight:bold;">{act.get('curso', 'N/A')}</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Asignatura / Planificación:</b></td><td style="border:1px solid #999; padding:8px;">{act.get('asignatura', 'N/A')}</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Módulo / Horario de Uso:</b></td><td style="border:1px solid #999; padding:8px; font-weight:bold; color:#cc0000;">{act.get('modulo', 'N/A')}</td></tr><tr><td style="border:1px solid #999; padding:8px;"><b>Fecha de la Jornada:</b></td><td style="border:1px solid #999; padding:8px;">{act.get('fecha', 'N/A')}</td></tr></table><p style="font-size: 11px; text-align: justify; color: #333; font-style: italic; margin-top: 15px;">Cláusula de Responsabilidad: El docente se compromete a supervisar el lote de tablets y a devolverlas de forma íntegra una vez finalizado el bloque horario escolar.</p><div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 12px; color: #000;"><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Profesor Custodio</b></div><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Encargado TI</b></div></div></div>"""
                st.markdown(html_acta.replace("\n", "").strip(), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔄 Concluir Operación e Imprimir", key="btn_close_master_entrega_final", use_container_width=True):
                    st.session_state["mostrar_acta_fullscreen"] = False
                    del st.session_state["acta_tablet_entrega"]
                    st.rerun()

            elif tipo_documento == "RECEPCION":
                act_r = st.session_state["acta_tablet_recepcion"]
                html_acta_r = f"""<div style="padding: 20px; border: 1px solid #111; background-color: #ffffff; color: #000; font-family: 'Arial', sans-serif; line-height: 1.6;"><div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">{imagen_logo}<div style="text-align: right;"><h3 style="margin: 0; color: #000; font-size: 18px; font-weight: bold;">ACTA DE RECEPCIÓN Y CONFORMIDAD DE TABLETS</h3><p style="margin: 3px 0 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">{nombre_institucion}</p><p style="margin: 2px 0 0 0; font-size: 11px; color: #444; font-family: monospace;">Ref: REG-TAB-REC-{act_r.get('id', 'N/A')}</p></div></div><hr style="border: 1px solid #000; margin-bottom: 15px;"><table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px; color: #000; background-color: #fff;"><tr style="background-color:#eee;"><th style="border: 1px solid #999; padding: 8px; text-align: left; width: 30%;">Concepto / Ítem</th><th style="border: 1px solid #999; padding: 8px; text-align: left;">Detalle de Asignación</th></tr><tr><td style="border: 1px solid #999; padding: 8px;"><b>Docente que Devuelve:</b></td><td style="border: 1px solid #999; padding: 8px; font-weight: bold;">{act_r.get('usuario', 'N/A')}</td></tr><tr><td style="border: 1px solid #999; padding: 8px;"><b>Fecha de Recepción:</b></td><td style="border: 1px solid #999; padding: 8px;">{act_r.get('fecha_r', 'N/A')}</td></tr><tr><td style="border: 1px solid #999; padding: 8px;"><b>Carga de Batería Lote:</b></td><td style="border: 1px solid #999; padding: 8px; font-weight: bold; color: #00f;">{act_r.get('bateria', 100)}% {'(Pasa a Estación de Carga)' if act_r.get('bateria', 100) <= 20 else '(Nivel Óptimo)'}</td></tr><tr><td style="border: 1px solid #999; padding: 8px;"><b>Auditoría Cargadores:</b></td><td style="border: 1px solid #999; padding: 8px;">{act_r.get('cargador', 'N/A')}</td></tr><tr><td style="border: 1px solid #999; padding: 8px;"><b>Auditoría Carcasas:</b></td><td style="border: 1px solid #999; padding: 8px;">{act_r.get('carcasa', 'N/A')}</td></tr><tr><td style="border: 1px solid #999; padding: 8px;"><b>IDs Lote Reintegrado:</b></td><td style="border: 1px solid #999; padding: 8px; font-family:monospace; font-weight:bold;">[{act_r.get('tablets', 'N/A')}]</td></tr></table><div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 12px; color: #000;"><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Profesor Custodio</b></div><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Receptor TI</b></div></div></div>"""
                st.markdown(html_acta_r.replace("\n", "").strip(), unsafe_allow_html=True)
                if st.button("🔄 Concluir Recepción y Liberar", key="btn_close_master_recepcion_final", use_container_width=True):
                    st.session_state["mostrar_acta_recepcion_fullscreen"] = False
                    del st.session_state["acta_tablet_recepcion"]
                    st.rerun()

        if mostrar_entrega: popup_maestro_actas_tablets("ENTREGA")
        elif mostrar_recepcion: popup_maestro_actas_tablets("RECEPCION")
