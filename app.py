import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io

st.set_page_config(page_title="Gestión de Laboratorio Pro", layout="wide")

CONN = sqlite3.connect("laboratorio.db", check_same_thread=False)
CURSOR = CONN.cursor()

CURSOR.execute("""
CREATE TABLE IF NOT EXISTS equipos (
    id_equipo TEXT PRIMARY KEY,
    tipo TEXT,
    marca TEXT,
    modelo TEXT,
    estado TEXT,
    ubicacion TEXT
)""")

CURSOR.execute("""
CREATE TABLE IF NOT EXISTS compras (
    id_compra INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT,
    cantidad INTEGER,
    costo_unitario REAL,
    proveedor TEXT,
    fecha TEXT
)""")

CURSOR.execute("""
CREATE TABLE IF NOT EXISTS prestamos (
    id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT,
    id_equipo TEXT,
    usuario TEXT,
    rut TEXT,
    fecha_prestamo TEXT,
    fecha_limite TEXT,
    fecha_devolucion TEXT,
    estado_prestamo TEXT,
    observaciones TEXT,
    FOREIGN KEY(id_equipo) REFERENCES equipos(id_equipo)
)""")
CONN.commit()

try:
    CURSOR.execute("ALTER TABLE prestamos ADD COLUMN observaciones TEXT")
    CONN.commit()
except sqlite3.OperationalError:
    pass 

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

st.title("🖥️ Sistema de Gestión de Laboratorio de Computación")
menu = ["Inventario de Equipos", "Gestión de Estados / Bajas", "Préstamo de Equipos", "Registro de Compras", "Panel de Control"]
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
                    CURSOR.execute("INSERT INTO equipos VALUES (?, ?, ?, ?, ?, ?)", (id_eq, tipo_eq, marca_eq, mod_eq, est_eq, ub_eq))
                    CONN.commit()
                    st.success(f"Equipo {id_eq} registrado con éxito.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("El ID de este equipo ya existe.")
            else:
                st.warning("El ID del equipo es obligatorio.")

    st.subheader("Equipos Registrados")
    df_equipos = pd.read_sql_query("SELECT * FROM equipos", CONN)
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
                if nueva_ub.strip() != "":
                    CURSOR.execute("UPDATE equipos SET estado = ?, ubicacion = ? WHERE id_equipo = ?", (nuevo_estado, nueva_ub, id_selec))
                else:
                    CURSOR.execute("UPDATE equipos SET estado = ? WHERE id_equipo = ?", (nuevo_estado, id_selec))
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
                        check_alumno = pd.read_sql_query(f"SELECT COUNT(*) as cuenta FROM prestamos WHERE rut = '{rut_limpio}' AND estado_prestamo = 'Activo'", CONN)
                        if int(check_alumno['cuenta'].iloc[0]) > 0:
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
            st.write("Selecciona para devolver")
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
    if not df_todos_prestamos.empty:
        st.download_button("📥 Exportar Préstamos a Excel", to_excel(df_todos_prestamos), "prestamos.xlsx")

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
        st.download_button("📥 Exportar Compras a Excel", to_excel(df_compras), "compras.xlsx")

    elif choice == "Panel de Control":
    st.header("📊 Resumen del Laboratorio")
    df_eq = pd.read_sql_query("SELECT * FROM equipos", CONN)
    df_co = pd.read_sql_query("SELECT * FROM compras", CONN)
    df_pr = pd.read_sql_query("SELECT * FROM prestamos WHERE estado_prestamo = 'Activo'", CONN)
    df_todos_pr = pd.read_sql_query("SELECT * FROM prestamos", CONN)
    
    prestamos_vencidos = []
    hoy_str = str(date.today())
    if not df_pr.empty:
        df_pr['fecha_limite_dt'] = pd.to_datetime(df_pr['fecha_limite'])
        df_vencidos = df_pr[df_pr['fecha_limite_dt'] < pd.to_datetime(hoy_str)]
        prestamos_vencidos = df_vencidos.to_dict('records')
    if prestamos_vencidos:
        st.error(f"🚨 Alerta: {len(prestamos_vencidos)} préstamos vencidos.")
        for p in prestamos_vencidos:
            st.markdown(f"* **{p['usuario']}** (RUT: {p['rut']}) tiene el equipo **{p['id_equipo']}**")
        st.markdown("---")
        
    if not df_todos_pr.empty:
        df_todos_pr['fecha_limite_dt'] = pd.to_datetime(df_todos_pr['fecha_limite'])
        df_todos_pr['fecha_devolucion_dt'] = pd.to_datetime(df_todos_pr['fecha_devolucion'], errors='coerce')
        cond_devuelto_tarde = (df_todos_pr['estado_prestamo'] == 'Devuelto') & (df_todos_pr['fecha_devolucion_dt'] > df_todos_pr['fecha_limite_dt'])
        cond_act_vencido = (df_todos_pr['estado_prestamo'] == 'Activo') & (df_todos_pr['fecha_limite_dt'] < pd.to_datetime(hoy_str))
        df_atrasos = df_todos_pr[cond_devuelto_tarde | cond_act_vencido]
        if not df_atrasos.empty:
            st.subheader("⚠️ Registro Histórico de Retrasos por Usuario")
            df_ranking = df_atrasos.groupby(['usuario', 'rut']).size().reset_index(name='Cantidad de Atrasos')
            df_ranking = df_ranking.sort_values(by='Cantidad de Atrasos', ascending=False)
            st.dataframe(df_ranking, use_container_width=True)
            st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Equipos", len(df_eq))
    
    if not df_eq.empty:
        col2.metric("Operativos", len(df_eq[df_eq["estado"] == "Operativo"]))
        col3.metric("En Mantención", len(df_eq[df_eq["estado"] == "En Mantenimiento"]))
    else:
        col2.metric("Operativos", 0)
        col3.metric("En Mantención", 0)
        
    col4.metric("Préstamos Activos", len(df_pr))
    
    st.markdown("---")
    if not df_co.empty:
        gasto_total = (df_co["cantidad"] * df_co["costo_unitario"]).sum()
        st.metric("Inversión Total Acumulada", f"${gasto_total:,.2f}")
    else:
        st.metric("Inversión Total Acumulada", "$0.00")
