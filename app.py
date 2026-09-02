import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io

# Configuración de la página web
st.set_page_config(page_title="Gestión de Laboratorio Pro", layout="wide")

# Conexión a la base de datos local SQLite
CONN = sqlite3.connect("laboratorio.db", check_same_thread=False)
CURSOR = CONN.cursor()

# Crear tablas si no existen
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

# NUEVA TABLA: Préstamos de equipos
CURSOR.execute("""
CREATE TABLE IF NOT EXISTS prestamos (
    id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT,
    id_equipo TEXT,
    usuario TEXT,
    fecha_prestamo TEXT,
    fecha_devolucion TEXT,
    estado_prestamo TEXT,
    FOREIGN KEY(id_equipo) REFERENCES equipos(id_equipo)
)""")
CONN.commit()

# Función para convertir DataFrame a Excel en memoria
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

# --- INTERFAZ DE USUARIO ---
st.title("🖥️ Sistema de Gestión de Laboratorio de Computación")

menu = ["Inventario de Equipos", "Gestión de Estados / Bajas", "Préstamo de Equipos", "Registro de Compras", "Panel de Control"]
choice = st.sidebar.selectbox("Navegación", menu)

# --- MÓDULO 1: INVENTARIO ---
if choice == "Inventario de Equipos":
    st.header("📋 Inventario de Hardware")
    
    with St.form("nuevo_equipo", clear_on_submit=True):
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
        excel_data = to_excel(df_equipos)
        st.download_button(
            label="📥 Exportar Inventario a Excel",
            data=excel_data,
            file_name=f"inventario_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- MÓDULO 2: GESTIÓN DE ESTADOS Y BAJAS ---
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
            nueva_ub = st.text_input("Actualizar Ubicación (Opcional, dejar vacío para mantener)")
            
            if st.form_submit_button("Actualizar Equipo"):
                if nueva_ub.strip() != "":
                    CURSOR.execute("UPDATE equipos SET estado = ?, ubicacion = ? WHERE id_equipo = ?", (nuevo_estado, nueva_ub, id_selec))
                else:
                    CURSOR.execute("UPDATE equipos SET estado = ? WHERE id_equipo = ?", (nuevo_estado, id_selec))
                CONN.commit()
                st.success(f"Equipo {id_selec} actualizado a estado: '{nuevo_estado}'")
                st.rerun()

# --- NUEVO MÓDULO 3: PRÉSTAMO DE EQUIPOS ---
elif choice == "Préstamo de Equipos":
    st.header("🤝 Módulo de Préstamos y Devoluciones")
    
    tab1, tab2 = st.tabs(["🆕 Registrar Préstamo", "🔙 Procesar Devolución"])
    
    with tab1:
        # Solo permitir prestar equipos que estén 'Operativos'
        df_operativos = pd.read_sql_query("SELECT id_equipo, tipo, marca FROM equipos WHERE estado = 'Operativo'", CONN)
        
        # Filtrar también para no prestar equipos que ya estén prestados actualmente
        df_activos = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo'", CONN)
        prestados_ids = df_activos["id_equipo"].tolist()
        df_disponibles = df_operativos[~df_operativos["id_equipo"].isin(prestados_ids)]
        
        if df_disponibles.empty:
            st.warning("No hay equipos operativos disponibles para préstamo en este momento.")
        else:
            with st.form("form_prestamo", clear_on_submit=True):
                lista_disp = [f"{row['id_equipo']} - {row['tipo']} ({row['marca']})" for _, row in df_disponibles.iterrows()]
                equipo_selec = st.selectbox("Selecciona el Equipo a Prestar", lista_disp)
                usuario_p = st.text_input("Nombre Completo del Usuario / Alumno / Profesor")
                fecha_p = st.date_input("Fecha de Entrega", datetime.now())
                
                if st.form_submit_button("Confirmar Préstamo"):
                    if usuario_p.strip() != "":
                        id_real = equipo_selec.split(" - ")[0]
                        CURSOR.execute(
                            "INSERT INTO prestamos (id_equipo, usuario, fecha_prestamo, fecha_devolucion, estado_prestamo) VALUES (?, ?, ?, ?, ?)",
                            (id_real, usuario_p, str(fecha_p), "Pendiente", "Activo")
                        )
                        CONN.commit()
                        st.success(f"Equipo {id_real} prestado exitosamente a {usuario_p}.")
                        st.rerun()
                    else:
                        st.warning("Por favor, ingresa el nombre del usuario.")
                        
    with tab2:
        df_prestados = pd.read_sql_query(
            "SELECT id_prestamo, id_equipo, usuario, fecha_prestamo FROM prestamos WHERE estado_prestamo = 'Activo'", CONN
        )
        
        if df_prestados.empty:
            st.info("No hay préstamos activos registrados en el sistema.")
        else:
            st.subheader("Préstamos en Curso")
            st.dataframe(df_prestados, use_container_width=True)
            
            with st.form("form_devolucion"):
                lista_prestamos = [f"ID:{row['id_prestamo']} | {row['id_equipo']} prestado a {row['usuario']}" for _, row in df_prestados.iterrows()]
                prestamo_selec = st.selectbox("Selecciona el préstamo a finalizar", lista_prestamos)
                fecha_d = st.date_input("Fecha de Devolución", datetime.now())
                
                if st.form_submit_button("Registrar Devolución"):
                    id_prestamo_real = int(prestamo_selec.split(" | ")[0].split(":")[1])
                    CURSOR.execute(
                        "UPDATE prestamos SET fecha_devolucion = ?, estado_prestamo = 'Devuelto' WHERE id_prestamo = ?",
                        (str(fecha_d), id_prestamo_real)
                    )
                    CONN.commit()
                    st.success("La devolución ha sido registrada y el equipo vuelve a estar disponible.")
                    st.rerun()
                    
    st.markdown("---")
    st.subheader("📜 Historial Completo de Préstamos")
    df_todos_prestamos = pd.read_sql_query("SELECT * FROM prestamos", CONN)
    st.dataframe(df_todos_prestamos, use_container_width=True)
    
    if not df_todos_prestamos.empty:
        excel_prestamos = to_excel(df_todos_prestamos)
        st.download_button(
            label="📥 Exportar Historial de Préstamos a Excel",
            data=excel_prestamos,
            file_name=f"historial_prestamos_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- MÓDULO 4: COMPRAS ---
elif choice == "Registro de Compras":
    st.header("💰 Historial de Compras y Adquisiciones")
    
    with st.form("nueva_compra", clear_on_submit=True):
        st.subheader("Registrar Nueva Compra")
        col1, col2, col3 = st.columns(3)
        item_c = col1.text_input("Artículo / Insumo")
        cant_c = col2.number_input("Cantidad", min_value=1, step=1)
        costo_c = col3.number_input("Costo Unitario ($)", min_value=0.0)
        
        col4, col5 = st.columns(2)
        prov_c = col4.text_input("Proveedor")
        fecha_c = col5.date_input("Fecha de Compra", datetime.now())
        
        if st.form_submit_button("Registrar Compra"):
            if item_c:
                CURSOR.execute("INSERT INTO compras (item, cantidad, costo_unitario, proveedor, fecha) VALUES (?, ?, ?, ?, ?)",
                               (item_c, cant_c, costo_c, prov_c, str(fecha_c)))
                CONN.commit()
                st.success(f"Compra de '{item_c}' registrada.")
                st.rerun()
            else:
