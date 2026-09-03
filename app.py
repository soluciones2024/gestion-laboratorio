import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io
import os
import shutil
# --- PANTALLA DE INICIO DE SESIÓN SEGURA ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("### 🔒 Acceso Restringido")
    password_input = st.text_input("Introduce la contraseña del Laboratorio:", type="password")
    if st.button("Iniciar Sesión"):
        if password_input == st.secrets["general"]["PASSWORD"]:
            st.session_state["authenticated"] = True
            st.success("Acceso concedido.")
            st.rerun()
        else:
            st.error("Contraseña incorrecta. Inténtalo de nuevo.")
    st.stop()
st.set_page_config(page_title="Gestión de Laboratorio Pro", layout="wide")

CONN = sqlite3.connect("laboratorio.db", check_same_thread=False)
CURSOR = CONN.cursor()

# Creación de tablas del sistema
CONN.commit()

CURSOR.execute("CREATE TABLE IF NOT EXISTS equipos (id_equipo TEXT PRIMARY KEY, tipo TEXT, marca TEXT, modelo TEXT, estado TEXT, ubicacion TEXT, fecha_cambio TEXT)")
CURSOR.execute("CREATE TABLE IF NOT EXISTS compras (id_compra INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, cantidad INTEGER, costo_unitario REAL, proveedor TEXT, fecha TEXT)")
CURSOR.execute("CREATE TABLE IF NOT EXISTS prestamos (id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT, id_equipo TEXT, usuario TEXT, rut TEXT, fecha_prestamo TEXT, fecha_limite TEXT, fecha_devolucion TEXT, estado_prestamo TEXT, observaciones TEXT)")
CURSOR.execute("CREATE TABLE IF NOT EXISTS infraestructura (id_item INTEGER PRIMARY KEY AUTOINCREMENT, elemento TEXT, ubicacion TEXT, estado TEXT, observaciones TEXT)")
CONN.commit()
# --- RESPALDO AUTOMÁTICO E INVISIBLE AL ENCENDER ---
try:
    carpeta_auto = "C:/respaldos_laboratorio/automaticos"
    if not os.path.exists(carpeta_auto):
        os.makedirs(carpeta_auto)
    # Guarda una copia fija diaria para no llenar el disco de archivos por cada clic
    nombre_auto = f"respaldo_auto_{datetime.now().strftime('%Y%m%d')}.db"
    ruta_auto = os.path.join(carpeta_auto, nombre_auto)
    if not os.path.exists(ruta_auto):
        shutil.copyfile("laboratorio.db", ruta_auto)
except Exception:
    pass # Si falla por permisos, la app sigue corriendo normalmente


def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

st.title("🖥️ Sistema de Gestión de Laboratorio de Computación Escuela Felipe Cubillos 2026")
menu = ["Inventario de Equipos", "Gestión de Estados / Bajas", "Préstamo de Equipos", "Infraestructura de Sala", "Registro de Compras", "Respaldo de Seguridad", "Bitácora de Notas", "Panel de Control"]
choice = st.sidebar.selectbox("Navegación", menu)
if choice == "Inventario de Equipos":
    st.header("📋 Inventario de Hardware")
    with st.form("nuevo_equipo", clear_on_submit=True):
        st.subheader("Añadir Nuevo Equipo")
        col1, col2, col3 = st.columns(3)
        id_eq = col1.text_input("ID / Código del Equipo (ej: PC-01)")
        tipo_eq = col2.selectbox("Tipo", ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"])
        marca_eq = col3.text_input("Marca")
        col4, col5, col6 = st.columns(3)
        mod_eq = col4.text_input("Modelo")
        est_eq = col5.selectbox("Estado", ["Operativo", "En Mantenimiento", "De Baja"])
        ub_eq = col6.text_input("Ubicación (ej: Fila 1 - Puesto 3)")
        if st.form_submit_button("Guardar Equipo"):
            if id_eq:
                try:
                    hoy = str(date.today())
                    CURSOR.execute("INSERT INTO equipos VALUES (?, ?, ?, ?, ?, ?, ?)", (id_eq, tipo_eq, marca_eq, mod_eq, est_eq, ub_eq, hoy))
                    CONN.commit()
                    st.success(f"Equipo {id_eq} registrado con éxito.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("El ID de este equipo ya existe.")
            else:
                st.warning("El ID del equipo es obligatorio.")
    df_equipos = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, estado, ubicacion FROM equipos", CONN)
    st.dataframe(df_equipos, use_container_width=True)
    if not df_equipos.empty:
        st.download_button("📥 Exportar Inventario a Excel", to_excel(df_equipos), "inventario.xlsx")

elif choice == "Gestión de Estados / Bajas":
    st.header("🔄 Actualizar Estado o Dar de Baja Equipos")
    df_equipos = pd.read_sql_query("SELECT id_equipo, tipo, marca, estado FROM equipos", CONN)
    if df_equipos.empty:
        st.info("No hay equipos registrados para modificar.")
    else:
        lista_ids = df_equipos["id_equipo"].tolist()
        with st.form("actualizar_estado"):
            id_selec = st.selectbox("Selecciona el ID del Equipo", lista_ids)
            nuevo_estado = st.selectbox("Nuevo Estado", ["Operativo", "En Mantenimiento", "De Baja"])
            nueva_ub = st.text_input("Actualizar Ubicación (Opcional)")
            if st.form_submit_button("Actualizar Equipo"):
                hoy = str(date.today())
                if nueva_ub.strip() != "":
                    CURSOR.execute("UPDATE equipos SET estado = ?, ubicacion = ?, fecha_cambio = ? WHERE id_equipo = ?", (nuevo_estado, nueva_ub, hoy, id_selec))
                else:
                    CURSOR.execute("UPDATE equipos SET estado = ?, fecha_cambio = ? WHERE id_equipo = ?", (nuevo_estado, hoy, id_selec))
                CONN.commit()
                st.success(f"Equipo {id_selec} actualizado.")
                st.rerun()

elif choice == "Préstamo de Equipos":
    st.header("🤝 Módulo de Préstamos y Devoluciones")
    tab1, tab2 = st.tabs(["🆕 Registrar Préstamo", "🔙 Procesar Devolución"])
    with tab1:
        df_operativos = pd.read_sql_query("SELECT id_equipo, tipo, marca FROM equipos WHERE estado = 'Operativo'", CONN)
        df_activos = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo'", CONN)
        prestados_ids = df_activos["id_equipo"].tolist()
        df_disponibles = df_operativos[~df_operativos["id_equipo"].isin(prestados_ids)]
        if df_disponibles.empty:
            st.warning("No hay equipos operativos disponibles.")
        else:
            with st.form("form_prestamo", clear_on_submit=True):
                lista_disp = [f"{row['id_equipo']} - {row['tipo']} ({row['marca']})" for _, row in df_disponibles.iterrows()]
                equipo_selec = st.selectbox("Selecciona el Equipo a Prestar", lista_disp)
                col_u1, col_u2 = st.columns(2)
                usuario_p = col_u1.text_input("Nombre Completo del Usuario")
                rut_p = col_u2.text_input("RUT / Documento de Identidad")
                col_f1, col_f2 = st.columns(2)
                fecha_p = col_f1.date_input("Fecha de Entrega", date.today())
                fecha_l = col_f2.date_input("Fecha Máxima de Devolución", date.today())
                obs_p = st.text_input("Observaciones de Entrega")
                if st.form_submit_button("Confirmar Préstamo"):
                    rut_limpio = rut_p.strip()
                    if usuario_p.strip() != "" and rut_limpio != "":
                        c_check = CONN.cursor()
                        c_check.execute("SELECT COUNT(*) FROM prestamos WHERE rut = ? AND estado_prestamo = 'Activo'", (rut_limpio,))
                        cuenta = c_check.fetchone()[0]
                        if cuenta > 0:
                            st.error(f"⛔ Bloqueado: El usuario con RUT {rut_limpio} ya tiene un equipo actualmente.")
                        else:
                            id_real = equipo_selec.split(" - ")[0]
                            CURSOR.execute("INSERT INTO prestamos (id_equipo, usuario, rut, fecha_prestamo, fecha_limite, fecha_devolucion, estado_prestamo, observaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (id_real, usuario_p, rut_limpio, str(fecha_p), str(fecha_l), "Pendiente", "Activo", obs_p))
                            CONN.commit()
                            st.success("Préstamo registrado con éxito.")
                            st.rerun()
                    else:
                        st.warning("Nombre y RUT son obligatorios.")
    with tab2:
        df_prestados = pd.read_sql_query("SELECT id_prestamo, id_equipo, usuario, rut, fecha_prestamo, fecha_limite, observaciones FROM prestamos WHERE estado_prestamo = 'Activo'", CONN)
        if df_prestados.empty:
            st.info("No hay préstamos activos.")
        else:
            st.dataframe(df_prestados, use_container_width=True)
            with st.form("form_devolucion"):
                lista_prestamos = [f"ID:{row['id_prestamo']} | {row['id_equipo']} de {row['usuario']}" for _, row in df_prestados.iterrows()]
                prestamo_selec = st.selectbox("Selecciona el préstamo a finalizar", lista_prestamos)
                fecha_d = st.date_input("Fecha de Devolución", date.today())
                if st.form_submit_button("Registrar Devolución"):
                    id_prestamo_real = int(prestamo_selec.split(" | ")[0].split(":")[1])
                    CURSOR.execute("UPDATE prestamos SET fecha_devolucion = ?, estado_prestamo = 'Devuelto' WHERE id_prestamo = ?", (str(fecha_d), id_prestamo_real))
                    CONN.commit()
                    st.success("Devolución registrada exitosamente.")
                    st.rerun()
    st.markdown("---")
    st.subheader("📜 Historial Completo de Préstamos")
    busqueda_rut = st.text_input("🔍 Buscar por RUT / Documento:")
    if busqueda_rut.strip() != "":
        df_todos_prestamos = pd.read_sql_query(f"SELECT * FROM prestamos WHERE rut LIKE '%{busqueda_rut.strip()}%'", CONN)
    else:
        df_todos_prestamos = pd.read_sql_query("SELECT * FROM prestamos", CONN)
    st.dataframe(df_todos_prestamos, use_container_width=True)

elif choice == "Infraestructura de Sala":
    st.header("🔌 Estado de Infraestructura de la Sala")
    with st.form("nueva_infra", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        elem = col1.text_input("Elemento (ej: Enchufe Fila 2, Proyector Central, Ampolleta Norte)")
        ubic = col2.text_input("Ubicación exacta")
        est_inf = col3.selectbox("Estado actual", ["Bueno", "Regular", "Malogrado"])
        obs_inf = st.text_input("Observaciones técnicas")
        if st.form_submit_button("Registrar Elemento"):
            if elem:
                CURSOR.execute("INSERT INTO infraestructura (elemento, ubicacion, estado, observaciones) VALUES (?, ?, ?, ?)", (elem, ubic, est_inf, obs_inf))
                CONN.commit()
                st.success("Elemento registrado correctamente.")
                st.rerun()
    df_infra = pd.read_sql_query("SELECT * FROM infraestructura", CONN)
    st.dataframe(df_infra, use_container_width=True)

elif choice == "Registro de Compras":
    st.header("💰 Historial de Compras")
    with st.form("nueva_compra", clear_on_submit=True):
        item_c = st.text_input("Artículo / Insumo")
        cant_c = st.number_input("Cantidad", min_value=1, step=1)
        costo_c = st.number_input("Costo Unitario ($)", min_value=0.0)
        prov_c = st.text_input("Proveedor")
        fecha_c = st.date_input("Fecha", date.today())
        if st.form_submit_button("Registrar Compra"):
            if item_c:
                CURSOR.execute("INSERT INTO compras (item, cantidad, costo_unitario, proveedor, fecha) VALUES (?, ?, ?, ?, ?)", (item_c, cant_c, costo_c, prov_c, str(fecha_c)))
                CONN.commit()
                st.success("Compra registrada.")
                st.rerun()
    df_compras = pd.read_sql_query("SELECT * FROM compras", CONN)
    if not df_compras.empty:
        df_compras["Costo Total"] = df_compras["cantidad"] * df_compras["costo_unitario"]
    st.dataframe(df_compras, use_container_width=True)
    # --- GRÁFICO DE GASTOS MENSUALES ---
    if not df_compras.empty:
        st.markdown("---")
        st.subheader("📊 Análisis de Gastos por Mes")
        
        import plotly.express as px
        # Convertir la columna de fecha a formato datetime y extraer el Año-Mes (ej: 2026-09)
        df_compras['fecha_dt'] = pd.to_datetime(df_compras['fecha'])
        df_compras['Mes'] = df_compras['fecha_dt'].dt.to_period('M').astype(str)
        
        # Agrupar y sumar el costo total invertido por cada mes
        df_gastos_mes = df_compras.groupby('Mes')['Costo Total'].sum().reset_index()
        df_gastos_mes = df_gastos_mes.sort_values(by='Mes')
        
        # Crear gráfico de barras moderno para los costos de adquisición
        fig_gastos = px.bar(df_gastos_mes, x='Mes', y='Costo Total',
                            labels={'Mes': 'Mes de Adquisición', 'Costo Total': 'Inversión Total ($)'},
                            title="Inversión Mensual en Insumos y Equipamiento",
                            color_discrete_sequence=['#3498db'])
        fig_gastos.update_layout(height=350, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_gastos, use_container_width=True)

elif choice == "Infraestructura de Sala":
    st.header("🔌 Estado de Infraestructura de la Sala")
    
    with st.form("nueva_infra", clear_on_submit=True):
        st.subheader("Registrar Reporte de Infraestructura")
        col1, col2, col3 = st.columns(3)
        elem = col1.text_input("Elemento (ej: Enchufe Fila 2, Proyector Central, Luminaria Norte)")
        ubic = col2.text_input("Ubicación exacta dentro del laboratorio")
        est_inf = col3.selectbox("Estado actual", ["Bueno", "Regular", "Malogrado"])
        obs_inf = st.text_input("Observaciones técnicas / Detalles de la falla")
        
        if st.form_submit_button("Registrar Elemento"):
            if elem:
                CURSOR.execute("INSERT INTO infraestructura (elemento, ubicacion, estado, observaciones) VALUES (?, ?, ?, ?)", 
                               (elem, ubic, est_inf, obs_inf))
                CONN.commit()
                st.success(f"Reporte de '{elem}' registrado correctamente.")
                st.rerun()
            else:
                st.warning("El nombre del elemento es obligatorio.")
                
    st.subheader("📋 Estado Actual de la Sala")
    df_infra = pd.read_sql_query("SELECT * FROM infraestructura", CONN)
    st.dataframe(df_infra, use_container_width=True)

elif choice == "Respaldo de Seguridad":
    st.header("💾 Copias de Seguridad del Sistema")
    st.write("Presiona el botón de abajo para resguardar toda tu base de datos local.")
    if st.button("🔄 Generar Copia de Seguridad"):
        carpeta_backup = "C:/respaldos_laboratorio"
        if not os.path.exists(carpeta_backup):
            os.makedirs(carpeta_backup)
        nombre_archivo = f"respaldo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        ruta_destino = os.path.join(carpeta_backup, nombre_archivo)
        shutil.copyfile("laboratorio.db", ruta_destino)
        st.success(f"¡Respaldo creado con éxito! Guardado en: `{ruta_destino}`")

elif choice == "Panel de Control":
    st.header("📊 Resumen General del Laboratorio")
    df_eq = pd.read_sql_query("SELECT * FROM equipos", CONN)
    df_co = pd.read_sql_query("SELECT * FROM compras", CONN)
    df_pr = pd.read_sql_query("SELECT * FROM prestamos WHERE estado_prestamo = 'Activo'", CONN)
    df_todos_pr = pd.read_sql_query("SELECT * FROM prestamos", CONN)
    
    if not df_eq.empty:
        df_mantenimiento = df_eq[df_eq['estado'] == 'En Mantenimiento'].copy()
        if not df_mantenimiento.empty:
            df_mantenimiento['dias'] = (pd.to_datetime(str(date.today())) - pd.to_datetime(df_mantenimiento['fecha_cambio'])).dt.days
            df_criticos = df_mantenimiento[df_mantenimiento['dias'] > 30]
            if not df_criticos.empty:
                st.error(f"🚨 ALERTA: Hay {len(df_criticos)} equipos estancados en mantenimiento por más de 30 días:")
                for _, equipo in df_criticos.iterrows():
                    st.markdown(f"* El equipo **{equipo['id_equipo']}** ({equipo['tipo']}) lleva **{equipo['dias']} días** en reparación.")
                st.markdown("---")
                
    if not df_todos_pr.empty:
        df_todos_pr['fecha_limite_dt'] = pd.to_datetime(df_todos_pr['fecha_limite'])
        df_todos_pr['fecha_devolucion_dt'] = pd.to_datetime(df_todos_pr['fecha_devolucion'], errors='coerce')
        cond_devuelto_tarde = (df_todos_pr['estado_prestamo'] == 'Devuelto') & (df_todos_pr['fecha_devolucion_dt'] > df_todos_pr['fecha_limite_dt'])
        cond_act_vencido = (df_todos_pr['estado_prestamo'] == 'Activo') & (df_todos_pr['fecha_limite_dt'] < pd.to_datetime(str(date.today())))
        df_atrasos = df_todos_pr[cond_devuelto_tarde | cond_act_vencido]
        if not df_atrasos.empty:
            st.subheader("⚠️ Registro Histórico de Retrasos por Usuario")
            df_ranking = df_atrasos.groupby(['usuario', 'rut']).size().reset_index(name='Cantidad de Atrasos')
            df_ranking = df_ranking.sort_values(by='Cantidad de Atrasos', ascending=False)
            st.dataframe(df_ranking, use_container_width=True)
            st.markdown("---")
    # Sistema de Alertas por color para Mantenimiento Crítico (>30 días)
    if not df_eq.empty:
        df_mantenimiento = df_eq[df_eq['estado'] == 'En Mantenimiento'].copy()
        if not df_mantenimiento.empty:
            # Calcular cuántos días lleva el equipo en ese estado respecto a hoy
            df_mantenimiento['dias'] = (pd.to_datetime(str(date.today())) - pd.to_datetime(df_mantenimiento['fecha_cambio'])).dt.days
            df_criticos = df_mantenimiento[df_mantenimiento['dias'] > 30]
            
            # Si hay equipos retrasados, lanzar un cuadro de alerta rojo
            if not df_criticos.empty:
                st.error(f"🚨 ALERTA CRÍTICA: Se detectaron {len(df_criticos)} equipos estancados en mantenimiento por más de 30 días:")
                for _, equipo in df_criticos.iterrows():
                    st.markdown(f"* El equipo **{equipo['id_equipo']}** ({equipo['tipo']}) lleva acumulados **{equipo['dias']} días** en servicio técnico.")
                st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Equipos", len(df_eq))
    col2.metric("Operativos", len(df_eq[df_eq["estado"] == "Operativo"]) if not df_eq.empty else 0)
    col3.metric("En Mantención", len(df_eq[df_eq["estado"] == "En Mantenimiento"]) if not df_eq.empty else 0)
    col4.metric("Préstamos Activos", len(df_pr))
    # --- SECCIÓN DE GRÁFICOS INTERACTIVOS ---
    st.markdown("---")
    st.subheader("📈 Estadísticas Visuales del Laboratorio")
    
    import plotly.express as px
    
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.markdown("##### Distribución de Equipos por Estado")
        if not df_eq.empty:
            # Agrupar datos por estado para el gráfico de torta
            df_pie = df_eq.groupby('estado').size().reset_index(name='Cantidad')
            fig_pie = px.pie(df_pie, values='Cantidad', names='estado', 
                             color_discrete_map={'Operativo':'#2ecc71', 'En Mantenimiento':'#f1c40f', 'De Baja':'#e74c3c'},
                             hole=0.4)
            fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay equipos registrados para mostrar gráficos.")
            
    with col_g2:
        st.markdown("##### Tipos de Hardware en el Inventario")
        if not df_eq.empty:
            # Agrupar datos por tipo de equipo para el gráfico de barras
            df_bar = df_eq.groupby('tipo').size().reset_index(name='Cantidad')
            fig_bar = px.bar(df_bar, x='tipo', y='Cantidad', 
                             labels={'tipo': 'Tipo de Equipo', 'Cantidad': 'Unidades'},
                             color='tipo', color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No hay equipos registrados para mostrar gráficos.")

    
    st.markdown("---")
    if not df_co.empty:
        gasto_total = (df_co["cantidad"] * df_co["costo_unitario"]).sum()
        st.metric("Inversión Total Acumulada", f"${gasto_total:,.2f}")
    else:
        st.metric("Inversión Total Acumulada", "$0.00")
elif choice == "Bitácora de Notas":
    st.header("📝 Bitácora de Novedades Diarias")
    
    # Crear la tabla de bitácora si no existe
    CURSOR.execute("CREATE TABLE IF NOT EXISTS bitacora (id_nota INTEGER PRIMARY KEY AUTOINCREMENT, nota TEXT, fecha TEXT, hora TEXT)")
    CONN.commit()
    
    with st.form("nueva_nota", clear_on_submit=True):
        st.subheader("Registrar Nueva Anotación")
        texto_nota = st.text_area("Escribe aquí la novedad o actividad del día (ej: Limpieza de filtros, orden de cableado...):")
        
        if st.form_submit_button("Guardar en Bitácora"):
            if texto_nota.strip() != "":
                fecha_actual = datetime.now().strftime("%Y-%m-%d")
                hora_actual = datetime.now().strftime("%H:%M:%S")
                CURSOR.execute("INSERT INTO bitacora (nota, fecha, hora) VALUES (?, ?, ?)", (texto_nota, fecha_actual, hora_actual))
                CONN.commit()
                st.success("Nota guardada exitosamente en la bitácora.")
                st.rerun()
            else:
                st.warning("El campo de texto no puede estar vacío.")
                
    st.subheader("📜 Historial de Novedades (Más recientes primero)")
    try:
        df_bitacora = pd.read_sql_query("SELECT fecha as 'Fecha', hora as 'Hora', nota as 'Detalle / Novedad' FROM bitacora ORDER BY id_nota DESC", CONN)
        st.dataframe(df_bitacora, use_container_width=True)
    except Exception:
        st.info("La bitácora está vacía actualmente.")
