import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io
import os
import shutil

st.set_page_config(page_title="Gestión de Laboratorio Pro", layout="wide")

CONN = sqlite3.connect("laboratorio.db", check_same_thread=False)
CURSOR = CONN.cursor()

# Creación de tablas del sistema (Incluye la nueva tabla de usuarios)
CURSOR.execute("CREATE TABLE IF NOT EXISTS equipos (id_equipo TEXT PRIMARY KEY, tipo TEXT, marca TEXT, modelo TEXT, estado TEXT, ubicacion TEXT, fecha_cambio TEXT)")
CURSOR.execute("CREATE TABLE IF NOT EXISTS compras (id_compra INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, cantidad INTEGER, costo_unitario REAL, proveedor TEXT, fecha TEXT)")
CURSOR.execute("CREATE TABLE IF NOT EXISTS prestamos (id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT, id_equipo TEXT, usuario TEXT, rut TEXT, fecha_prestamo TEXT, fecha_limite TEXT, fecha_devolucion TEXT, estado_prestamo TEXT, observaciones TEXT)")
CURSOR.execute("CREATE TABLE IF NOT EXISTS infraestructura (id_item INTEGER PRIMARY KEY AUTOINCREMENT, elemento TEXT, ubicacion TEXT, estado TEXT, observaciones TEXT)")
CURSOR.execute("CREATE TABLE IF NOT EXISTS usuarios (rut TEXT PRIMARY KEY, nombre TEXT, correo TEXT, tipo_usuario TEXT)")
CONN.commit()

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

st.title("🖥️ Sistema de Gestión de Laboratorio de Computación")

# Se añade "Mantenedor de Usuarios" al menú de navegación
menu = ["Inventario de Equipos", "Gestión de Estados / Bajas", "Mantenedor de Usuarios", "Préstamo de Equipos", "Infraestructura de Sala", "Registro de Compras", "Respaldo de Seguridad", "Bitácora de Notas", "Panel de Control"]
choice = st.sidebar.selectbox("Navegación", menu)

# --- COMPRESIÓN VISUAL MÁXIMA DEL MENÚ LATERAL ---
st.markdown("""
    <style>
    [data-testid="stSidebarContent"] { padding-top: 0.5rem !important; }
    [data-testid="stSidebarNav"] { padding-top: 0rem !important; margin-top: 0rem !important; padding-bottom: 0rem !important; }
    [data-testid="stSidebarNav"] li { padding: 0px !important; margin-top: 1px !important; margin-bottom: 1px !important; line-height: 1.1 !important; }
    [data-testid="stSidebarNav"] span { font-size: 13px !important; font-weight: 500 !important; }
    [data-testid="stSidebarNav"] svg { transform: scale(0.85) !important; margin-right: -4px !important; }
    </style>
""", unsafe_allow_html=True)
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

       
    # Filtros rápidos en la parte superior de la tabla
    
    st.markdown("---")
    st.subheader("🔍 Buscador Dinámico de Hardware")
    
    # Se cambian a 3 columnas para añadir el Tipo de Hardware
    col_b1, col_b2, col_b3 = st.columns(3)
    buscar_id = col_b1.text_input("Buscar por ID, Marca o Modelo:")
    filtrar_tipo = col_b2.selectbox("Filtrar por Tipo:", ["Todos", "Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"])
    filtrar_estado = col_b3.selectbox("Filtrar por Estado Técnico:", ["Todos", "Operativo", "En Mantenimiento", "De Baja"])
    
    # Consulta SQL dinámica base
    query_eq = "SELECT id_equipo as 'ID Equipo', tipo as 'Tipo', marca as 'Marca', modelo as 'Modelo', estado as 'Estado', ubicacion as 'Ubicación' FROM equipos WHERE 1=1"
    parametros_eq = []
    
    # 1. Filtro por texto libre
    if buscar_id.strip() != "":
        query_eq += " AND (id_equipo LIKE ? OR marca LIKE ? OR modelo LIKE ?)"
        term = f"%{buscar_id.strip()}%"
        parametros_eq.extend([term, term, term])
        
    # 2. Filtro por Tipo de Hardware
    if filtrar_tipo != "Todos":
        query_eq += " AND tipo = ?"
        parametros_eq.append(filtrar_tipo)
        
    # 3. Filtro por Estado Técnico
    if filtrar_estado != "Todos":
        query_eq += " AND estado = ?"
        parametros_eq.append(filtrar_estado)
        
    df_equipos = pd.read_sql_query(query_eq, CONN, params=parametros_eq)
    
    if not df_equipos.empty:
        st.dataframe(df_equipos, use_container_width=True)
        st.download_button("📥 Exportar Resultados a Excel", to_excel(df_equipos), "inventario_filtrado.xlsx")
    else:
        st.info("No se encontraron equipos que coincidan con los criterios de búsqueda.")

    
    # Construcción de la consulta SQL dinámica basada en lo que escribas
    query_eq = "SELECT id_equipo as 'ID Equipo', tipo as 'Tipo', marca as 'Marca', modelo as 'Modelo', estado as 'Estado', ubicacion as 'Ubicación' FROM equipos WHERE 1=1"
    parametros_eq = []
    
    if buscar_id.strip() != "":
        query_eq += " AND (id_equipo LIKE ? OR marca LIKE ? OR modelo LIKE ?)"
        term = f"%{buscar_id.strip()}%"
        parametros_eq.extend([term, term, term])
        
    if filtrar_estado != "Todos":
        query_eq += " AND estado = ?"
        parametros_eq.append(filtrar_estado)
        
    df_equipos = pd.read_sql_query(query_eq, CONN, params=parametros_eq)
    
    if not df_equipos.empty:
        st.dataframe(df_equipos, use_container_width=True)
    else:
        st.info("No se encontraron equipos que coincidan con los criterios de búsqueda.")

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

elif choice == "Mantenedor de Usuarios":
    st.header("👥 Mantenedor de Usuarios del Sistema")
    tab_u1, tab_u2 = st.tabs(["➕ Registrar Usuario", "❌ Eliminar Usuario"])
    
    with tab_u1:
        with st.form("nuevo_usuario", clear_on_submit=True):
            col_u1, col_u2 = st.columns(2)
            u_rut = col_u1.text_input("RUT / Documento de Identidad (Único)")
            u_nombre = col_u2.text_input("Nombre Completo")
            col_u3, col_u4 = st.columns(2)
            u_correo = col_u3.text_input("Correo Electrónico")
            u_tipo = col_u4.selectbox("Tipo de Usuario", ["Alumno", "Profesor", "Técnico", "Otro"])
            
            if st.form_submit_button("Guardar Usuario"):
                if u_rut.strip() != "" and u_nombre.strip() != "":
                    try:
                        CURSOR.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?)", (u_rut.strip(), u_nombre.strip(), u_correo.strip(), u_tipo))
                        CONN.commit()
                        st.success(f"Usuario {u_nombre} registrado exitosamente.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Este RUT ya se encuentra registrado.")
                else:
                    st.warning("El RUT y el Nombre son campos obligatorios.")
                    
    with tab_u2:
        df_del_u = pd.read_sql_query("SELECT rut, nombre, tipo_usuario FROM usuarios", CONN)
        if df_del_u.empty:
            st.info("No hay usuarios registrados para eliminar.")
        else:
            with st.form("eliminar_usuario_form"):
                lista_usuarios = [f"{row['rut']} - {row['nombre']} ({row['tipo_usuario']})" for _, row in df_del_u.iterrows()]
                usuario_eliminar = st.selectbox("Selecciona el usuario a eliminar", lista_usuarios)
                if st.form_submit_button("Eliminar permanentemente"):
                    rut_eliminar = usuario_eliminar.split(" - ")[0]
                    CURSOR.execute("DELETE FROM usuarios WHERE rut = ?", (rut_eliminar,))
                    CONN.commit()
                    st.success("Usuario eliminado correctamente.")
                    st.rerun()
                    
    st.markdown("---")
    st.subheader("🔍 Buscador Dinámico de Usuarios")
    buscar_u = st.text_input("Buscar por RUT o Nombre del Alumno / Profesor:")
    
    query_u = "SELECT rut as 'RUT', nombre as 'Nombre Completo', correo as 'Correo', tipo_usuario as 'Tipo de Usuario' FROM usuarios WHERE 1=1"
    parametros_u = []
    
    if buscar_u.strip() != "":
        query_u += " AND (rut LIKE ? OR nombre LIKE ?)"
        term_u = f"%{buscar_u.strip()}%"
        parametros_u.extend([term_u, term_u])
        
    df_usuarios = pd.read_sql_query(query_u, CONN, params=parametros_u)
    
    if not df_usuarios.empty:
        st.dataframe(df_usuarios, use_container_width=True)
    else:
        st.info("No se encontraron usuarios registrados con esos datos.")


elif choice == "Préstamo de Equipos":
    st.header("🤝 Módulo de Préstamos y Devoluciones")
    tab1, tab2 = st.tabs(["🆕 Registrar Préstamo", "🔙 Procesar Devolución"])
    
    # Cargar usuarios disponibles para el menú desplegable inteligente
    df_us_disp = pd.read_sql_query("SELECT rut, nombre FROM usuarios", CONN)
    
    with tab1:
        df_operativos = pd.read_sql_query("SELECT id_equipo, tipo, marca FROM equipos WHERE estado = 'Operativo'", CONN)
        df_activos = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo'", CONN)
        prestados_ids = df_activos["id_equipo"].tolist()
        df_disponibles = df_operativos[~df_operativos["id_equipo"].isin(prestados_ids)]
        
        if df_us_disp.empty:
            st.warning("⚠️ Bloqueado: Primero debes registrar al menos un usuario en el 'Mantenedor de Usuarios' para poder realizar préstamos.")
        elif df_disponibles.empty:
            st.warning("No hay equipos operativos disponibles.")
        else:
            with st.form("form_prestamo", clear_on_submit=True):
                lista_disp = [f"{row['id_equipo']} - {row['tipo']} ({row['marca']})" for _, row in df_disponibles.iterrows()]
                equipo_selec = st.selectbox("Selecciona el Equipo a Prestar", lista_disp)
                
                # Menú desplegable conectado al Mantenedor de Usuarios
                lista_usuarios_select = [f"{row['rut']} | {row['nombre']}" for _, row in df_us_disp.iterrows()]
                usuario_selec_box = st.selectbox("Selecciona el Usuario (RUT | Nombre)", lista_usuarios_select)
                
                col_f1, col_f2 = st.columns(2)
                fecha_p = col_f1.date_input("Fecha de Entrega", date.today())
                fecha_l = col_f2.date_input("Fecha Máxima de Devolución", date.today())
                obs_p = st.text_input("Observaciones de Entrega")
                
                if st.form_submit_button("Confirmar Préstamo"):
                    rut_limpio = usuario_selec_box.split(" | ")[0].strip()
                    nombre_limpio = usuario_selec_box.split(" | ")[1].strip()
                    
                    c_check = CONN.cursor()
                    c_check.execute("SELECT COUNT(*) FROM prestamos WHERE rut = ? AND estado_prestamo = 'Activo'", (rut_limpio,))
                    cuenta = c_check.fetchone()[0]
                    if cuenta > 0:
                        st.error(f"⛔ Bloqueado: El usuario {nombre_limpio} ya tiene un equipo actualmente.")
                    else:
                        id_real = equipo_selec.split(" - ")[0].strip()
                        CURSOR.execute("INSERT INTO prestamos (id_equipo, usuario, rut, fecha_prestamo, fecha_limite, fecha_devolucion, estado_prestamo, observaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (id_real, nombre_limpio, rut_limpio, str(fecha_p), str(fecha_l), "Pendiente", "Activo", obs_p))
                        CONN.commit()
                        st.success("Préstamo registrado con éxito.")
                        st.rerun()
                        
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
        elem = col1.text_input("Elemento (ej: Enchufe Fila 2, Proyector Central)")
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
    
    if not df_compras.empty:
        st.markdown("---")
        st.subheader("📊 Análisis de Gastos por Mes")
        import plotly.express as px
        df_compras['fecha_dt'] = pd.to_datetime(df_compras['fecha'])
        df_compras['Mes'] = df_compras['fecha_dt'].dt.to_period('M').astype(str)
        df_gastos_mes = df_compras.groupby('Mes')['Costo Total'].sum().reset_index()
        fig_gastos = px.bar(df_gastos_mes, x='Mes', y='Costo Total', labels={'Mes': 'Mes', 'Costo Total': 'Inversión ($)'}, title="Inversión Mensual", color_discrete_sequence=['#3498db'])
        fig_gastos.update_layout(height=300)
        st.plotly_chart(fig_gastos, use_container_width=True)

elif choice == "Respaldo de Seguridad":
    st.header("💾 Copias de Seguridad del Sistema")
    if st.button("🔄 Generar Copia de Seguridad"):
        carpeta_backup = "C:/respaldos_laboratorio"
        if not os.path.exists(carpeta_backup): os.makedirs(carpeta_backup)
        nombre_archivo = f"respaldo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copyfile("laboratorio.db", os.path.join(carpeta_backup, nombre_archivo))
        st.success("¡Respaldo creado con éxito!")

elif choice == "Bitácora de Notas":
    st.header("📝 Bitácora de Novedades Diarias")
    CURSOR.execute("CREATE TABLE IF NOT EXISTS bitacora (id_nota INTEGER PRIMARY KEY AUTOINCREMENT, nota TEXT, fecha TEXT, hora TEXT)")
    CONN.commit()
    with st.form("nueva_nota", clear_on_submit=True):
        texto_nota = st.text_area("Escribe aquí la novedad:")
        if st.form_submit_button("Guardar en Bitácora"):
            if texto_nota.strip() != "":
                CURSOR.execute("INSERT INTO bitacora (nota, fecha, hora) VALUES (?, ?, ?)", (texto_nota, str(date.today()), datetime.now().strftime("%H:%M:%S")))
                CONN.commit()
                st.success("Nota guardada.")
                st.rerun()
    df_bitacora = pd.read_sql_query("SELECT fecha, hora, nota FROM bitacora ORDER BY id_nota DESC", CONN)
    st.dataframe(df_bitacora, use_container_width=True)

elif choice == "Panel de Control":
    st.header("📊 Resumen General del Laboratorio")
    df_eq = pd.read_sql_query("SELECT * FROM equipos", CONN)
    df_co = pd.read_sql_query("SELECT * FROM compras", CONN)
    df_pr = pd.read_sql_query("SELECT * FROM prestamos WHERE estado_prestamo = 'Activo'", CONN)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Equipos", len(df_eq))
    col2.metric("Operativos", len(df_eq[df_eq["estado"] == "Operativo"]) if not df_eq.empty else 0)
    col3.metric("En Mantención", len(df_eq[df_eq["estado"] == "En Mantenimiento"]) if not df_eq.empty else 0)
    col4.metric("Préstamos Activos", len(df_pr))
    
    st.markdown("---")
    import plotly.express as px
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if not df_eq.empty:
            df_pie = df_eq.groupby('estado').size().reset_index(name='Cantidad')
            fig_pie = px.pie(df_pie, values='Cantidad', names='estado', title="Equipos por Estado", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
    with col_g2:
        if not df_eq.empty:
            df_bar = df_eq.groupby('tipo').size().reset_index(name='Cantidad')
            fig_bar = px.bar(df_bar, x='tipo', y='Cantidad', title="Tipos de Hardware")
            st.plotly_chart(fig_bar, use_container_width=True)