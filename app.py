import streamlit as st
# Este comando funciona de forma transparente en local y en la web
try:
    BREVO_API_KEY = st.secrets["BREVO_API_KEY"]
except KeyError:
    st.error("Falta configurar la API Key de Brevo en los secretos de Streamlit.")

# Tu código actual para la gestión del laboratorio y envíos de correo...

import pandas as pd
import sqlite3
from datetime import datetime, date
import os
import shutil
import plotly.express as px
import segno
import io  # 🚀 CORRECCIÓN: Agrega esta línea para habilitar el manejo de imágenes en memoria RAM

from database import obtener_conexion, inicializar_db, to_excel, obtener_bytes_db, restaurar_db_desde_bytes
#from database import obtener_conexion, inicializar_db, to_excel
# ... (El resto de tu código hacia abajo se mantiene exactamente igual)
from mod_qr import renderizar_modulo_qr


# Inicializar base de datos externa al arrancar
inicializar_db()

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

st.title("🖥️ Sistema de Gestión de Laboratorio Escuela Felipe Cubillos")
menu = ["Inventario de Equipos", "Gestión de Estados / Bajas", "Mantenedor de Usuarios", "Préstamo de Equipos", "Gestión de Salas", "Infraestructura de Sala", "Registro de Compras", "Generador de QR", "Respaldo de Seguridad", "Bitácora de Notas", "Panel de Control"]
choice = st.sidebar.selectbox("Navegación", menu)

# --- RUTAS DE NAVEGACIÓN MODULARES ---
# =========================================================================
# 📋 MÓDULO: INVENTARIO DE HARDWARE (AÑADIR, MODIFICAR, ELIMINAR Y LISTADO)
# =========================================================================
# =========================================================================
# 📋 MÓDULO: INVENTARIO DE HARDWARE (CON SELECTOR DINÁMICO DE SALAS)
# =========================================================================
if choice == "Inventario de Equipos":
    st.header("📋 Inventario de Hardware y Activos TI")
    
    t_eq1, t_eq2, t_eq3, t_eq4 = st.tabs(["➕ Añadir Equipo", "🔄 Modificar Equipo", "❌ Eliminar Equipo", "📋 Listado Completo"])
    
    with obtener_conexion() as conn:
        df_base_ids = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo FROM equipos ORDER BY id_equipo ASC", conn)
        # 🏢 NUEVA MEJORA: Consultamos las salas registradas en el sistema para el formulario
        df_salas_sistema = pd.read_sql_query("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC", conn)
        
    lista_equipos_bd = [f"{row['id_equipo']} - {row['tipo']} {row['marca']}" for _, row in df_base_ids.iterrows()]
    lista_salas_combo = df_salas_sistema["nombre_sala"].tolist() if not df_salas_sistema.empty else []

    # --- TAB 1: AÑADIR NUEVO EQUIPO (CON COMBO DE SALAS) ---
    with t_eq1:
        if st.session_state["rol"] == "Administrador":
            with st.form("nuevo_equipo", clear_on_submit=True):
                st.subheader("Añadir Nuevo Equipo al Inventario")
                col1, col2, col3 = st.columns(3)
                id_eq = col1.text_input("ID / Código del Equipo (ej: PC-01)")
                tipo_eq = col2.selectbox("Tipo", ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"])
                marca_eq = col3.text_input("Marca")
                
                col4, col5, col6 = st.columns(3)
                mod_eq = col4.text_input("Modelo")
                est_eq = col5.selectbox("Estado Técnico Inicial", ["Operativo", "En Mantenimiento", "De Baja"])
                
                # 🚀 MEJORA SOLICITADA: Cambiamos text_input por un selectbox dinámico amarrado a las salas creadas
                if lista_salas_combo:
                    ub_eq = col6.selectbox("Ubicación en Sala / Casillero:", lista_salas_combo)
                else:
                    # En caso de que la BD esté vacía, damos una opción por defecto para no bloquear el inicio
                    ub_eq = col6.selectbox("Ubicación en Sala / Casillero:", ["Bodega General TI (Por Defecto)"])
                
                st.markdown("**🧾 Datos Financieros de Adquisición:**")
                col7, col8, col9 = st.columns(3)
                num_doc = col7.text_input("Nro. Factura / Boleta:")
                prov_orig = col8.text_input("Proveedor de Venta:")
                costo_eq = col9.number_input("Costo de Adquisición ($):", min_value=0.0, step=1000.0, format="%.2f")
                
                if st.form_submit_button("Guardar Equipo"):
                    if id_eq and num_doc:
                        try:
                            hoy = date.today().isoformat()
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "INSERT INTO equipos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                    (id_eq.strip(), tipo_eq, marca_eq.strip(), mod_eq.strip(), est_eq, ub_eq, hoy, num_doc.strip(), prov_orig.strip(), costo_eq)
                                )
                                conn.commit()
                            st.success(f"✅ ¡Equipo {id_eq} registrado con éxito en {ub_eq}!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⛔ Error: El ID de este equipo ya existe registrado en el sistema.")
                    else:
                        st.warning("⚠️ El ID del equipo y el Número de Factura/Boleta son campos obligatorios.")
        else:
            st.warning("🔒 Permisos insuficientes: El perfil 'Visor' no puede añadir hardware al inventario.")

    # --- TAB 2: MODIFICAR EQUIPO EXISTENTE ---
    with t_eq2:
        st.subheader("🔄 Actualizar Características de Hardware")
        if st.session_state["rol"] == "Administrador":
            if not lista_equipos_bd: st.info("No hay equipos registrados para modificar.")
            else:
                eq_a_modificar = st.selectbox("Selecciona el equipo que deseas editar:", lista_equipos_bd, key="sb_mod_eq_main")
                id_mod_real = eq_a_modificar.split(" - ")[0].strip()
                
                with obtener_conexion() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT tipo, marca, modelo, ubicacion, num_documento, proveedor_origen, costo_compra FROM equipos WHERE id_equipo = ?", (id_mod_real,))
                    datos_act = cursor.fetchone()
                
                with st.form("form_modificar_equipo"):
                    st.caption(f"✍️ Modificando Ficha de Activo: **{id_mod_real}**")
                    col_m1, col_m2, col_m3 = st.columns(3)
                    tipo_m = col_m1.selectbox("Cambiar Tipo:", ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"], index=["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"].index(datos_act[0]))
                    marca_m = col_m2.text_input("Modificar Marca:", value=datos_act[1])
                    mod_m = col_m3.text_input("Modificar Modelo:", value=datos_act[2])
                    
                    col_m4, col_m5, col_m6 = st.columns(3)
                    # 🚀 MEJORA COMPLEMENTARIA: El formulario de modificación también usa el selectbox de salas si existen
                    if lista_salas_combo:
                        idx_sala_act = lista_salas_combo.index(datos_act[3]) if datos_act[3] in lista_salas_combo else 0
                        ub_m = col_m4.selectbox("Modificar Ubicación/Sala:", lista_salas_combo, index=idx_sala_act)
                    else:
                        ub_m = col_m4.text_input("Modificar Ubicación/Sala:", value=datos_act[3])
                        
                    doc_m = col_m5.text_input("Nro. Factura Actualizado:", value=datos_act[4])
                    prov_m = col_m6.text_input("Proveedor Actualizado:", value=datos_act[5])
                    costo_m = st.number_input("Costo de Compra Corregido ($):", min_value=0.0, value=float(datos_act[6] if datos_act[6] is not None else 0), format="%.2f")
                    
                    if st.form_submit_button("Actualizar Ficha Técnica"):
                        if doc_m.strip():
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE equipos SET tipo = ?, marca = ?, modelo = ?, ubicacion = ?, num_documento = ?, proveedor_origen = ?, costo_compra = ?, fecha_cambio = ? WHERE id_equipo = ?",
                                    (tipo_m, marca_m.strip(), mod_m.strip(), ub_m, doc_m.strip(), prov_m.strip(), costo_m, date.today().isoformat(), id_mod_real)
                                )
                                conn.commit()
                            st.success(f"✅ ¡La ficha técnica de {id_mod_real} fue actualizada correctamente!")
                            st.rerun()
                        else: st.error("El Número de Factura/Boleta es obligatorio.")
        else: st.warning("🔒 Permisos insuficientes.")

    # --- TAB 3: ELIMINAR EQUIPO PERMANENTEMENTE ---
    with t_eq3:
        st.subheader("🗑️ Eliminar Activo del Sistema")
        if st.session_state["rol"] == "Administrador":
            if not lista_equipos_bd: st.info("No hay equipos inventariados.")
            else:
                with st.form("eliminar_equipo_form"):
                    eq_a_eliminar = st.selectbox("Selecciona el equipo a borrar:", lista_equipos_bd, key="sb_del_eq_main")
                    id_del_real = eq_a_eliminar.split(" - ")[0].strip()
                    st.warning(f"⚠️ ¡Cuidado! Eliminar el activo **{id_del_real}** es permanente.")
                    if st.form_submit_button("🚨 Eliminar Permanentemente"):
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM prestamos WHERE id_equipo = ? AND estado_prestamo = 'Activo'", (id_del_real,))
                            if cursor.fetchone()[0] > 0:
                                st.error("⛔ Operación Cancelada: El equipo figura actualmente como 'Prestado'.")
                            else:
                                cursor.execute("DELETE FROM equipos WHERE id_equipo = ?", (id_del_real,))
                                cursor.execute("DELETE FROM historial_mantenimiento WHERE id_equipo = ?", (id_del_real,))
                                conn.commit()
                                st.success("Equipo removido de forma correcta.")
                                st.rerun()
        else: st.warning("🔒 Permisos insuficientes.")

    # --- TAB 4: LISTADO GENERAL COMPLETO ---
    with t_eq4:
        st.subheader("📋 Nómina Completa de Hardware en el Establecimiento")
        with obtener_conexion() as conn:
            df_nomina_total = pd.read_sql_query("SELECT id_equipo as 'ID Equipo', tipo as 'Tipo Hardware', marca as 'Marca', modelo as 'Modelo', estado as 'Estado Técnico', ubicacion as 'Ubicación / Sala', num_documento as 'Nro. Docto', proveedor_origen as 'Proveedor', costo_compra as 'Costo ($)' FROM equipos ORDER BY id_equipo ASC", conn)
        
        if not df_nomina_total.empty:
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Total de Equipos Inventariados", len(df_nomina_total))
            col_m2.metric("Inversión Global Acumulada", f"${df_nomina_total['Costo ($)'].sum():,.2f}")
            st.dataframe(df_nomina_total, use_container_width=True)
            st.download_button("📥 Descargar Inventario Completo (Excel)", to_excel(df_nomina_total), "inventario_general_escuela.xlsx")
        else: 
            st.info("No se registran equipos ingresados en el inventario todavía.")# Buscador dinámico histórico al final del módulo
            
     # Buscador dinámico histórico al final del módulo (Fuera de las pestañas)
    st.markdown("---")
    st.subheader("🔍 Buscador Dinámico de Hardware")
    buscar_id_b = st.text_input("Filtrar rápidamente por ID, Marca o Factura:")
    
    if buscar_id_b.strip():
        with obtener_conexion() as conn:
            # 🚀 CORRECCIÓN: Comillas triples para permitir saltos de línea limpios en SQL
            query_busqueda_completa = """
                SELECT id_equipo as 'ID Equipo', tipo as 'Tipo', marca as 'Marca', 
                       modelo as 'Modelo', estado as 'Estado', ubicacion as 'Ubicación', 
                       num_documento as 'Factura' 
                FROM equipos 
                WHERE id_equipo LIKE ? OR marca LIKE ? OR num_documento LIKE ?
            """
            df_busqueda = pd.read_sql_query(
                query_busqueda_completa, 
                conn, 
                params=(f"%{buscar_id_b}%", f"%{buscar_id_b}%", f"%{buscar_id_b}%")
            )
        if not df_busqueda.empty:
            st.dataframe(df_busqueda, use_container_width=True)
        else:
            st.caption("No se encontraron coincidencias para la búsqueda.")
 
# =========================================================================
# 🔄 MÓDULO: GESTIÓN DE ESTADOS / BAJAS Y HOJA DE VIDA TÉCNICA
# =========================================================================
elif choice == "Gestión de Estados / Bajas":
    st.header("🔄 Hoja de Vida y Control Técnico de Equipos")
    
    # 🛡️ Asegura que exista la tabla de taller en SQLite al entrar al módulo
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
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

    # 📑 Estructuración de pestañas operativas completas
    t_st1, t_st2, t_st3 = st.tabs(["⚙️ Cambiar Estado", "🛠️ Historial de Taller", "📋 Hoja de Vida y Costos"])
    
    with obtener_conexion() as conn:
        df_eq_status = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, estado FROM equipos ORDER BY id_equipo ASC", conn)
        df_salas_disp = pd.read_sql_query("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC", conn)
        
    lista_ids_equipos = df_eq_status["id_equipo"].tolist() if not df_eq_status.empty else []
    lista_salas_combo = df_salas_disp["nombre_sala"].tolist() if not df_salas_disp.empty else ["Bodega General TI"]

    if not lista_ids_equipos:
        st.info("⚠️ No hay equipos registrados en el inventario actual. Ingrese componentes en el Inventario primero.")
    else:
        # --- TAB 1: ACTUALIZAR ESTADO TÉCNICO ---
        with t_st1:
            st.subheader("⚙️ Actualizar Estado Operativo de un Activo")
            if st.session_state["rol"] == "Administrador":
                with st.form("actualizar_estado_form", clear_on_submit=True):
                    id_selec = st.selectbox("Selecciona el ID del Equipo:", lista_ids_equipos, key="sb_status_id_tab1")
                    nuevo_estado = st.selectbox("Nuevo Estado Técnico:", ["Operativo", "En Mantenimiento", "De Baja"])
                    
                    st.caption("🔄 Reubicar Espacio Físico (Opcional):")
                    cambiar_ub = st.checkbox("¿Deseas trasladar este equipo a otra sala?", value=False)
                    nueva_ub_sala = st.selectbox("Selecciona la nueva Sala de Destino:", lista_salas_combo, disabled=not cambiar_ub)
                    
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
                    costo_rep = st.number_input("Costo Real de los Repuestos ($ CLP):", min_value=0.0, step=1000.0, format="%.2f")
                    
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

 
elif choice == "Mantenedor de Usuarios":
    st.header("👥 Mantenedor de Usuarios")
    # 📑 Se añade la tercera pestaña "❌ Eliminar"
    t1, t2, t3 = st.tabs(["➕ Registrar", "📋 Ver Lista", "❌ Eliminar"])
    
    with t1:
        with st.form("u_f", clear_on_submit=True):
            u_rut = st.text_input("RUT (Único)")
            u_nom = st.text_input("Nombre Completo")
            u_cor = st.text_input("Correo")
            u_tip = st.selectbox("Tipo", ["Alumno", "Profesor", "Técnico"])
            
            if st.form_submit_button("Guardar"):
                if u_rut.strip() and u_nom.strip():
                    try:
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?)", (u_rut.strip(), u_nom.strip(), u_cor.strip(), u_tip))
                            conn.commit()
                        st.success(f"¡Usuario '{u_nom}' registrado con éxito!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(f"⛔ Error: El RUT '{u_rut}' ya se encuentra registrado en el sistema.")
                else:
                    st.warning("⚠️ El RUT y el Nombre Completo son campos obligatorios.")
                    
    with t2:
        st.subheader("📋 Nómina General del Establecimiento")
        with obtener_conexion() as conn:
            df_usuarios_completo = pd.read_sql_query("SELECT rut as 'RUT', nombre as 'Nombre Completo', correo as 'Correo Electrónico', tipo_usuario as 'Tipo de Usuario' FROM usuarios ORDER BY nombre ASC", conn)
        
        if not df_usuarios_completo.empty:
            st.dataframe(df_usuarios_completo, use_container_width=True)
        else:
            st.info("No hay usuarios registrados en la base de datos actualmente.")

    # ❌ NUEVA PESTAÑA: ELIMINAR USUARIOS CON VALIDACIÓN
    with t3:
        st.subheader("🗑️ Eliminar Usuario del Sistema")
        if st.session_state["rol"] == "Administrador":
            with obtener_conexion() as conn:
                df_del_u = pd.read_sql_query("SELECT rut, nombre, tipo_usuario FROM usuarios ORDER BY nombre ASC", conn)
            
            if df_del_u.empty:
                st.info("No hay usuarios registrados para eliminar.")
            else:
                with st.form("eliminar_usuario_form"):
                    # Creamos un listado descriptivo para el selectbox
                    lista_usuarios = [f"{row['rut']} - {row['nombre']} ({row['tipo_usuario']})" for _, row in df_del_u.iterrows()]
                    usuario_seleccionado = st.selectbox("Selecciona el usuario que deseas eliminar permanentemente:", lista_usuarios)
                    
                    st.warning("⚠️ Atención: Borrar un usuario no eliminará su historial técnico antiguo, pero impedirá que se le asignen nuevos préstamos.")
                    
                    if st.form_submit_button("🚨 Eliminar Definitivamente"):
                        # Extraemos el RUT antes del guión separador
                        rut_eliminar = usuario_seleccionado.split(" - ")[0].strip()
                        nombre_usuario = usuario_seleccionado.split(" - ")[1].strip()
                        
                        try:
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                # Verificamos primero si tiene un préstamo activo para evitar inconsistencias
                                cursor.execute("SELECT COUNT(*) FROM prestamos WHERE rut = ? AND estado_prestamo = 'Activo'", (rut_eliminar,))
                                if cursor.fetchone()[0] > 0:
                                    st.error(f"⛔ Bloqueado: No se puede eliminar a '{nombre_usuario}' porque tiene un equipo bajo su custodia actualmente.")
                                else:
                                    cursor.execute("DELETE FROM usuarios WHERE rut = ?", (rut_eliminar,))
                                    conn.commit()
                                    st.success(f"¡Usuario '{nombre_usuario}' eliminado correctamente de la base de datos!")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Ocurrió un error inesperado en la base de datos: {e}")
        else:
            st.warning("🔒 Permisos insuficientes: El perfil 'Visor' no puede eliminar usuarios. Solicite acceso de Administrador.")



elif choice == "Préstamo de Equipos":
    st.header("🤝 Módulo de Préstamos y Devoluciones")
    # 📑 Se añade la tercera pestaña "📋 Ver Historial"
    tab1, tab2, tab3 = st.tabs(["🆕 Registrar Préstamo", "🔙 Procesar Devolución", "📋 Ver Historial"])
    
    with obtener_conexion() as conn:
        df_us = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
    
    # --- TAB 1: REGISTRAR PRÉSTAMO ---
    with tab1:
        with obtener_conexion() as conn:
            df_operativos = pd.read_sql_query("SELECT id_equipo, tipo, marca FROM equipos WHERE estado = 'Operativo'", conn)
            df_activos = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo'", conn)
        df_disponibles = df_operativos[~df_operativos["id_equipo"].isin(df_activos["id_equipo"].tolist())]
        
        if df_us.empty:
            st.warning("⚠️ Primero debes registrar al menos un usuario en el Mantenedor de Usuarios.")
        elif df_disponibles.empty:
            st.warning("No hay equipos operativos disponibles en el inventario actual.")
        else:
            with st.form("form_prestamo", clear_on_submit=True):
                equipo_selec = st.selectbox("Selecciona el Equipo Disponible:", [f"{row['id_equipo']} - {row['tipo']} ({row['marca']})" for _, row in df_disponibles.iterrows()])
                usuario_selec_box = st.selectbox("Selecciona el Usuario:", [f"{row['rut']} | {row['nombre']}" for _, row in df_us.iterrows()])
                fecha_p = st.date_input("Fecha de Entrega", date.today())
                fecha_l = st.date_input("Fecha Máxima de Devolución", date.today())
                obs_p = st.text_input("Observaciones de Entrega (Opcional)")
                
                if st.form_submit_button("Confirmar Préstamo"):
                    rut_limpio = usuario_selec_box.split(" | ")[0].strip()
                    nombre_limpio = usuario_selec_box.split(" | ")[1].strip()
                    id_real = equipo_selec.split(" - ")[0].strip()
                    
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM prestamos WHERE rut = ? AND estado_prestamo = 'Activo'", (rut_limpio,))
                        if cursor.fetchone()[0] > 0:
                            st.error(f"⛔ Bloqueado: El usuario {nombre_limpio} ya posee un equipo bajo su custodia.")
                        else:
                            hoy_str = date.today().isoformat()
                            cursor.execute(
                                "INSERT INTO prestamos (id_equipo, usuario, rut, fecha_prestamo, fecha_limite, fecha_devolucion, estado_prestamo, observaciones) VALUES (?, ?, ?, ?, ?, 'Pendiente', 'Activo', ?)", 
                                (id_real, nombre_limpio, rut_limpio, str(fecha_p), str(fecha_l), obs_p)
                            )
                            conn.commit()
                            st.success(f"¡Préstamo del equipo {id_real} registrado con éxito!")
                            st.rerun()
                        
    # --- TAB 2: PROCESAR DEVOLUCIÓN ---
    with tab2:
        with obtener_conexion() as conn:
            df_prestados = pd.read_sql_query("SELECT id_prestamo, id_equipo, usuario, rut, fecha_prestamo, fecha_limite FROM prestamos WHERE estado_prestamo = 'Activo'", conn)
        if df_prestados.empty:
            st.info("No hay préstamos activos en este momento.")
        else:
            st.dataframe(df_prestados, use_container_width=True)
            with st.form("form_devolucion"):
                prestamo_selec = st.selectbox("Selecciona el registro a finalizar:", [f"ID:{row['id_prestamo']} | {row['id_equipo']} - Custodio: {row['usuario']}" for _, row in df_prestados.iterrows()])
                fecha_d = st.date_input("Fecha de Devolución Física", date.today())
                if st.form_submit_button("Registrar Devolución"):
                    id_prestamo_real = int(prestamo_selec.split(" | ")[0].split(":")[1])
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE prestamos SET fecha_devolucion = ?, estado_prestamo = 'Devuelto' WHERE id_prestamo = ?", (str(fecha_d), id_prestamo_real))
                        conn.commit()
                    st.success("Devolución procesada exitosamente. El equipo vuelve a estar disponible.")
                    st.rerun()

    # --- 📋 TAB 3: LISTADO COMPLETO E HISTORIAL (Nueva mejora solicitada) ---
    with tab3:
        st.subheader("📜 Registro Histórico de Movimientos de Hardware")
        
        # Filtros rápidos para facilitar la lectura del laboratorio
        col_f1, col_f2 = st.columns(2)
        filtro_estado_p = col_f1.selectbox("Filtrar por estado del préstamo:", ["Todos", "Activo", "Devuelto"])
        buscar_rut_p = col_f2.text_input("Buscar por RUT o Nombre de usuario:")
        
        query_p = """
            SELECT id_prestamo as 'ID Mov.', id_equipo as 'Código Equipo', usuario as 'Usuario', 
                   rut as 'RUT', fecha_prestamo as 'Fecha Entrega', fecha_limite as 'Fecha Límite', 
                   fecha_devolucion as 'Fecha Retorno', estado_prestamo as 'Estado Préstamo',
                   observaciones as 'Observaciones'
            FROM prestamos WHERE 1=1
        """
        parametros_p = []
        
        if filtro_estado_p != "Todos":
            query_p += " AND estado_prestamo = ?"
            parametros_p.append(filtro_estado_p)
            
        if buscar_rut_p.strip():
            query_p += " AND (rut LIKE ? OR usuario LIKE ?)"
            term_p = f"%{buscar_rut_p.strip()}%"
            parametros_p.extend([term_p, term_p])
            
        query_p += " ORDER BY id_prestamo DESC"
        
        with obtener_conexion() as conn:
            df_historial_prestamos = pd.read_sql_query(query_p, conn, params=parametros_p)
            
        if not df_historial_prestamos.empty:
            # Mostramos métricas de control rápidas
            total_activos = len(df_historial_prestamos[df_historial_prestamos['Estado Préstamo'] == 'Activo'])
            st.metric("Préstamos Vigentes en este filtro", total_activos)
            
            # Desplegamos la tabla prolija
            st.dataframe(df_historial_prestamos, use_container_width=True)
            
            # Botón de exportación masiva del historial
            st.download_button("📥 Descargar Historial Completo (Excel)", to_excel(df_historial_prestamos), "historial_prestamos_establecimiento.xlsx")
        else:
            st.info("No se registran movimientos que coincidan con los criterios de búsqueda.")


# =========================================================================
# 🏢 MÓDULO: GESTIÓN DE SALAS DE CLASES (CON REPORTE Y LISTADO COMPLETO)
# =========================================================================
elif choice == "Gestión de Salas":
    st.header("🏢 Mantenedor de Salas de Clases y Asignación de Hardware")
    # 📑 Se añade la tercera pestaña "📋 Reporte e Historial" solicitado
    tab_sala1, tab_sala2, tab_sala3 = st.tabs(["➕ Crear Salas", "💻 Asignar Equipos", "📋 Reporte e Historial"])

    # Extraer la nómina de funcionarios (Profesores y Técnicos) para los formularios
    with obtener_conexion() as conn:
        df_funcionarios_disp = pd.read_sql_query(
            "SELECT nombre, tipo_usuario FROM usuarios WHERE tipo_usuario IN ('Profesor', 'Técnico') ORDER BY nombre ASC", 
            conn
        )

    # --- TAB 1: CREAR Y VER SALAS ---
    with tab_sala1:
        if st.session_state["rol"] == "Administrador":
            with st.form("nueva_sala_form", clear_on_submit=True):
                st.subheader("Registrar Nueva Sala de Clases")
                col_s1, col_s2, col_s3 = st.columns(3)
                
                n_sala = col_s1.text_input("Nombre de Sala)")
                
                if not df_funcionarios_disp.empty:
                    lista_encargados = [f"{row['nombre']} ({row['tipo_usuario']})" for _, row in df_funcionarios_disp.iterrows()]
                    lista_encargados.insert(0, "Sin Funcionario a Cargo (Temporal)")
                    enc_sala_seleccionado = col_s2.selectbox("👤 Funcionario / Usuario a Cargo:", lista_encargados)
                else:
                    enc_sala_seleccionado = col_s2.selectbox("👤 Funcionario / Usuario a Cargo:", ["⚠️ No hay Profesores/Técnicos creados"], disabled=True)
                
                cap_sala = col_s3.number_input("Capacidad de Alumnos", min_value=1, value=30, step=1)
                
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
                lista_equipos_strings = [f"{row['id_equipo']} - {row['tipo']} {row['marca']} (Ubicación: {row['ubicacion']})" for _, row in df_equipos_disp.iterrows()]
                equipo_seleccionado = st.selectbox("2. Selecciona el Equipo a Trasladar:", lista_equipos_strings)
                detalle_ubicacion_especifica = st.text_input("3. Detalle específico (ej: Fila 2 - Computador Profesor):")

                if st.form_submit_button("Confirmar Traslado de Espacio"):
                    id_equipo_real = equipo_seleccionado.split(" - ")[0].strip()
                    ubicacion_final = f"{sala_seleccionada} - {detalle_ubicacion_especifica.strip()}" if detalle_ubicacion_especifica.strip() else sala_seleccionada
                    
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE equipos SET ubicacion = ? WHERE id_equipo = ?", (ubicacion_final, id_equipo_real))
                        conn.commit()
                    st.success(f"🚀 ¡El equipo {id_equipo_real} fue trasladado y reasignado a: {ubicacion_final}!")
                    st.rerun()

    # --- 📋 TAB 3: REPORTES Y NOMINA DE SALAS (Nueva mejora solicitada) ---
    with tab_sala3:
        st.subheader("📋 Nómina y Reporte de Salas en la Escuela")
        
        with obtener_conexion() as conn:
            df_salas_completo = pd.read_sql_query(
                "SELECT id_sala as 'ID Sala', nombre_sala as 'Nombre de la Sala', encargado as 'Funcionario Responsable', capacidad as 'Capacidad (Alumnos)' FROM salas ORDER BY nombre_sala ASC", 
                conn
            )
        
        if not df_salas_completo.empty:
            # Métrica indicadora en la parte superior
            st.metric("Total de Salas Implementadas", len(df_salas_completo))
            
            # Tabla interactiva con los datos de las salas
            st.dataframe(df_salas_completo, use_container_width=True)
            
            # Botón para exportar listado de salas a Excel
            st.download_button("📥 Descargar Reporte de Salas (Excel)", to_excel(df_salas_completo), "reporte_salas_escuela.xlsx")
        else:
            st.info("No se registran salas implementadas en la base de datos todavía.")

        # Buscador cruzado de hardware por sala integrado
        st.markdown("---")
        st.subheader("🔍 Consultar Equipamiento Asignado por Sala")
        if not df_salas_disp.empty:
            sala_filtro = st.selectbox("Selecciona un sector para auditar su hardware interno:", ["Ver Todo el Establecimiento"] + df_salas_disp["nombre_sala"].tolist())
            
            query_filtro = "SELECT id_equipo as 'ID Equipo', tipo as 'Tipo Hardware', marca as 'Marca', modelo as 'Modelo', estado as 'Estado Técnico', ubicacion as 'Ubicación Detallada' FROM equipos WHERE estado != 'De Baja'"
            if sala_filtro != "Ver Todo el Establecimiento":
                query_filtro += f" AND ubicacion LIKE '{sala_filtro}%'"
            
            with obtener_conexion() as conn:
                df_resultado_filtro = pd.read_sql_query(query_filtro, conn)
                
            if not df_resultado_filtro.empty:
                st.dataframe(df_resultado_filtro, use_container_width=True)
                st.caption(f"💡 Total de dispositivos localizados en esta zona: {len(df_resultado_filtro)} unidades.")
            else:
                st.info(f"La sala '{sala_filtro}' no registra hardware asignado en este momento.")
        else:
            st.caption("Cree una sala de clases para activar el visor de auditoría cruzada.")


elif choice == "Infraestructura de Sala":
    st.header("🔌 Infraestructura")
    with st.form("i_f"):
        el = st.text_input("Elemento:")
        ub = st.text_input("Ubicación:")
        if st.form_submit_button("Guardar"):
            with obtener_conexion() as conn:
                conn.cursor().execute("INSERT INTO infraestructura (elemento, ubicacion) VALUES (?, ?)", (el, ub))
                conn.commit()
            st.success("Registrado.")

elif choice == "Registro de Compras":
    st.header("💰 Historial de Compras")
    with st.form("c_f"):
        it = st.text_input("Artículo:")
        ca = st.number_input("Cantidad:", min_value=1)
        co = st.number_input("Costo:", min_value=0.0)
        if st.form_submit_button("Registrar Compra"):
            with obtener_conexion() as conn:
                conn.cursor().execute("INSERT INTO compras (item, cantidad, costo_unitario) VALUES (?, ?, ?)", (it, ca, co))
                conn.commit()
            st.success("Compra guardada.")

# 🚀 NUEVA RUTA MODULAR CALIBRADA: Llama al archivo externo sin colapsar el prompt

# =========================================================================
# 🖨️ MÓDULO: GENERADOR DE QR COMPACTO PRO (NATIVO ADHESIVO)
# =========================================================================
elif choice == "Generador de QR":
    import zipfile
    st.header("🖨️ Generador Avanzado de Etiquetas QR")
    nombre_institucion = st.text_input("🏫 Institución para la Etiqueta:", "LICEO FELIPE CUBILLOS").strip()
    
    with obtener_conexion() as conn:
        df_qr_equipos = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, estado, ubicacion, num_documento, proveedor_origen, costo_compra FROM equipos", conn)
    
    st.markdown("### ⚙️ Configuración Física de la Hoja de Etiquetas")
    with st.expander("📐 Ajustar Dimensiones de la Plantilla de Impresión", expanded=False):
        col_c1, col_c2, col_c3 = st.columns(3)
        columnas_hoja = col_c1.slider("Columnas por fila en papel adhesivo:", 2, 5, 3)
        ancho_etiqueta = col_c2.slider("Ancho de cada etiqueta (px):", 120, 300, 180)
        padding_etiqueta = col_c3.slider("Espaciado interno (Padding px):", 5, 25, 10)
        col_c4, col_c5 = st.columns(2)
        tamano_borde = col_c4.selectbox("Borde para corte:", ["Línea Segmentada", "Línea Continua", "Sin Borde"])
        estilo_borde_css = "2px dashed #000" if tamano_borde == "Línea Segmentada" else ("1px solid #000" if tamano_borde == "Línea Continua" else "none")
        incluir_bajada = col_c5.checkbox("Incluir texto aclaratorio inferior", value=True)

    st.markdown("---")
    modo_generacion = st.radio("Método de Generación:", ["Selección Única", "Selección Masiva por Ticket / Auto"], horizontal=True)
    df_filtrado_qr = pd.DataFrame()
    
    if df_qr_equipos.empty:
        st.warning("⚠️ El inventario está vacío. Registra equipos en 'Inventario de Equipos' primero.")
    else:
        tipos_disp = ["Todos los Tipos"] + sorted(df_qr_equipos["tipo"].unique().tolist())
        tipo_seleccionado = st.selectbox("🔍 Filtrar lista por Tipo de Equipo:", tipos_disp)
        df_base_f = df_qr_equipos if tipo_seleccionado == "Todos los Tipos" else df_qr_equipos[df_qr_equipos["tipo"] == tipo_seleccionado]
        
        if modo_generacion == "Selección Única" and not df_base_f.empty:
            lista_opciones_qr = [f"{row['id_equipo']} - {row['tipo']}" for _, row in df_base_f.iterrows()]
            seleccion_equipo = st.selectbox("Selecciona el Equipo Específico:", lista_opciones_qr)
            df_filtrado_qr = df_base_f[df_base_f['id_equipo'] == seleccion_equipo.split(" - ")[0].strip()]
        elif modo_generacion != "Selección Única" and not df_base_f.empty:
            if tipo_seleccionado == "Todos los Tipos":
                st.success(f"🚀 Modo Auto-Generación Activo: {len(df_qr_equipos)} equipos listos.")
                df_filtrado_qr = df_qr_equipos
            else:
                with st.expander("🗂️ Ver Casillas de Activos y Seleccionar", expanded=True):
                    cols_ticket = st.columns(3)
                    items_sel = []
                    for idx, row in df_base_f.reset_index(drop=True).iterrows():
                        if cols_ticket[idx % 3].checkbox(f"[{row['id_equipo']}] {row['tipo']}", value=False, key=f"chk_t_{row['id_equipo']}_{idx}"):
                            items_sel.append(row['id_equipo'])
                if items_sel:
                    df_filtrado_qr = df_base_f[df_base_f['id_equipo'].isin(items_sel)]
                else:
                    st.info("💡 Selecciona las casillas de los equipos arriba.")
                    
    if not df_filtrado_qr.empty:
        st.markdown("---")
        st.markdown("### 📊 Contenido Interno del Código QR")
        with st.expander("📝 Selecciona los datos que se guardarán DENTRO del código al escanear", expanded=True):
            col_d1, col_d2, col_d3 = st.columns(3)
            inc_id_ref = col_d1.checkbox("ID / Código", value=True, key="cfg_int_id_ref")
            inc_tipo = col_d1.checkbox("Tipo de Hardware", value=True, key="cfg_int_tipo")
            inc_marca = col_d1.checkbox("Marca y Modelo", value=True, key="cfg_int_marca")
            
            inc_ubic = col_d2.checkbox("Ubicación / Sala", value=True, key="cfg_int_ubic")
            inc_factura = col_d2.checkbox("Nro. Factura / Boleta", value=False, key="cfg_int_factura")
            inc_costo = col_d2.checkbox("Costo de Compra ($)", value=False, key="cfg_int_costo")
            
            # 🚀 MEJORA SOLICITADA: Agregamos la casilla de enlace al Historial Técnico Digital
            inc_historial_digital = col_d3.checkbox("🔗 Enlazar a Historial Técnico Digital (Acceso Remoto)", value=True, key="cfg_int_hist_dig")
            if inc_historial_digital:
                st.info("💡 Al escanear, abrirá directamente la Hoja de Vida y Reparaciones de este equipo en el navegador.")

        # 1. Compilar códigos QR en memoria RAM construyendo el texto y enlaces elegidos
        lista_bytes_qr = {}
        for idx, datos_fila in df_filtrado_qr.iterrows():
            txt = []
            
            # 🚀 LÓGICA: Si la casilla está marcada, inyectamos la URL base de red local al principio del QR
            if inc_historial_digital:
                # El parámetro ?buscar_id alimenta automáticamente al buscador dinámico del Inventario
                txt.append(f"http://localhost:8501/?buscar_id={datos_fila['id_equipo']}")
            
            if inc_id_ref: 
                txt.append(f"ID/Código: {datos_fila['id_equipo']}")
            else:
                txt.append(f"Ref: {datos_fila['id_equipo']}")
                
            if inc_tipo: txt.append(f"Tipo: {datos_fila['tipo']}")
            if inc_marca: txt.append(f"Mod: {datos_fila['marca']} {datos_fila['modelo']}")
            if inc_ubic: txt.append(f"Ubic: {datos_fila['ubicacion']}")
            if inc_factura: txt.append(f"Fact: {datos_fila['num_documento']}")
            if inc_costo: txt.append(f"Costo: ${datos_fila['costo_compra'] if datos_fila['costo_compra'] is not None else 0:.0f}")
            
            # El separador " | " ayuda a que las aplicaciones de escaneo lean el resto de los datos en orden si no tienen internet
            qr_local = segno.make_qr(" | ".join(txt), error='m')
            buffer = io.BytesIO()
            qr_local.save(buffer, kind='png', scale=5, border=2)
            lista_bytes_qr[datos_fila['id_equipo']] = buffer.getvalue()

        # 🔥 FILTRO QUIRÚRGICO CSS PARA IMPRESIÓN LIMPIA (Se mantiene idéntico abajo)
        st.markdown(f"""
            <style>
            @media print {{
                div[data-testid="stSidebar"], header, footer, div[data-testid="stHeader"], 
                div[class*="stRadio"], div[class*="stSelectbox"], div[class*="stTextInput"], 
                div[class*="stForm"], div.stAlert, div.stButton, .stDownloadButton, 
                [data-testid="stExpander"], h1, h2, h3, hr, p:not(.txt-eq), span:not(.txt-eq),
                div.stMarkdown:not(.zona-etiquetas) {{ 
                    display: none !important; 
                }}
                div[data-testid="stHorizontalBlock"] {{ display: flex !important; flex-direction: row !important; flex-wrap: wrap !important; width: 100% !important; gap: 5mm !important; }}
                div[data-testid="stColumn"] {{ min-width: {ancho_etiqueta}px !important; max-width: {ancho_etiqueta}px !important; width: {ancho_etiqueta}px !important; margin: 2mm !important; page-break-inside: avoid !important; display: block !important; }}
                .main, .main .block-container, [data-testid="stAppViewContainer"], [data-testid="stApp"], html, body {{ padding: 0mm !important; margin: 0mm !important; padding-top: 0mm !important; margin-top: 0mm !important; max-width: 100% !important; display: block !important; height: auto !important; min-height: auto !important; overflow: visible !important; position: relative !important; top: 0 !important; }}
                div[data-testid="stImage"], div[data-testid="stImage"] img {{ display: block !important; width: 100% !important; height: auto !important; }}
                * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                @page {{ margin: 6mm !important; size: auto; }}
            }}
            </style>
        """, unsafe_allow_html=True)

               # 2. Desplegar los disparadores colectivos superiores en pantalla
        if len(df_filtrado_qr) > 1:
            st.subheader("🛠️ Acciones Colectivas Masivas")
            col_masiva1, col_masiva2 = st.columns(2)
            
            # Generamos una estampa de tiempo única y segura para este lote de renderizado
            ts_lote_masivo = datetime.now().strftime("%H%M%S")
            cantidad_items_lote = len(df_filtrado_qr)
            
            with col_masiva1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for id_eq, bytes_img in lista_bytes_qr.items():
                        zip_file.writestr(f"QR_{id_eq}.png", bytes_img)
                
                st.download_button(
                    label=f"📥 Descargar {cantidad_items_lote} QRs en lote (.ZIP)", 
                    data=zip_buffer.getvalue(), 
                    file_name=f"lote_qr_{datetime.now().strftime('%Y%m%d')}.zip", 
                    mime="application/zip", 
                    key=f"btn_descarga_masiva_zip_{cantidad_items_lote}_{ts_lote_masivo}",
                    use_container_width=True
                )
                
            with col_masiva2:
                # 🚀 CORRECCIÓN CRÍTICA: Se añade una clave dinámica única basada en tiempo y cantidad de ítems
                if st.button("🖨️ Preparar Hoja para Imprimir (Ctrl + P)", key=f"btn_imprimir_hoja_masiva_pro_{cantidad_items_lote}_{ts_lote_masivo}", use_container_width=True):
                    st.info("💡 Todo configurado. Ahora presiona **Ctrl + P** en tu teclado físico para ver tu papel de etiquetas.")
                    
        elif len(df_filtrado_qr) == 1:
            # Blindamos también de forma segura la extracción del ID individual
            id_unico_seleccionado = str(df_filtrado_qr.iloc[0]['id_equipo']).strip().lower().replace("-", "_") if not df_filtrado_qr.empty else "indiv"
            ts_indiv = datetime.now().strftime("%H%M%S")
            
            if st.button("🖨️ Imprimir esta Etiqueta Individual (Ctrl + P)", key=f"btn_print_indiv_{id_unico_seleccionado}_{ts_indiv}", use_container_width=True):
                st.info("💡 Presiona las teclas **Ctrl + P** en tu equipo.")

        
        elif len(df_filtrado_qr) == 1:
            # 🚀 CORRECCIÓN CRÍTICA: Se añade una 'key' dinámica usando el ID del equipo seleccionado para blindar la app contra duplicados
            id_unico_seleccionado = df_filtrado_qr.iloc[0]['id_equipo']
            if st.button("🖨️ Imprimir esta Etiqueta Individual (Ctrl + P)", key=f"btn_print_indiv_{id_unico_seleccionado}", use_container_width=True):
                st.info("💡 Presiona las teclas **Ctrl + P** en tu equipo.")

        # 3. CONSTRUCCIÓN DE LA PLANTILLA REORDENADA CON COMPONENTES PROTEGIDOS
        st.markdown("### 📋 Vista Previa de la Plantilla")
        st.markdown('<div class="zona-etiquetas">', unsafe_allow_html=True)
        
        columnas_grilla = st.columns(columnas_hoja)
        # Forzamos un reset_index limpio para la grilla posicional
        df_render_final = df_filtrado_qr.reset_index(drop=True)
        
        # Generamos un marcador de tiempo único para evitar colisiones entre recargas de página
        id_sesion_tiempo = datetime.now().strftime("%H%M%S")
        
        for idx, datos_fila in df_render_final.iterrows():
            id_actual = datos_fila['id_equipo']
            bytes_raw = lista_bytes_qr[id_actual]
            
            # Limpiamos el ID quitando espacios y caracteres raros para la clave del widget
            id_clave_segura = str(id_actual).strip().lower().replace("-", "_")
            
            with columnas_grilla[idx % columnas_hoja]:
                with st.container(border=True if tamano_borde != "Sin Borde" else False):
                    st.markdown(f"<p class='txt-eq' style='text-align:center; font-size:11px; font-weight:bold; margin:0; text-transform:uppercase; color:#000;'>{nombre_institucion}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='txt-eq' style='text-align:center; font-family:monospace; font-size:13px; font-weight:bold; margin:2px 0; color:#000;'>ID: {id_actual}</p>", unsafe_allow_html=True)
                    st.image(bytes_raw, width=ancho_etiqueta - 20 if ancho_etiqueta > 40 else 100)
                    if incluir_bajada:
                        st.markdown("<p class='txt-eq' style='text-align:center; font-size:9px; font-style:italic; margin:0; color:#555;'>Escanee para validar historial</p>", unsafe_allow_html=True)
                
                # 🚀 CORRECCIÓN CRÍTICA: Clave dinámica triple blindada contra duplicados invisibles de Streamlit
                st.download_button(
                    label=f"💾 Guardar {id_actual}", 
                    data=bytes_raw, 
                    file_name=f"QR_{id_actual}.png", 
                    mime="image/png", 
                    key=f"btn_dl_f_{id_clave_segura}_{idx}_{id_sesion_tiempo}", 
                    use_container_width=True
                )
                
        st.markdown('</div>', unsafe_allow_html=True)

                 # 2. Desplegar los disparadores colectivos superiores en pantalla
        if len(df_filtrado_qr) > 1:
            st.subheader("🛠️ Acciones Colectivas Masivas")
            col_masiva1, col_masiva2 = st.columns(2)
            
            # 🚀 CORRECCIÓN CRÍTICA: Limpiamos el nombre del tipo seleccionado para usarlo como clave estática única
            tipo_clave_segura = str(tipo_seleccionado).strip().lower().replace(" ", "_")
            cantidad_items_lote = len(df_filtrado_qr)
            
            with col_masiva1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for id_eq, bytes_img in lista_bytes_qr.items():
                        zip_file.writestr(f"QR_{id_eq}.png", bytes_img)
                
                # 🔑 Clave fija amarrada al tipo de filtro (ej: btn_zip_lote_5_notebook)
                st.download_button(
                    label=f"📥 Descargar {cantidad_items_lote} QRs en lote (.ZIP)", 
                    data=zip_buffer.getvalue(), 
                    file_name=f"lote_qr_{datetime.now().strftime('%Y%m%d')}.zip", 
                    mime="application/zip", 
                    key=f"btn_zip_lote_{cantidad_items_lote}_{tipo_clave_segura}",
                    use_container_width=True
                )
                
            with col_masiva2:
                # 🔑 Clave fija amarrada al tipo de filtro (ej: btn_print_lote_5_notebook)
                if st.button("🖨️ Preparar Hoja para Imprimir (Ctrl + P)", key=f"btn_print_lote_{cantidad_items_lote}_{tipo_clave_segura}", use_container_width=True):
                    st.info("💡 Todo configurado. Ahora presiona **Ctrl + P** en tu teclado físico para ver tu papel de etiquetas.")
                    
        elif len(df_filtrado_qr) == 1:
            # Para el modo individual, usamos el ID físico directo del equipo (ej: pc_01), que es único por naturaleza
            id_unico_seleccionado = str(df_filtrado_qr.iloc[0]['id_equipo']).strip().lower().replace("-", "_") if not df_filtrado_qr.empty else "indiv"
            
            if st.button("🖨️ Imprimir esta Etiqueta Individual (Ctrl + P)", key=f"btn_print_indiv_final_{id_unico_seleccionado}", use_container_width=True):
                st.info("💡 Presiona las teclas **Ctrl + P** en tu equipo.")
                    
        elif len(df_filtrado_qr) == 1:
            id_unico_seleccionado = str(df_filtrado_qr.iloc[0]['id_equipo']).strip().lower().replace("-", "_")
            if st.button("🖨️ Imprimir esta Etiqueta Individual (Ctrl + P)", key=f"btn_print_indiv_{id_unico_seleccionado}", use_container_width=True):
                st.info("💡 Presiona las teclas **Ctrl + P** en tu equipo.")

                
        st.markdown("### 📋 Vista Previa de la Plantilla")
        st.markdown('<div class="zona-etiquetas">', unsafe_allow_html=True)
        columnas_grilla = st.columns(columnas_hoja)
        for idx, datos_fila in df_filtrado_qr.reset_index(drop=True).iterrows():
            id_actual = datos_fila['id_equipo']
            bytes_raw = lista_bytes_qr[id_actual]
            with columnas_grilla[idx % columnas_hoja]:
                with st.container(border=True if tamano_borde != "Sin Borde" else False):
                    st.markdown(f"<p class='txt-eq' style='text-align:center; font-size:11px; font-weight:bold; margin:0; text-transform:uppercase; color:#000;'>{nombre_institucion}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='txt-eq' style='text-align:center; font-family:monospace; font-size:13px; font-weight:bold; margin:2px 0; color:#000;'>ID: {id_actual}</p>", unsafe_allow_html=True)
                    st.image(bytes_raw, width=ancho_etiqueta - 20 if ancho_etiqueta > 40 else 100)
                    if incluir_bajada:
                        st.markdown("Escanee para validar historial", unsafe_allow_html=True)
                        st.download_button(f"💾 Guardar {id_actual}", bytes_raw, f"QR_{id_actual}.png", "image/png", key=f"btn_dl_f_{id_actual}_{idx}", use_container_width=True)
                        st.markdown('', unsafe_allow_html=True)

# =========================================================================
# 💾 MÓDULO: RESPALDO DE SEGURIDAD (CORREGIDO SIN VARIABLES GLOBALES)
# =========================================================================
elif choice == "Respaldo de Seguridad":
    st.header("💾 Copias de Seguridad")
    if st.button("🔄 Generar Respaldo Local de Seguridad"):
        # Creamos la carpeta si no existe en el directorio de la escuela
        if not os.path.exists("respaldos"): 
            os.makedirs("respaldos")
            
        # 🚀 CORRECCIÓN: Usamos el string "laboratorio.db" directamente en lugar de la variable DB_NAME
        nombre_archivo_backup = f"respaldos/respaldo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        try:
            shutil.copyfile("laboratorio.db", nombre_archivo_backup)
            st.success(f"✅ ¡Base de datos respaldada con éxito en: '{nombre_archivo_backup}'!")
        except Exception as e:
            st.error(f"⛔ Ocurrió un error al intentar copiar el archivo de base de datos: {e}")
    elif choice == "Respaldo de Seguridad":
        st.title("🗄️ Copias de Seguridad del Laboratorio")
        st.write("Administra tus respaldos tanto en entorno local como en la nube.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("1. Descargar Respaldo")
            st.write("Guarda una copia de la base de datos actual en tu computadora.")
            
            datos_db = obtener_bytes_db()
            if datos_db is not None:
                st.download_button(
                    label="📥 Descargar laboratorio.db",
                    data=datos_db,
                    file_name="respaldo_laboratorio.db",
                    mime="application/x-sqlite3",
                    use_container_width=True
                )
            else:
                st.warning("No se encontró la base de datos.")

        with col2:
            st.subheader("2. Restaurar Respaldo")
            st.write("Sube un archivo .db para actualizar el sistema.")
            
            archivo_subido = st.file_uploader(
                "Selecciona tu archivo de respaldo (.db)", 
                type=["db"],
                key="restaurador_db"
            )
            
            if archivo_subido is not None:
                if st.button("🔄 Aplicar y Actualizar Base de Datos", type="primary", use_container_width=True):
                    try:
                        bytes_subidos = archivo_subido.read()
                        restaurar_db_desde_bytes(bytes_subidos)
                        inicializar_db()
                        st.success("✅ ¡Base de datos actualizada!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    elif choice == "Bitácora de Notas":  # <-- Línea 1021 (Ahora Python la leerá perfecto)
        st.title("📝 Bitácora de Notas")
        # Aquí continúa tu código normal de la bitácora...


# =========================================================================
# 📝 MÓDULO: BITÁCORA DE NOVEDADES (CON ESTADO PENDIENTE/EJECUTADA Y FECHAS)
# =========================================================================
elif choice == "Bitácora de Notas":
    st.header("📝 Bitácora de Novedades Diarias del Laboratorio")
    
    # 🛡️ PARCHE AUTO-ACTUALIZADOR INTERNO: Asegura que la BD tenga las columnas de estado y ejecución
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        for col_name, col_type in [("estado_nota", "TEXT DEFAULT 'Pendiente'"), ("fecha_ejecucion", "TEXT DEFAULT 'N/A'")]:
            try:
                cursor.execute(f"ALTER TABLE bitacora ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass
        conn.commit()

    # 📑 Estructuración de pestañas operativas
    t_bit1, t_bit2, t_bit3, t_bit4 = st.tabs(["➕ Añadir Nota", "🔄 Modificar / Cerrar Nota", "❌ Eliminar Nota", "📋 Ver Listado Completo"])
    
    # --- TAB 1: AÑADIR NUEVA NOTA ---
    with t_bit1:
        with st.form("nueva_nota_form", clear_on_submit=True):
            texto_nota = st.text_area("Escribe la novedad detectada hoy:")
            col_add1, col_add2 = st.columns(2)
            est_inicial = col_add1.selectbox("Estado Inicial:", ["Pendiente", "Ejecutada"])
            
            # Fecha de ejecución opcional si nace completada
            f_ej_inicial = "N/A"
            if est_inicial == "Ejecutada":
                f_ej_inicial = str(col_add2.date_input("Fecha de Ejecución:", date.today()))
                
            if st.form_submit_button("Guardar Nota en Bitácora"):
                if texto_nota.strip():
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO bitacora (nota, fecha, hora, estado_nota, fecha_ejecucion) VALUES (?, ?, ?, ?, ?)", 
                            (texto_nota.strip(), date.today().isoformat(), datetime.now().strftime("%H:%M:%S"), est_inicial, f_ej_inicial)
                        )
                        conn.commit()
                    st.success("✅ Nota almacenada exitosamente en la bitácora.")
                    st.rerun()
                else:
                    st.warning("⚠️ No puedes guardar una nota vacía.")

    # --- TAB 2: MODIFICAR ESTADO Y TEXTO DE UNA NOTA ---
    with t_bit2:
        st.subheader("🔄 Modificar o Resolver Tareas de la Bitácora")
        with obtener_conexion() as conn:
            df_notas_disp = pd.read_sql_query("SELECT id_nota, fecha, hora, nota, estado_nota, fecha_ejecucion FROM bitacora ORDER BY id_nota DESC LIMIT 50", conn)
        
        if df_notas_disp.empty:
            st.info("No hay novedades registradas para modificar.")
        else:
            opciones_notas = [f"ID:{row['id_nota']} | Est: {row['estado_nota']} | {row['fecha']} - {row['nota'][:30]}..." for _, row in df_notas_disp.iterrows()]
            nota_a_modificar = st.selectbox("Selecciona la nota que deseas editar o resolver:", opciones_notas, key="sb_mod_nota")
            
            # Extracción segura del ID sin errores de split
            parte_id_texto = nota_a_modificar.split(" | ")
            id_nota_mod = int(parte_id_texto[0].split(":")[1])
            
            # Extraer registro específico seleccionado
            registro_fila = df_notas_disp[df_notas_disp['id_nota'] == id_nota_mod].iloc[0]
            texto_actual = str(registro_fila['nota'])
            estado_actual = str(registro_fila['estado_nota'])
            fecha_ej_actual = str(registro_fila['fecha_ejecucion'])
            
            with st.form("form_modificar_nota"):
                st.caption(f"📝 Editando nota ID: {id_nota_mod} (Registrada originalmente el {registro_fila['fecha']})")
                nuevo_texto_nota = st.text_area("Corregir texto de la novedad:", value=texto_actual)
                
                col_mod1, col_mod2 = st.columns(2)
                nuevo_estado = col_mod1.selectbox("Cambiar Estado de la Nota:", ["Pendiente", "Ejecutada"], index=["Pendiente", "Ejecutada"].index(estado_actual) if estado_actual in ["Pendiente", "Ejecutada"] else 0)
                
                # Gestión de fecha de resolución dinámica
                if nuevo_estado == "Ejecutada":
                    val_fecha_def = date.today() if fecha_ej_actual == "N/A" else date.fromisoformat(fecha_ej_actual)
                    f_ejecucion_final = str(col_mod2.date_input("Fecha de Resolución / Ejecución:", val_fecha_def))
                else:
                    f_ejecucion_final = "N/A"
                    col_mod2.info("⏳ Nota marcada como Pendiente de resolución.")
                
                if st.form_submit_button("Actualizar y Guardar Cambios"):
                    if nuevo_texto_nota.strip():
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE bitacora SET nota = ?, estado_nota = ?, fecha_ejecucion = ? WHERE id_nota = ?", 
                                (nuevo_texto_nota.strip(), nuevo_estado, f_ejecucion_final, id_nota_mod)
                            )
                            conn.commit()
                        st.success("✅ Cambios y estados guardados correctamente.")
                        st.rerun()
                    else:
                        st.error("El texto de la nota no puede quedar vacío.")

    # --- TAB 3: ELIMINAR NOTA PERMANENTEMENTE ---
    with t_bit3:
        st.subheader("🗑️ Eliminar Registro de la Bitácora")
        if st.session_state["rol"] == "Administrador":
            with obtener_conexion() as conn:
                df_notas_del = pd.read_sql_query("SELECT id_nota, fecha, hora, nota FROM bitacora ORDER BY id_nota DESC LIMIT 50", conn)
            
            if df_notas_del.empty:
                st.info("No hay registros en la bitácora para eliminar.")
            else:
                with st.form("eliminar_nota_form"):
                    opciones_del = [f"ID:{row['id_nota']} | {row['fecha']} {row['hora']} - {row['nota'][:40]}..." for _, row in df_notas_del.iterrows()]
                    nota_a_eliminar = st.selectbox("Selecciona la nota que deseas borrar permanentemente:", opciones_del, key="sb_del_nota")
                    
                    parte_id_del_texto = nota_a_eliminar.split(" | ")
                    id_nota_del = int(parte_id_del_texto[0].split(":")[1])
                    
                    st.warning("⚠️ Cuidado: Esta acción es destructiva y eliminará permanentemente la nota.")
                    
                    if st.form_submit_button("🚨 Eliminar Nota Definitivamente"):
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM bitacora WHERE id_nota = ?", (id_nota_del,))
                            conn.commit()
                        st.success("¡El registro de la bitácora fue eliminado exitosamente!")
                        st.rerun()
        else:
            st.warning("🔒 Permisos insuficientes: Solo un perfil Administrador puede borrar registros.")

    # --- TAB 4: VER LISTADO COMPLETO Y EXPORTAR ---
    with t_bit4:
        st.subheader("📋 Historial Cronológico de Novedades")
        
        col_fil1, col_fil2 = st.columns(2)
        filtro_estado = col_fil1.selectbox("Filtrar por Estado Técnico:", ["Todas las Notas", "Solo Pendientes", "Solo Ejecutadas"])
        buscar_palabra = col_fil2.text_input("🔍 Buscar notas por palabra clave:")
        
        query_bit = "SELECT id_nota as 'ID', fecha as 'Fecha Registro', hora as 'Hora Registro', nota as 'Novedad / Observación', estado_nota as 'Estado', fecha_ejecucion as 'Fecha Ejecución' FROM bitacora WHERE 1=1"
        parametros_bit = []
        
        if filtro_estado == "Solo Pendientes":
            query_bit += " AND estado_nota = 'Pendiente'"
        elif filtro_estado == "Solo Ejecutadas":
            query_bit += " AND estado_nota = 'Ejecutada'"
            
        if buscar_palabra.strip():
            query_bit += " AND nota LIKE ?"
            parametros_bit.append(f"%{buscar_palabra.strip()}%")
            
        query_bit += " ORDER BY id_nota DESC"
        
        with obtener_conexion() as conn:
            df_bitacora_completa = pd.read_sql_query(query_bit, conn, params=parametros_bit)
            
        if not df_bitacora_completa.empty:
            c_m1, c_m2 = st.columns(2)
            c_m1.metric("Total de Novedades Registradas", len(df_bitacora_completa))
            c_m2.metric("Tareas Pendientes de Resolución", len(df_bitacora_completa[df_bitacora_completa['Estado'] == 'Pendiente']))
            
            st.dataframe(df_bitacora_completa, use_container_width=True)
            st.download_button("📥 Descargar Bitácora Completa (Excel)", to_excel(df_bitacora_completa), "bitacora_novedades_laboratorio.xlsx", key="btn_download_bit_excel")
        else:
            st.info("No se registran novedades en la bitácora que coincidan con la búsqueda.")

# =========================================================================
# 📧 MÓDULO: ENVÍO DE AVISOS DE COBRANZA (MASIVO E INDIVIDUAL POR API WEB)
# =========================================================================
elif choice == "Envío de Avisos":
    st.header("📧 Centro de Notificaciones de Cobranza")
    
    query_mora_global = """
        SELECT p.id_prestamo, p.id_equipo, p.usuario, p.rut, p.fecha_limite, u.correo 
        FROM prestamos p 
        INNER JOIN usuarios u ON p.rut = u.rut 
        WHERE p.estado_prestamo = 'Activo'
    """
    with obtener_conexion() as conn:
        df_notif_global = pd.read_sql_query(query_mora_global, conn)
    
    hoy_dt = pd.to_datetime(date.today())
    
    if df_notif_global.empty:
        st.success("✅ ¡Excelente! No se registran préstamos activos en el sistema actualmente.")
    else:
        df_notif_global['fecha_limite_dt'] = pd.to_datetime(df_notif_global['fecha_limite'], errors='coerce')
        df_morosos_global = df_notif_global[df_notif_global['fecha_limite_dt'] < hoy_dt].copy()
        
        if df_morosos_global.empty:
            st.success("✅ ¡Todo al día! Todos los préstamos vigentes se encuentran dentro del plazo.")
        else:
            df_morosos_global['dias_atraso'] = (hoy_dt - df_morosos_global['fecha_limite_dt']).dt.days
            
            df_vista_escuela = df_morosos_global[['id_equipo', 'usuario', 'correo', 'fecha_limite', 'dias_atraso']].copy()
            df_vista_escuela.columns = ['Código Hardware', 'Usuario Custodio', 'Correo Electrónico', 'Fecha Límite', 'Días de Retraso']
            
            st.warning(f"⚠️ Atención: Se han detectado **{len(df_morosos_global)} deudores vigentes** fuera de plazo.")
            st.dataframe(df_vista_escuela, use_container_width=True)
            
            st.markdown("### 🚀 Acciones de Despacho Masivo")
            col_masiva_mail, _ = st.columns([0.4, 0.6])
            
            with col_masiva_mail:
                if st.button("🚨 Enviar Alertas Masivas a Todos los Morosos", key="btn_envio_masivo_global_notif", use_container_width=True):
                    contador_exitos = 0
                    progreso_envio = st.progress(0, text="Iniciando ráfaga de correos...")
                    
                    for idx, (index_fila, fila_deudor) in enumerate(df_morosos_global.iterrows()):
                        exito_rafaga = enviar_correo_mora_local(
                            fila_deudor['correo'], 
                            fila_deudor['usuario'], 
                            fila_deudor['id_equipo'], 
                            fila_deudor['fecha_limite'], 
                            fila_deudor['dias_atraso']
                        )
                        if exito_rafaga:
                            contador_exitos += 1
                        
                        porcentaje_carga = (idx + 1) / len(df_morosos_global)
                        progreso_envio.progress(porcentaje_carga, text=f"Notificando a: {fila_deudor['usuario']}...")
                    
                    progreso_envio.empty()
                    st.success(f"📬 Ráfaga finalizada. Se enviaron {contador_exitos} notificaciones.")
                    st.rerun()
            
            st.markdown("---")
            st.markdown("### 👤 Envío Controlado por Usuario")
            
            for idx, fila_indiv in df_morosos_global.iterrows():
                col_txt_indiv, col_btn_indiv = st.columns([0.75, 0.25])
                with col_txt_indiv:
                    st.markdown(f"📧 **{fila_indiv['usuario']}** - Equipo: **{fila_indiv['id_equipo']}** (**{fila_indiv['dias_atraso']} días** de retraso).")
                with col_btn_indiv:
                    llave_boton_indiv = f"btn_envio_indiv_modulo_{fila_indiv['id_prestamo']}_{idx}"
                    primer_nom_indiv = str(fila_indiv['usuario']).split(" ")[0]
                    if st.button(f"Notificar a {primer_nom_indiv}", key=llave_boton_indiv, use_container_width=True):
                        with st.spinner(f"Enviando correo..."):
                            exito_indiv_send = enviar_correo_mora_local(
                                fila_indiv['correo'], 
                                fila_indiv['usuario'], 
                                fila_indiv['id_equipo'], 
                                fila_indiv['fecha_limite'], 
                                fila_indiv['dias_atraso']
                            )
                            if exito_indiv_send:
                                st.toast(f"¡Aviso despachado!", icon="✅")
                            else:
                                st.error("Fallo al procesar la entrega en Brevo.")

# =========================================================================
# 📊 MÓDULO: PANEL DE CONTROL Y MÉTRICAS GENERALES (CON BOTÓN DE ENVÍO DIRECTO)
# =========================================================================
elif choice == "Panel de Control":
    st.header("📊 Resumen General y Métricas del Laboratorio")
    
    # 1. Extracción de datos con consultas SQL unificadas y seguras
    with obtener_conexion() as conn:
        df_eq = pd.read_sql_query("SELECT estado, tipo, ubicacion FROM equipos", conn)
        df_co = pd.read_sql_query("SELECT cantidad, costo_unitario FROM compras", conn)
        df_bit = pd.read_sql_query("SELECT estado_nota FROM bitacora", conn)
        df_sal = pd.read_sql_query("SELECT * FROM salas", conn)
        
        # Consulta de préstamos activos con INNER JOIN para traer el correo del usuario custodio
        query_pr_kpi = """
            SELECT p.id_prestamo, p.id_equipo, p.usuario, p.rut, p.fecha_limite, u.correo 
            FROM prestamos p 
            INNER JOIN usuarios u ON p.rut = u.rut 
            WHERE p.estado_prestamo = 'Activo'
        """
        df_pr = pd.read_sql_query(query_pr_kpi, conn)
        
        # Extracción inmediata de rankings dentro del mismo contexto activo
        df_rank_equipos = pd.read_sql_query("""
            SELECT id_equipo as 'Código Equipo', COUNT(*) as 'Total Préstamos'
            FROM prestamos 
            GROUP BY id_equipo 
            ORDER BY COUNT(*) DESC LIMIT 5
        """, conn)
        
        df_rank_usuarios = pd.read_sql_query("""
            SELECT usuario as 'Nombre Custodio', rut as 'RUT', COUNT(*) as 'Veces Solicitado'
            FROM prestamos 
            GROUP BY rut 
            ORDER BY COUNT(*) DESC LIMIT 5
        """, conn)
    
    hoy_dt = pd.to_datetime(date.today())
    
        # 🚨 BANDA DE ALERTAS CRÍTICAS: Comparación por strings (Inmune a choques de Pandas)
    if not df_pr.empty:
        try:
            # Filtramos los registros vencidos comparando texto puro (AAAA-MM-DD)
            hoy_str = date.today().isoformat()
            
            # Buscamos los préstamos cuya fecha límite sea menor al día de hoy
            df_vencidos = df_pr[df_pr['fecha_limite'] < hoy_str].copy()
            
            if not df_vencidos.empty:
                # Calculamos los días de atraso de forma nativa e individual
                dias_atraso_lista = []
                for _, row in df_vencidos.iterrows():
                    try:
                        f_limite_obj = date.fromisoformat(str(row['fecha_limite']))
                        atraso = (date.today() - f_limite_obj).days
                        dias_atraso_lista.append(max(atraso, 1))
                    except:
                        dias_atraso_lista.append(1) # Resguardo seguro si la fecha está rota
                
                df_vencidos['dias_atraso'] = dias_atraso_lista
                st.error(f"🚨 ALERTA CRÍTICA: Se detectan {len(df_vencidos)} préstamos fuera de plazo con morosidad activa.")
####               
                for idx, prestamo in df_vencidos.iterrows():
                    col_alerta_txt, col_alerta_btn = st.columns([0.75, 0.25])
                    
                    with col_alerta_txt:
                        st.markdown(f"⚠️ **{prestamo['usuario']}** ({prestamo['correo']}) retiene el equipo **{prestamo['id_equipo']}** (Venció el {prestamo['fecha_limite']}).")
                    
                    with col_alerta_btn:
                        primer_nombre = str(prestamo['usuario']).split(" ")[0]
                        # 🚀 CORRECCIÓN CLAVE: Pasamos el 'key' con el índice de la fila para evitar colisiones
                        if st.button(f"📧 Avisar a {primer_nombre}", key=f"btn_pnl_notif_fix_{prestamo['id_prestamo']}_{idx}", use_container_width=True):
                            with st.spinner("Despachando correo transaccional..."):
                                exito_mail = enviar_correo_mora_local(
                                    prestamo['correo'], 
                                    prestamo['usuario'], 
                                    prestamo['id_equipo'], 
                                    prestamo['fecha_limite'], 
                                    int(prestamo['dias_atraso'])
                                )
                                if exito_mail:
                                    st.toast(f"¡Notificación enviada con éxito!", icon="✅")
                                else:
                                    st.error("Fallo al despachar. Revise los parámetros SMTP.")
 #####      

        except Exception as err_morosidad:
            # Imprime el error real en la consola de comandos para saber exactamente qué falló
            print(f"❌ Error real en el Panel: {err_morosidad}")
            st.warning("⚠️ Nota: Ocurrió un inconveniente al calcular los días de retraso.")
    
    # 2. Renderizado de KPIs principales
    st.markdown("### 📈 Indicadores Clave de Rendimiento (KPIs)")
    col1, col2, col3, col4 = st.columns(4)
    total_equipos = len(df_eq) if not df_eq.empty else 0
    equipos_operativos = len(df_eq[df_eq["estado"] == "Operativo"]) if not df_eq.empty else 0
    prestamos_activos = len(df_pr) if not df_pr.empty else 0
    notas_pendientes = len(df_bit[df_bit["estado_nota"] == "Pendiente"]) if not df_bit.empty else 0
    
    col1.metric("📦 Total de Equipos", total_equipos)
    col2.metric("✅ Equipos Operativos", equipos_operativos)
    col3.metric("🤝 Préstamos Activos", prestamos_activos)
    col4.metric("🛠️ Tareas Pendientes (Bitácora)", notas_pendientes)
    
    # 3. Renderizado de Gráficos Plotly
    st.markdown("---")
    st.markdown("### 🔍 Distribución del Inventario")
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if not df_eq.empty:
            st.plotly_chart(px.pie(df_eq.groupby('estado').size().reset_index(name='Cantidad'), values='Cantidad', names='estado', title="Estado Técnico", hole=0.4), use_container_width=True, key="g_pie_pnl")
    with col_g2:
        if not df_eq.empty:
            st.plotly_chart(px.bar(df_eq.groupby('tipo').size().reset_index(name='Cantidad'), x='tipo', y='Cantidad', title="Categorías de Hardware"), use_container_width=True, key="g_bar_pnl")
            
    # 4. Balances Financieros
    st.markdown("---")
    st.markdown("### 💵 Balance Financiero e Inversión Escolar")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        gasto_compras = (df_co["cantidad"] * df_co["costo_unitario"]).sum() if not df_co.empty else 0
        st.metric("Total Invertido en Adquisiciones", f"${gasto_compras:,.0f} CLP")
    with col_f2:
        total_salas_reales = len(df_sal) if not df_sal.empty else 0
        st.metric("🏛️ Salas de Clases Supervisadas", total_salas_reales)

    # 5. Renderizado de Rankings
    st.markdown("---")
    st.markdown("### 🏆 Historial de Alta Demanda y Uso del Laboratorio")
    col_rk1, col_rank2 = st.columns(2)
    
    with col_rk1:
        st.markdown("##### 💻 Top 5 Equipos Más Pedidos")
        if not df_rank_equipos.empty:
            st.dataframe(df_rank_equipos, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran movimientos históricos de préstamos.")
            
    with col_rank2:
        st.markdown("##### 👥 Top 5 Usuarios con Mayor Uso")
        if not df_rank_usuarios.empty:
            st.dataframe(df_rank_usuarios, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran transacciones de usuarios.")

    # 6. Procesamiento y gráfico de distribución por sala
    st.markdown("---")
    st.markdown("##### 🏛️ Ocupación y Distribución de Hardware por Sala de Clases")
    if not df_eq.empty:
        df_eq['Sala'] = df_eq['ubicacion'].apply(lambda x: str(x).split(" - ")[0].strip() if " - " in str(x) else str(x).strip())
        df_rank_salas = df_eq.groupby('Sala').size().reset_index(name='Cantidad de Equipos')
        df_rank_salas = df_rank_salas.sort_values(by='Cantidad de Equipos', ascending=False).reset_index(drop=True)
        
        col_s_rk1, col_s_rk2 = st.columns([0.4, 0.6])
        with col_s_rk1:
            st.dataframe(df_rank_salas.head(5), use_container_width=True, hide_index=True)
        with col_s_rk2:
            fig_salas = px.bar(
                df_rank_salas.head(5), 
                x='Cantidad de Equipos', 
                y='Sala', 
                orientation='h',
                title="Top 5 Salas con Mayor Carga de Hardware",
                color='Sala',
                color_discrete_sequence=px.colors.qualitative.Bold,
                labels={'Cantidad de Equipos': 'Nro. de Dispositivos', 'Sala': 'Dependencia'}
            )
            fig_salas.update_layout(showlegend=False, yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_salas, use_container_width=True, key="grafico_ranking_salas_master")
    else:
        st.info("No se registran dependencias con equipamiento asignado.")


