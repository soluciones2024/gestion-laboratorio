import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import os
import shutil
import plotly.express as px
import segno
import io  
import requests
import zipfile

# Importaciones de tu configuración de base de datos
from database import obtener_conexion, inicializar_db, to_excel, obtener_bytes_db, restaurar_db_desde_bytes
from mod_qr import renderizar_modulo_qr

# Configuración de API Key de Brevo
try:
    BREVO_API_KEY = st.secrets["BREVO_API_KEY"]
except KeyError:
    st.error("Falta configurar la API Key de Brevo en los secretos de Streamlit.")

# --- Definición de la función de envío de correos ---
def enviar_correo_mora_local(correo_destino, usuario, id_equipo, fecha_limite, dias_atraso):
    if "BREVO_API_KEY" not in st.secrets:
        return False
    
    headers_api = {
        "accept": "application/json",
        "api-key": st.secrets["BREVO_API_KEY"],
        "content-type": "application/json"
    }
    asunto = f"🚨 ALERTA: Retraso en devolución de equipo {id_equipo}"
    payload = {
        "sender": {"name": "Sistema Laboratorio", "email": "no-reply@escuelafelipecubillos.cl"},
        "to": [{"email": correo_destino, "name": usuario}],
        "subject": asunto,
        "htmlContent": f"<html><body><h2>Recordatorio de Laboratorio</h2><p>Hola {usuario}, registras un retraso de {dias_atraso} días en la devolución del equipo <b>{id_equipo}</b> (Plazo máximo: {fecha_limite}). Por favor acérquese a regularizar.</p></body></html>"
    }
    try:
        res = requests.post("https://brevo.com", json=payload, headers=headers_api)
        return res.status_code == 200 or res.status_code == 201
    except Exception:
        return False

# Inicializar base de datos externa al arrancar
inicializar_db()
# --- CONTROL DE ACCESO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "rol" not in st.session_state:
    st.session_state["rol"] = "Visor"

if not st.session_state["authenticated"]:
    st.markdown("### 🔒 Acceso Restringido al Laboratorio")
    password_input = st.text_input("Introduce tu clave de acceso:", type="password", key="login_pass_role")
    if st.button("Iniciar Sesión"):
        if password_input == st.secrets["general"]["PASSWORD_ADMIN"]:
            st.session_state["authenticated"] = True
            st.session_state["rol"] = "Administrador"
            st.rerun()
        elif password_input == st.secrets["general"]["PASSWORD_VISOR"]:
            st.session_state["authenticated"] = True
            st.session_state["rol"] = "Visor"
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

st.sidebar.markdown(f"👤 **Sesión:** `{st.session_state['rol']}`")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- MENÚ DE NAVEGACIÓN ---
st.title("🖥️ Sistema de Gestión de Laboratorio Escuela Felipe Cubillos")
menu = [
    "Panel de Control", 
    "Inventario de Equipos", 
    "Gestión de Estados / Bajas", 
    "Mantenedor de Usuarios", 
    "Préstamo de Equipos", 
    "Gestión de Salas", 
    "Generador de QR", 
    "Respaldo de Seguridad", 
    "Bitácora de Notas", 
]
choice = st.sidebar.selectbox("Navegación", menu)

# =========================================================================
# 📊 MÓDULO: PANEL DE CONTROL (EDICIÓN INTEGRAL COMPLETA)
# =========================================================================
if choice == "Panel de Control":
    st.header("📊 Resumen General y Métricas del Laboratorio")
    
    with obtener_conexion() as conn:
        df_eq = pd.read_sql_query("SELECT estado, tipo, ubicacion FROM equipos", conn)
        df_co = pd.read_sql_query("SELECT cantidad, costo_unitario FROM compras", conn)
        df_sal = pd.read_sql_query("SELECT * FROM salas", conn)
        
        try:
            df_bit = pd.read_sql_query("SELECT id_nota, nota, fecha_vencimiento, estado_nota FROM bitacora", conn)
        except Exception:
            df_bit = pd.DataFrame(columns=["id_nota", "nota", "fecha_vencimiento", "estado_nota"])
        
        # Consulta de préstamos activos con INNER JOIN para deudores
        query_pr_kpi = """
            SELECT p.id_prestamo, p.id_equipo, p.usuario, p.rut, p.fecha_limite, u.correo 
            FROM prestamos p 
            INNER JOIN usuarios u ON p.rut = u.rut 
            WHERE p.estado_prestamo = 'Activo'
        """
        df_pr = pd.read_sql_query(query_pr_kpi, conn)
        
        # 🏆 CONSULTAS NUEVAS: Rankings históricos para Alta Demanda
        df_rank_equipos = pd.read_sql_query("""
            SELECT id_equipo as 'Código Equipo', COUNT(*) as 'Total Préstamos'
            FROM prestamos 
            GROUP BY id_equipo 
            ORDER BY COUNT(*) DESC 
            LIMIT 5
        """, conn)
        
        df_rank_usuarios = pd.read_sql_query("""
            SELECT usuario as 'Nombre Custodio', rut as 'RUT', COUNT(*) as 'Veces Solicitado'
            FROM prestamos 
            GROUP BY rut 
            ORDER BY COUNT(*) DESC 
            LIMIT 5
        """, conn)
    
    hoy_str = date.today().isoformat()
    
    # 🚨 BANDA DE ALERTAS: Hardware en Mora
    if not df_pr.empty:
        df_vencidos = df_pr[df_pr['fecha_limite'] < hoy_str].copy()
        if not df_vencidos.empty:
            st.error(f"🚨 **ALERTA HARDWARE:** Se detectan {len(df_vencidos)} préstamos con morosidad activa.")
            for idx, prestamo in df_vencidos.iterrows():
                col_alerta_txt, col_alerta_btn = st.columns([0.75, 0.25])
                with col_alerta_txt:
                    st.markdown(f"⚠️ **{prestamo['usuario']}** retiene el equipo **{prestamo['id_equipo']}** (Venció: {prestamo['fecha_limite']}).")
                with col_alerta_btn:
                    partes_nombre = str(prestamo['usuario']).split(" ") if prestamo['usuario'] else ["Usuario"]
                    primer_nombre = partes_nombre[0]
                    if st.button(f"📧 Avisar a {primer_nombre}", key=f"btn_pnl_notif_{prestamo['id_prestamo']}_{idx}", use_container_width=True):
                        with st.spinner("Despachando correo..."):
                            try: 
                                f_lim = date.fromisoformat(str(prestamo['fecha_limite']))
                                atraso = max((date.today() - f_lim).days, 1)
                            except: 
                                atraso = 1
                            if enviar_correo_mora_local(prestamo['correo'], prestamo['usuario'], prestamo['id_equipo'], prestamo['fecha_limite'], atraso):
                                st.toast("¡Notificación enviada!", icon="✅")
                            else: 
                                st.error("Fallo al despachar.")

    # 🚨 BANDA DE ALERTAS: Bitácora de Tareas Atrasadas
    if not df_bit.empty and "estado_nota" in df_bit.columns:
        df_retrasos_pnl_bit = df_bit[(df_bit['estado_nota'] == 'Pendiente') & (df_bit['fecha_vencimiento'] != 'N/A') & (df_bit['fecha_vencimiento'] < hoy_str)].copy()
        if not df_retrasos_pnl_bit.empty:
            st.warning(f"📝 **ALERTA BITÁCORA:** Hay **{len(df_retrasos_pnl_bit)} tareas pendientes** fuera de plazo.")
            with st.expander("🔍 Ver detalles de tareas atrasadas", expanded=False):
                for idx, fila_b in df_retrasos_pnl_bit.iterrows():
                    try:
                        f_v = date.fromisoformat(fila_b['fecha_vencimiento'])
                        dias_atraso_b = (date.today() - f_v).days
                    except:
                        dias_atraso_b = 1
                    st.write(f"🔴 **[ID {fila_b['id_nota']}] - Hace {dias_atraso_b} días:** {fila_b['nota'][:100]}...")

    # 📈 INDICADORES CLAVE DE RENDIMIENTO (KPIs)
    st.markdown("---")
    st.markdown("### 📈 Indicadores Clave de Rendimiento (KPIs)")
    col1, col2, col3, col4 = st.columns(4)
    
    total_equipos = len(df_eq)
    equipos_operativos = len(df_eq[df_eq["estado"] == "Operativo"]) if "estado" in df_eq.columns else 0
    prestamos_activos = len(df_pr)
    notas_pendientes = len(df_bit[df_bit["estado_nota"] == "Pendiente"]) if "estado_nota" in df_bit.columns else 0
    
    col1.metric("📦 Total de Equipos", total_equipos)
    col2.metric("✅ Equipos Operativos", equipos_operativos)
    col3.metric("🤝 Préstamos Activos", prestamos_activos)
    col4.metric("🛠️ Tareas Pendientes (Bitácora)", notas_pendientes)

    # 🔍 DISTRIBUCIÓN DEL INVENTARIO (GRÁFICOS PLOTLY)
    st.markdown("---")
    st.markdown("### 🔍 Distribución del Inventario")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if not df_eq.empty and 'estado' in df_eq.columns:
            st.plotly_chart(px.pie(df_eq.groupby('estado').size().reset_index(name='Cantidad'), values='Cantidad', names='estado', title="Estado Técnico", hole=0.4), use_container_width=True, key="g_pie_pnl")
    with col_g2:
        if not df_eq.empty and 'tipo' in df_eq.columns:
            st.plotly_chart(px.bar(df_eq.groupby('tipo').size().reset_index(name='Cantidad'), x='tipo', y='Cantidad', title="Categorías de Hardware"), use_container_width=True, key="g_bar_pnl")
            
    # 💵 SECCIÓN NUEVA: BALANCE FINANCIERO E INVERSIÓN ESCOLAR
    st.markdown("---")
    st.markdown("### 💵 Balance Financiero e Inversión Escolar")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        gasto_compras = (df_co["cantidad"] * df_co["costo_unitario"]).sum() if not df_co.empty else 0
        st.metric("Total Invertido en Adquisiciones", f"${gasto_compras:,.0f} CLP")
    with col_f2:
        st.metric("🏛️ Salas de Clases Supervisadas", len(df_sal))

    # 🏆 SECCIÓN NUEVA: HISTORIAL DE ALTA DEMANDA Y USO DEL LABORATORIO
    st.markdown("---")
    st.markdown("### 🏆 Historial de Alta Demanda y Uso del Laboratorio")
    col_rk1, col_rank2 = st.columns(2)
    with col_rk1:
        st.markdown("##### 💻 Top 5 Equipos Más Pedidos")
        if not df_rank_equipos.empty:
            st.dataframe(df_rank_equipos, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran movimientos históricos de préstamos de hardware.")
    with col_rank2:
        st.markdown("##### 👥 Top 5 Usuarios con Mayor Uso (Custodios)")
        if not df_rank_usuarios.empty:
            st.dataframe(df_rank_usuarios, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran transacciones de usuarios en el historial.")

    # 🏢 COMPLEMENTO SANEADO: Distribución física final por sala de clases
    st.markdown("---")
    st.markdown("##### 🏛️ Ocupación y Distribución de Hardware por Sala de Clases")
    if not df_eq.empty and 'ubicacion' in df_eq.columns:
        df_eq['Sala'] = df_eq['ubicacion'].apply(lambda x: str(x).split(" - ")[0].strip() if " - " in str(x) else str(x).strip())
        df_rank_salas = df_eq.groupby('Sala').size().reset_index(name='Cantidad de Equipos').sort_values(by='Cantidad de Equipos', ascending=False).reset_index(drop=True)
        
        col_s_rk1, col_s_rk2 = st.columns([0.4, 0.6])
        with col_s_rk1:
            st.dataframe(df_rank_salas.head(5), use_container_width=True, hide_index=True)
        with col_s_rk2:
            fig_salas = px.bar(df_rank_salas.head(5), x='Cantidad de Equipos', y='Sala', orientation='h', title="Top 5 Salas con Hardware", color='Sala')
            st.plotly_chart(fig_salas, use_container_width=True, key="grafico_ranking_salas_master")

# =========================================================================
# 📋 MÓDULO: INVENTARIO DE EQUIPOS
# =========================================================================
elif choice == "Inventario de Equipos":
    st.header("📋 Inventario de Hardware y Activos TI")
    t_eq1, t_eq2, t_eq3, t_eq4 = st.tabs(["➕ Añadir Equipo", "🔄 Modificar Equipo", "❌ Eliminar Equipo", "📋 Listado Completo"])
    
    with obtener_conexion() as conn:
        df_base_ids = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo FROM equipos ORDER BY id_equipo ASC", conn)
        df_salas_sistema = pd.read_sql_query("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC", conn)
        
    lista_equipos_bd = [f"{row['id_equipo']} - {row['tipo']} {row['marca']}" for _, row in df_base_ids.iterrows()]
    lista_salas_combo = df_salas_sistema["nombre_sala"].tolist() if not df_salas_sistema.empty else ["Bodega General TI (Por Defecto)"]

    with t_eq1:
        if st.session_state["rol"] == "Administrador":
            with st.form("nuevo_equipo", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                id_eq = col1.text_input("ID / Código del Equipo (ej: PC-01)")
                tipo_eq = col2.selectbox("Tipo", ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"])
                marca_eq = col3.text_input("Marca")
                
                col4, col5, col6 = st.columns(3)
                mod_eq = col4.text_input("Modelo")
                est_eq = col5.selectbox("Estado Técnico Inicial", ["Operativo", "En Mantenimiento", "De Baja"])
                ub_eq = col6.selectbox("Ubicación en Sala / Casillero:", lista_salas_combo)
                
                col7, col8, col9 = st.columns(3)
                num_doc = col7.text_input("Nro. Factura / Boleta:")
                prov_orig = col8.text_input("Proveedor de Venta:")
                costo_eq = col9.number_input("Costo de Adquisición ($):", min_value=0.0, step=1000.0)
                
                if st.form_submit_button("Guardar Equipo"):
                    if id_eq and num_doc:
                        try:
                            with obtener_conexion() as conn:
                                conn.cursor().execute("INSERT INTO equipos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                            (id_eq.strip(), tipo_eq, marca_eq.strip(), mod_eq.strip(), est_eq, ub_eq, date.today().isoformat(), num_doc.strip(), prov_orig.strip(), costo_eq))
                                conn.commit()
                            st.success(f"✅ ¡Equipo {id_eq} registrado!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⛔ Error: El ID de este equipo ya existe.")
                    else:
                        st.warning("⚠️ ID y Factura son obligatorios.")
        else:
            st.warning("🔒 Acceso exclusivo de Administrador.")

    with t_eq2:
        if st.session_state["rol"] == "Administrador" and lista_equipos_bd:
            eq_a_modificar = st.selectbox("Selecciona el equipo a editar:", lista_equipos_bd, key="sb_mod_eq_main")
            id_mod_real = eq_a_modificar.split(" - ")[0].strip()
            
            with obtener_conexion() as conn:
                datos_act = conn.cursor().execute("SELECT tipo, marca, modelo, ubicacion, num_documento, proveedor_origen FROM equipos WHERE id_equipo = ?", (id_mod_real,)).fetchone()
            
            if datos_act:
                with st.form("form_modificar_equipo"):
                    col_m1, col_m2, col_m3 = st.columns(3)
                    tipo_m = col_m1.selectbox("Cambiar Tipo:", ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"], index=["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"].index(datos_act[0]) if datos_act[0] in ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"] else 0)
                    marca_m = col_m2.text_input("Modificar Marca:", value=datos_act[1])
                    mod_m = col_m3.text_input("Modificar Modelo:", value=datos_act[2])
                    
                    col_m4, col_m5, col_m6 = st.columns(3)
                    ub_m = col_m4.selectbox("Modificar Ubicación/Sala:", lista_salas_combo, index=lista_salas_combo.index(datos_act[3]) if datos_act[3] in lista_salas_combo else 0)
                    doc_m = col_m5.text_input("Modificar Factura:", value=datos_act[4])
                    prov_m = col_m6.text_input("Modificar Proveedor:", value=datos_act[5])
                    
                    if st.form_submit_button("Actualizar Ficha Técnica"):
                        with obtener_conexion() as conn:
                            conn.cursor().execute("UPDATE equipos SET tipo=?, marca=?, modelo=?, ubicacion=?, num_documento=?, proveedor_origen=?, fecha_cambio=? WHERE id_equipo=?", 
                                        (tipo_m, marca_m.strip(), mod_m.strip(), ub_m, doc_m.strip(), prov_m.strip(), date.today().isoformat(), id_mod_real))
                            conn.commit()
                        st.success("Ficha actualizada.")
                        st.rerun()

    with t_eq3:
        if st.session_state["rol"] == "Administrador" and lista_equipos_bd:
            eq_a_eliminar = st.selectbox("Selecciona el equipo a borrar:", lista_equipos_bd, key="sb_del_eq_main")
            id_del_real = eq_a_eliminar.split(" - ")[0].strip()
            if st.button("🚨 Confirmar Eliminación Permanente", key="btn_del_real_eq"):
                with obtener_conexion() as conn:
                    conn.cursor().execute("DELETE FROM equipos WHERE id_equipo = ?", (id_del_real,))
                    conn.commit()
                st.success("Equipo removido.")
                st.rerun()
 # --- PESTAÑA 4: LISTADO GENERAL COMPLETO ---
    with t_eq4:
        st.subheader("📋 Nómina Completa de Hardware en el Establecimiento")
        with obtener_conexion() as conn:
            df_nomina_total = pd.read_sql_query("""
                SELECT id_equipo as 'ID Equipo', 
                       tipo as 'Tipo Hardware', 
                       marca as 'Marca', 
                       modelo as 'Modelo', 
                       estado as 'Estado Técnico', 
                       ubicacion as 'Ubicación / Sala', 
                       num_documento as 'Nro. Docto', 
                       proveedor_origen as 'Proveedor', 
                       costo_compra as 'Costo ($)' 
                FROM equipos 
                ORDER BY id_equipo ASC
            """, conn)
        
        if df_nomina_total is not None and not df_nomina_total.empty:
            df_nomina_total['Costo ($)'] = pd.to_numeric(df_nomina_total['Costo ($)'], errors='coerce').fillna(0)
            
            # 📊 Indicadores Superiores Fijos
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Total de Equipos Inventariados", len(df_nomina_total))
            col_m2.metric("Inversión Global Acumulada", f"${df_nomina_total['Costo ($)'].sum():,.0f} CLP")
            
            # 🔍 BUSCADOR DINÁMICO INTEGRADO
            st.markdown("---")
            st.markdown("#### 🔍 Buscador Dinámico de Hardware")
            buscar_txt = st.text_input("Filtrar rápidamente por ID, Marca o Factura:", key="txt_buscar_inventario_tab4")
            
            # Aplicar filtro en memoria RAM con Pandas si el usuario escribe algo
            if buscar_txt.strip():
                termino = buscar_txt.strip().lower()
                df_filtrado = df_nomina_total[
                    df_nomina_total['ID Equipo'].astype(str).str.lower().str.contains(termino) |
                    df_nomina_total['Marca'].astype(str).str.lower().str.contains(termino) |
                    df_nomina_total['Nro. Docto'].astype(str).str.lower().str.contains(termino)
                ]
                
                if not df_filtrado.empty:
                    st.caption(f"💡 Se encontraron {len(df_filtrado)} coincidencias:")
                    st.dataframe(df_filtrado, use_container_width=True)
                else:
                    st.warning("⚠️ No se encontraron equipos que coincidan con la búsqueda.")
            else:
                # Si el buscador está vacío, muestra la lista completa normal
                st.dataframe(df_nomina_total, use_container_width=True)
            
            st.markdown("---")
            # 📥 Botón para descargar el reporte a Excel
            st.download_button(
                label="📥 Descargar Inventario Completo (Excel)", 
                data=to_excel(df_nomina_total), 
                file_name="inventario_general_escuela.xlsx",
                key="btn_descarga_inventario_completo_excel"
            )
        else:
            st.info("No se registran equipos ingresados en el inventario todavía.")
            
# =========================================================================
# 🛠️ MÓDULO: GESTIÓN DE ESTADOS / BAJAS
# =========================================================================
elif choice == "Gestión de Estados / Bajas":
    st.header("🔄 Hoja de Vida y Control Técnico de Equipos")
    
    # Asegura que exista la tabla de taller en SQLite al entrar al módulo
    with obtener_conexion() as conn:
        conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS historial_mantenimiento (
                id_registro INTEGER PRIMARY KEY AUTOINCREMENT, 
                id_equipo TEXT, 
                fecha_ingreso TEXT, 
                fecha_salida TEXT, 
                detalle_reparacion TEXT, 
                costo_repuestos REAL
            )
        """)
        conn.commit()

    t_st1, t_st2, t_st3 = st.tabs(["⚙️ Cambiar Estado", "🛠️ Historial de Taller", "📋 Hoja de Vida y Costos"])
    
    with obtener_conexion() as conn:
        df_eq_status = pd.read_sql_query("SELECT id_equipo, estado FROM equipos ORDER BY id_equipo ASC", conn)
    lista_ids_equipos = df_eq_status["id_equipo"].tolist() if not df_eq_status.empty else []

    if not lista_ids_equipos:
        st.info("⚠️ No hay equipos registrados en el inventario actual. Ingrese componentes en el Inventario primero.")
    else:
        # --- TAB 1: ACTUALIZAR ESTADO TÉCNICO Y REUBICAR ---
        with t_st1:
            st.subheader("⚙️ Actualizar Estado Operativo de un Activo")
            if st.session_state["rol"] == "Administrador":
                with obtener_conexion() as conn:
                    df_salas_disp = pd.read_sql_query("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC", conn)
                lista_salas_combo = df_salas_disp["nombre_sala"].tolist() if not df_salas_disp.empty else ["Bodega General TI"]

                with st.form("actualizar_estado_form", clear_on_submit=True):
                    id_selec = st.selectbox("Selecciona el ID del Equipo:", lista_ids_equipos, key="sb_status_id_tab1")
                    nuevo_estado = st.selectbox("Nuevo Estado Técnico:", ["Operativo", "En Mantenimiento", "De Baja"])
                    
                    st.markdown("---")
                    st.markdown("##### 🔄 Reubicar Espacio Físico (Opcional)")
                    cambiar_ub = st.checkbox("¿Deseas trasladar este equipo a otra sala?", value=False, key="chk_reubicar_sala")
                    nueva_ub_sala = st.selectbox("Selecciona la nueva Sala de Destino:", lista_salas_combo, disabled=not cambiar_ub, key="sb_reubicar_sala_destino")
                    
                    if st.form_submit_button("Guardar Cambios Técnicos"):
                        hoy_str = date.today().isoformat()
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            if cambiar_ub:
                                cursor.execute("UPDATE equipos SET estado = ?, ubicacion = ?, fecha_cambio = ? WHERE id_equipo = ?", (nuevo_estado, nueva_ub_sala, hoy_str, id_selec))
                            else:
                                cursor.execute("UPDATE equipos SET estado = ?, fecha_cambio = ? WHERE id_equipo = ?", (nuevo_estado, hoy_str, id_selec))
                            conn.commit()
                        st.success(f"✅ ¡Estado del equipo {id_selec} actualizado a '{nuevo_estado}' con éxito!")
                        st.rerun()
            else:
                st.warning("🔒 Permisos insuficientes: El perfil 'Visor' no puede alterar los estados del hardware.")

        # --- TAB 2: REGISTRAR GASTOS DE REPARACIÓN Y TALLER ---
        with t_st2:
            st.subheader("🛠️ Registro de Mantenciones y Gastos de Soporte")
            if st.session_state["rol"] == "Administrador":
                with st.form("gasto_mantenimiento_form", clear_on_submit=True):
                    id_maint = st.selectbox("Selecciona el ID del Equipo Reparado:", lista_ids_equipos, key="sb_status_id_tab2")
                    detalle_rep = st.text_area("Detalle técnico de la reparación / Repuestos comprados:")
                    costo_rep = st.number_input("Costo Real de los Repuestos ($ CLP):", min_value=0.0, step=1000.0, format="%.0f")
                    
                    st.info("💡 Al guardar, el equipo se registrará en la hoja de vida histórica y volverá automáticamente a estado 'Operativo'.")
                    
                    if st.form_submit_button("Registrar Ingreso a Taller"):
                        if detalle_rep.strip():
                            hoy_str = date.today().isoformat()
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "INSERT INTO historial_mantenimiento (id_equipo, fecha_ingreso, fecha_salida, detalle_reparacion, costo_repuestos) VALUES (?, ?, ?, ?, ?)", 
                                    (id_maint, hoy_str, hoy_str, detalle_rep.strip(), costo_rep)
                                )
                                cursor.execute("UPDATE equipos SET estado = 'Operativo', fecha_cambio = ? WHERE id_equipo = ?", (hoy_str, id_maint))
                                conn.commit()
                            st.success(f"✅ ¡Reparación del equipo {id_maint} archivada! El dispositivo vuelve a estar disponible.")
                            st.rerun()
                        else:
                            st.error("Por favor, describe el detalle técnico de la mantención realizada.")
            else:
                st.warning("🔒 Solo un usuario Administrador puede ingresar gastos de mantenimiento.")

        # --- TAB 3: AUDITORÍA DE HOJA DE VIDA Y COSTOS ACUMULADOS ---
        with t_st3:
            st.subheader("📋 Historial Técnico Cruzado y Costo Acumulado")
            id_auditar = st.selectbox("Selecciona un Activo para auditar su Hoja de Vida:", lista_ids_equipos, key="sb_status_id_tab3")
            
            with obtener_conexion() as conn:
                df_h_prestamos = pd.read_sql_query("SELECT usuario as 'Usuario Custodio', rut as 'RUT', fecha_prestamo as 'Fecha Entrega', fecha_devolucion as 'Fecha Retorno', estado_prestamo as 'Estado Préstamo' FROM prestamos WHERE id_equipo = ? ORDER BY id_prestamo DESC", conn, params=(id_auditar,))
                df_h_gastos = pd.read_sql_query("SELECT fecha_ingreso as 'Fecha', detalle_reparacion as 'Detalle de Reparación', costo_repuestos as 'Costo Repuestos ($)' FROM historial_mantenimiento WHERE id_equipo = ? ORDER BY id_registro DESC", conn, params=(id_auditar,))
            
            st.markdown("##### 🤝 Historial de Préstamos y Asignaciones Pasadas")
            if not df_h_prestamos.empty:
                st.dataframe(df_h_prestamos, use_container_width=True)
            else:
                st.caption("Este dispositivo no registra movimientos o préstamos antiguos en la escuela.")
                
            st.markdown("---")
            st.markdown("##### 💰 Registro Financiero de Taller")
            if not df_h_gastos.empty:
                col_g1, col_g2 = st.columns(2)
                total_reparaciones_maquina = df_h_gastos['Costo Repuestos ($)'].sum()
                col_g1.metric("Gasto Acumulado en este Activo", f"${total_reparaciones_maquina:,.0f} CLP")
                col_g2.metric("Cantidad de Entradas a Taller", len(df_h_gastos))
                st.dataframe(df_h_gastos, use_container_width=True)
            else:
                st.caption("Este equipo se encuentra en perfectas condiciones y no registra gastos de mantención.")
# =========================================================================
# 👥 MÓDULO: MANTENEDOR DE USUARIOS
# =========================================================================
elif choice == "Mantenedor de Usuarios":
    st.header("👥 Mantenedor de Usuarios")
    t1, t2, t3, t4 = st.tabs(["➕ Registrar", "🔍 Buscar y Ver Lista", "🔄 Modificar", "❌ Eliminar"])
    
    # --- TAB 1: REGISTRAR USUARIO ---
    with t1:
        with st.form("u_f", clear_on_submit=True):
            u_rut = st.text_input("RUT (Único)")
            u_nom = st.text_input("Nombre Completo")
            u_cor = st.text_input("Correo")
            u_tip = st.selectbox("Tipo", ["Alumno", "Profesor", "Técnico"])
            if st.form_submit_button("Guardar"):
                if u_rut.strip() and u_nom.strip():
                    with obtener_conexion() as conn:
                        try:
                            conn.cursor().execute("INSERT INTO usuarios VALUES (?, ?, ?, ?)", (u_rut.strip(), u_nom.strip(), u_cor.strip(), u_tip))
                            conn.commit()
                            st.success("Usuario registrado con éxito.")
                        except sqlite3.IntegrityError:
                            st.error("El RUT ya existe registrado.")
                else:
                    st.warning("El RUT y el Nombre Completo son obligatorios.")

    # --- TAB 2: BUSCAR Y VER LISTA ---
    with t2:
        st.subheader("🔍 Buscador y Nómina General de Usuarios")
        with obtener_conexion() as conn:
            df_usuarios_all = pd.read_sql_query("SELECT rut as 'RUT', nombre as 'Nombre Completo', correo as 'Correo Electrónico', tipo_usuario as 'Tipo de Usuario' FROM usuarios ORDER BY nombre ASC", conn)
        
        if not df_usuarios_all.empty:
            buscar_u_txt = st.text_input("Filtrar rápidamente por RUT, Nombre o Tipo:", key="txt_buscar_usuario_tab2")
            
            if buscar_u_txt.strip():
                term_u = buscar_u_txt.strip().lower()
                df_u_filtrado = df_usuarios_all[
                    df_usuarios_all['RUT'].astype(str).str.lower().str.contains(term_u) |
                    df_usuarios_all['Nombre Completo'].astype(str).str.lower().str.contains(term_u) |
                    df_usuarios_all['Tipo de Usuario'].astype(str).str.lower().str.contains(term_u)
                ]
                if not df_u_filtrado.empty:
                    st.caption(f"💡 Se encontraron {len(df_u_filtrado)} usuarios:")
                    st.dataframe(df_u_filtrado, use_container_width=True)
                else:
                    st.warning("⚠️ No se encontraron usuarios con ese criterio.")
            else:
                st.dataframe(df_usuarios_all, use_container_width=True)
        else:
            st.info("No hay usuarios registrados en el sistema.")

    # --- TAB 3: MODIFICAR USUARIO ---
    with t3:
        st.subheader("🔄 Actualizar Datos de Usuario")
        if st.session_state["rol"] == "Administrador":
            with obtener_conexion() as conn:
                df_mod_u = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
            
            if not df_mod_u.empty:
                opciones_mod_u = [f"{r['rut']} - {r['nombre']}" for _, r in df_mod_u.iterrows()]
                user_a_modificar = st.selectbox("Selecciona el usuario a editar:", opciones_mod_u, key="sb_user_mod_tab3")
                rut_mod_real = user_a_modificar.split(" - ")[0].strip()
                
                with obtener_conexion() as conn:
                    datos_u_act = conn.cursor().execute("SELECT nombre, correo, tipo_usuario FROM usuarios WHERE rut = ?", (rut_mod_real,)).fetchone()
                
                if datos_u_act:
                    with st.form("form_modificar_usuario_real"):
                        st.caption(f"✍️ Editando al RUT: **{rut_mod_real}**")
                        nuevo_nom_u = st.text_input("Modificar Nombre Completo:", value=datos_u_act[0])
                        nuevo_cor_u = st.text_input("Modificar Correo Electrónico:", value=datos_u_act[1])
                        nuevo_tip_u = st.selectbox("Cambiar Tipo de Usuario:", ["Alumno", "Profesor", "Técnico"], index=["Alumno", "Profesor", "Técnico"].index(datos_u_act[2]) if datos_u_act[2] in ["Alumno", "Profesor", "Técnico"] else 0)
                        
                        if st.form_submit_button("Actualizar Información"):
                            if nuevo_nom_u.strip():
                                with obtener_conexion() as conn:
                                    conn.cursor().execute(
                                        "UPDATE usuarios SET nombre = ?, correo = ?, tipo_usuario = ? WHERE rut = ?",
                                        (nuevo_nom_u.strip(), nuevo_cor_u.strip(), nuevo_tip_u, rut_mod_real)
                                    )
                                    conn.commit()
                                st.success("✅ ¡Datos de usuario actualizados correctamente!")
                                st.rerun()
                            else:
                                st.error("El nombre completo no puede quedar vacío.")
            else:
                st.info("No hay usuarios cargados para modificar.")
        else:
            st.warning("🔒 Permisos insuficientes: Requiere perfil Administrador para modificar datos.")

    # --- TAB 4: ELIMINAR USUARIO ---
    with t4:
        st.subheader("🗑️ Eliminar Usuario del Sistema")
        if st.session_state["rol"] == "Administrador":
            with obtener_conexion() as conn:
                df_del_u = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
            if not df_del_u.empty:
                user_sel = st.selectbox("Usuario a eliminar:", [f"{r['rut']} - {r['nombre']}" for _, r in df_del_u.iterrows()], key="sb_user_del_tab4")
                if st.button("🚨 Eliminar Definitivamente", key="btn_del_user_db"):
                    rut_del = user_sel.split(" - ")[0].strip()
                    with obtener_conexion() as conn:
                        conn.cursor().execute("DELETE FROM usuarios WHERE rut = ?", (rut_del,))
                        conn.commit()
                    st.success("Usuario eliminado de la base de datos.")
                    st.rerun()
            else:
                st.info("No hay usuarios en el sistema.")
        else:
            st.warning("🔒 Permisos insuficientes.")

# =========================================================================
# 🏢 MÓDULO: GESTIÓN DE SALAS
# =========================================================================
elif choice == "Gestión de Salas":
    st.header("🏢 Mantenedor de Salas de Clases y Asignación de Hardware")
    tab_sala1, tab_sala2, tab_sala3 = st.tabs(["➕ Crear Salas", "💻 Asignar Equipos", "📋 Reporte e Historial"])

    # Asegura la existencia de la tabla salas al entrar al módulo
    with obtener_conexion() as conn:
        conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS salas (
                id_sala INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_sala TEXT UNIQUE,
                encargado TEXT,
                capacidad INTEGER
            )
        """)
        conn.commit()

    # Extraer la nómina de funcionarios (Profesores y Técnicos) para los formularios
    with obtener_conexion() as conn:
        df_funcionarios_disp = pd.read_sql_query(
            "SELECT nombre, tipo_usuario FROM usuarios WHERE tipo_usuario IN ('Profesor', 'Técnico') ORDER BY nombre ASC", 
            conn
        )

    # --- TAB 1: CREAR NUEVA SALA ---
    with tab_sala1:
        if st.session_state["rol"] == "Administrador":
            with st.form("nueva_sala_form", clear_on_submit=True):
                st.subheader("Registrar Nueva Sala de Clases")
                col_s1, col_s2, col_s3 = st.columns(3)
                
                n_sala = col_s1.text_input("Nombre de Sala):")
                
                if not df_funcionarios_disp.empty:
                    lista_encargados = [f"{row['nombre']} ({row['tipo_usuario']})" for _, row in df_funcionarios_disp.iterrows()]
                    lista_encargados.insert(0, "Sin Funcionario a Cargo (Temporal)")
                    enc_sala_seleccionado = col_s2.selectbox("👤 Funcionario Responsable:", lista_encargados)
                else:
                    enc_sala_seleccionado = col_s2.selectbox("👤 Funcionario Responsable:", ["⚠️ No hay Profesores/Técnicos creados"], disabled=True)
                
                cap_sala = col_s3.number_input("Capacidad de Alumnos:", min_value=1, value=30, step=1)
                
                if st.form_submit_button("Guardar Sala de Clases"):
                    if n_sala.strip():
                        if enc_sala_seleccionado in ["Sin Funcionario a Cargo (Temporal)", "⚠️ No hay Profesores/Técnicos creados"]:
                            encargado_final = "Por Asignar"
                        else:
                            encargado_final = enc_sala_seleccionado.split(" (")[0].strip()
                        
                        try:
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "INSERT INTO salas (nombre_sala, encargado, capacidad) VALUES (?, ?, ?)", 
                                    (n_sala.strip(), encargado_final, cap_sala)
                                )
                                conn.commit()
                            st.success(f"✅ ¡Sala '{n_sala}' registrada exitosamente!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⛔ Error: Ya existe una sala de clases registrada con ese nombre exacto.")
                    else:
                        st.warning("⚠️ El nombre de la sala de clases es un campo obligatorio.")
        else:
            st.warning("🔒 Permisos insuficientes: Solo un perfil Administrador puede crear nuevas salas.")

    # --- TAB 2: ASIGNAR EQUIPOS A SALA ---
    with tab_sala2:
        with obtener_conexion() as conn:
            df_salas_disp = pd.read_sql_query("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC", conn)
            df_equipos_disp = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, ubicacion FROM equipos WHERE estado != 'De Baja' ORDER BY id_equipo ASC", conn)

        if df_salas_disp.empty:
            st.warning("⚠️ Operación bloqueada: Primero debes registrar una sala de clases en la primera pestaña.")
        elif df_equipos_disp.empty:
            st.info("No se registran dispositivos o artículos libres en el inventario general.")
        else:
            st.subheader("Asignar Ubicación Física de un Equipo a una Sala")
            with st.form("asignar_equipo_sala_form"):
                sala_seleccionada = st.selectbox("1. Selecciona la Sala de Destino:", df_salas_disp["nombre_sala"].tolist())
                lista_equipos_strings = [f"{row['id_equipo']} - {row['tipo']} {row['marca']} (Ubicación Actual: {row['ubicacion']})" for _, row in df_equipos_disp.iterrows()]
                equipo_seleccionado = st.selectbox("2. Selecciona el Equipo a Trasladar:", lista_equipos_strings)
                detalle_ubicacion_especifica = st.text_input("3. Detalle específico de ubicación (ej: Fila 2 - Computador Profesor):")

                if st.form_submit_button("Confirmar Traslado de Espacio"):
                    id_equipo_real = equipo_seleccionado.split(" - ")[0].strip()
                    ubicacion_final = f"{sala_seleccionada} - {detalle_ubicacion_especifica.strip()}" if detalle_ubicacion_especifica.strip() else sala_seleccionada
                    
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE equipos SET ubicacion = ? WHERE id_equipo = ?", (ubicacion_final, id_equipo_real))
                        conn.commit()
                    st.success(f"🚀 ¡El equipo {id_equipo_real} fue reasignado con éxito a: {ubicacion_final}!")
                    st.rerun()

    # --- TAB 3: REPORTES E HISTORIAL POR SALA ---
    with tab_sala3:
        st.subheader("📋 Reporte General y Auditoría de Carga por Sala")
        
        with obtener_conexion() as conn:
            df_salas_completo = pd.read_sql_query(
                "SELECT id_sala as 'ID Sala', nombre_sala as 'Nombre de la Sala', encargado as 'Funcionario Responsable', capacidad as 'Capacidad (Alumnos)' FROM salas ORDER BY nombre_sala ASC", 
                conn
            )
        
        if not df_salas_completo.empty:
            st.metric("Total de Salas Implementadas", len(df_salas_completo))
            st.dataframe(df_salas_completo, use_container_width=True)
            
            st.markdown("---")
            st.markdown("#### 🔍 Consultar Equipamiento Interno Asignado")
            
            lista_para_auditoria = df_salas_completo['Nombre de la Sala'].tolist()
            sala_a_auditar = st.selectbox("Selecciona una Sala para auditar su inventario:", lista_para_auditoria, key="sb_auditoria_interna_salas")
            
            with obtener_conexion() as conn:
                df_resultado_sala = pd.read_sql_query("""
                    SELECT id_equipo as 'ID Equipo', 
                           tipo as 'Tipo Hardware', 
                           marca as 'Marca', 
                           modelo as 'Modelo', 
                           estado as 'Estado Técnico', 
                           ubicacion as 'Ubicación Detallada' 
                    FROM equipos 
                    WHERE ubicacion LIKE ? AND estado != 'De Baja'
                """, conn, params=(f"{sala_a_auditar}%",))
                
            if not df_resultado_sala.empty:
                st.caption(f"💡 Se detectan {len(df_resultado_sala)} dispositivos operativos en este sector:")
                st.dataframe(df_resultado_sala, use_container_width=True)
            else:
                st.info(f"La sala '{sala_a_auditar}' no registra hardware operativo asignado en este momento.")
                
            st.markdown("---")
            st.download_button(
                label="📥 Descargar Reporte de Salas (Excel)", 
                data=to_excel(df_salas_completo), 
                file_name="reporte_salas_escuela.xlsx",
                key="btn_descarga_reporte_salas_excel"
            )
        else:
            st.info("No se registran salas implementadas en la base de datos todavía.")
 
# =========================================================================
# 🤝 MÓDULO: PRÉSTAMO DE EQUIPOS
# =========================================================================

elif choice == "Préstamo de Equipos":
    st.header("🤝 Módulo de Préstamos y Devoluciones")
    tab1, tab2, tab3 = st.tabs(["🆕 Registrar Préstamo", "🔙 Procesar Devolución", "📋 Ver Historial y Estadísticas"])
    
    with obtener_conexion() as conn:
        df_us = pd.read_sql_query("SELECT rut, nombre FROM usuarios", conn)
        df_op = pd.read_sql_query("SELECT id_equipo FROM equipos WHERE estado = 'Operativo'", conn)
        df_ac = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo'", conn)
    df_disponibles = df_op[~df_op["id_equipo"].isin(df_ac["id_equipo"].tolist())]

    with tab1:
        if not df_us.empty and not df_disponibles.empty:
            with st.form("form_p"):
                eq_sel = st.selectbox("Equipo Disponible:", df_disponibles["id_equipo"])
                us_sel = st.selectbox("Usuario:", [f"{r['rut']} | {r['nombre']}" for _, r in df_us.iterrows()])
                f_limite = st.date_input("Fecha Límite")
                if st.form_submit_button("Confirmar Préstamo"):
                    rut_r = us_sel.split(" | ")[0].strip()
                    nom_r = us_sel.split(" | ")[1].strip()
                    with obtener_conexion() as conn:
                        conn.cursor().execute("INSERT INTO prestamos (id_equipo, usuario, rut, fecha_prestamo, fecha_limite, fecha_devolucion, estado_prestamo) VALUES (?,?,?,?,?,'Pendiente','Activo')",
                                    (eq_sel, nom_r, rut_r, date.today().isoformat(), f_limite.isoformat()))
                        conn.commit()
                    st.success("Préstamo Exitoso.")
                    st.rerun()

    with tab2:
        with obtener_conexion() as conn:
            df_act = pd.read_sql_query("SELECT id_prestamo, id_equipo, usuario FROM prestamos WHERE estado_prestamo='Activo'", conn)
        if not df_act.empty:
            p_sel = st.selectbox("Préstamo a devolver:", [f"ID:{r['id_prestamo']} | {r['id_equipo']}" for _, r in df_act.iterrows()])
            if st.button("Procesar Devolución Física"):
                id_p = int(p_sel.split(" | ")[0].split(":")[1])
                with obtener_conexion() as conn:
                    conn.cursor().execute("UPDATE prestamos SET fecha_devolucion=?, estado_prestamo='Devuelto' WHERE id_prestamo=?", (date.today().isoformat(), id_p))
                    conn.commit()
                st.success("Devolución archivada.")
                st.rerun()

    # --- TAB 3: HISTORIAL, BUSCADOR Y ESTADÍSTICAS ---
# --- TAB 3: HISTORIAL, BUSCADOR Y ESTADÍSTICAS ---
    with tab3:
        with obtener_conexion() as conn:
            df_historial_completo = pd.read_sql_query("""
                SELECT id_prestamo as 'ID Mov.', 
                       id_equipo as 'Código Equipo', 
                       usuario as 'Usuario Custodio', 
                       rut as 'RUT', 
                       fecha_prestamo as 'Fecha Entrega', 
                       fecha_limite as 'Fecha Límite', 
                       fecha_devolucion as 'Fecha Retorno', 
                       estado_prestamo as 'Estado Préstamo' 
                FROM prestamos 
                ORDER BY id_prestamo DESC
            """, conn)
            
        # 📊 SECCIÓN 1: ESTADÍSTICAS (EQUIPOS MÁS PRESTADOS)
        st.markdown("#### 🏆 Historial de Equipos Más Prestados")
        if not df_historial_completo.empty:
            # Calcular el ranking agrupando por el código del equipo
            df_ranking = df_historial_completo.groupby('Código Equipo').size().reset_index(name='Total Préstamos')
            df_ranking = df_ranking.sort_values(by='Total Préstamos', ascending=False).head(5).reset_index(drop=True)
            
            col_graph1, col_graph2 = st.columns([0.4, 0.6])
            with col_graph1:
                st.caption("🟢 Top 5 Equipos con Mayor Rotación")
                st.dataframe(df_ranking, use_container_width=True, hide_index=True)
            with col_graph2:
                # Dibujar gráfico de barras horizontal interactivo
                fig_rank_eq = px.bar(
                    df_ranking, 
                    x='Total Préstamos', 
                    y='Código Equipo', 
                    orientation='h',
                    color='Código Equipo',
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                    labels={'Total Préstamos': 'Veces Solicitado', 'Código Equipo': 'Dispositivo'}
                )
                fig_rank_eq.update_layout(showlegend=False, height=180, margin=dict(l=0, r=0, t=10, b=10))
                st.plotly_chart(fig_rank_eq, use_container_width=True, key="grafico_ranking_equipos_prestamos")
        else:
            st.info("No hay transacciones registradas para generar métricas de uso.")
            
        # 🔍 SECCIÓN 2: BUSCADOR CON FILTROS AVANZADOS
        st.markdown("---")
        st.markdown("#### 🔍 Buscador de Movimientos e Historial")
        
        if not df_historial_completo.empty:
            # 🎛️ NUEVOS CONTROLES: Métrica e Interfaz de Filtros en Paralelo
            col_filtro_txt, col_filtro_est, col_met_total = st.columns([0.45, 0.30, 0.25])
            
            with col_filtro_txt:
                buscar_p_txt = st.text_input("Buscar por ID Equipo, RUT o Nombre:", key="txt_buscar_prestamo_tab3")
                
            with col_filtro_est:
                # Menú desplegable para aislar por estado
                estado_seleccionado = st.selectbox("Filtrar por Estado:", ["Todos", "Activo", "Devuelto"], key="sb_filtro_estado_tab3")
            
            # --- Proceso de filtrado combinado en memoria con Pandas ---
            df_resultado = df_historial_completo.copy()
            
            # 1. Filtro por Estado
            if estado_seleccionado != "Todos":
                df_resultado = df_resultado[df_resultado['Estado Préstamo'] == estado_seleccionado]
                
            # 2. Filtro por Texto (si el usuario escribió algo)
            if buscar_p_txt.strip():
                term_p = buscar_p_txt.strip().lower()
                df_resultado = df_resultado[
                    df_resultado['Código Equipo'].astype(str).str.lower().str.contains(term_p) |
                    df_resultado['RUT'].astype(str).str.lower().str.contains(term_p) |
                    df_resultado['Usuario Custodio'].astype(str).str.lower().str.contains(term_p)
                ]
            
            with col_met_total:
                # 📈 MUESTRA EL TOTAL DINÁMICO EN BASE A LO FILTRADO
                st.metric("Total de Préstamos", len(df_resultado))
                
            # Despliegue de la tabla según los filtros aplicados
            if not df_resultado.empty:
                st.dataframe(df_resultado, use_container_width=True)
            else:
                st.warning("⚠️ No se encontraron movimientos que coincidan con los filtros aplicados.")
                
            st.markdown("---")
            # Botón de descarga masiva para auditorías externas de la escuela
            st.download_button(
                label="📥 Descargar Historial de Préstamos (Excel)", 
                data=to_excel(df_historial_completo), 
                file_name="historial_prestamos_escuela.xlsx",
                key="btn_descarga_prestamos_excel"
            )
        else:
            st.info("No se registran préstamos guardados en el sistema todavía.")
# =========================================================================
# 🖨️ MÓDULO: GENERADOR DE QR
# =========================================================================
elif choice == "Generador de QR":
    st.header("🖨️ Generador Avanzado de Etiquetas QR")
    nombre_institucion = st.text_input("🏫 Institución para la Etiqueta:", "LICEO FELIPE CUBILLOS").strip()
    
    with obtener_conexion() as conn:
        df_qr_equipos = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, estado, ubicacion, num_documento, proveedor_origen, costo_compra FROM equipos", conn)
    
    # 📐 1. CONFIGURACIÓN FÍSICA DE LA HOJA
    st.markdown("### ⚙️ Configuración Física de la Hoja de Etiquetas")
    with st.expander("📐 Ajustar Dimensiones de la Plantilla de Impresión", expanded=False):
        col_c1, col_c2, col_c3 = st.columns(3)
        columnas_hoja = col_c1.slider("Columnas por fila en papel adhesivo:", 2, 5, 3, key="cfg_cols_hoja")
        ancho_etiqueta = col_c2.slider("Ancho de cada etiqueta (px):", 120, 300, 180, key="cfg_ancho_et")
        padding_etiqueta = col_c3.slider("Espaciado interno (Padding px):", 5, 25, 10, key="cfg_pad_et")
        
        col_c4, col_c5 = st.columns(2)
        tamano_borde = col_c4.selectbox("Borde para corte:", ["Línea Segmentada", "Línea Continua", "Sin Borde"], key="cfg_borde")
        incluir_bajada = col_c5.checkbox("Incluir texto aclaratorio inferior", value=True, key="cfg_bajada")
        
        estilo_borde_css = "2px dashed #000" if tamano_borde == "Línea Segmentada" else ("1px solid #000" if tamano_borde == "Línea Continua" else "none")

    # 📝 2. SELECTOR DE CONTENIDO INTERNO DEL QR
    st.markdown("---")
    st.markdown("### 📊 Contenido Interno del Código QR")
    with st.expander("📝 Selecciona los datos que se guardarán DENTRO del código al escanear", expanded=True):
        col_d1, col_d2 = st.columns(2)
        inc_id_ref = col_d1.checkbox("ID / Código de Equipo", value=True, key="cfg_int_id_ref")
        inc_tipo = col_d1.checkbox("Tipo de Hardware", value=True, key="cfg_int_tipo")
        inc_marca = col_d1.checkbox("Marca y Modelo", value=True, key="cfg_int_marca")
        
        inc_ubic = col_d2.checkbox("Ubicación / Sala", value=True, key="cfg_int_ubic")
        inc_factura = col_d2.checkbox("Nro. Factura / Boleta", value=False, key="cfg_int_factura")
        inc_costo = col_d2.checkbox("Costo de Compra ($)", value=False, key="cfg_int_costo")

    # 🔍 3. MÉTODOS DE SELECCIÓN Y FILTRADO POR TIPO
    st.markdown("---")
    st.markdown("### 🗂️ Selección de Equipos")
    
    if df_qr_equipos.empty:
        st.warning("⚠️ El inventario está vacío. Registra equipos en 'Inventario de Equipos' primero.")
    else:
        # Filtro maestro por tipo de hardware
        tipos_disp = ["Todos los Tipos"] + sorted(df_qr_equipos["tipo"].unique().tolist())
        tipo_seleccionado = st.selectbox("🔍 Filtrar lista por Tipo de Equipo:", tipos_disp, key="sb_tipo_qr_master")
        df_base_f = df_qr_equipos if tipo_seleccionado == "Todos los Tipos" else df_qr_equipos[df_qr_equipos["tipo"] == tipo_seleccionado]
        
        modo_generacion = st.radio("Método de Generación:", ["Selección Única", "Selección por Grupo / Casillas", "Todo el Tipo de Hardware Seleccionado"], horizontal=True, key="rb_modo_gen_qr")
        df_filtrado_qr = pd.DataFrame()
        
        if modo_generacion == "Selección Única" and not df_base_f.empty:
            lista_opciones_qr = [f"{row['id_equipo']} - {row['tipo']} {row['marca']}" for _, row in df_base_f.iterrows()]
            seleccion_equipo = st.selectbox("Selecciona el Equipo Específico:", lista_opciones_qr, key="sb_eq_unico_qr")
            id_real_qr = seleccion_equipo.split(" - ")[0].strip()
            df_filtrado_qr = df_base_f[df_base_f['id_equipo'] == id_real_qr]
            
        elif modo_generacion == "Selección por Grupo / Casillas" and not df_base_f.empty:
            st.markdown("##### Marque los equipos que desea incorporar al lote:")
            # Grilla compacta de casillas de verificación
            cols_ticket = st.columns(3)
            items_sel = []
            for idx, row in df_base_f.reset_index(drop=True).iterrows():
                with cols_ticket[idx % 3]:
                    if st.checkbox(f"[{row['id_equipo']}] {row['marca']}", value=False, key=f"chk_lote_qr_{row['id_equipo']}_{idx}"):
                        items_sel.append(row['id_equipo'])
            if items_sel:
                df_filtrado_qr = df_base_f[df_base_f['id_equipo'].isin(items_sel)]
            else:
                st.info("💡 Selecciona las casillas de los equipos arriba para armar el grupo.")
                
        elif modo_generacion == "Todo el Tipo de Hardware Seleccionado":
            df_filtrado_qr = df_base_f
            st.success(f"🚀 Modo Masivo Activo: Se procesarán las {len(df_filtrado_qr)} unidades de la categoría '{tipo_seleccionado}'.")

        # 🖼️ 4. CONSTRUCCIÓN DE MATRICES QR EN MEMORIA RAM
        if not df_filtrado_qr.empty:
            lista_bytes_qr = {}
            for idx, datos_fila in df_filtrado_qr.iterrows():
                txt_interno = []
                if inc_id_ref: txt_interno.append(f"ID:{datos_fila['id_equipo']}")
                if inc_tipo: txt_interno.append(f"Tipo:{datos_fila['tipo']}")
                if inc_marca: txt_interno.append(f"Mod:{datos_fila['marca']} {datos_fila['modelo']}")
                if inc_ubic: txt_interno.append(f"Ubic:{datos_fila['ubicacion']}")
                if inc_factura: txt_interno.append(f"Fact:{datos_fila['num_documento']}")
                if inc_costo: txt_interno.append(f"Costo:${datos_fila['costo_compra']:.0f}" if datos_fila['costo_compra'] is not None else "Costo:$0")
                
                # El separador " | " asegura lectura limpia en cualquier lector portátil
                qr_local = segno.make_qr(" | ".join(txt_interno), error='m')
                buffer = io.BytesIO()
                qr_local.save(buffer, kind='png', scale=5, border=2)
                lista_bytes_qr[datos_fila['id_equipo']] = buffer.getvalue()

            # 🛠️ ACCIONES DE DESPARRAMO COLECTIVO Y DESCARGAS (.ZIP)
            st.markdown("---")
            st.markdown("### 📋 Vista Previa y Descargas")
            
            if len(df_filtrado_qr) > 1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for id_eq, bytes_img in lista_bytes_qr.items():
                        zip_file.writestr(f"QR_{id_eq}.png", bytes_img)
                
                st.download_button(
                    label=f"📦 Descargar Lote Completo de QRs ({len(df_filtrado_qr)} unidades) en .ZIP", 
                    data=zip_buffer.getvalue(), 
                    file_name=f"lote_qr_{datetime.now().strftime('%Y%m%d')}.zip", 
                    mime="application/zip", 
                    key="btn_descarga_masiva_zip_qr",
                    use_container_width=True
                )
            
            # Grilla dinámica visual basada en los deslizadores físicos
            columnas_grilla = st.columns(columnas_hoja)
            df_render_final = df_filtrado_qr.reset_index(drop=True)
            
            for idx, datos_fila in df_render_final.iterrows():
                id_actual = datos_fila['id_equipo']
                bytes_raw = lista_bytes_qr[id_actual]
                
                with columnas_grilla[idx % columnas_hoja]:
                    # Contenedor simulador de etiqueta física adhesiva con CSS dinámico
                    st.markdown(f"""
                        <div style="border:{estilo_borde_css}; padding:{padding_etiqueta}px; text-align:center; background-color:#fff; margin-bottom:10px; border-radius:4px;">
                            <p style='text-align:center; font-size:11px; font-weight:bold; margin:0; text-transform:uppercase; color:#000;'>{nombre_institucion}</p>
                            <p style='text-align:center; font-family:monospace; font-size:12px; font-weight:bold; margin:2px 0; color:#000;'>ID: {id_actual}</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.image(bytes_raw, width=ancho_etiqueta - 20 if ancho_etiqueta > 40 else 100)
                    
                    if incluir_bajada:
                        st.markdown(f"<p style='text-align:center; font-size:9px; font-style:italic; margin-top:2px; color:#555;'>{datos_fila['tipo']} - {datos_fila['marca']}</p>", unsafe_allow_html=True)
                    
                    st.download_button(
                        label=f"💾 Guardar {id_actual}", 
                        data=bytes_raw, 
                        file_name=f"QR_{id_actual}.png", 
                        mime="image/png", 
                        key=f"btn_dl_individual_qr_{id_actual}_{idx}",
                        use_container_width=True
                    )
# =========================================================================
# 💾 MÓDULO: RESPALDO DE SEGURIDAD
# =========================================================================
elif choice == "Respaldo de Seguridad":
    st.header("💾 Centro de Copias de Seguridad del Laboratorio")
    st.write("Administra tus respaldos locales, genera descargas directas o restaura estados anteriores del sistema.")
    
    col_resp_left, col_resp_right = st.columns(2)
    
    # --- COLUMNA 1: GENERAR Y DESCARGAR RESPALDOS ---
    with col_resp_left:
        st.subheader("1. Crear y Descargar Copia")
        
        # Entrada de texto para ingresar un nombre personalizado para el respaldo
        sufijo_nombre = st.text_input("Ingresar nombre para el respaldo (Opcional):", placeholder="ej: antes_de_inventario, fin_de_año").strip()
        
        if st.button("🔄 Generar Respaldo Local", key="btn_generar_backup_local_custom", use_container_width=True):
            # Crear la carpeta de respaldos si no existe
            if not os.path.exists("respaldos"): 
                os.makedirs("respaldos")
                
            # Construir el nombre con el formato de fecha u opcionalmente el texto ingresado
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if sufijo_nombre:
                # Limpiar espacios o caracteres extraños del nombre ingresado
                nombre_limpio = sufijo_nombre.lower().replace(" ", "_")
                nombre_archivo_backup = f"respaldos/respaldo_{timestamp}_{nombre_limpio}.db"
            else:
                nombre_archivo_backup = f"respaldos/respaldo_{timestamp}.db"
                
            try:
                shutil.copyfile("laboratorio.db", nombre_archivo_backup)
                st.success(f"✅ ¡Base de datos respaldada con éxito en local como: `{nombre_archivo_backup}`!")
            except Exception as e:
                st.error(f"⛔ Error al copiar el archivo de base de datos: {e}")
                
        st.markdown("---")
        st.write("📥 **Descarga Directa:** Guarda una copia inmediata del archivo SQLite actual en tu computadora.")
        
        datos_db = obtener_bytes_db()
        if datos_db is not None:
            st.download_button(
                label="📥 Descargar archivo laboratorio.db",
                data=datos_db,
                file_name=f"respaldo_laboratorio_{datetime.now().strftime('%Y%m%d')}.db",
                mime="application/x-sqlite3",
                key="btn_descarga_directa_db_file",
                use_container_width=True
            )
        else:
            st.warning("⚠️ No se pudo extraer la base de datos para descarga.")

    # --- COLUMNA 2: RESTAURACIÓN DE LA BASE DE DATOs ---
    with col_resp_right:
        st.subheader("2. Restauración del Sistema")
        st.write("Sube un archivo `.db` previamente respaldado para actualizar el sistema a un estado anterior.")
        
        if st.session_state["rol"] == "Administrador":
            # Selector e importador de archivos nativo de Streamlit
            archivo_subido = st.file_uploader(
                "Selecciona tu archivo de respaldo (.db)", 
                type=["db"],
                key="uploader_restaurador_db_master"
            )
            
            if archivo_subido is not None:
                st.warning("⚠️ ¡Atención! Aplicar una restauración sobrescribirá todos los datos actuales del laboratorio por los del archivo subido. Esta acción no se puede deshacer.")
                
                if st.button("🔄 Aplicar y Actualizar Base de Datos", type="primary", key="btn_ejecutar_restauracion_db", use_container_width=True):
                    try:
                        bytes_subidos = archivo_subido.read()
                        # Llama a tu función de base de datos para escribir los bytes en el archivo local
                        restaurar_db_desde_bytes(bytes_subidos)
                        # Re-inicializa las tablas para asegurar consistencia estructural
                        inicializar_db()
                        st.success("✅ ¡Base de datos restaurada con éxito! El sistema se ha actualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"⛔ Error durante el proceso de restauración: {e}")
        else:
            st.warning("🔒 Permisos insuficientes: Solo un perfil con rol de Administrador puede realizar restauraciones en la base de datos.")

# =========================================================================
# 📝 MÓDULO: BITÁCORA DE NOTAS (PARTE 1 DE 2)
# =========================================================================
elif choice == "Bitácora de Notas":
    st.header("📝 Bitácora de Novedades Diarias del Laboratorio")
    
    # 🛡️ PARCHE AUTO-ACTUALIZADOR: Asegura que la BD tenga las columnas necesarias para la planificación
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        columnas_nuevas = [
            ("estado_nota", "TEXT DEFAULT 'Pendiente'"), 
            ("fecha_ejecucion", "TEXT DEFAULT 'N/A'"),
            ("fecha_vencimiento", "TEXT DEFAULT 'N/A'")
        ]
        for col_name, col_type in columnas_nuevas:
            try:
                cursor.execute(f"ALTER TABLE bitacora ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass
        conn.commit()

    # 🚨 BANDA DE ALERTAS CRÍTICAS: Tareas demoradas con despacho de email
    hoy_str = date.today().isoformat()
    query_alertas_bit = """
        SELECT id_nota, nota, fecha_vencimiento 
        FROM bitacora 
        WHERE estado_nota = 'Pendiente' AND fecha_vencimiento != 'N/A' AND fecha_vencimiento < ?
    """
    with obtener_conexion() as conn:
        df_retrasos_bit = pd.read_sql_query(query_alertas_bit, conn, params=(hoy_str,))

    if not df_retrasos_bit.empty:
        st.error(f"⚠️ **AVISO DE DEMORA:** Se han detectado **{len(df_retrasos_bit)} tareas pendientes** que superaron su fecha máxima de ejecución.")
        
        with obtener_conexion() as conn:
            df_encargados_mail = pd.read_sql_query("SELECT nombre, correo FROM usuarios WHERE tipo_usuario IN ('Profesor', 'Técnico')", conn)
            
        for idx, fila_retraso in df_retrasos_bit.iterrows():
            try:
                f_venc = date.fromisoformat(fila_retraso['fecha_vencimiento'])
                dias_atraso = (date.today() - f_venc).days
            except:
                dias_atraso = 1
            
            col_txt_b, col_sel_b, col_btn_b = st.columns([0.45, 0.35, 0.20])
            with col_txt_b:
                st.markdown(f"🔴 **[ID {fila_retraso['id_nota']}] - {dias_atraso} días demorada:** {fila_retraso['nota'][:40]}...")
            
            with col_sel_b:
                if not df_encargados_mail.empty:
                    lista_u_notif = [f"{r['nombre']} | {r['correo']}" for _, r in df_encargados_mail.iterrows()]
                    usuario_a_notificar = st.selectbox("Notificar a:", lista_u_notif, key=f"sb_notif_bit_user_{fila_retraso['id_nota']}_{idx}")
                else:
                    usuario_a_notificar = None
                    st.caption("Sin usuarios creados")
                    
            with col_btn_b:
                if st.button("✉️ Enviar Alerta", key=f"btn_send_mail_bit_{fila_retraso['id_nota']}_{idx}", disabled=(usuario_a_notificar is None), use_container_width=True):
                    with st.spinner("Enviando..."):
                        partes_usuario = usuario_a_notificar.split(" | ")
                        u_nombre = partes_usuario[0].strip()
                        u_correo = partes_usuario[1].strip()
                        
                        if "BREVO_API_KEY" in st.secrets:
                            headers_api = {
                                "accept": "application/json",
                                "api-key": st.secrets["BREVO_API_KEY"],
                                "content-type": "application/json"
                            }
                            
                            asunto_api = f"🚨 ALERTA: Tarea Demorada ID {fila_retraso['id_nota']} en el Laboratorio"
                            
                            payload_api = {
                                "sender": {"name": "Sistema Laboratorio", "email": "no-reply@escuelafelipecubillos.cl"},
                                "to": [{"email": u_correo, "name": u_nombre}],
                                "subject": asunto_api,
                                "htmlContent": f"<html><body><h2>Bitácora Felipe Cubillos</h2><p>Hola {u_nombre}, se solicita la ejecución de la siguiente tarea demorada por {dias_atraso} días:<br><br><b>Tarea ID {fila_retraso['id_nota']}:</b> {fila_retraso['nota']}<br><b>Fecha Máxima Planificada:</b> {fila_retraso['fecha_vencimiento']}</p></body></html>"
                            }
                            
                            try:
                                res = requests.post("https://brevo.com", json=payload_api, headers=headers_api)
                                if res.status_code == 200 or res.status_code == 201:
                                    st.toast(f"¡Aviso enviado a {u_nombre}!", icon="✅")
                                else:
                                    st.error(f"Brevo rechazó el envío (Código: {res.status_code}).")
                            except Exception as e_api:
                                st.error(f"Error de conexión al enviar: {e_api}")
                        else:
                            st.error("Falta configurar la API Key de Brevo en los secretos.")
        st.markdown("---")
    # 📑 Estructuración de Pestañas (Parte 2)
    t_bit1, t_bit2, t_bit3 = st.tabs(["➕ Añadir Nota", "🔄 Modificar Nota / Estado", "📋 Ver Listado Completo"])
    
    # --- TAB 1: AÑADIR NUEVA NOTA CON FECHA MÁXIMA ---
    with t_bit1:
        with st.form("nueva_nota_form", clear_on_submit=True):
            texto_nota = st.text_area("Escribe la novedad o tarea detectada hoy:")
            
            col_add1, col_add2, col_add3 = st.columns(3)
            f_registro = col_add1.date_input("Fecha de Registro:", date.today())
            f_vencimiento = col_add2.date_input("Fecha Máxima de Ejecución:", date.today() + pd.Timedelta(days=2))
            est_inicial = col_add3.selectbox("Estado Inicial:", ["Pendiente", "Ejecutada"])
            
            f_ej_inicial = f_registro.isoformat() if est_inicial == "Ejecutada" else "N/A"
                
            if st.form_submit_button("Guardar Nota en Bitácora"):
                if texto_nota.strip():
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO bitacora (nota, fecha, hora, estado_nota, fecha_ejecucion, fecha_vencimiento) VALUES (?, ?, ?, ?, ?, ?)", 
                            (texto_nota.strip(), f_registro.isoformat(), datetime.now().strftime("%H:%M:%S"), est_inicial, f_ej_inicial, f_vencimiento.isoformat())
                        )
                        conn.commit()
                    st.success("✅ Nota y planificación almacenadas exitosamente.")
                    st.rerun()
                else:
                    st.warning("⚠️ No puedes guardar una nota vacía.")

    # --- TAB 2: MODIFICAR TEXTO Y ESTADO DE UNA NOTA ---
    with t_bit2:
        st.subheader("🔄 Modificar Detalles y Estado de Tareas")
        with obtener_conexion() as conn:
            df_notas_disp = pd.read_sql_query("SELECT id_nota, fecha, nota, estado_nota, fecha_ejecucion, fecha_vencimiento FROM bitacora ORDER BY id_nota DESC LIMIT 30", conn)
        
        if df_notas_disp.empty:
            st.info("No hay novedades registradas para modificar.")
        else:
            opciones_notas = [f"ID:{row['id_nota']} | Est: {row['estado_nota']} | {row['nota'][:30]}..." for _, row in df_notas_disp.iterrows()]
            nota_a_modificar = st.selectbox("Selecciona la nota que deseas editar o resolver:", opciones_notas, key="sb_mod_nota_real")
            
            id_nota_mod = int(nota_a_modificar.split(" | ")[0].split(":")[1])
            registro_fila = df_notas_disp[df_notas_disp['id_nota'] == id_nota_mod].iloc[0]
            
            with st.form("form_modificar_nota_real"):
                st.caption(f"📝 Editando nota ID: {id_nota_mod} (Creada el {registro_fila['fecha']})")
                nuevo_texto_nota = st.text_area("Corregir texto de la novedad:", value=str(registro_fila['nota']))
                
                col_mod1, col_mod2, col_mod3 = st.columns(3)
                
                try: 
                    val_venc_def = date.fromisoformat(str(registro_fila['fecha_vencimiento']))
                except: 
                    val_venc_def = date.today()
                
                nuevo_vencimiento = col_mod1.date_input("Modificar fecha máxima:", val_venc_def)
                nuevo_estado = col_mod2.selectbox("Cambiar Estado:", ["Pendiente", "Ejecutada"], index=["Pendiente", "Ejecutada"].index(str(registro_fila['estado_nota'])) if str(registro_fila['estado_nota']) in ["Pendiente", "Ejecutada"] else 0)
                
                if nuevo_estado == "Ejecutada":
                    try: 
                        val_fecha_def = date.fromisoformat(str(registro_fila['fecha_ejecucion']))
                    except: 
                        val_fecha_def = date.today()
                    f_ejecucion_final = str(col_mod3.date_input("Fecha de Resolución Real:", val_fecha_def))
                else:
                    f_ejecucion_final = "N/A"
                    col_mod3.info("⏳ Nota guardada como Pendiente.")
                
                if st.form_submit_button("Actualizar y Guardar Cambios"):
                    if nuevo_texto_nota.strip():
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE bitacora SET nota = ?, estado_nota = ?, fecha_ejecucion = ?, fecha_vencimiento = ? WHERE id_nota = ?",
                                (nuevo_texto_nota.strip(), nuevo_estado, f_ejecucion_final, nuevo_vencimiento.isoformat(), id_nota_mod)
                            )
                            conn.commit()
                        st.success("✅ Cambios y estados guardados correctamente.")
                        st.rerun()
                    else:
                        st.error("El texto de la nota no puede quedar vacío.")

    # --- TAB 3: VER LISTADO COMPLETO ---
    with t_bit3:
        st.subheader("📋 Historial de Notas Planificadas")
        with obtener_conexion() as conn:
            df_lista_bitacora = pd.read_sql_query("""
                SELECT id_nota as 'ID', 
                       fecha as 'Fecha Registro', 
                       nota as 'Descripción / Tarea', 
                       estado_nota as 'Estado', 
                       fecha_vencimiento as 'Fecha Máxima', 
                       fecha_ejecucion as 'Fecha Resolución Real' 
                FROM bitacora 
                ORDER BY id_nota DESC
            """, conn)
        if not df_lista_bitacora.empty:
            st.dataframe(df_lista_bitacora, use_container_width=True)
        else:
            st.info("No se registran notas guardadas en la bitácora todavía.")
