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
CONN.commit()

# Función para convertir DataFrame a Excel en memoria
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

# --- INTERFAZ DE USUARIO ---
st.title("🖥️ Sistema de Gestión de Laboratorio de Computación")

menu = ["Inventario de Equipos", "Gestión de Estados / Bajas", "Registro de Compras", "Panel de Control"]
choice = st.sidebar.selectbox("Navegación", menu)

# --- MÓDULO 1: INVENTARIO ---
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
                except sqlite3.IntegrityError:
                    st.error("El ID de este equipo ya existe.")
            else:
                st.warning("El ID del equipo es obligatorio.")

    st.subheader("Equipos Registrados")
    df_equipos = pd.read_sql_query("SELECT * FROM equipos", CONN)
    st.dataframe(df_equipos, use_container_width=True)
    
    # Botón para exportar Inventario
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
            
            # Buscar datos actuales del equipo seleccionado
            info_actual = df_equipos[df_equipos["id_equipo"] == id_selec].iloc[0]
            st.write(f"**Equipo seleccionado:** {info_actual['tipo']} {info_actual['marca']} (Estado actual: {info_actual['estado']})")
            
            if st.form_submit_button("Actualizar Equipo"):
                if nueva_ub.strip() != "":
                    CURSOR.execute("UPDATE equipos SET estado = ?, ubicacion = ? WHERE id_equipo = ?", (nuevo_estado, nueva_ub, id_selec))
                else:
                    CURSOR.execute("UPDATE equipos SET estado = ? WHERE id_equipo = ?", (nuevo_estado, id_selec))
                CONN.commit()
                st.success(f"Equipo {id_selec} actualizado a estado: '{nuevo_estado}'")
                st.rerun()

# --- MÓDULO 3: COMPRAS ---
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
            else:
                st.warning("El nombre del artículo es obligatorio.")

    st.subheader("Historial de Transacciones")
    df_compras = pd.read_sql_query("SELECT * FROM compras", CONN)
    if not df_compras.empty:
        df_compras["Costo Total"] = df_compras["cantidad"] * df_compras["costo_unitario"]
    st.dataframe(df_compras, use_container_width=True)
    
    # Botón para exportar Compras
    if not df_compras.empty:
        excel_compras = to_excel(df_compras)
        st.download_button(
            label="📥 Exportar Historial de Compras a Excel",
            data=excel_compras,
            file_name=f"compras_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- MÓDULO 4: PANEL DE CONTROL ---
elif choice == "Panel de Control":
    st.header("📊 Resumen del Laboratorio")
    
    df_eq = pd.read_sql_query("SELECT * FROM equipos", CONN)
    df_co = pd.read_sql_query("SELECT * FROM compras", CONN)
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_equipos = len(df_eq)
    col1.metric("Total Equipos", total_equipos)
    
    if total_equipos > 0:
        operativos = len(df_eq[df_eq["estado"] == "Operativo"])
        en_mant = len(df_eq[df_eq["estado"] == "En Mantenimiento"])
        de_baja = len(df_eq[df_eq["estado"] == "De Baja"])
        
        col2.metric("Equipos Operativos", operativos)
        col3.metric("En Mantenimiento", en_mant)
        col4.metric("Dados de Baja", de_baja)
    else:
        col2.metric("Equipos Operativos", 0)
        col3.metric("En Mantenimiento", 0)
        col4.metric("Dados de Baja", 0)
        
    st.markdown("---")
    if not df_co.empty:
        gasto_total = (df_co["cantidad"] * df_co["costo_unitario"]).sum()
        st.metric("Inversión Total Acumulada", f"${gasto_total:,.2f}")
    else:
        st.metric("Inversión Total Acumulada", "$0.00")
