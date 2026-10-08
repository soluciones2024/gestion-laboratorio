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
import base64
import smtplib
import barcode
from barcode.writer import ImageWriter      # <--- REVISAR QUE ESTÉ
from email.mime.text import MIMEText        # <--- REVISAR QUE ESTÉ
from email.header import Header             # <--- REVISAR QUE ESTÉ

from respaldo import descargar_base_datos, respaldar_base_datos

# 1. Intentar descargar la base de datos de la nube al arrancar
descargar_base_datos()

# 2. FORZAR RESPALDO DE ARRANQUE: Crea el archivo en Dropbox si la carpeta está vacía
respaldar_base_datos()

# Esto debe ejecutarse antes de cualquier consulta SQL
descargar_base_datos()

# =========================================================================
# ⚙️ FUNCIONES MOTOR: LECTOR DE CÓDIGO DE BARRAS EXPRESADOS (EVITA INDENTATIONERROR)
# =========================================================================
def renderizar_ingreso_codigo_barra_local(nombre_institucion):
    st.header("⚡ Recepción Rápida con Lector de Código de Barras")
    st.caption("Pistolee el código de barras o etiqueta QR. El sistema procesará el ingreso de forma automática.")
    
    tab_bar1, tab_bar2, tab_bar3 = st.tabs([
        "💻 Pistolear Máquinas (Equipos)", 
        "📦 Pistolear Insumos (Bodega)", 
        "🖨️ Crear Etiquetas CODE128"
    ])

    with obtener_conexion() as conn:
        df_salas_bar = pd.read_sql_query("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC", conn)
        df_insumos_bar = pd.read_sql_query("SELECT id_insumo, nombre_insumo, stock_actual, unidad_medida FROM insumos_stock ORDER BY nombre_insumo ASC", conn)
        df_equipos_print = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo FROM equipos ORDER BY id_equipo ASC", conn)
        
    lista_salas_bar = df_salas_bar["nombre_sala"].tolist() if not df_salas_bar.empty else ["Bodega General TI"]
    lista_insumos_bar = [f"ID:{r['id_insumo']} | {r['nombre_insumo']} ({r['stock_actual']} {r['unidad_medida']})" for _, r in df_insumos_bar.iterrows()]

    with tab_bar1:
        st.subheader("💻 Alta Automatizada de Equipos Físicos")
        col_f1, col_f2, col_f3 = st.columns(3)
        tipo_fijo = col_f1.selectbox("Tipo de Hardware común:", ["Notebook", "Desktop", "Monitor", "Proyector", "Switch", "Otro"], key="bar_eq_tipo")
        marca_fija = col_f2.text_input("Marca común de la caja / lote:", value="Lenovo", key="bar_eq_marca")
        modelo_fijo = col_f3.text_input("Modelo común de la caja / lote:", value="ThinkPad", key="bar_eq_modelo")
        col_f4, col_f5, col_f6 = st.columns(3)
        sala_fija = col_f4.selectbox("Asignar a Sala de destino:", lista_salas_bar, key="bar_eq_sala")
        doc_fijo = col_f5.text_input("Nro. Factura / Boleta asociada:", value="FACT-2026", key="bar_eq_doc")
        costo_fijo = col_f6.number_input("Costo Unitario ($):", min_value=0.0, value=450000.0, step=10000.0, key="bar_eq_costo")

        st.markdown("---")
        codigo_pistoleado_eq = st.text_input("👇 HAGA CLIC AQUÍ ANTES DE PISTOLEAR EL EQUIPO:", value="", placeholder="Pistolee la etiqueta aquí...", key="txt_lector_pistola_equipos")
        
        if codigo_pistoleado_eq.strip():
            id_leido = codigo_pistoleado_eq.strip().upper()
            hoy_str = date.today().isoformat()
            with obtener_conexion() as conn:
                cursor = conn.cursor()
                existe = cursor.execute("SELECT id_equipo FROM equipos WHERE id_equipo = ?", (id_leido,)).fetchone()
                if existe:
                    st.error(f"⛔ El equipo con ID `{id_leido}` ya se encuentra registrado.")
                else:
                    cursor.execute("INSERT INTO equipos VALUES (?, ?, ?, ?, 'Operativo', ?, ?, ?, 'Proveedor Lote Masivo', ?)",
                                   (id_leido, tipo_fijo, marca_fija.strip(), modelo_fijo.strip(), sala_fija, hoy_str, doc_fijo.strip(), costo_fijo))
                    conn.commit()
                    st.markdown('<audio autoplay src="https://google.com" type="audio/mpeg" style="display:none;"></audio>', unsafe_allow_html=True)
                    st.toast(f"✅ Equipo {id_leido} ingresado con éxito.", icon="💻")
                    st.session_state["txt_lector_pistola_equipos"] = ""
                    conn.commit()
                    ejecutar_respaldo_automatico_ti() # <--- INYECTAR AQUÍ
                    st.markdown('<audio autoplay src="..."></audio>', unsafe_allow_html=True)
                    st.rerun()
                       
    with tab_bar2:
        st.subheader("📦 Carga Rápida de Stock e Insumos")
        if not lista_insumos_bar:
            st.info("Para usar esta función, primero debes catalogar un insumo en el 'Gestor de Inventario'.")
        else:
            col_i1, col_i2 = st.columns(2)
            insumo_maestro_sel = col_i1.selectbox("Selecciona el Insumo que vas a recibir en lote:", lista_insumos_bar, key="bar_ins_select")
            cantidad_por_pistoleo = col_i2.number_input("Cantidad a sumar por cada pitido:", min_value=1, value=1, step=1)
            st.markdown("---")
            codigo_pistoleado_ins = st.text_input("👇 HAGA CLIC AQUÍ ANTES DE PISTOLEAR EL INSUMO:", value="", placeholder="Escanee el código de barra...", key="txt_lector_pistola_insumos")
            
            if codigo_pistoleado_ins.strip():
                partes_ins = insumo_maestro_sel.split(" | ")
                id_insumo_real = int(partes_ins[0].split(":")[1])
                nombre_insumo_real = partes_ins[1].split(" (")[0].strip()
                with obtener_conexion() as conn:
                    cursor = conn.cursor()
                    stock_bd = cursor.execute("SELECT stock_actual FROM insumos_stock WHERE id_insumo = ?", (id_insumo_real,)).fetchone()
                    stock_actual = stock_bd[0] if stock_bd else 0
                    nuevo_stock = stock_actual + cantidad_por_pistoleo
                    cursor.execute("UPDATE insumos_stock SET stock_actual = ? WHERE id_insumo = ?", (nuevo_stock, id_insumo_real))
                    cursor.execute("INSERT INTO insumos_movimientos (id_insumo, tipo_movimiento, cantidad, fecha, responsable, motivo) VALUES (?, 'Entrada', ?, ?, ?, ?)",
                                   (id_insumo_real, cantidad_por_pistoleo, date.today().isoformat(), st.session_state.get("usuario", "Operador"), f"📥 Ingreso por barra (Cód: {codigo_pistoleado_ins.strip()})"))
                    conn.commit()
                    st.markdown('<audio autoplay src="https://google.com" type="audio/mpeg" style="display:none;"></audio>', unsafe_allow_html=True)
                    st.toast(f"📦 Stock Sincronizado: {nuevo_stock}", icon="📦")
                st.session_state["txt_lector_pistola_insumos"] = ""
                st.rerun()

    with tab_bar3:
        # Remueve el código defectuoso de barcode e integra el import dinámico
        st.subheader("🖨️ Generador de Etiquetas Autoadhesivas TI")
        try:
            from mod_etiquetas import renderizar_modulo_etiquetas
            renderizar_modulo_etiquetas()
        except Exception as e:
            st.error(f"Error al cargar el módulo de etiquetas: {e}")


    st.markdown("---")
    st.subheader("📋 Últimos movimientos detectados en esta pantalla")
    with obtener_conexion() as conn:
        df_recientes_eq = pd.read_sql_query("SELECT id_equipo AS 'ID', tipo AS 'Tipo', marca AS 'Marca', ubicacion AS 'Destino' FROM equipos ORDER BY fecha_cambio DESC LIMIT 3", conn)
        df_recientes_mov = pd.read_sql_query("SELECT m.fecha AS 'Fecha', s.nombre_insumo AS 'Artículo', m.cantidad AS 'Cant' FROM insumos_movimientos m INNER JOIN insumos_stock s ON m.id_insumo = s.id_insumo ORDER BY m.id_movimiento DESC LIMIT 3", conn)
    col_v1, col_v2 = st.columns(2)
    col_v1.dataframe(df_recientes_eq, use_container_width=True, hide_index=True)
    col_v2.dataframe(df_recientes_mov, use_container_width=True, hide_index=True)

# Importaciones de tu configuración de base de datos
from database import obtener_conexion, inicializar_db, to_excel, obtener_bytes_db, restaurar_db_desde_bytes
from mod_qr import renderizar_modulo_qr
from mod_tablets import renderizar_modulo_tablets  # <--- PEGA ESTA LÍNEA EXACTAMENTE AQUÍ


# =========================================================================
# ⚙️ FUNCIONES MOTOR: PRÉSTAMOS RÁPIDOS POR BARRA (EVITA INDENTATIONERROR)
# =========================================================================
def renderizar_prestamos_rapidos_barra_local(nombre_institucion):
    st.header("🤝 Préstamos y Devoluciones Express con Lector")
    st.caption("Seleccione al custodio o acción, luego pistolee el hardware. El sistema emitirá un pitido de confirmación.")
    
    tab_pbar1, tab_pbar2 = st.tabs(["🆕 Registrar Salida Masiva", "🔙 Procesar Retorno Express"])

    with obtener_conexion() as conn:
        df_usuarios_pbar = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
        df_activos_prestados = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo'", conn)
        
    lista_combobox_pbar_us = [f"{row['rut']} | {row['nombre']}" for _, row in df_usuarios_pbar.iterrows()] if not df_usuarios_pbar.empty else ["⚠️ No hay Usuarios Registrados"]

    with tab_pbar1:
        st.subheader("🆕 Salida Express de Equipos")
        col_ps1, col_ps2 = st.columns(2)
        usuario_fijo = col_ps1.selectbox("Seleccione el Usuario Custodio Responsable:", lista_combobox_pbar_us, key="pbar_custodio")
        dias_prestamo = col_ps2.slider("Días de plazo para la devolución máxima:", 1, 30, 5, key="pbar_dias")
        obs_fija_pbar = st.text_input("Observación común de salida:", value="Entregado conforme con accesorios originales.", key="pbar_obs")

        st.markdown("---")
        codigo_prestamo_bar = st.text_input("👇 HAGA CLIC AQUÍ ANTES DE PISTOLEAR PARA ASIGNAR PRÉSTAMO:", value="", placeholder="Pistolee el código del equipo...", key="txt_prestamo_barra_live")
        
        if codigo_prestamo_bar.strip():
            id_eq_leido = codigo_prestamo_bar.strip().upper()
            
            if usuario_fijo == "⚠️ No hay Usuarios Registrados":
                st.error("⛔ Operación cancelada: Debe registrar usuarios en el sistema primero.")
            else:
                partes_us = usuario_fijo.split(" | ")
                rut_r = partes_us[0].strip()
                nom_r = partes_us[1].strip()
                
                hoy_dt = date.today()
                hoy_str = hoy_dt.isoformat()
                fecha_l_str = (hoy_dt + pd.Timedelta(days=dias_prestamo)).isoformat()
                
                with obtener_conexion() as conn:
                    cursor = conn.cursor()
                    equipos_atrasados = cursor.execute("""
                        SELECT COUNT(*) FROM prestamos 
                        WHERE rut = ? AND estado_prestamo = 'Activo' AND fecha_limite < ?
                    """, (rut_r, hoy_str)).fetchone()[0]
                
                if equipos_atrasados > 0:
                    st.markdown('<audio autoplay src="https://google.com" type="audio/mpeg" style="display:none;"></audio>', unsafe_allow_html=True)
                    st.error(f"⛔ PRÉSTAMO BLOQUEADO: El usuario {nom_r} registra {equipos_atrasados} deudas pendientes en biblioteca.")
                else:
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        existe_eq = cursor.execute("SELECT estado FROM equipos WHERE id_equipo = ?", (id_eq_leido,)).fetchone()
                        ya_prestado = id_eq_leido in df_activos_prestados["id_equipo"].tolist()
                        
                        if not existe_eq:
                            st.error(f"❌ El código `{id_eq_leido}` no pertenece a ninguna máquina del inventario.")
                        elif existe_eq[0] == "De Baja":
                            st.error(f"❌ Operación bloqueada: El equipo `{id_eq_leido}` figura como DE BAJA DEFINITIVA.")
                        elif ya_prestado:
                            st.error(f"⛔ Error: El dispositivo `{id_eq_leido}` ya se encuentra retenido en un préstamo activo.")
                        else:
                            cursor.execute(
                                "INSERT INTO prestamos (id_equipo, usuario, rut, fecha_prestamo, fecha_limite, fecha_devolucion, estado_prestamo, observaciones) VALUES (?,?,?,?,?,'Pendiente','Activo',?)",
                                (id_eq_leido, nom_r, rut_r, hoy_str, fecha_l_str, obs_fija_pbar.strip())
                            )
                            conn.commit()
                            st.markdown('<audio autoplay src="https://google.com" type="audio/mpeg" style="display:none;"></audio>', unsafe_allow_html=True)
                            st.toast(f"🔔 ¡Préstamo Exitoso! Equipo {id_eq_leido} asignado.", icon="🤝")
            
                            st.session_state["txt_prestamo_barra_live"] = ""
                            conn.commit()
                            ejecutar_respaldo_automatico_ti() # <--- INYECTAR AQUÍ
                            st.toast("¡Movimiento Sincronizado!", icon="🔔")
                            st.rerun()

    with tab_pbar2:
        st.subheader("🔙 Recepción y Retorno Express en Bodega")
        obs_devolucion_bar = st.text_input("Condición física de recepción actual:", value="Devuelto a tiempo, operativo sin novedades.", key="pbar_dev_obs")
        
        st.markdown("---")
        codigo_devolucion_bar = st.text_input("👇 HAGA CLIC AQUÍ ANTES DE PISTOLEAR PARA DEVOLVER:", value="", placeholder="Pistolee el código del hardware devuelto...", key="txt_devolucion_barra_live")
        
        if codigo_devolucion_bar.strip():
            id_eq_dev_leido = codigo_devolucion_bar.strip().upper()
            hoy_str = date.today().isoformat()
            
            with obtener_conexion() as conn:
                cursor = conn.cursor()
                prestamo_activo = cursor.execute("SELECT id_prestamo, usuario FROM prestamos WHERE id_equipo = ? AND estado_prestamo = 'Activo'", (id_eq_dev_leido,)).fetchone()
                
                if not prestamo_activo:
                    st.warning(f"⚠️ El equipo `{id_eq_dev_leido}` no registra ningún préstamo activo. Ya se encuentra en bodega.")
                else:
                    id_p_real = prestamo_activo[0]
                    nombre_custodio = prestamo_activo[1]
                    
                    cursor.execute("UPDATE prestamos SET fecha_devolucion=?, estado_prestamo='Devuelto', observaciones=? WHERE id_prestamo=?", (hoy_str, obs_devolucion_bar.strip(), id_p_real))
                    conn.commit()
                    
                    st.markdown('<audio autoplay src="https://google.com" type="audio/mpeg" style="display:none;"></audio>', unsafe_allow_html=True)
                    st.toast(f"🔔 ¡Retorno Procesado! Recibido equipo {id_eq_dev_leido}.", icon="📥")
            
            st.session_state["txt_devolucion_barra_live"] = ""
            st.rerun()

    st.markdown("---")
    st.subheader("📊 Panel de Trazabilidad Exclusiva de Lector")
    with obtener_conexion() as conn:
        df_auditoria_bar = pd.read_sql_query("SELECT id_equipo AS 'Código Hardware', usuario AS 'Custodio Asociado', fecha_prestamo AS 'Fecha Mov', estado_prestamo AS 'Condición en Sistema' FROM prestamos ORDER BY id_prestamo DESC LIMIT 3", conn)
    if not df_auditoria_bar.empty:
        st.dataframe(df_auditoria_bar, use_container_width=True, hide_index=True)

# =========================================================================
# ⚙️ FUNCIÓN MOTOR: RESPALDO AUTOMÁTICO POST-MOVIMIENTO (OPCIÓN A)
# =========================================================================

def ejecutar_respaldo_automatico_ti():
    """Genera una copia de seguridad en local cada vez que ocurre un cambio exitoso"""
    destino_carpeta = "respaldos_automaticos"
    archivo_origen = "laboratorio.db"
    
    if not os.path.exists(destino_carpeta): 
        try: os.makedirs(destino_carpeta)
        except Exception: return False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"{destino_carpeta}/auto_respaldo_{timestamp}.db"
    
    try:
        if os.path.exists(archivo_origen):
            # Clonación binaria pura corregida sin parámetros inválidos
            shutil.copyfile(archivo_origen, nombre_archivo)
            
            archivos = sorted([
                os.path.join(destino_carpeta, f) 
                for f in os.listdir(destino_carpeta) 
                if f.endswith('.db') and f.startswith('auto_respaldo_')
            ])
            while len(archivos) > 10:
                archivo_antiguo = archivos.pop(0)
                if os.path.exists(archivo_antiguo): os.remove(archivo_antiguo)
            st.toast(f"💾 Copia de seguridad guardada: {timestamp}", icon="🔄")
            return True
    except Exception as e:
        st.sidebar.error(f"❌ Error en motor de respaldo: {str(e)}")
        return False
    return False



# =========================================================================
# ⚙️ FUNCIÓN MOTOR: GESTIÓN DE SALAS CON TRAZABILIDAD DE BARRAS (VERIFICADO)
# =========================================================================


# --- Definición de la función de envío de correos ---
# --- Función principal de envío por mora de equipos (Bypass de Red integrado) ---

def enviar_correo_mora_local(correo_destino, usuario, id_equipo, fecha_limite, dias_atraso):
# Reemplaza la sección de credenciales por esta estructura:
    remitente_b = st.secrets["email"]["sender"]
    contrasena_b = st.secrets["email"]["password"]    
    asunto = f"🚨 ALERTA: Retraso en devolución de equipo {id_equipo}"
    cuerpo_html = f"""
    <html>
        <body style='font-family: Arial, sans-serif; color: #333;'>
            <h2>Recordatorio de Laboratorio</h2>
            <p>Hola {usuario},</p>
            <p>Registras un retraso de <b>{dias_atraso} días</b> en la devolución del equipo <b>{id_equipo}</b>.</p>
            <p>Plazo máximo de entrega: <b>{fecha_limite}</b>.</p>
            <hr style='border: none; border-top: 1px solid #eee; margin-top:20px;'>
            <p style='font-size:11px; color:#999;'>Gestión Automática TI - Escuela Felipe Cubillos</p>
        </body>
    </html>
    """
    
    msg = MIMEText(cuerpo_html, 'html', 'utf-8')
    msg['Subject'] = Header(asunto, 'utf-8')
    msg['From'] = Header(f"Sistema Laboratorio Escuela <{remitente}>", 'utf-8')
    msg['To'] = Header(correo_destino, 'utf-8')
    
    try:
        # ACTUALIZACIÓN COMPATIBLE 2026: Servidor universal de Outlook
        server = smtplib.SMTP("://outlook.com", 587, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(remitente, contrasena)
        server.sendmail(remitente, [correo_destino], msg.as_string())
        server.quit()
        return True
    except Exception:
        return False
        
# Inicializar base de datos externa al arrancar
inicializar_db()

# Declaración global del nombre del establecimiento
nombre_institucion = "ESCUELA FELIPE CUBILLOS"

# --- CONTROL DE ACCESO ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "rol" not in st.session_state:
    st.session_state["rol"] = "Visor"

# =========================================================================
# 🤖 SISTEMA DE AUTOMATIZACIÓN DE ALARMAS MATUTINAS (EQUIPOS + BITÁCORA)
# =========================================================================
############
# 1. Asegurar la existencia de la tabla de control diario al arrancar
# 1. Asegurar la existencia de la tabla de control diario y bitácora al arrancar
with obtener_conexion() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS control_notificaciones (
            fecha_envio TEXT PRIMARY KEY,
            estado TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora (
            id_nota INTEGER PRIMARY KEY AUTOINCREMENT,
            nota TEXT,
            fecha TEXT,
            hora TEXT,
            estado_nota TEXT DEFAULT 'Pendiente',
            fecha_ejecucion TEXT DEFAULT 'N/A',
            fecha_vencimiento TEXT DEFAULT 'N/A'
        )
    """)
    conn.commit()

################
# --- FUNCIÓN A: DESPACHO AUTOMÁTICO DE EQUIPOS EN MORA ---
def ejecutar_reporte_bitacora_vencida_automatico(correo_supervisor):
    """Detecta tareas de la bitácora vencidas y pendientes, enviando un consolidado diario por email"""
    if "email" not in st.secrets:
        return False
        
    hoy_str = date.today().isoformat()
    clave_control_diario = f"BITACORA_{hoy_str}"
    
    try:
        with obtener_conexion() as conn:
            ya_enviado_bit = conn.cursor().execute("SELECT estado FROM control_notificaciones WHERE fecha_envio = ?", (clave_control_diario,)).fetchone()
    except Exception:
        # Si las tablas de control diario no existen en producción todavía, evita que la app falle al arrancar
        ya_enviado_bit = True
        
    if not ya_enviado_bit:
        query_bitacora_caducada = """
            SELECT id_nota, fecha, nota, fecha_vencimiento 
            FROM bitacora 
            WHERE estado_nota = 'Pendiente' AND fecha_vencimiento != 'N/A' AND fecha_vencimiento < ?
            ORDER BY fecha_vencimiento ASC
        """
        try:
            with obtener_conexion() as conn:
                df_bit_vencidas = pd.read_sql_query(query_bitacora_caducada, conn, params=(hoy_str,))
        except Exception:
            # Si la tabla 'bitacora' no existe o la consulta falla por incompatibilidad, creamos un DataFrame vacío seguro
            df_bit_vencidas = pd.DataFrame()
            
        if not df_bit_vencidas.empty:
            filas_html_bitacora = ""
            for _, fila in df_bit_vencidas.iterrows():
                try:
                    f_v = date.fromisoformat(str(fila['fecha_vencimiento']))
                    dias_atraso = (date.today() - f_v).days
                except Exception:
                    dias_atraso = 1
                    
                filas_html_bitacora += f"""
                    <tr>
                        <td style='border:1px solid #ddd; padding:8px; text-align:center;'><b>ID {fila['id_nota']}</b></td>
                        <td style='border:1px solid #ddd; padding:8px;'>{fila['nota']}</td>
                        <td style='border:1px solid #ddd; padding:8px; text-align:center;'>{fila['fecha']}</td>
                        <td style='border:1px solid #ddd; padding:8px; text-align:center; color:#d9534f;'><b>{fila['fecha_vencimiento']}</b></td>
                        <td style='border:1px solid #ddd; padding:8px; text-align:center; color:#d9534f;'><b>{dias_atraso} días</b></td>
                    </tr>
                """
            
            cuerpo_html = f"""
            <html>
            <body style='font-family: Arial, sans-serif; color: #333; line-height: 1.6;'>
                <h2 style='color: #d9534f;'>🚨 REPORTE DIARIO: Tareas Caducadas en Bitácora</h2>
                <p>Estimado Supervisor del Laboratorio,</p>
                <p>Se ha generado de manera automatizada el listado de novedades y tareas del sistema que se encuentran en estado <b>Pendiente</b> y han superado su fecha máxima planificada de resolución:</p>
                <table style='width:100%; border-collapse: collapse; margin: 20px 0; font-size:14px;'>
                    <tr style='background-color:#f8f9fa;'>
                        <th style='border:1px solid #ddd; padding:10px;'>ID Tarea</th>
                        <th style='border:1px solid #ddd; padding:10px;'>Descripción / Novedad Detectada</th>
                        <th style='border:1px solid #ddd; padding:10px;'>Fecha Registro</th>
                        <th style='border:1px solid #ddd; padding:10px;'>Fecha Límite</th>
                        <th style='border:1px solid #ddd; padding:10px;'>Retraso Acumulado</th>
                    </tr>
                    {filas_html_bitacora}
                </table>
                <p style='font-size: 13px; color: #666;'>Por favor, ingrese al Sistema de Gestión de Laboratorio para actualizar o dar resolución real a estas alertas.</p>
                <hr style='border: none; border-top: 1px solid #eee; margin-top:30px;'>
                <p style='text-align:center; font-size:11px; color:#999;'>Gestión Automática TI - Escuela Felipe Cubillos</p>
            </body>
            </html>
            """
            
            try:
                remitente_auto = st.secrets["SMTP_CORREO_EMISOR"]
                contrasena_auto = st.secrets["SMTP_CONTRASENA_APP"]
                
                msg_auto = MIMEText(cuerpo_html, 'html', 'utf-8')
                msg_auto['Subject'] = Header(f"⚠️ ALERTA BITÁCORA: {len(df_bit_vencidas)} Tareas Fuera de Plazo Activas", 'utf-8')
                msg_auto['From'] = Header(f"Sistema Laboratorio <{remitente_auto}>", 'utf-8')
                msg_auto['To'] = Header(correo_supervisor, 'utf-8')
                
                server_auto = smtplib.SMTP("://gmail.com", 587)
                server_auto.starttls()
                server_auto.login(remitente_auto, contrasena_auto)
                server_auto.sendmail(remitente_auto, [correo_supervisor], msg_auto.as_string())
                server_auto.quit()
                
                with obtener_conexion() as conn:
                    conn.cursor().execute(
                        "INSERT INTO bitacora (nota, fecha, hora, estado_nota, fecha_ejecucion, fecha_vencimiento) VALUES (?, ?, ?, 'Ejecutada', ?, 'N/A')",
                        (f"🤖 [SISTEMA] Reporte consolidado de {len(df_bit_vencidas)} tareas caducadas enviado automáticamente al supervisor.", hoy_str, datetime.now().strftime("%H:%M:%S"), hoy_str)
                    )
                    conn.commit()
            except Exception:
                pass
                
        try:
            with obtener_conexion() as conn:
                conn.cursor().execute("INSERT INTO control_notificaciones VALUES (?, 'Procesado')", (clave_control_diario,))
                conn.commit()
        except Exception:
            pass

# --- 🚀 GATILLO DE EJECUCIÓN DIARIA AL INICIAR LA PLATAFORMA ---
# Cambia este correo por la dirección exacta que deba recibir el consolidado de tareas vencidas
CORREO_SUPERVISOR_TI = "jcaceres@escuelafelipecubillos.cl"

#ejecutar_despacho_automatico_matutino()
#ejecutar_reporte_bitacora_vencida_automatico(CORREO_SUPERVISOR_TI)

# --- PANTALLA DE INGRESO DE CLAVE DE ACCESO UNIFICADA (CON ACCESO ESTUDIANTE) ---
# =========================================================================
# 🔑 PANTALLA DE ACCESO UNIFICADA (CORREGIDA SIN ERRORES DE SINTAXIS)
# =========================================================================

# --- PANTALLA DE ACCESO UNIFICADA ---
if not st.session_state.get("authenticated", False):
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns(3)
    
    with col_l2:
        if os.path.exists("logo_escuela.png"):
            st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{base64.b64encode(open("logo_escuela.png", "rb").read()).decode()}" style="width: 120px;"></div>', unsafe_allow_html=True)
        
        st.subheader("🔑 Acceso TI")
        st.caption("Escuela Felipe Cubillos")
        
        with st.form("login_form_sistema_dinamico", clear_on_submit=False):
            usr_input = st.text_input("Usuario o Clave Maestra:")
            pwd_input = st.text_input("Contraseña:", type="password")
            submitted = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if submitted:
                # 1. Validar Administrador Maestro por st.secrets
                if "claves_acceso" in st.secrets and pwd_input == st.secrets["claves_acceso"].get("PASSWORD_ADMIN"):
                    st.session_state["authenticated"] = True
                    st.session_state["usuario"] = "Administrador Maestro"
                    st.session_state["rol"] = "Administrador"
                    st.session_state["modulos"] = [
                        "Panel de Control", 
                        "Inventario de Equipos", 
                        "Gestor de Inventario", 
                        "Préstamo de Equipos", 
                        "Préstamos Rápidos por Barra", 
                        "Bitácora de Notas", 
                        "Gestión de Compras", 
                        "Gestión de Salas", 
                        "Mantenedor de Usuarios", 
                        "Mantenedor de Cuentas", 
                        "Respaldo de Seguridad", 
                        "Gestor de Informes", # <--- VERIFICAR QUE ESTÉ EXACTAMENTE ASÍ
                        "Ingreso por Código de Barra",
                        "Gestión de Tablets",
                        "Generador de Etiquetas",
                        "Generador de QR"  # <--- AGREGA ESTA LÍNEA AQUÍ
                    ]
                    st.rerun()


                # 2. Buscar las cuentas personalizadas en la Base de Datos SQLite
                else:
                    found = False
                    try:
                        with obtener_conexion() as conn:
                            row = conn.cursor().execute("SELECT rol, modulos FROM cuentas_acceso WHERE usuario = ? AND password = ?", (usr_input.strip(), pwd_input.strip())).fetchone()
                            if row:
                                st.session_state["authenticated"] = True
                                st.session_state["usuario"] = usr_input.strip()
                                st.session_state["rol"] = str(row[0]).strip()
                                st.session_state["modulos"] = str(row[1]).split(",")
                                found = True
                                st.rerun()
                    except Exception:
                        pass
                        
                    if not found:
                        st.error("❌ Usuario o contraseña incorrectos. Inténtalo de nuevo.")
                        
    st.stop()

menu_options = st.session_state.get("modulos", ["Inventario de Equipos"])
choice = st.sidebar.selectbox("Selecciona un Módulo:", menu_options, key="navegacion_principal_sistema")

if st.sidebar.button("🔄 Cerrar Sesión", use_container_width=True, key="btn_cerrar_sesion_sidebar_unico"):
    st.session_state.clear()
    st.rerun()

# =========================================================================
# 📊 MÓDULO: PANEL DE CONTROL (PARTE 1 DE 3 - VENTANAS EMERGENTES FLOTANTES)
# =========================================================================
if choice == "Panel de Control":
    st.header("📊 Resumen General y Métricas del Laboratorio")

    # 🪟 1. DECLARACIÓN DE LAS VENTANAS EMERGENTES (DIALOGS)
    @st.dialog("🚨 ALERTA CRÍTICA: Equipos en Mora Vencidos", width="large")
    def popup_equipos_mora(df_equipos):
        st.markdown("Los siguientes dispositivos tecnológicos se encuentran retenidos **fuera del plazo máximo institucional**:")
        st.dataframe(df_equipos[[
            'id_equipo', 'usuario', 'fecha_limite'
        ]].rename(columns={
            'id_equipo': 'Código Equipo', 
            'usuario': 'Custodio Responsable', 
            'fecha_limite': 'Plazo de Entrega'
        }), use_container_width=True, hide_index=True)
        st.error("⚠️ Por favor, solicite la restitución inmediata de estos activos.")
        if st.button("Cerrar Ventana", key="btn_popup_eq_close", use_container_width=True):
            st.rerun()

    @st.dialog("📝 ALERTA: Tareas de Bitácora Fuera de Plazo")
    def popup_bitacora_mora(df_bitacora):
        st.markdown("Se detectan novedades o incidencias en estado **Pendiente** que superaron su fecha límite de resolución:")
        for _, nota in df_bitacora.iterrows():
            st.markdown(f"🔴 **[ID {nota['id_nota']}]** *(Venció: {nota['fecha_vencimiento']})*")
            st.info(f"{nota['nota']}")
        st.warning("💡 Ingrese al módulo 'Bitácora de Notas' para actualizar o dar resolución real a estas alertas.")
        if st.button("Entendido", key="btn_popup_bit_close", use_container_width=True):
            st.rerun()

    # 🤖 2. MOTOR DE DETECCIÓN Y DISPARO ÚNICO POR SESIÓN
    hoy_str = date.today().isoformat()
    
    if "popup_equipos_mostrado" not in st.session_state:
        st.session_state["popup_equipos_mostrado"] = False
    if "popup_bitacora_mostrado" not in st.session_state:
        st.session_state["popup_bitacora_mostrado"] = False

    with obtener_conexion() as conn:
        df_mora_eq_popup = pd.read_sql_query("""
            SELECT id_equipo, usuario, fecha_limite 
            FROM prestamos 
            WHERE estado_prestamo = 'Activo' AND fecha_limite < ?
        """, conn, params=(hoy_str,))
        
        try:
            df_mora_bit_popup = pd.read_sql_query("""
                SELECT id_nota, nota, fecha_vencimiento 
                FROM bitacora 
                WHERE estado_nota = 'Pendiente' AND fecha_vencimiento != 'N/A' AND fecha_vencimiento < ?
            """, conn, params=(hoy_str,))
        except Exception:
            df_mora_bit_popup = pd.DataFrame()

    # Evaluador secuencial de Ventanas Emergentes
    if not df_mora_eq_popup.empty and not st.session_state["popup_equipos_mostrado"]:
        st.session_state["popup_equipos_mostrado"] = True
        popup_equipos_mora(df_mora_eq_popup)
    elif not df_mora_bit_popup.empty and not st.session_state["popup_bitacora_mostrado"]:
        st.session_state["popup_bitacora_mostrado"] = True
        popup_bitacora_mora(df_mora_bit_popup)
    # --- CÁLCULO DE MÉTRICAS GLOBALES (PARTE 2 DE 3) ---
    with obtener_conexion() as conn:
        df_eq = pd.read_sql_query("SELECT estado, tipo, ubicacion FROM equipos", conn)
        df_co = pd.read_sql_query("SELECT cantidad, costo_unitario FROM compras", conn)
        df_sal = pd.read_sql_query("SELECT * FROM salas", conn)
        
        try:
            df_bit = pd.read_sql_query("SELECT id_nota, nota, fecha_vencimiento, estado_nota FROM bitacora", conn)
        except Exception:
            df_bit = pd.DataFrame(columns=["id_nota", "nota", "fecha_vencimiento", "estado_nota"])
            
        try:
            df_maint_pnl = pd.read_sql_query("""
                SELECT id_equipo as 'Equipo', 
                       fecha_salida as 'Fecha Alta', 
                       detalle_reparacion as 'Detalle Técnico', 
                       costo_repuestos as 'Gasto' 
                FROM historial_mantenimiento 
                ORDER BY id_registro DESC 
                LIMIT 4
            """, conn)
        except Exception:
            df_maint_pnl = pd.DataFrame()
            
        query_prestamos_avanzados = """
            SELECT p.id_prestamo, p.id_equipo, p.usuario, p.fecha_limite, u.correo, u.tipo_usuario
            FROM prestamos p
            INNER JOIN usuarios u ON p.rut = u.rut
        """
        df_pr_completo = pd.read_sql_query(query_prestamos_avanzados, conn)
        
        df_pr = df_pr_completo[df_pr_completo['id_prestamo'].isin(
            pd.read_sql_query("SELECT id_prestamo FROM prestamos WHERE estado_prestamo='Activo'", conn)['id_prestamo'].tolist()
        )].copy()
        
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
            
    # 💵 BALANCE FINANCIERO E INVERSIÓN ESCOLAR
    st.markdown("---")
    st.markdown("### 💵 Balance Financiero e Inversión Escolar")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        gasto_compras = (df_co["cantidad"] * df_co["costo_unitario"]).sum() if not df_co.empty else 0
        st.metric("Total Invertido en Adquisiciones", f"${gasto_compras:,.0f} CLP")
    with col_f2:
        st.metric("🏛️ Salas de Clases Supervisadas", len(df_sal))

# =========================================================================
# 📊 MÓDULO: PANEL DE CONTROL
# =========================================================================
if choice == "Panel de Control":
    st.header("📊 Resumen General y Métricas del Laboratorio")


    # 💵 BALANCE FINANCIERO E INVERSIÓN ESCOLAR
    st.markdown("---")
    st.markdown("### 💵 Balance Financiero e Inversión Escolar")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        gasto_compras = (df_co["cantidad"] * df_co["costo_unitario"]).sum() if not df_co.empty else 0
        st.metric("Total Invertido en Adquisiciones", f"${gasto_compras:,.0f} CLP")
    with col_f2:
        st.metric("🏛️ Salas de Clases Supervisadas", len(df_sal))

    # 💵 BALANCE FINANCIERO E INVERSIÓN ESCOLAR
    st.markdown("---")
    st.markdown("### 💵 Balance Financiero e Inversión Escolar")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        gasto_compras = (df_co["cantidad"] * df_co["costo_unitario"]).sum() if not df_co.empty else 0
        st.metric("Total Invertido en Adquisiciones", f"${gasto_compras:,.0f} CLP")
    with col_f2:
        st.metric("🏛️ Salas de Clases Supervisadas", len(df_sal))

    # =========================================================================
    # 🚨 MEJORA 2: DASHBOARD DE STOCK CRÍTICO DE INSUMOS Y CONSUMIBLES
    # =========================================================================
    st.markdown("---")
    st.markdown("### 📦 Monitor de Alertas de Stock y Repuestos Críticos")
    
    with obtener_conexion() as conn:
        try:
            df_insumos_pnl = pd.read_sql_query("""
                SELECT nombre_insumo, categoria, stock_actual, stock_minimo, unidad_medida 
                FROM insumos_stock
            """, conn)
        except Exception:
            df_insumos_pnl = pd.DataFrame()

    if not df_insumos_pnl.empty:
        # Filtrar elementos en desabastecimiento (Menor o igual al mínimo crítico)
        df_en_alerta = df_insumos_pnl[df_insumos_pnl["stock_actual"] <= df_insumos_pnl["stock_minimo"]]
        df_sin_stock = df_insumos_pnl[df_insumos_pnl["stock_actual"] == 0]
        
        col_stk1, col_stk2, col_stk3 = st.columns(3)
        col_stk1.metric("Variedad de Insumos", f"{len(df_insumos_pnl)} artículos")
        col_stk2.metric("⚠️ En Stock Crítico", f"{len(df_en_alerta)} materiales", delta="Reabastecer", delta_color="inverse")
        col_stk3.metric("🚨 Agotados (Stock 0)", f"{len(df_sin_stock)} unidades", delta="Crítico", delta_color="off")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not df_en_alerta.empty:
            col_list_stk1, col_list_stk2 = st.columns([0.6, 0.4])
            with col_list_stk1:
                st.caption("🔴 **Detalle de Artículos que requieren Adquisición Inmediata:**")
                df_en_alerta_fmt = df_en_alerta.rename(columns={
                    "nombre_insumo": "Descripción Material",
                    "categoria": "Categoría",
                    "stock_actual": "Disponibles",
                    "stock_minimo": "Mínimo Requerido",
                    "unidad_medida": "Unidad"
                })
                st.dataframe(df_en_alerta_fmt, use_container_width=True, hide_index=True)
            with col_list_stk2:
                # Gráfico interactivo de barras de materiales críticos
                fig_stk_critico = px.bar(
                    df_en_alerta, 
                    x='stock_actual', 
                    y='nombre_insumo', 
                    orientation='h',
                    title="Nivel de Alerta de Materiales",
                    color='stock_actual',
                    color_continuous_scale=px.colors.sequential.Reds
                )
                fig_stk_critico.update_layout(showlegend=False, height=180, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_stk_critico, use_container_width=True, key="grafico_stock_critico_panel")
        else:
            st.success("✅ ¡Perfecto! Todos los consumibles e insumos de la bodega se encuentran con niveles de stock conformes.")
    else:
        st.info("💡 No se registran materiales consumibles indexados en el catálogo de bodega todavía.")

    # =========================================================================
    # 📈 MEJORA 4: ÍNDICE COMPARATIVO CRUZADO NOTEBOOKS VS TABLETS (PEGA AQUÍ)
    # =========================================================================
    st.markdown("---")
    st.markdown("### 📊 Índice Comparativo de Uso Tecnológico (Impacto Pedagógico)")
    
    with obtener_conexion() as conn:
        total_prestamos_pc = conn.cursor().execute("SELECT COUNT(*) FROM prestamos").fetchone()[0]
        try:
            total_prestamos_tabs = conn.cursor().execute("SELECT COUNT(*) FROM tablets_prestamos").fetchone()[0]
        except Exception:
            total_prestamos_tabs = 0
            
    col_cross1, col_cross2, col_cross3 = st.columns(3)
    col_cross1.metric("Solicitudes de Notebooks (Total)", f"{total_prestamos_pc} asignaciones", delta="Equipos Fijos/Laptops")
    col_cross2.metric("Solicitudes de Tablets (Total)", f"{total_prestamos_tabs} asignaciones", delta="Equipos Móviles", delta_color="normal")
    
    if total_prestamos_pc == 0 and total_prestamos_tabs == 0:
        tecnologia_lider = "Sin datos de uso registrados"
    else:
        tecnologia_lider = "💻 Notebooks / Estaciones Fijas" if total_prestamos_pc >= total_prestamos_tabs else "📱 Tablets Digitales Móviles"
        
    col_cross3.metric("Tecnología con Mayor Impacto en Aula", tecnologia_lider)


    # 🔧 SECCIÓN: HISTORIAL DE SOPORTE TÉCNICO Y REPARACIONES EN PANEL
    st.markdown("---")
    st.markdown("### 🔧 Últimas Altas y Reparaciones de Taller")
    if not df_maint_pnl.empty:
        col_t1, col_t2 = st.columns([0.3, 0.7])
        with col_t1:
            with obtener_conexion() as conn:
                try:
                    total_taller = conn.cursor().execute("SELECT SUM(costo_repuestos) FROM historial_mantenimiento").fetchone()
                    total_taller = total_taller[0] if total_taller and total_taller[0] else 0
                except:
                    total_taller = 0
            st.metric("Gasto Total Acumulado en Repuestos", f"${total_taller:,.0f} CLP")
            st.caption("💡 Muestra los últimos 4 dispositivos que salieron de mantención y volvieron a estar operativos.")
        with col_t2:
            st.dataframe(df_maint_pnl, use_container_width=True, hide_index=True)
    else:
        st.info("Perfecto: No se registran ingresos recientes en el historial de taller mecánico o soporte técnico.")
    # --- HISTORIALES Y MAPAS DE CALOR PEDAGÓGICOS (PARTE 3 DE 3) ---
    st.markdown("---")
    st.markdown("### 🏆 Historial de Alta Demanda y Uso del Laboratorio")
    col_rk1, col_rank2 = st.columns(2)
    with col_rk1:
        st.markdown("##### 💻 Top 5 Equipos Más Pedidos")
        if not df_rank_equipos.empty:
            st.dataframe(df_rank_equipos, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran movimientos históricos de hardware.")
    with col_rank2:
        st.markdown("##### 👥 Top 5 Usuarios con Mayor Uso (Custodios)")
        if not df_rank_usuarios.empty:
            st.dataframe(df_rank_usuarios, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran transacciones de usuarios en el historial.")

    # 🏢 Distribución física por sala de clases
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

    # --- PROCESAMIENTO AVANZADO DE DEMANDA INSTITUCIONAL ---
    #st.markdown("---")
    #st.markdown("### 📈 Análisis de Demanda y Uso Pedagógico del Hardware")
    
    if not df_pr_completo.empty and 'tipo_usuario' in df_pr_completo.columns:
        cursos_prestamos = []
        asignaturas_prestamos = []
        
        for _, fila_pr in df_pr_completo.iterrows():
            cargo_str = str(fila_pr['tipo_usuario'])
            if "(" in cargo_str and ")" in cargo_str:
                contenido = cargo_str.split("(")[1].replace(")", "").strip()
                sub_elementos = contenido.split(" - ")
                
                lista_cursos_fijos = ["Primero Básico", "Segundo Básico", "Tercero Básico", "Cuarto Básico", "Quinto Básico", "Sexto Básico", "Séptimo Básico", "Octavo Básico", "Kinder", "Pre-Kinder"]
                lista_asig_fijas = ["Lenguaje", "Matemáticas", "Ciencias Naturales", "Historia", "Inglés", "Artes Visuales", "Educación Física", "Música", "Tecnología"]
                
                for item in sub_elementos:
                    item_clean = item.strip()
                    if item_clean in lista_cursos_fijos:
                        cursos_prestamos.append(item_clean)
                    elif item_clean in lista_asig_fijas:
                        asignaturas_prestamos.append(item_clean)
            elif "Profesor" in cargo_str:
                cursos_prestamos.append("Docente General")
                asignaturas_prestamos.append("General / Otras")
 
        col_graf_av1, col_graf_av2 = st.columns(2)
        
        with col_graf_av1:
            st.markdown("##### 🏫 Cursos con Mayor Uso de Equipos")
            if cursos_prestamos:
                df_graf_cursos = pd.DataFrame(cursos_prestamos, columns=['Curso']).value_counts().reset_index(name='Cantidad Préstamos')
                fig_cursos_av = px.bar(df_graf_cursos.head(5), x='Cantidad Préstamos', y='Curso', orientation='h', color='Curso', color_discrete_sequence=px.colors.qualitative.Set2)
                fig_cursos_av.update_layout(showlegend=False, height=240, margin=dict(l=0, r=0, t=10, b=10))
                st.plotly_chart(fig_cursos_av, use_container_width=True, key="grafico_demanda_avanzada_cursos")
            else:
                st.info("No hay suficientes datos de cursos para generar la métrica.")
                
        with col_graf_av2:
            st.markdown("##### 📚 Asignaturas con Mayor Demanda TI")
            if asignaturas_prestamos:
                df_graf_asig = pd.DataFrame(asignaturas_prestamos, columns=['Asignatura']).value_counts().reset_index(name='Cantidad Préstamos')
                fig_asig_av = px.pie(df_graf_asig.head(5), values='Cantidad Préstamos', names='Asignatura', hole=0.3, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_asig_av.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=10))
                st.plotly_chart(fig_asig_av, use_container_width=True, key="grafico_demanda_avanzada_asignaturas")
            else:
                st.info("No hay suficientes datos de asignaturas para generar la métrica.")
    else:
        st.info("Realiza préstamos a docentes calificados para poblar el mapa de calor de demanda pedagógica.")
# =========================================================================
# 📋 MÓDULO: INVENTARIO DE EQUIPOS (PARTE 1: INICIALIZACIÓN COMPLETA Y SEGURA)
# =========================================================================

# =========================================================================
# 📋 MÓDULO: INVENTARIO DE EQUIPOS (CON INGRESO POR PISTOLA DE BARRAS) - PARTE 1
# =========================================================================
elif choice == "Inventario de Equipos":
    st.header("📋 Inventario de Hardware y Activos TI")
    
    # Declaración de las 6 pestañas de trabajo originales
    t_eq1, t_eq2, t_eq3, t_eq4, t_eq5, t_eq6 = st.tabs([
        "➕ Añadir Equipo", "🔄 Modificar Equipo", "❌ Eliminar Registro", 
        "📋 Listado Completo", "🗑️ Dar de Baja", "📥 Carga Masiva (Excel)"
    ])
    
    # Consolidación de lecturas en una sola transacción SQL
    with obtener_conexion() as conn:
        df_base_ids = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, estado, ubicacion FROM equipos ORDER BY id_equipo ASC", conn)
        df_salas_sistema = pd.read_sql_query("SELECT nombre_sala FROM salas ORDER BY nombre_sala ASC", conn)
        df_tecnicos = pd.read_sql_query("SELECT nombre FROM usuarios WHERE tipo_usuario IN ('Técnico', 'Administrador', 'Administrativo') ORDER BY nombre ASC", conn)
        
    lista_equipos_bd = [f"{row['id_equipo']} - {row['tipo']} {row['marca']} {row['modelo']}" for _, row in df_base_ids.iterrows()]
    lista_equipos_operativos = [f"{row['id_equipo']} - {row['tipo']} {row['marca']}" for _, row in df_base_ids.iterrows() if row['estado'] != 'De Baja']
    lista_salas_combo = df_salas_sistema["nombre_sala"].tolist() if not df_salas_sistema.empty else ["Bodega General TI (Por Defecto)"]
    lista_firmas_tecnicas = [row['nombre'] for _, row in df_tecnicos.iterrows()] if not df_tecnicos.empty else ["Encargado de Laboratorio TI"]

    # --- PESTAÑA 1: AÑADIR NUEVO EQUIPO (INTEGRACIÓN LECTOR DE BARRAS) ---

    # --- PESTAÑA 1: AÑADIR NUEVO EQUIPO (CON SOLUCIÓN ESTABLE PARA LECTOR) ---
    with t_eq1:
        if st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro":
            st.subheader("➕ Registro Físico de Hardware")
            st.caption("Pistolee la etiqueta de barras del activo en el casillero express para autocompletar la ficha de inmediato.")

            # ⚡ CAPTURA EXPRESS FUERA DEL FORMULARIO PARA DISPARO EN TIEMPO REAL
            codigo_lector_fijo = st.text_input(
                "📸 PISTOLEE EL CÓDIGO DE BARRAS AQUÍ:", 
                value="", 
                placeholder="Haga clic aquí antes de usar la pistola lectora...", 
                key="txt_pistola_inventario_maestro_directo"
            ).strip().upper()

            # Lógica de prellenado automático si detecta el pitido de la pistola
            id_inicial_formulario = ""
            if codigo_lector_fijo:
                id_inicial_formulario = codigo_lector_fijo
                st.toast(f"💻 Código capturado: {id_inicial_formulario}", icon="⚡")

            # Formulario tradicional estandarizado de la escuela
            with st.form("nuevo_equipo_maestro_final", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                
                id_eq = col1.text_input(
                    "ID / Código del Equipo:", 
                    value=id_inicial_formulario,
                    placeholder="ej: PC-01 o LAP-105"
                )
                tipo_eq = col2.selectbox("Tipo Hardware:", ["Notebook", "Desktop", "Monitor", "Proyector", "Switch", "Tablet", "Otro"])
                marca_eq = col3.text_input("Marca de fábrica:")

                col4, col5, col6 = st.columns(3)
                mod_eq = col4.text_input("Modelo específico:")
                est_eq = col5.selectbox("Estado Técnico Inicial:", ["Operativo", "En Mantenimiento", "De Baja"])
                ub_eq = col6.selectbox("Sala / Destino Física Inicial:", lista_salas_combo)
            
                col7, col8, col9 = st.columns(3)
                num_doc = col7.text_input("Nro. Factura / Boleta contable:")
                prov_orig = col8.text_input("Proveedor adjudicado:")
                costo_eq = col9.number_input("Costo Real de Adquisición ($):", min_value=0.0, step=1000.0)
 
                if st.form_submit_button("Guardar Componente en Base de Datos", use_container_width=True):
                    if id_eq.strip() and num_doc.strip():
                        try:
                            with obtener_conexion() as conn:
                                sql_insert = """
                                    INSERT INTO equipos (
                                        id_equipo, tipo, marca, modelo, estado, 
                                        ubicacion, fecha_cambio, num_documento, proveedor_origen, costo_compra
                                    ) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """
                                conn.cursor().execute(sql_insert, (
                                    id_eq.strip().upper(), tipo_eq, marca_eq.strip(), mod_eq.strip(), 
                                    est_eq, ub_eq, date.today().isoformat(), num_doc.strip().upper(), prov_orig.strip(), costo_eq
                                ))
                                conn.commit()
                            
                            # 🔄 SOLUCIÓN AL ERROR: Eliminamos la asignación conflictiva de session_state.
                            # Al gatillar el rerun, Streamlit limpia de manera limpia el formulario por su parámetro nativo.
                            ejecutar_respaldo_automatico_ti()
                            st.success(f"✅ ¡Equipo {id_eq.upper()} registrado exitosamente!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⛔ Error de base de datos: El ID de este hardware ya se encuentra registrado.")
                    else:
                        st.warning("⚠️ El ID único y el Nro. de Factura son campos obligatorios para guardar la ficha.")
        else:
           st.warning("🔒 Permisos insuficientes: Requiere perfil Administrador para registrar activos.")


    # --- PESTAÑA 2: MODIFICAR FICHA TÉCNICA (PARTE 2) ---
    with t_eq2:
        if st.session_state["rol"] == "Administrador" and lista_equipos_bd:
            eq_a_modificar = st.selectbox("Selecciona el componente físico a editar:", lista_equipos_bd, key="sb_mod_eq_main_inventario_v2")
            id_mod_real = eq_a_modificar.split(" - ")[0].strip()
            
            with obtener_conexion() as conn:
                datos_act = conn.cursor().execute("SELECT tipo, marca, modelo, ubicacion, num_documento, proveedor_origen FROM equipos WHERE id_equipo = ?", (id_mod_real,)).fetchone()
            
            if datos_act:
                with st.form("form_modificar_equipo_maestro_v2"):
                    col_m1, col_m2, col_m3 = st.columns(3)
                    tipo_m = col_m1.selectbox("Cambiar Categoría:", ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"], index=["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"].index(datos_act[0]) if datos_act[0] in ["Desktop", "Notebook", "Monitor", "Proyector", "Switch", "Otro"] else 0)
                    marca_m = col_m2.text_input("Modificar Marca:", value=datos_act[1])
                    mod_m = col_m3.text_input("Modificar Modelo:", value=datos_act[2])
                    
                    col_m4, col_m5, col_m6 = st.columns(3)
                    ub_m = col_m4.selectbox("Modificar Asignación de Sala:", lista_salas_combo, index=lista_salas_combo.index(datos_act[3]) if datos_act[3] in lista_salas_combo else 0)
                    doc_m = col_m5.text_input("Modificar Nro. Docto:", value=datos_act[4])
                    prov_m = col_m6.text_input("Modificar Proveedor Contable:", value=datos_act[5])
                    
                    if st.form_submit_button("Sincronizar Cambios de la Ficha"):
                        with obtener_conexion() as conn:
                            conn.cursor().execute("UPDATE equipos SET tipo=?, marca=?, modelo=?, ubicacion=?, num_documento=?, proveedor_origen=?, fecha_cambio=? WHERE id_equipo=?", 
                                        (tipo_m, marca_m.strip(), mod_m.strip(), ub_m, doc_m.strip().upper(), prov_m.strip(), date.today().isoformat(), id_mod_real))
                            conn.commit()
                        st.success(f"✅ Ficha técnica de {id_mod_real} actualizada correctamente.")
                        st.rerun()
        elif not lista_equipos_bd:
            st.info("No hay hardware disponible para modificación en la base de datos.")
        else:
            st.warning("🔒 Acceso exclusivo para perfiles Administradores.")

    # --- PESTAÑA 3: ELIMINAR REGISTRO FISCAL ---
    with t_eq3:
        if st.session_state["rol"] == "Administrador" and lista_equipos_bd:
            eq_a_eliminar = st.selectbox("Selecciona el equipo a borrar definitivamente:", lista_equipos_bd, key="sb_del_eq_main_inventario_v2")
            id_del_real = eq_a_eliminar.split(" - ")[0].strip()
            
            st.warning("⚠️ ¡Atención Institucional! Eliminar permanentemente un registro destruirá su trazabilidad histórica de compras. Si el hardware quedó obsoleto, use la pestaña 'Dar de Baja'.")
            if st.button("🚨 Confirmar Eliminación Absoluta del Registro", key="btn_del_real_eq_inventario_v2", use_container_width=True):
                with obtener_conexion() as conn:
                    conn.cursor().execute("DELETE FROM equipos WHERE id_equipo = ?", (id_del_real,))
                    conn.commit()
                st.success(f"🔥 El registro del equipo {id_del_real} ha sido purgado de la base de datos.")
                st.rerun()
        elif not lista_equipos_bd:
            st.info("No se registran componentes para eliminación contable.")
        else:
            st.warning("🔒 Módulo restringido por políticas de seguridad.")

    # --- PESTAÑA 4: LISTADO GENERAL COMPLETO (GRILLA INTERACTIVA AVANZADA) ---

    with t_eq4:
        st.subheader("📋 Nómina Completa de Hardware del Establecimiento")
        buscar_txt = st.text_input("🔍 Filtrar rápidamente la grilla por ID, Marca o Nro. Factura:", key="txt_buscar_inventario_tab4_inventario_v2")
        
        if buscar_txt.strip():
            query_busca = "SELECT id_equipo, tipo, marca, modelo, estado, ubicacion, num_documento, proveedor_origen, costo_compra FROM equipos WHERE id_equipo LIKE ? OR marca LIKE ? OR num_documento LIKE ? ORDER BY id_equipo ASC"
            term = f"%{buscar_txt.strip()}%"
            params = (term, term, term)
        else:
            query_busca = "SELECT id_equipo, tipo, marca, modelo, estado, ubicacion, num_documento, proveedor_origen, costo_compra FROM equipos ORDER BY id_equipo ASC"
            params = ()

        with obtener_conexion() as conn:
            df_nomina_total = pd.read_sql_query(query_busca, conn, params=params)
        
        if not df_nomina_total.empty:
            df_nomina_total['costo_compra'] = pd.to_numeric(df_nomina_total['costo_compra'], errors='coerce').fillna(0)
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Equipos Encontrados", len(df_nomina_total))
            col_m2.metric("Inversión Global Consolidada", f"${df_nomina_total['costo_compra'].sum():,.0f} CLP")
            
            # ... (Líneas anteriores donde se muestra el st.metric de inversión global) ...
            
            st.dataframe(
                df_nomina_total,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id_equipo": st.column_config.TextColumn("Código ID", help="Identificador único del activo"),
                    "tipo": st.column_config.TextColumn("Tipo Hardware"),
                    "marca": st.column_config.TextColumn("Marca"),
                    "modelo": st.column_config.TextColumn("Modelo"),
                    "estado": st.column_config.SelectboxColumn("Estado Técnico", options=["Operativo", "En Mantenimiento", "De Baja"]),
                    "costo_compra": st.column_config.NumberColumn("Inversión Neto", format="$ %,.0f CLP"),
                    "ubicacion": st.column_config.TextColumn("📍 Ubicación / Sala"),
                    "num_documento": st.column_config.TextColumn("Nro. Docto"),
                    "proveedor_origen": st.column_config.TextColumn("Proveedor")
                }
            )
            
            # --- 🛠️ GENERACIÓN DEL REPORTE IMPRIMIBLE HTML ---
            filas_tabla_html = ""
            for _, r in df_nomina_total.iterrows():
                costo_fmt = f"${r['costo_compra']:,.0f}" if pd.notnull(r['costo_compra']) else "$0"
                filas_tabla_html += f"""
                <tr>
                    <td style="border: 1px solid #333; padding: 6px; font-family: monospace; font-weight: bold;">{r['id_equipo']}</td>
                    <td style="border: 1px solid #333; padding: 6px;">{r['tipo']}</td>
                    <td style="border: 1px solid #333; padding: 6px;">{r['marca']} {r['modelo']}</td>
                    <td style="border: 1px solid #333; padding: 6px; text-align: center;">{r['estado']}</td>
                    <td style="border: 1px solid #333; padding: 6px;">{r['ubicacion']}</td>
                    <td style="border: 1px solid #333; padding: 6px; text-align: right;">{costo_fmt}</td>
                </tr>
                """

            imagen_logo_listado = ""
            if os.path.exists("logo_escuela.png"):
                try:
                    with open("logo_escuela.png", "rb") as img_f:
                        encoded_string = base64.b64encode(img_f.read()).decode()
                    imagen_logo_listado = f"<img src='data:image/png;base64,{encoded_string}' style='height: 65px; width: auto;'>"
                except Exception:
                    pass

            html_listado_completo = f"""
            <div style="font-family: Arial, sans-serif; color: #000; padding: 5px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                    {imagen_logo_listado}
                    <div style="text-align: right;">
                        <h2 style="margin: 0; font-size: 20px;">INVENTARIO GENERAL DE HARDWARE Y ACTIVOS TI</h2>
                        <p style="margin: 4px 0 0 0; font-size: 13px; font-weight: bold; text-transform: uppercase;">{nombre_institucion}</p>
                        <p style="margin: 2px 0 0 0; font-size: 11px; color: #444;">Fecha de Extracción: {date.today().strftime('%d/%m/%Y')} | Registros: {len(df_nomina_total)}</p>
                    </div>
                </div>
                <hr style="border: 1px solid #000; margin-bottom: 15px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead>
                        <tr style="background-color: #eee;">
                            <th style="border: 1px solid #333; padding: 8px; text-align: left; width: 15%;">Código ID</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: left; width: 15%;">Tipo</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: left; width: 25%;">Marca / Modelo</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: center; width: 15%;">Estado</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: left; width: 20%;">📍 Ubicación</th>
                            <th style="border: 1px solid #333; padding: 8px; text-align: right; width: 10%;">Costo Neto</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_tabla_html}
                    </tbody>
                </table>
                <div style="margin-top: 25px; text-align: right; font-size: 13px; font-weight: bold;">
                    Inversión Total Consultada: ${df_nomina_total['costo_compra'].sum():,.0f} CLP
                </div>
            </div>
            """

            html_pagina_impresion_listado = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Listado de Inventario - {nombre_institucion}</title>
                <style>
                    body {{ background: #ffffff; margin: 0; padding: 8mm; font-family: Arial, sans-serif; }}
                    tr {{ page-break-inside: avoid; }}
                    @media print {{
                        body {{ padding: 0; }}
                        @page {{ margin: 12mm; size: letter landscape; }}
                    }}
                </style>
            </head>
            <body>
                {html_listado_completo}
                <script>
                    window.onload = function() {{
                        setTimeout(function() {{ window.print(); }}, 400);
                    }};
                </script>
            </body>
            </html>
            """
            
            html_escape_b64_listado = base64.b64encode(html_pagina_impresion_listado.encode('utf-8')).decode('utf-8')

            # --- BOTONERA DE ACCIONES DE SALIDA EN PARALELO ---
            st.markdown("---")
            col_list_btn1, col_list_btn2 = st.columns(2)
            
            with col_list_btn1:
                # Botón con inyección segura que levanta la visualización horizontal (Landscape)
                if st.button("🖨️ Imprimir Listado Consultado", key="btn_print_forced_listado_hardware", use_container_width=True, type="primary"):
                    js_bypass_sandbox_listado = f"""
                    <script>
                        var win = window.open();
                        if (win) {{
                            win.document.write(atob("{html_escape_b64_listado}"));
                            win.document.close();
                        }} else {{
                            alert("⚠️ Navegador bloqueado: Habilite los permisos para ventanas emergentes (Pop-ups) en la barra de direcciones.");
                        }}
                    </script>
                    """
                    st.components.v1.html(js_bypass_sandbox_listado, height=0, width=0)
                    
            with col_list_btn2:
                st.download_button(label="📥 Descargar Reporte Consolidado de Hardware (Excel)", data=to_excel(df_nomina_total), file_name="inventario_general_escuela.xlsx", use_container_width=True, key="btn_descarga_excel_inventario_maestro")
        else:
            st.info("No se encontraron registros de activos fijos con esos criterios de búsqueda.")

  # --- PESTAÑA 5: DAR DE BAJA CON ACTA AUTOMÁTICA (PARTE 3) ---







    with t_eq5:
        st.subheader("❌ Proceso de Baja Técnica Definitiva")
        st.caption("Permite retirar un activo del flujo operativo escolar, actualizar su estado a 'De Baja' y emitir el acta firmada.")
        
        if st.session_state.get("rol") == "Administrador":
            if not lista_equipos_operativos:
                st.info("👍 Todo el hardware se encuentra operativo o no hay inventario disponible para descarte.")
            else:
                with st.form("form_baja_tecnica_inventario_maestro_v2", clear_on_submit=False):
                    col_b1, col_b2 = st.columns(2)
                    eq_baja_sel = col_b1.selectbox("Selecciona el Equipo a dar de Baja:", lista_equipos_operativos, key="sb_eq_baja_master_inventario_v2")
                    responsable_baja = col_b2.selectbox("Técnico / Evaluador que autoriza la baja:", lista_firmas_tecnicas, key="sb_tecnico_baja_inventario_v2")
                    
                    motivo_baja = st.selectbox("Diagnóstico causante del descarte:", [
                        "Obsolescencia Tecnológica (No compatible con software actual)",
                        "Falla de Hardware Irreparable (Costo de repuesto excede valor comercial)",
                        "Daño Estructural por Siniestro / Accidente",
                        "Pérdida de Vida Útil / Desgaste General",
                        "Otro (Especificar en observaciones)"
                    ], key="sb_motivo_baja_inventario_v2")
                    
                    obs_baja = st.text_area("Desglose del informe técnico y piezas salvadas:", placeholder="Ej: Placa madre quemada por alza de voltaje...")
                    btn_procesar_baja = st.form_submit_button("🚨 Confirmar y Procesar Baja Técnica de Hardware", use_container_width=True)
                    
                    if btn_procesar_baja:
                        if obs_baja.strip() == "":
                            st.error("⛔ Por integridad institucional, debes describir brevemente el informe técnico.")
                        else:
                            id_eq_real_baja = eq_baja_sel.split(" - ")[0].strip()
                            hoy_str = date.today().isoformat()
                            
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE equipos SET estado = 'De Baja', ubicacion = 'Bodega de Desecho Tecnológico', fecha_cambio = ? WHERE id_equipo = ?", (hoy_str, id_eq_real_baja))
                                cursor.execute("""
                                    INSERT INTO historial_mantenimiento (id_equipo, fecha_ingreso, fecha_salida, detalle_reparacion, costo_repuestos) 
                                    VALUES (?, ?, ?, ?, 0.0)
                                """, (id_eq_real_baja, hoy_str, hoy_str, f"❌ [BAJA TÉCNICA DEFINITIVA] Autorizado por {responsable_baja}. Motivo: {motivo_baja}. Detalle: {obs_baja.strip()}"))
                                conn.commit()
                            
                            st.success(f"🚀 El equipo {id_eq_real_baja} fue retirado de los flujos activos correctamente.")
                            st.session_state["ultimo_acta_baja"] = {
                                "id_equipo": id_eq_real_baja,
                                "equipo_txt": eq_baja_sel.split(" - ")[1] if len(eq_baja_sel.split(" - ")) > 1 else eq_baja_sel,
                                "fecha": hoy_str,
                                "autoriza": responsable_baja,
                                "motivo": motivo_baja,
                                "observaciones": obs_baja.strip()
                            }
                            st.rerun()

                if "ultimo_acta_baja" in st.session_state:
                    st.markdown("---")
                    st.markdown("### 🖨️ Documento de Baja Técnica Generado")
                    datos_baja = st.session_state["ultimo_acta_baja"]
                    imagen_logo_baja = ""
                    if os.path.exists("logo_escuela.png"):
                        try: 
                            encoded_string = base64.b64encode(open("logo_escuela.png", "rb").read()).decode()
                            imagen_logo_baja = f"<img class='print-txt' src='data:image/png;base64,{encoded_string}' style='height: 70px; width: auto;'>"                        
                        except Exception: 
                            pass

                    html_baja = f"""<div class="zona-baja" style="padding: 25px; border: 2px solid #333; background-color: #ffffff; border-radius: 4px; color: #000; font-family: 'Arial', sans-serif; line-height: 1.6;"><div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">{imagen_logo_baja}<div style="text-align: right;"><h3 class="print-txt" style="margin: 0; color: #000; font-size: 18px;">ACTA DE BAJA TÉCNICA DEFINITIVA</h3><p class="print-txt" style="margin: 3px 0 0 0; font-size: 12px; font-weight: bold; text-transform: uppercase;">{nombre_institucion}</p><p class="print-txt" style="margin: 2px 0 0 0; font-size: 11px; color: #444;">Ref: REG-BAJA-{datos_baja['id_equipo']}</p></div></div><hr style="border: 1px solid #000; margin-bottom: 20px;"><p class="print-txt" style="font-size: 14px; text-align: justify;">En Talca, con fecha <b>{datos_baja['fecha']}</b>, la unidad de Gestión de Activos de la <b>{nombre_institucion}</b> procede a la revisión, descarte y baja administrativa del componente:</p><table class="print-txt" style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; color: #000;"><tr><td style="border: 1px solid #000; padding: 10px; width: 35%;"><b>Código Único ID:</b></td><td style="border: 1px solid #000; padding: 10px; font-family: monospace; font-weight: bold;">{datos_baja['id_equipo']}</td></tr><tr><td style="border: 1px solid #000; padding: 10px;"><b>Descripción / Tipo:</b></td><td style="border: 1px solid #000; padding: 10px;">{datos_baja['equipo_txt']}</td></tr><tr><td style="border: 1px solid #000; padding: 10px;"><b>Causa de la Baja:</b></td><td style="border: 1px solid #000; padding: 10px; color: #c00; font-weight: bold;">{datos_baja['motivo']}</td></tr><tr><td style="border: 1px solid #000; padding: 10px;"><b>Evaluador Técnico:</b></td><td style="border: 1px solid #000; padding: 10px;">{datos_baja['autoriza']}</td></tr></table><div class="print-txt" style="margin: 20px 0; padding: 12px; border: 1px solid #000; background: #fafafa; font-size: 13px; color: #000;"><b>Informe de Diagnóstico Técnico:</b><br>{datos_baja['observaciones']}</div><div class="print-txt" style="margin-top: 60px; display: flex; justify-content: space-between; font-size: 13px; color: #000;"><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Técnico Soporte</b><br>Unidad de Cómputo</div><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Validation Dirección</b><br>{nombre_institucion}</div></div></div>"""
                    
                    # === ESTRUCTURA DE IMPRESIÓN COMPLETA PARA EL ACTA DE BAJA ===
                    html_pagina_impresion_baja = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <title>Acta de Baja Tecnica - {datos_baja['id_equipo']}</title>
                        <style>
                            body {{ background: #ffffff; margin: 0; padding: 10mm; font-family: Arial, sans-serif; }}
                            @media print {{
                                body {{ padding: 0; }}
                                @page {{ margin: 15mm; size: letter; }}
                            }}
                        </style>
                    </head>
                    <body>
                        {html_baja}
                        <script>
                            window.onload = function() {{
                                setTimeout(function() {{ window.print(); }}, 350);
                            }};
                        </script>
                    </body>
                    </html>
                    """
                    
                    html_escape_b64_baja = base64.b64encode(html_pagina_impresion_baja.encode('utf-8')).decode('utf-8')

                    st.markdown(html_baja.replace("\n", "").strip(), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col_btn_b1, col_btn_b2, col_btn_b3 = st.columns(3)
                    
                    with col_btn_b1:
                        # NUEVO BOTÓN DE IMPRESIÓN CON BYPASS PARA ACTAS DE BAJA
                        if st.button("🖨️ Abrir Ventana de Impresión", key=f"btn_print_forced_baja_{datos_baja['id_equipo']}", use_container_width=True, type="primary"):
                            js_bypass_sandbox_baja = f"""
                            <script>
                                var win = window.open();
                                if (win) {{
                                    win.document.write(atob("{html_escape_b64_baja}"));
                                    win.document.close();
                                }} else {{
                                    alert("⚠️ Navegador bloqueado: Habilite los permisos para ventanas emergentes (Pop-ups) en la barra de direcciones.");
                                }}
                            </script>
                            """
                            st.components.v1.html(js_bypass_sandbox_baja, height=0, width=0)
                            
                    with col_btn_b2: 
                        st.download_button(label="📥 Descargar Acta (.html)", data=f"<!DOCTYPE html><html><body style='padding:20px; background:#fff;'>{html_baja}</body></html>", file_name=f"acta_baja_{datos_baja['id_equipo']}.html", mime="text/html", use_container_width=True)
                    
                    with col_btn_b3:
                        if st.button("🔄 Siguiente Registro", use_container_width=True):
                            if "ultimo_acta_baja" in st.session_state: 
                                del st.session_state["ultimo_acta_baja"]
                            st.rerun()



        else: st.warning("🔒 Perfil Administrador requerido.")

    # --- PESTAÑA 6: CARGA MASIVA DE COMPONENTES ---
    with t_eq6:
        st.subheader("📥 Carga Masiva de Equipos desde Excel")
        archivo_equipos = st.file_uploader("Seleccione el archivo Excel de Equipos:", type=["xlsx"], key="uploader_equipos_masivo")
        if archivo_equipos is not None:
            try:
                df_excel_eq = pd.read_excel(archivo_equipos)
                if st.button("🚀 Confirmar Carga de Equipos", use_container_width=True, type="primary"):
                    registrados = 0
                    hoy_str = date.today().isoformat()
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        for _, fila in df_excel_eq.iterrows():
                            try:
                                cursor.execute("INSERT INTO equipos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (str(fila["ID Equipo"]).strip().upper(), str(fila["Tipo Hardware"]).strip(), str(fila["Marca"]).strip(), str(fila["Modelo"]).strip(), str(fila["Estado"]).strip(), str(fila["Ubicacion"]).strip(), hoy_str, str(fila["Nro Factura"]).strip().upper(), str(fila["Proveedor"]).strip(), float(fila["Costo"])))
                                registrados += 1
                            except Exception: pass
                        conn.commit()
                    ejecutar_respaldo_automatico_ti()
                    st.success(f"✅ Registrados con éxito: {registrados} unidades.")
                    st.rerun()
            except Exception as e: st.error(f"Error: {e}")


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
# 👥 MÓDULO: MANTENEDOR DE USUARIOS (ROLES ESCOLARES AMPLIADOS) - PARTE 1
# =========================================================================
elif choice == "Mantenedor de Usuarios":
    st.header("👥 Registro de Personal Docente y Asistentes de la Educación")
    st.caption("Administración de fichas contractuales, cursos asignados y validación matemática de identidad.")
    
    t1, t2, t3, t4, t5 = st.tabs(["➕ Registrar", "🔍 Buscar y Ver Lista", "🔄 Modificar", "❌ Eliminar", "📥 Carga Masiva (Excel)"])
   
    # 📋 LISTA MAESTRA DE ROLES INSTITUCIONALES AMPLIADA (SOLICITADA 2026)
    lista_roles_institucion = [
        "Profesor de primero", "Profesor de música", "Profesor", "Inspector", 
        "Asistente", "Psicólogo", "Fonoaudióloga", "Administrativo", "Funcionario", "Técnico"
    ]
    
    # --- FUNCIÓN MATEMÁTICA: VALIDADOR DE RUT CHILENO (MÓDULO 11) ---
    def validar_rut_chileno(rut_completo):
        rut_limpio = str(rut_completo).replace(".", "").replace("-", "").replace(" ", "").upper()
        if len(rut_limpio) < 2: return False
        cuerpo = rut_limpio[:-1]
        dv_ingresado = rut_limpio[-1]
        if not cuerpo.isdigit(): return False
        suma = 0
        multiplicador = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplicador
            multiplicador = 2 if multiplicador == 7 else multiplicador + 1
        remante = 11 - (suma % 11)
        dv_esperado = "0" if remante == 11 else ("K" if remante == 10 else str(remante))
        return dv_ingresado == dv_esperado

    # --- TAB 1: REGISTRAR USUARIO CON ROLES DINÁMICOS ---
    with t1:
        st.subheader("➕ Incorporar Funcionario al Sistema")
        lista_roles_con_otro = lista_roles_institucion + ["Otro (Ingresar manualmente...)"]
        u_tip_seleccionado = st.selectbox("Seleccione el Cargo o Rol Institucional:", lista_roles_con_otro, key="sb_registro_cargo_live")
        
        u_curso = "N/A"
        u_asignatura = "N/A"
        u_tip_manual = ""
        
        # Activa selectores de especialidad pedagógica si el rol contiene la palabra "Profesor"
        if "Profesor" in u_tip_seleccionado:
            st.markdown("##### 🏫 Detalles del Despliegue Pedagógico")
            col_doc1, col_doc2 = st.columns(2)
            with col_doc1:
                u_curso = st.selectbox(
                    "Curso Jefe / Asignado:", 
                    ["N/A", "Primero Básico", "Segundo Básico", "Tercero Básico", "Cuarto Básico", "Quinto Básico", "Sexto Básico", "Séptimo Básico", "Octavo Básico", "Kinder", "Pre-Kinder"],
                    key="sb_live_curso"
                )
            with col_doc2:
                asig_defecto = "Música" if "música" in u_tip_seleccionado.lower() else "N/A"
                lista_asig = ["N/A", "Lenguaje", "Matemáticas", "Ciencias Naturales", "Historia", "Inglés", "Artes Visuales", "Educación Física", "Música", "Tecnología"]
                u_asignatura = st.selectbox("Asignatura Principal:", lista_asig, index=lista_asig.index(asig_defecto), key="sb_live_asig")
        
        if u_tip_seleccionado == "Otro (Ingresar manualmente...)":
            u_tip_manual = st.text_input("Escribe el nuevo cargo personalizado:", placeholder="ej: Kinesióloga, Directivo, SGE...", key="txt_live_otro_cargo")
        
        st.markdown("---")
        with st.form("u_f", clear_on_submit=True):
            u_rut = st.text_input("RUT del Funcionario (ej: 11.674.808-8 o 11674808-8):")
            u_nom = st.text_input("Nombre Completo:")
            u_cor = st.text_input("Correo Electrónico Institucional:")
            
            if st.form_submit_button("Guardar Registro del Personal", use_container_width=True):
                if u_rut.strip() and u_nom.strip():
                    if not validar_rut_chileno(u_rut):
                        st.error("⛔ El RUT ingresado no es válido en la República de Chile. Verifique el dígito verificador.")
                    else:
                        rut_final_guardar = u_rut.strip().replace(".", "").replace(" ", "").replace("-", "")
                        rut_final_guardar = f"{rut_final_guardar[:-1]}-{rut_final_guardar[-1]}".upper()
                        
                        if u_tip_seleccionado == "Otro (Ingresar manualmente...)":
                            u_tip = u_tip_manual.strip().upper()
                        elif "Profesor" in u_tip_seleccionado:
                            detalles = []
                            if u_curso != "N/A": detalles.append(u_curso)
                            if u_asignatura != "N/A": detalles.append(u_asignatura)
                            u_tip = f"{u_tip_seleccionado} ({' - '.join(detalles)})" if detalles else u_tip_seleccionado
                        else:
                            u_tip = u_tip_seleccionado
                        
                        if u_tip_seleccionado == "Otro (Ingresar manualmente...)" and not u_tip:
                            st.error("⛔ Debes especificar el nombre del rol personalizado.")
                        else:
                            with obtener_conexion() as conn:
                                try:
                                    conn.cursor().execute("INSERT INTO usuarios VALUES (?, ?, ?, ?)", (rut_final_guardar, u_nom.strip().upper(), u_cor.strip().lower(), u_tip))
                                    conn.commit()
                                    st.success(f"✅ ¡{u_nom.strip().upper()} registrado con éxito como {u_tip}!")
                                    ejecutar_respaldo_automatico_ti()
                                    st.rerun()
                                except sqlite3.IntegrityError:
                                    st.error("⛔ Error: El RUT ingresado ya cuenta con una ficha contractual en el laboratorio.")
                else:
                    st.warning("⚠️ El RUT y el Nombre Completo son campos obligatorios.")    # --- TAB 2: BUSCAR Y VER LISTA (PARTE 2) ---

    # --- TAB 2: BUSCAR Y VER LISTA CON BOTÓN DE IMPRESIÓN ROJO PREMIUM ---

    # --- TAB 2: BUSCAR Y VER LISTA CON BOTÓN DE IMPRESIÓN ROJO PREMIUM (PARCHADO TILDES) ---
    with t2:
        st.subheader("🔍 Buscador y Nómina General de Usuarios")
        with obtener_conexion() as conn:
            df_usuarios_all = pd.read_sql_query("SELECT rut as 'RUT', nombre as 'Nombre Completo', correo as 'Correo Electrónico', tipo_usuario as 'Cargo / Función' FROM usuarios ORDER BY nombre ASC", conn)
        
        if not df_usuarios_all.empty:
            buscar_u_txt = st.text_input("Filtrar rápidamente por RUT, Nombre o Cargo (ej: Psicólogo, Música o Fonoaudióloga):", key="txt_buscar_usuario_tab2")
            
            # Proceso de filtrado dinámico en memoria con Pandas si el usuario escribe algo
            if buscar_u_txt.strip():
                term_u = buscar_u_txt.strip().lower()
                df_u_filtrado = df_usuarios_all[
                    df_usuarios_all['RUT'].astype(str).str.lower().str.contains(term_u) |
                    df_usuarios_all['Nombre Completo'].astype(str).str.lower().str.contains(term_u) |
                    df_usuarios_all['Cargo / Función'].astype(str).str.lower().str.contains(term_u)
                ]
            else:
                df_u_filtrado = df_usuarios_all.copy()

            # Despliegue de la grilla interactiva normal en Streamlit
            st.dataframe(df_u_filtrado, use_container_width=True, hide_index=True)

            # --- 🛠️ COMPILACIÓN DINÁMICA DE LA TABLA COMPATIBLE CON EL FILTRADO ---
            filas_usuarios_html = ""
            for _, r in df_u_filtrado.iterrows():
                filas_usuarios_html += f"""
                <tr>
                    <td style="border: 1px solid #333; padding: 7px; font-family: monospace; font-weight: bold;">{r['RUT']}</td>
                    <td style="border: 1px solid #333; padding: 7px;">{r['Nombre Completo']}</td>
                    <td style="border: 1px solid #333; padding: 7px;">{r['Correo Electrónico']}</td>
                    <td style="border: 1px solid #333; padding: 7px;">{r['Cargo / Función']}</td>
                </tr>
                """

            imagen_logo_usuarios = ""
            if os.path.exists("logo_escuela.png"):
                try:
                    with open("logo_escuela.png", "rb") as img_f:
                        encoded_string = base64.b64encode(img_f.read()).decode()
                    imagen_logo_usuarios = f"<img src='data:image/png;base64,{encoded_string}' style='height: 65px; width: auto;'>"
                except Exception:
                    pass

            html_listado_usuarios = f"""
            <div style="font-family: Arial, sans-serif; color: #000; padding: 5px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                    {imagen_logo_usuarios}
                    <div style="text-align: right;">
                        <h2 style="margin: 0; font-size: 20px;">NÓMINA GENERAL DE FUNCIONARIOS Y ASISTENTES</h2>
                        <p style="margin: 4px 0 0 0; font-size: 13px; font-weight: bold; text-transform: uppercase;">{nombre_institucion}</p>
                        <p style="margin: 2px 0 0 0; font-size: 11px; color: #444;">Fecha de Extracción: {date.today().strftime('%d/%m/%Y')} | Total Personal: {len(df_u_filtrado)} funcionarios</p>
                    </div>
                </div>
                <hr style="border: 1px solid #000; margin-bottom: 15px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; color: #000;">
                    <thead>
                        <tr style="background-color: #f2f2f2;">
                            <th style="border: 1px solid #333; padding: 9px; text-align: left; width: 15%;">RUT</th>
                            <th style="border: 1px solid #333; padding: 9px; text-align: left; width: 35%;">Nombre Completo</th>
                            <th style="border: 1px solid #333; padding: 9px; text-align: left; width: 25%;">Correo Institucional</th>
                            <th style="border: 1px solid #333; padding: 9px; text-align: left; width: 25%;">Cargo / Función Escolar</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_usuarios_html}
                    </tbody>
                </table>
            </div>
            """

            html_pagina_impresion_usuarios = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Nomina Personal - {nombre_institucion}</title>
                <style>
                    body {{ background: #ffffff; margin: 0; padding: 8mm; font-family: Arial, sans-serif; }}
                    tr {{ page-break-inside: avoid; }}
                    @media print {{
                        body {{ padding: 0; }}
                        @page {{ margin: 12mm; size: letter landscape; }}
                    }}
                </style>
            </head>
            <body>
                {html_listado_usuarios}
                <script>
                    window.onload = function() {{
                        setTimeout(function() {{ window.print(); }}, 400);
                    }};
                </script>
            </body>
            </html>
            """
            
            # Usamos un decodificador JavaScript nativo (decodeURIComponent + escape) en el bypass final 
            # para desempaquetar el UTF-8 puro sin corromper tildes ni eñes en la nueva pestaña
            html_escape_b64_usuarios = base64.b64encode(html_pagina_impresion_usuarios.encode('utf-8')).decode('utf-8')

            st.markdown("---")
            
            st.markdown("""
                <style>
                    button[kind="secondary"] {
                        background-color: #ef4444 !important;
                        color: white !important;
                        border: none !important;
                    }
                    button[kind="secondary"]:hover {
                        background-color: #dc2626 !important;
                        color: white !important;
                    }
                </style>
            """, unsafe_allow_html=True)
            
            if st.button("🖨️ Abrir Ventana de Impresión de Personal", key="btn_print_forced_listado_usuarios", use_container_width=True):
                js_bypass_sandbox_usuarios = f"""
                <script>
                    var win = window.open();
                    if (win) {{
                        // El método decodeURIComponent(escape(atob(...))) obliga a decodificar con soporte UTF-8 estricto
                        var html_decode = decodeURIComponent(escape(window.atob("{html_escape_b64_usuarios}")));
                        win.document.write(html_decode);
                        win.document.close();
                    }} else {{
                        alert("⚠️ Navegador bloqueado: Habilite los permisos para ventanas emergentes (Pop-ups) en la barra de direcciones.");
                    }}
                </script>
                """
                st.components.v1.html(js_bypass_sandbox_usuarios, height=0, width=0)
        else:
            st.info("No hay usuarios registrados en el sistema.")





    # --- TAB 3: MODIFICAR USUARIO CON ROLES AMPLIADOS ---
    with t3:
        st.subheader("🔄 Actualizar Datos y Cargo de Usuario")
        if st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro":
            with obtener_conexion() as conn:
                df_mod_u = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
            
            if not df_mod_u.empty:
                opciones_mod_u = [f"{r['rut']} - {r['nombre']}" for _, r in df_mod_u.iterrows()]
                user_a_modificar = st.selectbox("Selecciona el funcionario a editar:", opciones_mod_u, key="sb_user_mod_tab3")
                rut_mod_real = user_a_modificar.split(" - ")[0].strip()
                
                with obtener_conexion() as conn:
                    datos_u_act = conn.cursor().execute("SELECT nombre, correo, tipo_usuario FROM usuarios WHERE rut = ?", (rut_mod_real,)).fetchone()
                
                if datos_u_act:
                    nombre_actual_bd = datos_u_act[0]
                    correo_actual_bd = datos_u_act[1]
                    cargo_actual_bd = datos_u_act[2]
                    
                    rol_base_detectado = cargo_actual_bd
                    curso_detectado = "N/A"
                    asignatura_detectada = "N/A"
                    
                    if "(" in cargo_actual_bd and ")" in cargo_actual_bd:
                        partes_cargo = cargo_actual_bd.split(" (")
                        rol_base_detectado = partes_cargo[0].strip()
                        contenido_parentesis = partes_cargo[1].replace(")", "").strip()
                        detalles_internos = contenido_parentesis.split(" - ")
                        
                        lista_cursos_fijos = ["Primero Básico", "Segundo Básico", "Tercero Básico", "Cuarto Básico", "Quinto Básico", "Sexto Básico", "Séptimo Básico", "Octavo Básico", "Kinder", "Pre-Kinder"]
                        lista_asig_fijas = ["Lenguaje", "Matemáticas", "Ciencias Naturales", "Historia", "Inglés", "Artes Visuales", "Educación Física", "Música", "Tecnología"]
                        
                        for item in detalles_internos:
                            item_clean = item.strip()
                            if item_clean in lista_cursos_fijos: curso_detectado = item_clean
                            elif item_clean in lista_asig_fijas: asignatura_detectada = item_clean

                    lista_roles_modificar = lista_roles_institucion.copy()
                    if rol_base_detectado not in lista_roles_modificar:
                        lista_roles_modificar.append(rol_base_detectado)
                    
                    with st.form("form_modificar_usuario_real"):
                        st.markdown(f"✍️ Editando al RUT: **{rut_mod_real}**")
                        nuevo_nom_u = st.text_input("Modificar Nombre Completo:", value=nombre_actual_bd)
                        nuevo_cor_u = st.text_input("Modificar Correo Electrónico:", value=correo_actual_bd)
                        nuevo_rol_base = st.selectbox("Cambiar Rol Base / Cargo:", lista_roles_modificar, index=lista_roles_modificar.index(rol_base_detectado) if rol_base_detectado in lista_roles_modificar else 0)
                        
                        nuevo_mod_curso = "N/A"
                        nuevo_mod_asig = "N/A"
                        if "Profesor" in nuevo_rol_base:
                            st.markdown("##### 🏫 Actualizar Detalles Pedagógicos")
                            col_m_doc1, col_m_doc2 = st.columns(2)
                            cursos_opciones = ["N/A", "Primero Básico", "Segundo Básico", "Tercero Básico", "Cuarto Básico", "Quinto Básico", "Sexto Básico", "Séptimo Básico", "Octavo Básico", "Kinder", "Pre-Kinder"]
                            asig_opciones = ["N/A", "Lenguaje", "Matemáticas", "Ciencias Naturales", "Historia", "Inglés", "Artes Visuales", "Educación Física", "Música", "Tecnología"]
                            
                            with col_m_doc1: nuevo_mod_curso = st.selectbox("Modificar Curso:", cursos_opciones, index=cursos_opciones.index(curso_detectado) if curso_detectado in cursos_opciones else 0)
                            with col_m_doc2: nuevo_mod_asig = st.selectbox("Modificar Asignatura:", asig_opciones, index=asig_opciones.index(asignatura_detectada) if asignatura_detectada in asig_opciones else 0)
                        
                        if st.form_submit_button("Actualizar Información de Contrato", use_container_width=True):
                            if nuevo_nom_u.strip():
                                if "Profesor" in nuevo_rol_base:
                                    detalles_nuevos = []
                                    if nuevo_mod_curso != "N/A": detalles_nuevos.append(nuevo_mod_curso)
                                    if nuevo_mod_asig != "N/A": detalles_nuevos.append(nuevo_mod_asig)
                                    cargo_final_guardar = f"{nuevo_rol_base} ({' - '.join(detalles_nuevos)})" if detalles_nuevos else nuevo_rol_base
                                else:
                                    cargo_final_guardar = nuevo_rol_base
                                
                                with obtener_conexion() as conn:
                                    conn.cursor().execute("UPDATE usuarios SET nombre = ?, correo = ?, tipo_usuario = ? WHERE rut = ?", (nuevo_nom_u.strip().upper(), nuevo_cor_u.strip().lower(), cargo_final_guardar, rut_mod_real))
                                    conn.commit()
                                st.success("✅ ¡Datos de funcionario actualizados en la base de datos!")
                                ejecutar_respaldo_automatico_ti()
                                st.rerun()
    # --- TAB 4: ELIMINAR USUARIO (PARTE 3) ---
    with t4:
        st.subheader("🗑️ Rescindir Ficha de Usuario")
        if st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro":
            if not df_mod_u.empty:
                user_sel = st.selectbox("Seleccione el funcionario a desvincular:", opciones_mod_u, key="sb_user_del_tab4")
                if st.button("🚨 Eliminar Definitivamente del Sistema", use_container_width=True):
                    rut_del = user_sel.split(" - ")[0].strip()
                    with obtener_conexion() as conn:
                        conn.cursor().execute("DELETE FROM usuarios WHERE rut = ?", (rut_del,))
                        conn.commit()
                    st.success("🗑️ Ficha purgada de la base de datos de manera conforme.")
                    ejecutar_respaldo_automatico_ti()
                    st.rerun()
        else: st.warning("🔒 Requiere perfil Administrador.")

    # --- TAB 5: CARGA MASIVA DE FUNCIONARIOS ---
    with t5:
        st.subheader("📥 Carga Masiva Escolar por Excel")
        archivo_usuarios = st.file_uploader("Seleccione el archivo Excel de Usuarios:", type=["xlsx"], key="uploader_usuarios_masivo")
        if archivo_usuarios is not None:
            try:
                df_excel_u = pd.read_excel(archivo_usuarios)
                if st.button("🚀 Confirmar Importación Masiva de Personal", use_container_width=True):
                    registrados = 0
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        for _, fila in df_excel_u.iterrows():
                            rut_limpio = str(fila["RUT"]).strip().replace(".", "").upper()
                            rut_final = f"{rut_limpio[:-1]}-{rut_limpio[-1]}" if "-" not in rut_limpio and len(rut_limpio) > 1 else rut_limpio
                            if validar_rut_chileno(rut_final):
                                try:
                                    cursor.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?)", (rut_final, str(fila["Nombre Completo"]).strip().upper(), str(fila["Correo"]).strip().lower(), str(fila["Cargo"]).strip()))
                                    registrados += 1
                                except sqlite3.IntegrityError: pass
                        conn.commit()
                    st.success(f"✅ Proceso terminado. Se inyectaron {registrados} fichas contractuales.")
                    ejecutar_respaldo_automatico_ti()
                    st.rerun()
            except Exception as e: st.error(f"Error en matriz: {e}")


# =========================================================================
# MÓDULO: MANTENEDOR DE CUENTAS (VERSION REPARADA DEFINITIVA)
# =========================================================================

# =========================================================================
# 👥 MÓDULO CORREGIDO: MANTENEDOR DE CUENTAS DE ACCESO Y PERMISOS
# =========================================================================
elif choice == "Mantenedor de Cuentas":
    # 1. Asegurar la existencia de la tabla en SQLite de forma local inmediata
    with obtener_conexion() as conn:
        conn.cursor().execute("""
            CREATE TABLE IF NOT EXISTS cuentas_acceso (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                usuario TEXT UNIQUE, 
                password TEXT, 
                rol TEXT, 
                modulos TEXT
            )
        """)
        conn.commit()

    # 2. Validación de seguridad contra accesos no autorizados
    rol_actual = st.session_state.get("rol", "Visor")
    if isinstance(rol_actual, tuple) and len(rol_actual) > 0:
        rol_actual = rol_actual[0]
    
    if "Administrador" not in str(rol_actual) and st.session_state.get("usuario") != "Administrador Maestro":
        st.warning("🔒 Acceso restringido: Se requiere perfil de Administrador.")
        st.stop()
        
    st.subheader("👥 Mantenedor de Cuentas y Permisos Avanzados")
    st.caption("Crea nuevos usuarios y personaliza sus accesos estrictos al sistema de la Escuela Felipe Cubillos.")
    
    # 🔥 CORRECCIÓN: Lista maestra alineada al 100% con las llamadas de app.py

    lista_modulos_disponibles = [
        "Panel de Control", 
        "Inventario de Equipos", 
        "Gestor de Inventario", 
        "Préstamo de Equipos",  
        "Bitácora de Notas", 
        "Gestión de Compras", 
        "Gestión de Salas", 
        "Mantenedor de Usuarios",
        "Mantenedor de Cuentas", 
        "Respaldo de Seguridad",       
        "Ingreso por Código de Barra",
        "Préstamos Rápidos por Barra",
        "Gestión de Tablets",
        "Generador de Etiquetas",
        "Generador de QR"             # <--- AGREGA ESTA LÍNEA EXACTA AQUÍ
    ]

    
    with st.form("form_crear_cuenta_reparado_final", clear_on_submit=True):
        nuevo_usuario = st.text_input("Nombre de Usuario / Login:")
        nueva_clave = st.text_input("Contraseña de Acceso:", type="password")
        nuevo_rol = st.selectbox("Perfil / Rol del Usuario:", ["Administrador", "Estudiante", "Profesor"])
        
        # Casilla masiva de pre-selección total para acelerar la creación de perfiles administradores
        seleccionar_todos = st.checkbox("⚡ Habilitar todos los módulos para esta cuenta")
        
        modulos_seleccionados = st.multiselect(
            "Módulos Habilitados para esta cuenta:", 
            lista_modulos_disponibles,
            default=lista_modulos_disponibles if seleccionar_todos else []
        )
        
        if st.form_submit_button("🚀 Registrar Cuenta y Activar Permisos", use_container_width=True):
            if nuevo_usuario.strip() and nueva_clave.strip() and modulos_seleccionados:
                # Unificación limpia por comas sin espacios para evitar errores de parseo en split()
                modulos_str = ",".join(modulos_seleccionados)
                try:
                    with obtener_conexion() as conn:
                        conn.cursor().execute(
                            "INSERT INTO cuentas_acceso (usuario, password, rol, modulos) VALUES (?, ?, ?, ?)", 
                            (nuevo_usuario.strip(), nueva_clave.strip(), nuevo_rol, modulos_str)
                        )
                        conn.commit()
                    st.toast(f"¡Cuenta '{nuevo_usuario.strip()}' creada exitosamente con {len(modulos_seleccionados)} módulos activos!", icon="✅")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("⛔ Error: El nombre de usuario ya se encuentra registrado en el sistema.")
                except Exception as e:
                    st.error(f"Error inesperado en la base de datos: {e}")
            else:
                st.error("⚠️ Todos los campos son obligatorios. Seleccione al menos un módulo de la lista.")
                
    st.markdown("---")
    st.subheader("📋 Lista de Cuentas Activas")
    
    with obtener_conexion() as conn:
        df_cuentas = pd.read_sql_query("SELECT id AS 'ID', usuario AS 'Usuario', rol AS 'Rol', modulos AS 'Módulos con Acceso' FROM cuentas_acceso", conn)
        
    if not df_cuentas.empty:
        st.dataframe(df_cuentas, use_container_width=True, hide_index=True)
        
        st.markdown("##### 🗑️ Eliminar Cuenta de Acceso")
        col_del1, col_del2 = st.columns([0.7, 0.3])
        id_a_borrar = col_del1.number_input("Ingrese el ID exacto de la cuenta a remover:", min_value=1, step=1, key="num_del_acc_id_real")
        
        st.markdown("<div style='padding-top:10px;'></div>", unsafe_allow_html=True)
        if st.button("🚨 Eliminar Cuenta Seleccionada", use_container_width=True):
            with obtener_conexion() as conn:
                cursor = conn.cursor()
                existe = cursor.execute("SELECT usuario FROM cuentas_acceso WHERE id = ?", (id_a_borrar,)).fetchone()
                if existe:
                    cursor.execute("DELETE FROM cuentas_acceso WHERE id = ?", (id_a_borrar,))
                    conn.commit()
                    st.toast(f"Cuenta ID {id_a_borrar} eliminada.", icon="🗑️")
                    st.rerun()
                else:
                    st.error("❌ El ID ingresado no corresponde a ninguna cuenta registrada.")
    else:
        st.info("No se registran cuentas secundarias creadas en la base de datos todavía.")

# =========================================================================
# 💵 MÓDULO: GESTIÓN DE COMPRAS (ACTUALIZADO CON BUSCADOR Y LISTADO)
# =========================================================================
elif choice == "Gestión de Compras":
    st.header("💵 Control de Adquisiciones y Compras")
    
    # ⚙️ MIGRACIÓN Y REPARACIÓN MULTI-COLUMNA DE LA TABLA
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        # 1. Asegurar la existencia base de la tabla compras
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compras (
                id_compra INTEGER PRIMARY KEY AUTOINCREMENT
            )
        """)
        conn.commit()
        
        # 2. Obtener la lista de columnas que existen actualmente en el archivo .db
        cursor.execute("PRAGMA table_info(compras)")
        columnas_actuales = [row[1] for row in cursor.fetchall()]  # Extraer solo el nombre de la columna
        
        # 3. Mapear todas las columnas que el sistema necesita de forma obligatoria
        columnas_necesarias = {
            "fecha_compra": "TEXT",
            "item": "TEXT",
            "cantidad": "INTEGER",
            "costo_unitario": "REAL",
            "num_factura": "TEXT",
            "proveedor": "TEXT"
        }
        
        # Soporte de compatibilidad por si la columna antes se llamaba simplemente 'fecha'
        if "fecha" in columnas_actuales and "fecha_compra" not in columnas_actuales:
            try:
                cursor.execute("ALTER TABLE compras RENAME COLUMN fecha TO fecha_compra")
                conn.commit()
                columnas_actuales.append("fecha_compra")
            except Exception:
                pass

        # 4. Inyectar de forma masiva cualquier columna faltante sin alterar los datos existentes
        for col_name, col_type in columnas_necesarias.items():
            if col_name not in columnas_actuales:
                try:
                    cursor.execute(f"ALTER TABLE compras ADD COLUMN {col_name} {col_type}")
                    conn.commit()
                except Exception:
                    pass

    # Creación de pestañas internas del módulo
    tab_c1, tab_c2 = st.tabs(["➕ Registrar Compra", "📋 Historial y Listado de Adquisiciones"])

    # --- TAB 1: REGISTRAR NUEVA ADQUISICIÓN ---
    with tab_c1:
        if st.session_state.get("rol") == "Administrador":
            with st.form("form_nueva_compra", clear_on_submit=True):
                col_c1, col_c2, col_c3 = st.columns(3)
                f_compra = col_c1.date_input("Fecha de Adquisición:", date.today())
                art_compra = col_c2.text_input("Artículo / Detalle del Material:")
                prov_compra = col_c3.text_input("Proveedor:")

                col_c4, col_c5, col_c6 = st.columns(3)
                cant_compra = col_c4.number_input("Cantidad:", min_value=1, value=1, step=1)
                costo_u_compra = col_c5.number_input("Costo Unitario ($ CLP):", min_value=0.0, step=1000.0)
                fact_compra = col_c6.text_input("Nro. Factura / Boleta:")

                if st.form_submit_button("Guardar Registro de Compra"):
                    if art_compra.strip() and fact_compra.strip():
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO compras (fecha_compra, item, cantidad, costo_unitario, num_factura, proveedor)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (f_compra.isoformat(), art_compra.strip(), cant_compra, costo_u_compra, fact_compra.strip(), prov_compra.strip()))
                            conn.commit()
                        st.success(f"✅ ¡Compra de '{art_compra.strip()}' registrada con éxito!")
                        st.rerun()
                    else:
                        st.warning("⚠️ El Nombre del Artículo y el Nro. de Factura son obligatorios.")
        else:
            st.warning("🔒 Acceso exclusivo de Administrador para registrar gastos.")

    # --- TAB 2: HISTORIAL, BUSCADOR Y LISTADO DE GASTOS ---
    with tab_c2:
        st.subheader("📋 Nómina General de Adquisiciones")
        
        with obtener_conexion() as conn:
            df_historial_compras = pd.read_sql_query("""
                SELECT id_compra as 'ID Registro', 
                       fecha_compra as 'Fecha Compra', 
                       item as 'Artículo / Detalle', 
                       cantidad as 'Cantidad', 
                       costo_unitario as 'Costo Unitario ($)', 
                       (cantidad * costo_unitario) as 'Total Invertido ($)', 
                       num_factura as 'Nro. Docto', 
                       proveedor as 'Proveedor' 
                FROM compras 
                ORDER BY id_compra DESC
            """, conn)

        if not df_historial_compras.empty:
            # Asegurar la conversión de tipos de datos en la carga de Pandas
            df_historial_compras['Cantidad'] = pd.to_numeric(df_historial_compras['Cantidad'], errors='coerce').fillna(0)
            df_historial_compras['Costo Unitario ($)'] = pd.to_numeric(df_historial_compras['Costo Unitario ($)'], errors='coerce').fillna(0)
            df_historial_compras['Total Invertido ($)'] = df_historial_compras['Cantidad'] * df_historial_compras['Costo Unitario ($)']
            
            # Indicadores financieros superiores (KPIs)
            total_gastado = df_historial_compras['Total Invertido ($)'].sum()
            total_articulos = df_historial_compras['Cantidad'].sum()
            
            col_kpi1, col_kpi2 = st.columns(2)
            col_kpi1.metric("Presupuesto Total Invertido", f"${total_gastado:,.0f} CLP")
            col_kpi2.metric("Unidades Totales Adquiridas", f"{total_articulos:,.0f} unidades")
            
            st.markdown("---")
            
            # 🔍 BARRA DE HERRAMIENTAS: Buscador + Botón Listado / Actualizar
            col_buscar, col_btn_listado = st.columns([0.75, 0.25])
            
            with col_buscar:
                buscar_compra_txt = st.text_input("🔍 Filtrar listado por Artículo, Proveedor o Nro. Documento:", key="txt_buscar_compra_live")
            
            with col_btn_listado:
                st.markdown("<div style='padding-top: 24px;'></div>", unsafe_allow_html=True)
                if st.button("🔄 Actualizar Listado", key="btn_actualizar_listado_compras", use_container_width=True):
                    st.toast("Lista de compras sincronizada", icon="📋")
                    st.rerun()

            # Filtrado dinámico en memoria con Pandas si el usuario escribe algo
            if buscar_compra_txt.strip():
                termino = buscar_compra_txt.strip().lower()
                df_filtrado_compras = df_historial_compras[
                    df_historial_compras['Artículo / Detalle'].astype(str).str.lower().str.contains(termino) |
                    df_historial_compras['Proveedor'].astype(str).str.lower().str.contains(termino) |
                    df_historial_compras['Nro. Docto'].astype(str).str.lower().str.contains(termino)
                ]
                
                if not df_filtrado_compras.empty:
                    st.caption(f"💡 Se encontraron {len(df_filtrado_compras)} registros coincidentes:")
                    st.dataframe(df_filtrado_compras, use_container_width=True, hide_index=True)
                else:
                    st.warning("⚠️ No se encontraron compras que coincidan con la búsqueda.")
            else:
                # Si no hay texto en el buscador, muestra el listado completo normal
                st.dataframe(df_historial_compras, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            # Exportador a Excel integrado utilizando tu función global 'to_excel'
            st.download_button(
                label="📥 Descargar Listado de Compras (Excel)", 
                data=to_excel(df_historial_compras), 
                file_name="historial_compras_laboratorio.xlsx",
                key="btn_descarga_compras_excel",
                use_container_width=True
            )
        else:
            st.info("No se registran compras ni adquisiciones en la base de datos todavía.")

# =========================================================================
# 📊 MÓDULO: GESTOR DE INFORMES (PARTE 1 DE 3 - TRAZABILIDAD POR FACTURA)
# =========================================================================

elif choice == "Gestor de Informes":
    st.header("📊 Centro Digital de Informes y Auditoría TI")
    st.caption("Generación, filtrado avanzado y exportación masiva de datos institucionales.")

    # 1. Selector principal del tipo de informe
    tipo_informe = st.selectbox(
        "🗂️ Selecciona el Tipo de Informe que deseas generar:",
        [
            "Seleccionar una opción...",
            "🧾 Desglose de Ítems por Nro. de Factura",
            "📋 Catálogo General de Hardware (Equipos)",
            "🤝 Historial de Préstamos y Devoluciones",
            "📦 Balance de Stock e Insumos (Consumibles)",
            "💵 Auditoría de Compras y Presupuesto"
        ],
        key="sb_selector_tipo_informes_master"
    )

    st.markdown("---")

    if tipo_informe == "Seleccionar una opción...":
        st.info("💡 Por favor, selecciona una categoría del menú desplegable superior para cargar los datos en pantalla.")

    # --- 🧾 CATEGORÍA: INFORME TOTALIZADO POR FACTURA ---
    elif "Factura" in tipo_informe:
        st.subheader("🧾 Auditoría y Trazabilidad por Nro. de Factura")
        st.caption("Filtra por documento para rastrear la ubicación, el equipo físico y el custodio actual de cada ítem comprado.")

        with obtener_conexion() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT num_factura FROM compras WHERE num_factura != '' AND num_factura IS NOT NULL
                UNION
                SELECT DISTINCT num_documento FROM equipos WHERE num_documento != '' AND num_documento IS NOT NULL
                ORDER BY num_factura ASC
            """)
            lista_facturas_bd = [row[0] for row in cursor.fetchall() if row[0]]

        if not lista_facturas_bd:
            st.info("📂 No se registran números de facturas o boletas en el historial del sistema todavía.")
        else:
            factura_seleccionada = st.selectbox(
                "🔎 Selecciona la Factura que deseas desglosar:",
                ["Seleccione un documento..."] + lista_facturas_bd,
                key="sb_informe_factura_selector"
            )

            if factura_seleccionada != "Seleccione un documento...":
                st.markdown(f"### 📋 Detalle de Trazabilidad: Factura Nro. **{factura_seleccionada}**")
                
                query_trazabilidad_factura = """
                    SELECT 
                        e.id_equipo AS 'Código Equipo',
                        e.tipo AS 'Tipo Hardware',
                        e.marca AS 'Marca',
                        e.modelo AS 'Modelo',
                        e.estado AS 'Estado Técnico',
                        e.ubicacion AS 'Ubicación Física Base',
                        CASE 
                            WHEN p.usuario IS NOT NULL THEN p.usuario
                            ELSE 'Disponible en Bodega / Sala'
                        END AS 'Custodio / Usuario Actual',
                        CASE 
                            WHEN p.usuario IS NOT NULL THEN '🚨 Prestado (En Tenencia)'
                            ELSE '✅ En su Ubicación'
                        END AS 'Condición Actual'
                    FROM equipos e
                    LEFT JOIN prestamos p ON e.id_equipo = p.id_equipo AND p.estado_prestamo = 'Activo'
                    WHERE e.num_documento = ?
                    ORDER BY e.id_equipo ASC
                """
                
                with obtener_conexion() as conn:
                    df_trazabilidad = pd.read_sql_query(query_trazabilidad_factura, conn, params=(factura_seleccionada,))

                if df_trazabilidad.empty:
                    st.warning(f"⚠️ Los ítems de la factura **{factura_seleccionada}** están registrados contablemente pero no ingresados como máquinas físicas.")
                else:
                    col_kf1, col_kf2 = st.columns(2)
                    col_kf1.metric("Componentes Físicos en Factura", f"{len(df_trazabilidad)} unidades")
                    col_kf2.metric("Equipos en Circulación", f"{len(df_trazabilidad[df_trazabilidad['Condición Actual'].str.contains('Prestado')])} en uso")
                    
                    st.markdown("---")
                    st.dataframe(df_trazabilidad, use_container_width=True, hide_index=True)
                    
                    st.download_button(
                        label="📥 Descargar Reporte de Factura (Excel)",
                        data=to_excel(df_trazabilidad),
                        file_name=f"trazabilidad_factura_{factura_seleccionada}.xlsx",
                        key="btn_dl_trazabilidad_factura_excel",
                        use_container_width=True
                    )

    # --- 📋 CATEGORÍA: INFORME DE HARDWARE ---
    elif "Hardware" in tipo_informe:
        st.subheader("📋 Informe de Fichas Técnicas y Activos Fijos")
        
        with obtener_conexion() as conn:
            df_inf_eq = pd.read_sql_query("SELECT id_equipo as 'Código', tipo as 'Tipo', marca as 'Marca', modelo as 'Modelo', estado as 'Estado Técnico', ubicacion as 'Ubicación / Sala', costo_compra as 'Costo ($)' FROM equipos ORDER BY id_equipo ASC", conn)
            
        if not df_inf_eq.empty:
            df_inf_eq['Costo ($)'] = pd.to_numeric(df_inf_eq['Costo ($)'], errors='coerce').fillna(0)
            
            col_f1, col_f2 = st.columns(2)
            filtro_est = col_f1.multiselect("Filtrar por Estado Técnico:", sorted(df_inf_eq['Estado Técnico'].unique().tolist()), default=sorted(df_inf_eq['Estado Técnico'].unique().tolist()))
            filtro_tipo = col_f2.multiselect("Filtrar por Categoría de Hardware:", sorted(df_inf_eq['Tipo'].unique().tolist()), default=sorted(df_inf_eq['Tipo'].unique().tolist()))
            
            df_res_eq = df_inf_eq[(df_inf_eq['Estado Técnico'].isin(filtro_est)) & (df_inf_eq['Tipo'].isin(filtro_tipo))]
            
            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Equipos Seleccionados", len(df_res_eq))
            col_m2.metric("Inversión en este Lote", f"${df_res_eq['Costo ($)'].sum():,.0f} CLP")
            
            st.dataframe(df_res_eq, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Informe de Equipos a Excel",
                data=to_excel(df_res_eq),
                file_name="informe_equipos_laboratorio.xlsx",
                key="btn_dl_informe_equipos",
                use_container_width=True
            )
        else:
            st.warning("No hay equipos registrados en la base de datos.")
    # --- 🤝 CATEGORÍA: INFORME HISTÓRICO DE PRÉSTAMOS ---
    elif "Préstamos" in tipo_informe:
        st.subheader("🤝 Informe Histórico de Movimientos y Comodatos")
        
        with obtener_conexion() as conn:
            df_inf_pr = pd.read_sql_query("SELECT id_prestamo as 'ID Mov', id_equipo as 'Código Hardware', usuario as 'Custodio', rut as 'RUT', fecha_prestamo as 'Fecha Entrega', fecha_limite as 'Plazo Máximo', fecha_devolucion as 'Fecha Retorno', estado_prestamo as 'Estado' FROM prestamos ORDER BY id_prestamo DESC", conn)
            
        if not df_inf_pr.empty:
            est_pr_sel = st.radio("Filtrar por condición del flujo:", ["Todos los Registros", "Sólo Préstamos Activos", "Sólo Devoluciones Concluidas"], horizontal=True)
            
            if "Activos" in est_pr_sel:
                df_res_pr = df_inf_pr[df_inf_pr['Estado'] == 'Activo']
            elif "Concluidas" in est_pr_sel:
                df_res_pr = df_inf_pr[df_inf_pr['Estado'] == 'Devuelto']
            else:
                df_res_pr = df_inf_pr
                
            st.metric("Total de Transacciones Registradas", len(df_res_pr))
            st.dataframe(df_res_pr, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Historial de Préstamos a Excel",
                data=to_excel(df_res_pr),
                file_name="informe_movimientos_comodatos.xlsx",
                key="btn_dl_informe_prestamos",
                use_container_width=True
            )
        else:
            st.warning("No se registran movimientos de préstamos históricos.")

    # --- 📦 CATEGORÍA: BALANCE DE STOCK E INSUMOS ---
    elif "Stock" in tipo_informe:
        st.subheader("📦 Informe de Insumos y Consumibles de Bodega")
        
        try:
            with obtener_conexion() as conn:
                df_inf_ins = pd.read_sql_query("SELECT id_insumo as 'ID', nombre_insumo as 'Descripción', categoria as 'Categoría', stock_actual as 'Stock Disponible', stock_minimo as 'Mínimo Alerta', unidad_medida as 'Unidad' FROM insumos_stock ORDER BY categoria ASC", conn)
        except Exception:
            df_inf_ins = pd.DataFrame()
            
        if not df_inf_ins.empty:
            solo_criticos = st.checkbox("🔥 Mostrar únicamente insumos en desabastecimiento (Bajo el mínimo)", value=False)
            
            if solo_criticos:
                df_res_ins = df_inf_ins[df_inf_ins['Stock Disponible'] <= df_inf_ins['Mínimo Alerta']]
            else:
                df_res_ins = df_inf_ins
                
            st.metric("Variedades de Artículos en Catálogo", len(df_res_ins))
            st.dataframe(df_res_ins, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Estado de Insumos a Excel",
                data=to_excel(df_res_ins),
                file_name="informe_stock_consumibles.xlsx",
                key="btn_dl_informe_insumos",
                use_container_width=True
            )
        else:
            st.warning("No se detectan artículos registrados en el módulo de Insumos.")

    # --- 💵 CATEGORÍA: AUDITORÍA DE COMPRAS ---
    elif "Compras" in tipo_informe:
        st.subheader("💵 Informe Financiero de Adquisiciones")
        
        try:
            with obtener_conexion() as conn:
                df_inf_co = pd.read_sql_query("SELECT id_compra as 'ID', fecha_compra as 'Fecha', item as 'Artículo', cantidad as 'Cantidad', costo_unitario as 'Costo U.', num_factura as 'Factura', proveedor as 'Proveedor' FROM compras ORDER BY fecha_compra DESC", conn)
        except Exception:
            df_inf_co = pd.DataFrame()
            
        if not df_inf_co.empty:
            df_inf_co['Cantidad'] = pd.to_numeric(df_inf_co['Cantidad'], errors='coerce').fillna(0)
            df_inf_co['Costo U.'] = pd.to_numeric(df_inf_co['Costo U.'], errors='coerce').fillna(0)
            df_inf_co['Total ($)'] = df_inf_co['Cantidad'] * df_inf_co['Costo U.']
            
            prov_busc = st.text_input("🔍 Filtrar el informe financiero por nombre de Proveedor:", placeholder="ej: PC Factory, Dimerc...").strip().lower()
            df_res_co = df_inf_co[df_inf_co['Proveedor'].str.lower().str.contains(prov_busc)] if prov_busc else df_inf_co
            
            col_mc1, col_mc2 = st.columns(2)
            col_mc1.metric("Órdenes de Compra Auditadas", len(df_res_co))
            col_mc2.metric("Inversión Global Sincronizada", f"${df_res_co['Total ($)'].sum():,.0f} CLP")
            
            st.dataframe(df_res_co, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Balance Financiero a Excel",
                data=to_excel(df_res_co),
                file_name="informe_gastos_compras.xlsx",
                key="btn_dl_informe_compras",
                use_container_width=True
            )
        else:
            st.warning("No existen registros cargados en el historial de adquisiciones financieras.")

    # --- 🛠️ MOTOR DE IMPRESIÓN MASIVO COMPATIBLE (BYPASS DE SANDBOX) ---
    # Detecta cuál DataFrame dinámico está activo para renderizarlo dentro del reporte físico
    df_imprimir_actual = pd.DataFrame()
    if "Factura" in tipo_informe and 'df_trazabilidad' in locals(): df_imprimir_actual = df_trazabilidad
    elif "Hardware" in tipo_informe and 'df_res_eq' in locals(): df_imprimir_actual = df_res_eq
    elif "Préstamos" in tipo_informe and 'df_res_pr' in locals(): df_imprimir_actual = df_res_pr
    elif "Stock" in tipo_informe and 'df_res_ins' in locals(): df_imprimir_actual = df_res_ins
    elif "Compras" in tipo_informe and 'df_res_co' in locals(): df_imprimir_actual = df_res_co

    if not df_imprimir_actual.empty:
        st.markdown("---")
        
        # Carga el logotipo de la escuela para añadirlo al membrete
        imagen_logo_reportes = ""
        if os.path.exists("logo_escuela.png"):
            try:
                with open("logo_escuela.png", "rb") as img_f:
                    encoded_string = base64.b64encode(img_f.read()).decode()
                imagen_logo_reportes = f"<img src='data:image/png;base64,{encoded_string}' style='height: 65px; width: auto;'>"
            except Exception:
                pass

        html_contenido_tabla = df_imprimir_actual.to_html(index=False)
        html_hoja_completa = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Reporte de Auditoria TI - {nombre_institucion}</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 10mm; background: #ffffff; color: #000000; }}
                .header-rep {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 15px; color: #000; }}
                th {{ background-color: #f2f2f2; border: 1px solid #333; padding: 7px; text-align: left; font-weight: bold; }}
                td {{ border: 1px solid #333; padding: 6px; }}
                tr {{ page-break-inside: avoid; }}
                @media print {{
                    body {{ padding: 0; }}
                    @page {{ size: letter landscape; margin: 10mm; }}
                }}
            </style>
        </head>
        <body>
            <div class="header-rep">
                {imagen_logo_reportes}
                <div style="text-align: right;">
                    <h2 style="margin: 0; font-size: 18px;">INFORME OFICIAL DE AUDITORÍA Y CONTROL</h2>
                    <h4 style="margin: 4px 0 0 0; text-transform: uppercase; color: #333;">{tipo_informe}</h4>
                    <p style="margin: 2px 0 0 0; font-size: 11px; color: #555;">Establecimiento: {nombre_institucion} | Fecha: {date.today().strftime('%d/%m/%Y')}</p>
                </div>
            </div>
            <hr style="border: 1px solid #000;">
            {html_contenido_tabla}
        </body>
        </html>
        """
        
        b64_listados = base64.b64encode(html_hoja_completa.encode('utf-8')).decode('utf-8')
        
        # Botón definitivo inyectado en el Layout de Streamlit
        if st.button("🖨️ Abrir Ventana de Impresión de Reporte", key="btn_print_informes_digitales_unificado", type="primary", use_container_width=True):
            js_print_informes = f"""
            <script>
                var win = window.open();
                if (win) {{
                    win.document.write(atob("{b64_listados}"));
                    win.document.close();
                }} else {{
                    alert("⚠️ Pop-ups bloqueados: Permita las ventanas emergentes en la barra de navegación.");
                }}
            </script>
            """
            st.components.v1.html(js_print_informes, height=0, width=0)


    elif "Préstamos" in tipo_informe:
        st.subheader("🤝 Informe Histórico de Movimientos y Comodatos")
        
        with obtener_conexion() as conn:
            df_inf_pr = pd.read_sql_query("SELECT id_prestamo as 'ID Mov', id_equipo as 'Código Hardware', usuario as 'Custodio', rut as 'RUT', fecha_prestamo as 'Fecha Entrega', fecha_limite as 'Plazo Máximo', fecha_devolucion as 'Fecha Retorno', estado_prestamo as 'Estado' FROM prestamos ORDER BY id_prestamo DESC", conn)
            
        if not df_inf_pr.empty:
            est_pr_sel = st.radio("Filtrar por condición del flujo:", ["Todos los Registros", "Sólo Préstamos Activos (En Mora/Vigentes)", "Sólo Devoluciones Concluidas"], horizontal=True)
            
            if "Activos" in est_pr_sel:
                df_res_pr = df_inf_pr[df_inf_pr['Estado'] == 'Activo']
            elif "Concluidas" in est_pr_sel:
                df_res_pr = df_inf_pr[df_inf_pr['Estado'] == 'Devuelto']
            else:
                df_res_pr = df_inf_pr
                
            st.metric("Total de Transacciones Registradas", len(df_res_pr))
            st.dataframe(df_res_pr, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Historial de Préstamos a Excel",
                data=to_excel(df_res_pr),
                file_name="informe_movimientos_comodatos.xlsx",
                key="btn_dl_informe_prestamos",
                use_container_width=True
            )
        else:
            st.warning("No se registran movimientos de préstamos históricos.")

    elif "Préstamos" in tipo_informe:
        st.subheader("🤝 Informe Histórico de Movimientos y Comodatos")
        
        with obtener_conexion() as conn:
            df_inf_pr = pd.read_sql_query("SELECT id_prestamo as 'ID Mov', id_equipo as 'Código Hardware', usuario as 'Custodio', rut as 'RUT', fecha_prestamo as 'Fecha Entrega', fecha_limite as 'Plazo Máximo', fecha_devolucion as 'Fecha Retorno', estado_prestamo as 'Estado' FROM prestamos ORDER BY id_prestamo DESC", conn)
            
        if not df_inf_pr.empty:
            est_pr_sel = st.radio("Filtrar por condición del flujo:", ["Todos los Registros", "Sólo Préstamos Activos (En Mora/Vigentes)", "Sólo Devoluciones Concluidas"], horizontal=True)
            
            if "Activos" in est_pr_sel:
                df_res_pr = df_inf_pr[df_inf_pr['Estado'] == 'Activo']
            elif "Concluidas" in est_pr_sel:
                df_res_pr = df_inf_pr[df_inf_pr['Estado'] == 'Devuelto']
            else:
                df_res_pr = df_inf_pr
                
            st.metric("Total de Transacciones Registradas", len(df_res_pr))
            st.dataframe(df_res_pr, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Historial de Préstamos a Excel",
                data=to_excel(df_res_pr),
                file_name="informe_movimientos_comodatos.xlsx",
                key="btn_dl_informe_prestamos",
                use_container_width=True
            )
        else:
            st.warning("No se registran movimientos de préstamos históricos.")
    # --- DETALLES DE CIERRE (PARTE 3 DE 3 - BODEGA Y COMPRAS) ---
    elif "Stock" in tipo_informe:
        st.subheader("📦 Informe de Insumos y Consumibles de Bodega")
        
        try:
            with obtener_conexion() as conn:
                df_inf_ins = pd.read_sql_query("SELECT id_insumo as 'ID', nombre_insumo as 'Descripción', categoria as 'Categoría', stock_actual as 'Stock Disponible', stock_minimo as 'Mínimo Alerta', unidad_medida as 'Unidad' FROM insumos_stock ORDER BY categoria ASC", conn)
        except Exception:
            df_inf_ins = pd.DataFrame()
            
        if not df_inf_ins.empty:
            solo_criticos = st.checkbox("🔥 Mostrar únicamente insumos en desabastecimiento (Bajo el mínimo)", value=False)
            
            if solo_criticos:
                df_res_ins = df_inf_ins[df_inf_ins['Stock Disponible'] <= df_inf_ins['Mínimo Alerta']]
            else:
                df_res_ins = df_inf_ins
                
            st.metric("Variedades de Artículos en Catálogo", len(df_res_ins))
            st.dataframe(df_res_ins, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Estado de Insumos a Excel",
                data=to_excel(df_res_ins),
                file_name="informe_stock_consumibles.xlsx",
                key="btn_dl_informe_insumos",
                use_container_width=True
            )
        else:
            st.warning("No se detectan artículos registrados en el módulo de Insumos.")

    elif "Compras" in tipo_informe:
        st.subheader("💵 Informe Financiero de Adquisiciones")
        
        try:
            with obtener_conexion() as conn:
                df_inf_co = pd.read_sql_query("SELECT id_compra as 'ID', fecha_compra as 'Fecha', item as 'Artículo', cantidad as 'Cantidad', costo_unitario as 'Costo U.', num_factura as 'Factura', proveedor as 'Proveedor' FROM compras ORDER BY fecha_compra DESC", conn)
        except Exception:
            df_inf_co = pd.DataFrame()
            
        if not df_inf_co.empty:
            df_inf_co['Cantidad'] = pd.to_numeric(df_inf_co['Cantidad'], errors='coerce').fillna(0)
            df_inf_co['Costo U.'] = pd.to_numeric(df_inf_co['Costo U.'], errors='coerce').fillna(0)
            df_inf_co['Total ($)'] = df_inf_co['Cantidad'] * df_inf_co['Costo U.']
            
            prov_busc = st.text_input("🔍 Filtrar el informe financiero por nombre de Proveedor:", placeholder="ej: Pcfactory, Dimerc...").strip().lower()
            df_res_co = df_inf_co[df_inf_co['Proveedor'].str.lower().str.contains(prov_busc)] if prov_busc else df_inf_co
            
            col_mc1, col_mc2 = st.columns(2)
            col_mc1.metric("Órdenes de Compra Auditadas", len(df_res_co))
            col_mc2.metric("Inversión Global Sincronizada", f"${df_res_co['Total ($)'].sum():,.0f} CLP")
            
            st.dataframe(df_res_co, use_container_width=True, hide_index=True)
            st.download_button(
                label="📥 Exportar Balance Financiero a Excel",
                data=to_excel(df_res_co),
                file_name="informe_gastos_compras.xlsx",
                key="btn_dl_informe_compras",
                use_container_width=True
            )
        else:
            st.warning("No existen registros cargados en el historial de adquisiciones financieras.")

# =========================================================================
# 🤝 MÓDULO: PRÉSTAMO DE EQUIPOS
# =========================================================================
###########################################
#########################################

elif choice == "Préstamo de Equipos":
    st.header("🤝 Módulo de Préstamos y Devoluciones")
    tab1, tab2, tab3 = st.tabs(["🆕 Registrar Préstamo", "🔙 Procesar Devolución", "📋 Ver Historial y Estadísticas"])
    
    with obtener_conexion() as conn:
        df_us = pd.read_sql_query("SELECT rut, nombre FROM usuarios", conn)
        df_op = pd.read_sql_query("SELECT id_equipo FROM equipos WHERE estado = 'Operativo'", conn)
        df_ac = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo'", conn)
    df_disponibles = df_op[~df_op["id_equipo"].isin(df_ac["id_equipo"].tolist())]


    with tab1:
        st.subheader("🆕 Asignación de Comodato con Lector Express")
        st.caption("Pistolee el código de barras del componente para cargar su ficha técnica y emitir su documento contable.")

        # ⚡ Inicialización segura de estados de persistencia en la sesión
        if "cache_codigo_prestamo" not in st.session_state:
            st.session_state["cache_codigo_prestamo"] = ""
        if "acta_comodato_print_cache" not in st.session_state:
            st.session_state["acta_comodato_print_cache"] = None

        # Capturador atómico de la pistola lectora
        codigo_leido_input = st.text_input(
            "📸 PISTOLEE EL CÓDIGO DE BARRAS DEL HARDWARE AQUÍ:",
            value=st.session_state["cache_codigo_prestamo"],
            placeholder="Haga clic aquí antes de usar la pistola lectora...",
            key="txt_pistola_prestamos_maestro_directo_v4"
        ).strip().upper()

        # Sincronizamos la entrada del widget con nuestro estado persistente
        if codigo_leido_input != st.session_state["cache_codigo_prestamo"]:
            st.session_state["cache_codigo_prestamo"] = codigo_leido_input
            st.rerun()

        id_formulario = st.session_state["cache_codigo_prestamo"]
        tipo_detectado = "No cargado"
        marca_detectada = "No cargada"
        modelo_detectado = "No cargado"
        ubicacion_detectada = "No cargado"
        bloqueado_por_estado = False

        # Procesamiento de la Ficha Técnica y validación local de estados
        if id_formulario:
            # Consultas atómicas locales para blindar el flujo contra pérdidas de memoria de Pandas
            with obtener_conexion() as conn:
                df_maquina_local = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, ubicacion, estado FROM equipos WHERE UPPER(id_equipo) = ?", conn, params=(id_formulario,))
                df_prestados_local = pd.read_sql_query("SELECT id_equipo FROM prestamos WHERE estado_prestamo = 'Activo' AND UPPER(id_equipo) = ?", conn, params=(id_formulario,))
            
            if not df_maquina_local.empty:
                datos_maquina = df_maquina_local.to_dict('records')[0]
                tipo_detectado = datos_maquina.get('tipo', 'N/A')
                marca_detectada = datos_maquina.get('marca', 'N/A')
                modelo_detectado = datos_maquina.get('modelo', 'N/A')
                ubicacion_detectada = datos_maquina.get('ubicacion', 'N/A')
                
                # Evaluaciones de seguridad institucional directas desde la base de datos
                if not df_prestados_local.empty:
                    st.error(f"⛔ Error: El dispositivo `{id_formulario}` ya registra un préstamo ACTIVO vigente en el establecimiento.")
                    bloqueado_por_estado = True
                elif datos_maquina.get('estado') == "De Baja":
                    st.error(f"❌ Operación denegada: El equipo `{id_formulario}` fue retirado del colegio por BAJA TÉCNICA DEFINITIVA.")
                    bloqueado_por_estado = True
            else:
                st.error(f"❌ El código `{id_formulario}` no pertenece a ninguna máquina registrada en el inventario.")
                bloqueado_por_estado = True

        # Renderizado visual de la Ficha del Hardware Escaneado
        st.markdown("##### 💻 Ficha del Hardware Escaneado")
        col_inf1, col_inf2, col_inf3, col_inf4 = st.columns(4)
        col_inf1.markdown(f"**Tipo:** {tipo_detectado}")
        col_inf2.markdown(f"**Marca:** {marca_detectada}")
        col_inf3.markdown(f"**Modelo:** {modelo_detectado}")
        col_inf4.markdown(f"**Ubicación:** {ubicacion_detectada}")
        st.markdown("---")
        # Formulario de Custodia y Cierre de Movimiento
        with st.form("form_registro_prestamo_barra_v4", clear_on_submit=False):
            st.markdown("##### 👥 Datos del Custodio Responsable y Plazos")
            col_com1, col_com2 = st.columns(2)
            

            # Carga local de emergencia para evitar el NameError si la variable no viene de afuera
            with obtener_conexion() as conn:
                df_us_local = pd.read_sql_query("SELECT rut, nombre FROM usuarios ORDER BY nombre ASC", conn)
            lista_usuarios_comodato_local = [f"{r['rut']} | {r['nombre']}" for _, r in df_us_local.iterrows()] if not df_us_local.empty else []

            us_sel = col_com1.selectbox(
                "Seleccione el Funcionario Responsable:", 
                lista_usuarios_comodato_local if lista_usuarios_comodato_local else ["No hay usuarios registrados"], 
                key="sb_p_us_barra_real_v4"
            )


            fecha_l = col_com2.date_input("Fecha Máxima de Retorno Planificada:", date.today() + pd.Timedelta(days=5), key="date_p_limite_barra_v4")
            obs_p = st.text_input("Observaciones o accesorios incluidos al entregar:", value="Entregado operativo con sus cables originales.", key="txt_p_obs_barra_v4")
            
            btn_confirmar_prestamo = st.form_submit_button("Confirmar e Imprimir Acta de Comodato", use_container_width=True)
            
            if btn_confirmar_prestamo:
                if id_formulario == "" or bloqueado_por_estado:
                    st.error("⛔ Operación inválida: Escanee un equipo operativo disponible antes de guardar.")
                else:
                    partes_usuario = us_sel.split(" | ")
                    rut_r = partes_usuario[0].strip()
                    nom_r = partes_usuario[1].strip() if len(partes_usuario) > 1 else partes_usuario[0].strip()
                    hoy_str = date.today().isoformat()
                    
                    with obtener_conexion() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO prestamos (id_equipo, usuario, rut, fecha_prestamo, fecha_limite, fecha_devolucion, estado_prestamo, observaciones) 
                            VALUES (?, ?, ?, ?, ?, 'Pendiente', 'Activo', ?)
                        """, (id_formulario, nom_r, rut_r, hoy_str, fecha_l.isoformat(), obs_p.strip()))
                        id_movimiento_generado = cursor.lastrowid
                        conn.commit()
                        
                    st.success(f"✅ ¡Préstamo del equipo {id_formulario} asignado correctamente a {nom_r}!")
                    try: ejecutar_respaldo_automatico_ti()
                    except: pass
                    
                    # Estructuramos la caché para renderizar el documento imprimible
                    st.session_state["acta_comodato_print_cache"] = {
                        "id_prestamo": id_movimiento_generado,
                        "id_equipo": id_formulario,
                        "tipo": tipo_detectado,
                        "marca": marca_detectada,
                        "modelo": modelo_detectado,
                        "custodio": nom_r,
                        "rut": rut_r,
                        "fecha_entrega": date.today().strftime('%d/%m/%Y'),
                        "fecha_limite": fecha_l.strftime('%d/%m/%Y'),
                        "observaciones": obs_p.strip()
                    }
                    st.session_state["cache_codigo_prestamo"] = ""
                    st.rerun()

        # --- RECEPTÁCULO DEL ACTA OFICIAL: GENERACIÓN E IMPRESIÓN ---
        if st.session_state["acta_comodato_print_cache"] is not None:
            st.markdown("---")
            st.markdown("### 🖨️ Acta de Asignación y Comodato Emitida")
            
            dt_acta = st.session_state["acta_comodato_print_cache"]
            
            logo_escuela_b64 = ""
            if os.path.exists("logo_escuela.png"):
                try:
                    logo_escuela_b64 = f"<img src='data:image/png;base64,{base64.b64encode(open('logo_escuela.png', 'rb').read()).decode()}' style='height:70px;'>"
                except: pass

            # Plantilla HTML limpia del acta escolar para st.html
            html_documento_comodato = f"""
            <div style="padding:22px; border:2px solid #333; background:#fff; color:#000; font-family:Arial,sans-serif; line-height:1.6;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    {logo_escuela_b64}
                    <div style="text-align:right;">
                        <h3 style="margin:0; font-size:17px; font-weight:bold; color:#000;">ACTA DE ASIGNACIÓN Y COMODATO TECNOLÓGICO</h3>
                        <p style="margin:2px 0; font-weight:bold; font-size:12px; color:#000;">{nombre_institucion}</p>
                        <p style="margin:0; font-family:monospace; font-size:11px; color:#444;">Ref: REG-COMODATO-{dt_acta['id_prestamo']}</p>
                    </div>
                </div>
                <hr style="border:1px solid #000; margin:15px 0;">
                <p style="font-size:14px; text-align:justify; color:#000;">Por medio del presente documento, se deja constancia oficial del préstamo, entrega conforme y asignación de responsabilidad bajo resguardo del siguiente activo informático institucional:</p>
                
                <table style="width:100%; border-collapse:collapse; margin:15px 0; font-size:13px; color:#000;">
                    <tr style="background:#f2f2f2;">
                        <th style="border:1px solid #000; padding:7px; text-align:left; width:35%;">Especificación del Componente</th>
                        <th style="border:1px solid #000; padding:7px; text-align:left;">Detalle y Trazabilidad Registrada</th>
                    </tr>
                    <tr><td style="border:1px solid #000; padding:7px;"><b>Código Único Activo (ID):</b></td><td style="border:1px solid #000; padding:7px; font-family:monospace; font-weight:bold;">{dt_acta['id_equipo']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:7px;"><b>Tipo de Hardware:</b></td><td style="border:1px solid #000; padding:7px;">{dt_acta['tipo']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:7px;"><b>Marca / Modelo:</b></td><td style="border:1px solid #000; padding:7px;">{dt_acta['marca']} / {dt_acta['modelo']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:7px;"><b>Docente Custodio:</b></td><td style="border:1px solid #000; padding:7px; font-weight:bold;">{dt_acta['custodio']} (RUT: {dt_acta['rut']})</td></tr>
                    <tr><td style="border:1px solid #000; padding:7px;"><b>Fecha de Asignación:</b></td><td style="border:1px solid #000; padding:7px;">{dt_acta['fecha_entrega']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:7px;"><b>Plazo Máximo de Retorno:</b></td><td style="border:1px solid #000; padding:7px; color:#00f; font-weight:bold;">{dt_acta['fecha_limite']}</td></tr>
                </table>
                
                <div style="border:1px solid #333; padding:10px; background:#fafafa; font-size:13px; margin:15px 0; color:#000;">
                    <b>Elementos, Cables y Accesorios Adicionales Entregados:</b><br>{dt_acta['observaciones']}
                </div>
                
                <div style="margin-top:55px; display:flex; justify-content:space-between; font-size:12px; color:#000;">
                    <div style="text-align:center; width:45%; border-top:1px solid #000; padding-top:4px;"><b>Firma Funcionario Custodio</b><br>Aceptación de Responsabilidad</div>
                    <div style="text-align:center; width:45%; border-top:1px solid #000; padding-top:4px;"><b>Firma Entrega Conforme</b><br>Soporte e Inventario TI</div>
                </div>
            </div>
            """

            # Contenedor adaptativo para mandar a la impresora
            html_pagina_impresion_comodato = f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='padding:10mm; background:#fff;'>{html_documento_comodato}<script>window.onload=function(){{setTimeout(function(){{window.print();}},300);}};</script></body></html>"
            b64_print_comodato = base64.b64encode(html_pagina_impresion_comodato.encode('utf-8')).decode('utf-8')

            # Renderizado nativo
            st.html(html_documento_comodato)
            st.markdown("<br>", unsafe_allow_html=True)
            
            c_c_btn1, c_c_btn2 = st.columns(2)
            with c_c_btn1:
                if st.button("🖨️ Abrir Pantalla de Impresión", type="primary", use_container_width=True, key=f"btn_print_comodato_final_{dt_acta['id_prestamo']}"):
                    js_action_comodato = f"<script>var w=window.open(); if(w){{w.document.write(atob('{b64_print_comodato}')); w.document.close();}}else{{alert('⚠️ Por favor, habilite los permisos para Pop-ups.');}}</script>"
                    st.components.v1.html(js_action_comodato, height=0, width=0)
            with c_c_btn2:
                if st.button("🔄 Siguiente Transacción / Concluir", use_container_width=True, key="btn_clear_comodato_final_action"):
                    st.session_state["acta_comodato_print_cache"] = None
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

    # --- TAB 2: PROCESAR DEVOLUCIÓN Y GENERAR ACTA DE RETORNO (PARTE 1 DE 3) ---
    with tab2:
        st.subheader("🔙 Procesar Devolución Física de Equipos")
        
        with obtener_conexion() as conn:
            df_act = pd.read_sql_query("SELECT id_prestamo, id_equipo, usuario, rut, observaciones FROM prestamos WHERE estado_prestamo='Activo'", conn)
            
        if not df_act.empty:
            lista_combobox_dev = [f"ID:{r['id_prestamo']} | Equipo: {r['id_equipo']} | Custodio: {r['usuario']}" for _, r in df_act.iterrows()]
            p_sel = st.selectbox("Selecciona el Préstamo/Equipo a recibir:", lista_combobox_dev, key="sb_procesar_dev_master")
            
            obs_devolucion = st.text_input("Estado o condición de recepción del hardware:", placeholder="ej: Devuelto con cargador, operativo sin detalles.")
            
            if st.button("Procesar Devolución Física", key="btn_ejecutar_devolucion_real", use_container_width=True):
                # Extraemos de forma segura el ID numérico del préstamo seleccionado
                id_p = int(p_sel.split(" | ")[0].split(":")[1])
                
                # Buscamos en el DataFrame los datos de la fila seleccionada
                fila_seleccionada = df_act[df_act['id_prestamo'] == id_p].iloc[0]
                hoy_str = date.today().isoformat()
                
                with obtener_conexion() as conn:
                    conn.cursor().execute("UPDATE prestamos SET fecha_devolucion=?, estado_prestamo='Devuelto', observaciones=? WHERE id_prestamo=?", (hoy_str, obs_devolucion.strip(), id_p))
                    conn.commit()
                
                st.success(f"✅ ¡Devolución del equipo {fila_seleccionada['id_equipo']} archivada correctamente!")
                
                # Almacenamos la información en el estado de sesión para el renderizado único del reporte HTML
                st.session_state["ultima_devolucion"] = {
                    "id_prestamo": id_p,
                    "id_equipo": fila_seleccionada['id_equipo'],
                    "usuario": fila_seleccionada['usuario'],
                    "rut": fila_seleccionada['rut'],
                    "fecha_devolucion": hoy_str,
                    "observaciones_entrega": fila_seleccionada['observaciones'],
                    "observaciones_retorno": obs_devolucion.strip()
                }
                st.rerun()
        else:
            st.info("🤝 Actualmente no existen préstamos de hardware activos en el establecimiento. Todos los equipos se encuentran en bodega.")

        # --- TAB 2: PROCESAR DEVOLUCIÓN Y GENERAR ACTA DE RETORNO (PARTE 2 DE 3) ---
        if "ultima_devolucion" in st.session_state:
            st.markdown("---")
            st.markdown("### 🖨️ Documento Acta de Recepción Generado")
            st.info("💡 Revisa los datos abajo. Haz clic en 'Abrir Impresión Física' o presiona **Ctrl + P** en tu teclado para mandar a la impresora o guardar como PDF.")
            
            datos_d = st.session_state["ultima_devolucion"]
            
            # Extracción limpia del cargo evitando tuplas ('',)
            with obtener_conexion() as conn:
                res_bd_dev = conn.cursor().execute("SELECT tipo_usuario FROM usuarios WHERE rut = ?", (datos_d['rut'],)).fetchone()
            
            cargo_usuario_dev = res_bd_dev[0] if res_bd_dev and res_bd_dev[0] else "Personal Institucional"
            
            # Procesamiento automático de la imagen Base64 para el logo de la escuela
            imagen_logo_html_dev = ""
            ruta_logo_local = "logo_escuela.png"
            
            if os.path.exists(ruta_logo_local):
                try:
                    with open(ruta_logo_local, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode()
                    imagen_logo_html_dev = f"<img class='print-txt' src='data:image/png;base64,{encoded_string}' style='height: 75px; width: auto; object-fit: contain;'>"
                except Exception:
                    pass

            st.markdown("""
                <style>
                @media print {
                    div[data-testid="stSidebar"], header, footer, div[data-testid="stHeader"],
                    div.stAlert, div.stButton, button, .stDownloadButton, [data-testid="stExpander"], 
                    h1, h2, h3, hr, p:not(.print-txt), span:not(.print-txt), div:not(.zona-comodato) { 
                        display: none !important; 
                    }
                    .main, .main .block-container, [data-testid="stAppViewContainer"], html, body {
                        padding: 0mm !important; margin: 0mm !important; max-width: 100% !important; background-color: #fff !important; color: #000 !important;
                    }
                    .zona-comodato {
                        display: block !important; padding: 10mm !important; font-family: 'Arial', sans-serif !important; color: #000 !important; background: #fff !important; line-height: 1.5 !important; border: none !important;
                    }
                    * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
                    @page { margin: 15mm !important; size: letter; }
                }
                </style>
            """, unsafe_allow_html=True)
            
            html_devolucion = '<div class="zona-comodato" style="padding: 20px; border: 1px solid #ccc; background-color: #fafafa; border-radius: 6px; color: #000;">'
            html_devolucion += "<div style='display: flex; align-items: center; justify-content: center; gap: 20px; margin-bottom: 15px;'> "
            html_devolucion += imagen_logo_html_dev
            html_devolucion += "<div style='text-align: center;'>"
            html_devolucion += "<h2 class='print-txt' style='margin: 0; color: #111; font-size: 20px;'>ACTA DE RECEPCIÓN Y DEVOLUCIÓN TI</h2>"
            html_devolucion += f"<p class='print-txt' style='margin: 5px 0 0 0; font-size: 13px; text-transform: uppercase; font-weight: bold; letter-spacing: 1px;'>{nombre_institucion}</p>"
            html_devolucion += "</div></div><hr style='border: 1px solid #000;'><br>"
            
            html_devolucion += f"""
                <p class='print-txt' style='font-size:14px; margin-top:20px;'>Por medio del presente documento, se deja constancia oficial del retorno y recepción del activo tecnológico de propiedad del establecimiento educacional descrito a continuación:</p>
                <table class='print-txt' style='width:100%; border-collapse: collapse; margin: 20px 0; font-size:14px;'>
                    <tr style='background-color:#eee;'><th style='border:1px solid #999; padding:8px; text-align:left;'>Concepto / Ítem</th><th style='border:1px solid #999; padding:8px; text-align:left;'>Detalle de Recepción</th></tr>
                    <tr><td style='border:1px solid #999; padding:8px;'><b>ID Operación Movimiento:</b></td><td style='border:1px solid #999; padding:8px;'>DEV-{datos_d['id_prestamo']}</td></tr>
                    <tr><td style='border:1px solid #999; padding:8px;'><b>Código de Equipo Recibido:</b></td><td style='border:1px solid #999; padding:8px;'>{datos_d['id_equipo']}</td></tr>
                    <tr><td style='border:1px solid #999; padding:8px;'><b>Custodio que Devuelve:</b></td><td style='border:1px solid #999; padding:8px;'>{datos_d['usuario']}</td></tr>
                    <tr><td style='border:1px solid #999; padding:8px;'><b>RUT Custodio:</b></td><td style='border:1px solid #999; padding:8px;'>{datos_d['rut']}</td></tr>
                    <tr><td style='border:1px solid #999; padding:8px;'><b>Tipo de Usuario / Cargo:</b></td><td style='border:1px solid #999; padding:8px;'>{cargo_usuario_dev}</td></tr>
                    <tr><td style='border:1px solid #999; padding:8px;'><b>Fecha Real de Retorno:</b></td><td style='border:1px solid #999; padding:8px;'>{datos_d['fecha_devolucion']}</td></tr>
                </table>
            """
            # --- TAB 2: PROCESAR DEVOLUCIÓN Y GENERAR ACTA DE RETORNO (PARTE 3 DE 3 CORREGIDA) ---
            html_devolucion += f"<div class='print-txt' style='margin:15px 0; padding:10px; border:1px solid #999; background:#fff; font-size:13px;'><b>Historial Clínico del Hardware:</b><br>📌 <i>Estado inicial al prestarse:</i> {datos_d['observaciones_entrega'] if datos_d['observaciones_entrega'] else 'Sin observaciones registradas.'}<br>📥 <i>Condición física de recepción en bodega:</i> {datos_d['observaciones_retorno'] if datos_d['observaciones_retorno'] else 'Equipo devuelto conforme y completo.'}</div>"
            
            html_devolucion += f"<div class='print-txt' style='font-size:12px; text-align:justify; margin-top:20px; color:#111; line-height:1.4;'><b>DECLARACIÓN DE CONFORMIDAD TI:</b><br>Por el presente acto, la unidad de Gestión Tecnológica del establecimiento certifica haber recibido el hardware inventariado de vuelta en sus dependencias. El custodio queda liberado de la responsabilidad de tenencia y cuidado del componente a partir de la firma de este documento.</div>"
            
            # CORRECCIÓN DEFINITIVA DE SANGRÍA MULTILÍNEA: Concatenación directa sin saltos de carro que rompan Python
            html_devolucion += f"<div class='print-txt' style='margin-top:60px; display:flex; justify-content:space-between; font-size:13px;'><div style='text-align:center; width:45%; border-top:1px solid #000; padding-top:5px;'>Firma Funcionario que Devuelve<br>RUT: {datos_d['rut']}</div><div style='text-align:center; width:45%; border-top:1px solid #000; padding-top:5px;'>Firma Encargado de Laboratorio<br>{nombre_institucion}</div></div>"
            
            html_devolucion += f"<p class='print-txt' style='text-align:center; font-size:10px; margin-top:40px; color:#666;'>Acta de Cierre TI - Escuela Felipe Cubillos</p>"

            html_devolucion += "</div>"

            # === NUEVA SOLUCIÓN DE IMPRESIÓN FORZADA (BYPASS SANDBOX) COMPATIBLE CON MARGINS ===
            html_pagina_impresion_d = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Acta de Recepcion - Escuela Felipe Cubillos</title>
                <style>
                    body {{ background: #ffffff; margin: 0; padding: 10mm; font-family: Arial, sans-serif; }}
                    @media print {{
                        body {{ padding: 0; }}
                        @page {{ margin: 15mm; size: letter; }}
                    }}
                </style>
            </head>
            <body>
                {html_devolucion}
                <script>
                    window.onload = function() {{
                        setTimeout(function() {{ window.print(); }}, 350);
                    }};
                </script>
            </body>
            </html>
            """

            # Codificación limpia para el inyector de devoluciones
            html_escape_b64_d = base64.b64encode(html_pagina_impresion_d.encode('utf-8')).decode('utf-8')

            st.markdown(html_devolucion, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            col_dev_btn1, col_dev_btn2, col_dev_btn3 = st.columns(3)
            
            with col_dev_btn1:
                # NUEVO BOTÓN PREMIUM COMPATIBLE CON VENTANAS EMERGENTES SEGURAS
                if st.button("🖨️ Abrir Ventana de Impresión", key=f"btn_print_forced_dev_{datos_d['id_prestamo']}", use_container_width=True, type="primary"):
                    js_bypass_sandbox_d = f"""
                    <script>
                        var win = window.open();
                        if (win) {{
                            win.document.write(atob("{html_escape_b64_d}"));
                            win.document.close();
                        }} else {{
                            alert("⚠️ Navegador bloqueado: Habilite los permisos para ventanas emergentes (Pop-ups) en la barra de direcciones.");
                        }}
                    </script>
                    """
                    st.components.v1.html(js_bypass_sandbox_d, height=0, width=0)
            
            with col_dev_btn2:
                html_descargable_dev = f"<!DOCTYPE html><html><body style='padding:20px;'>{html_devolucion}</body></html>"
                st.download_button(
                    label="📥 Descargar Acta (.html)",
                    data=html_descargable_dev,
                    file_name=f"acta_recepcion_{datos_d['id_equipo']}.html",
                    mime="text/html",
                    key=f"btn_dl_dev_{datos_d['id_prestamo']}",
                    use_container_width=True
                )
                
            with col_dev_btn3:
                if st.button("🔄 Siguiente Devolución", key=f"btn_clr_dev_{datos_d['id_prestamo']}", use_container_width=True):
                    if "ultima_devolucion" in st.session_state:
                        del st.session_state["ultima_devolucion"]
                    st.rerun()

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
    nombre_institucion = st.text_input("🏫 Institución para la Etiqueta:", value=nombre_institucion, key="txt_input_global_institucion_qr").strip()
    
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
# 📦 MÓDULO INTEGRAL COMPLETO: GESTOR DE INVENTARIO (PARTE 1 DE 6)
# =========================================================================
elif choice == "Gestor de Inventario":
    st.header("📦 Control de Inventario de Insumos y Consumibles")
    st.caption("Administración de stock general de materiales, repuestos técnicos y artículos de oficina.")
    
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insumos_stock (
                id_insumo INTEGER PRIMARY KEY AUTOINCREMENT, 
                nombre_insumo TEXT UNIQUE,
                categoria TEXT, 
                stock_actual INTEGER DEFAULT 0, 
                stock_minimo INTEGER DEFAULT 5, 
                unidad_medida TEXT DEFAULT 'Unidades'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS insumos_movimientos (
                id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT, 
                id_insumo INTEGER, 
                tipo_movimiento TEXT,
                cantidad INTEGER, 
                fecha TEXT, 
                responsable TEXT, 
                motivo TEXT, 
                FOREIGN KEY(id_insumo) REFERENCES insumos_stock(id_insumo)
            )
        """)
        conn.commit()

    # Estructuración unificada de las 5 pestañas de trabajo escolar
    tab_ins1, tab_ins2, tab_ins3, tab_ins4, tab_ins5 = st.tabs([
        "📊 Stock y Alertas", 
        "🔄 Registrar Movimiento", 
        "📋 Historial de Auditoría", 
        "🗑️ Dar de Baja Artículo", 
        "✏️ Modificar Artículo"
    ])

    with obtener_conexion() as conn:
        df_insumos_base = pd.read_sql_query("SELECT id_insumo, nombre_insumo, stock_actual, unidad_medida FROM insumos_stock ORDER BY nombre_insumo ASC", conn)
        df_usuarios_ins = pd.read_sql_query("SELECT nombre FROM usuarios ORDER BY nombre ASC", conn)
    
    lista_insumos_combo = [f"ID:{row['id_insumo']} | {row['nombre_insumo']} ({row['stock_actual']} {row['unidad_medida']})" for _, row in df_insumos_base.iterrows()]
    lista_responsables_ins = [row['nombre'] for _, row in df_usuarios_ins.iterrows()] if not df_usuarios_ins.empty else ["Encargado TI General"]
    # =========================================================================
    # 📦 MÓDULO INTEGRAL COMPLETO: GESTOR DE INVENTARIO (PARTE 2 DE 6)
    # =========================================================================

    # --- PESTAÑA 1: STOCK ACTUAL ---
    with tab_ins1:
        st.subheader("📊 Niveles de Stock en Bodega")
        with obtener_conexion() as conn:
            df_stock = pd.read_sql_query("""
                SELECT id_insumo as 'ID', 
                       nombre_insumo as 'Descripción del Artículo', 
                       categoria as 'Categoría', 
                       stock_actual as 'Stock Actual', 
                       stock_minimo as 'Mínimo Crítico', 
                       unidad_medida as 'Unidad' 
                FROM insumos_stock 
                ORDER BY categoria ASC, nombre_insumo ASC
            """, conn)
            
        if not df_stock.empty:
            df_critico = df_stock[df_stock['Stock Actual'] <= df_stock['Mínimo Crítico']]
            if not df_critico.empty:
                st.error(f"🚨 **ALERTA DE REABASTECIMIENTO:** Hay **{len(df_critico)} artículos** con stock crítico igual o inferior al mínimo.")
                for _, fila_c in df_critico.iterrows():
                    st.markdown(f"❌ **{fila_c['Descripción del Artículo']}** registra solo **{fila_c['Stock Actual']} {fila_c['Unidad']}**")
                st.markdown("---")
            
            buscar_ins = st.text_input("🔍 Filtrar insumos por descripción o categoría:", key="key_buscador_stock_ins_tab1_fijo")
            df_stock_filtrado = df_stock.copy()
            if buscar_ins.strip():
                term = buscar_ins.strip().lower()
                df_stock_filtrado = df_stock[df_stock['Descripción del Artículo'].str.lower().str.contains(term) | df_stock['Categoría'].str.lower().str.contains(term)]
            
            st.dataframe(df_stock_filtrado, use_container_width=True, hide_index=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 Descargar Reporte de Bodega Consolidado (Excel)",
                data=to_excel(df_stock_filtrado),
                file_name="inventario_stock_insumos.xlsx",
                use_container_width=True,
                key="btn_dl_excel_insumos_stock_p1"
            )
        else:
            st.info("💡 La bodega de consumibles se encuentra vacía. Catalogue su primer artículo en la pestaña 'Registrar Movimiento'.")
    # =========================================================================
    # 📦 MÓDULO INTEGRAL COMPLETO: GESTOR DE INVENTARIO (PARTE 3 DE 6)
    # =========================================================================

    # --- PESTAÑA 2: MOVIMIENTOS CON LECTOR ---
    with tab_ins2:
        st.subheader("🔄 Gestión de Flujos de Materiales")
        accion_inventario = st.radio("Selecciona la operación de bodega a tramitar:", ["📉 Registrar Salida / Consumo", "📈 Registrar Entrada / Reabastecimiento", "✨ Crear Nuevo Artículo de Insumo"], horizontal=True, key="radio_accion_insumos_v5_final")
        st.markdown("---")
        
        if "cache_barra_insumo" not in st.session_state: st.session_state["cache_barra_insumo"] = ""
        if "insumo_seleccionado_id" not in st.session_state: st.session_state["insumo_seleccionado_id"] = None
        if "cache_crear_barra_insumo" not in st.session_state: st.session_state["cache_crear_barra_insumo"] = ""

        # --- FLUJO A: PROCESAMIENTO DE ENTRADAS Y SALIDAS DE MATERIALES ---
        if accion_inventario == "📉 Registrar Salida / Consumo" or accion_inventario == "📈 Registrar Entrada / Reabastecimiento":
            tipo_mov = "Salida" if "Salida" in accion_inventario else "Entrada"
            codigo_barra_ins_input = st.text_input("📸 PISTOLEE EL CÓDIGO DE BARRAS DEL INSUMO AQUÍ:", value=st.session_state["cache_barra_insumo"], placeholder="Haga clic aquí antes de pasar el lector...", key="txt_pistola_insumos_directo_flow").strip().upper()

            if codigo_barra_ins_input != st.session_state["cache_barra_insumo"]:
                st.session_state["cache_barra_insumo"] = codigo_barra_ins_input
                st.rerun()

            id_leido_insumo = st.session_state["cache_barra_insumo"]
            insumo_encontrado_dict = None
            bloqueado_por_bodega = False

            if id_leido_insumo:
                id_busqueda = id_leido_insumo.replace("ID-INS-", "").replace("ID:", "").strip()
                try: id_busqueda_int = int(id_busqueda.split("|")[0])
                except ValueError: id_busqueda_int = -1

                with obtener_conexion() as conn:
                    df_ins_local = pd.read_sql_query("SELECT id_insumo, nombre_insumo, categoria, stock_actual, stock_minimo, unidad_medida FROM insumos_stock WHERE id_insumo = ? OR UPPER(nombre_insumo) = ?", conn, params=(id_busqueda_int, id_leido_insumo))
                if not df_ins_local.empty:
                    res_lista = df_ins_local.to_dict('records')
                    insumo_encontrado_dict = res_lista[0]
                    st.session_state["insumo_seleccionado_id"] = insumo_encontrado_dict['id_insumo']
                else:
                    st.error(f"❌ El código '{id_leido_insumo}' no corresponde a ningún artículo catalogado en bodega.")
                    st.session_state["insumo_seleccionado_id"] = None
                    bloqueado_por_bodega = True
                    if st.button("🔄 Limpiar Lector", use_container_width=True, key="btn_clear_lector_err"):
                        st.session_state["cache_barra_insumo"] = ""
                        st.rerun()

            st.markdown("##### 📦 Estado de Existencias del Material")
            col_b_ins1, col_b_ins2, col_b_ins3, col_b_ins4 = st.columns(4)
            col_b_ins1.markdown(f"**Nombre:** {insumo_encontrado_dict['nombre_insumo'] if insumo_encontrado_dict else 'No cargado'}")
            col_b_ins2.markdown(f"**Categoría:** {insumo_encontrado_dict['categoria'] if insumo_encontrado_dict else 'No cargada'}")
            col_b_ins3.markdown(f"**Stock Actual:** {insumo_encontrado_dict['stock_actual'] if insumo_encontrado_dict else 0}")
            col_b_ins4.markdown(f"**Mínimo Crítico:** {insumo_encontrado_dict['stock_minimo'] if insumo_encontrado_dict else 0}")
            st.markdown("---")
    # =========================================================================
    # 📦 MÓDULO INTEGRAL COMPLETO: GESTOR DE INVENTARIO (PARTE 4 DE 6)
    # =========================================================================
            with st.form("form_movimiento_stock_barra_premium_v4", clear_on_submit=False):
                col_f_ins1, col_f_ins2 = st.columns(2)
                cant_mov = col_f_ins1.number_input(f"Cantidad física a registrar:", min_value=1, value=1, step=1, key="num_cant_mov_ins_v4")
                resp_mov = col_f_ins1.selectbox("Funcionario Responsable:", lista_responsables_ins, key="sb_resp_mov_ins_v4")
                motivo_mov = col_f_ins2.text_area("Justificación o destino:", placeholder="ej: Retiro para sala...", key="tx_motivo_mov_ins_v4")
                if st.form_submit_button(f"Sincronizar {tipo_mov} en Bodega", use_container_width=True):
                    id_insumo_real = st.session_state["insumo_seleccionado_id"]
                    if not id_insumo_real or bloqueado_por_bodega: st.error("⛔ Escanee un artículo válido.")
                    else:
                        stock_actual_bd = int(insumo_encontrado_dict['stock_actual'])
                        if tipo_mov == "Salida" and cant_mov > stock_actual_bd: st.error("⛔ Error de Stock.")
                        else:
                            nuevo_stock = (stock_actual_bd + cant_mov) if tipo_mov == "Entrada" else (stock_actual_bd - cant_mov)
                            with obtener_conexion() as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE insumos_stock SET stock_actual = ? WHERE id_insumo = ?", (nuevo_stock, id_insumo_real))
                                cursor.execute("INSERT INTO insumos_movimientos (id_insumo, tipo_movimiento, cantidad, fecha, responsable, motivo) VALUES (?, ?, ?, ?, ?, ?)", (id_insumo_real, tipo_mov, cant_mov, date.today().isoformat(), resp_mov, motivo_mov.strip()))
                                conn.commit()
                            st.toast("📦 Stock Sincronizado.", icon="✅")
                            st.session_state["cache_barra_insumo"] = ""
                            st.session_state["insumo_seleccionado_id"] = None
                            st.rerun()

        # --- FLUJO B: CREACIÓN DE NUEVOS ARTÍCULOS ---
        if accion_inventario == "✨ Crear Nuevo Artículo de Insumo":
            if st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro":
                codigo_barra_nuevo_ins = st.text_input("📸 PISTOLEE EL CÓDIGO DE BARRAS DEL ARTÍCULO NUEVO (OPCIONAL):", value=st.session_state["cache_crear_barra_insumo"], placeholder="👉 HAGA CLIC AQUÍ Y PISTOLEE LA CAJA...", key="txt_pistola_crear_insumo_nuevo_v4").strip().upper()
                if codigo_barra_nuevo_ins != st.session_state["cache_crear_barra_insumo"]:
                    st.session_state["cache_crear_barra_insumo"] = codigo_barra_nuevo_ins
                    st.rerun()

                id_leido_nuevo = st.session_state["cache_crear_barra_insumo"]
                with st.form("form_crear_insumo_nuevo_real_v4", clear_on_submit=False):
                    st.markdown("##### Ficha de Catalogación de Insumo Nuevo")
                    sugerencia_nombre = f"[{id_leido_nuevo}] " if id_leido_nuevo else ""
                    n_nuevo = st.text_input("Nombre / Descripción del Artículo:", value=sugerencia_nombre, key="txt_nombre_nuevo_ins_v4")
                    cat_nuevo = st.selectbox("Categoría del Material:", ["Periféricos / Computación", "Material de Oficina", "Conectividad y Redes", "Repuestos Técnicos", "Otros"], key="sb_cat_nuevo_ins_v4")
                    col_form1, col_form2, col_form3 = st.columns(3)
                    stock_ini = col_form1.number_input("Stock Inicial:", min_value=0, value=0, step=1, key="num_stock_ini_ins_v4")
                    min_ini = col_form2.number_input("Mínimo Crítico:", min_value=1, value=5, step=1, key="num_min_ini_ins_v4")
                    ud_medida = col_form3.selectbox("Unidad de Medida:", ["Unidades", "Metros", "Cajas"], key="sb_ud_medida_ins_v4")
                    
                    if st.form_submit_button("Catalogar Insumo en Sistema", use_container_width=True):
                        if n_nuevo.strip():
                            try:
                                with obtener_conexion() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("INSERT INTO insumos_stock (nombre_insumo, categoria, stock_actual, stock_minimo, unidad_medida) VALUES (?, ?, ?, ?, ?)", (n_nuevo.strip().upper(), cat_nuevo, stock_ini, min_ini, ud_medida))
                                    id_generado = cursor.lastrowid
                                    if stock_ini > 0:
                                        cursor.execute("INSERT INTO insumos_movimientos (id_insumo, tipo_movimiento, cantidad, fecha, responsable, motivo) VALUES (?, 'Entrada', ?, ?, 'Sistema', 'Inventario inicial')", (id_generado, stock_ini, date.today().isoformat()))
                                    conn.commit()
                                st.success("✅ Artículo catalogado.")
                                st.session_state["cache_crear_barra_insumo"] = ""
                                st.rerun()
                            except sqlite3.IntegrityError: st.error("⛔ El artículo ya existe.")
                        else: st.warning("⚠️ Nombre obligatorio.")
            else: st.warning("🔒 Permisos insuficientes.")
    # =========================================================================
    # 📦 MÓDULO INTEGRAL COMPLETO: GESTOR DE INVENTARIO (PARTE 5 DE 6)
    # =========================================================================

    # --- PESTAÑA 3: AUDITORÍA ---
    with tab_ins3:
        st.subheader("📋 Libro de Acta de Movimientos de Bodega")
        with obtener_conexion() as conn:
            df_historial_mov = pd.read_sql_query("SELECT m.id_movimiento as 'Nro Mov', m.fecha as 'Fecha', s.nombre_insumo as 'Artículo', s.categoria as 'Categoría', m.tipo_movimiento as 'Tipo', m.cantidad as 'Cant', m.responsable as 'Operador', m.motivo as 'Motivo' FROM insumos_movimientos m INNER JOIN insumos_stock s ON m.id_insumo = s.id_insumo ORDER BY m.id_movimiento DESC", conn)
        if not df_historial_mov.empty:
            buscar_mov = st.text_input("🔍 Filtrar historial por artículo u operador:", key="key_buscador_auditoria_ins_fijo_2026")
            df_mov_filtrado = df_historial_mov.copy()
            if buscar_mov.strip():
                term_mov = buscar_mov.strip().lower()
                df_mov_filtrado = df_historial_mov[df_historial_mov['Artículo'].str.lower().str.contains(term_mov) | df_historial_mov['Operador'].str.lower().str.contains(term_mov)]
            st.dataframe(df_mov_filtrado, use_container_width=True, hide_index=True)
        else: st.info("No se registran transacciones.")

    # --- PESTAÑA 4: COMPROBANTES E IMPRESIÓN DE ACTAS DE BAJA ---
    with tab_ins4:
        st.subheader("🗑️ Depuración de Catálogo por Obsolescencia")
        if st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro":
            if not lista_insumos_combo: st.info("No hay artículos.")
            else:
                with st.form("form_dar_de_baja_insumo_real_v2", clear_on_submit=False):
                    insumo_a_borrar = st.selectbox("Selecciona el artículo a remover permanentemente:", lista_insumos_combo, key="sb_baja_ins_real_v2")
                    cant_a_borrar = st.number_input("Cantidad física a dar de baja:", min_value=1, value=1, step=1, key="num_baja_ins_cant_v2")
                    motivo_baja = st.selectbox("Diagnóstico causante del descarte:", ["Pérdida de Vida Útil", "Material Dañado / Inoperativo", "Obsolescencia Tecnológica"], key="sb_baja_ins_motivo_v2")
                    obs_baja = st.text_area("Detalle del informe de descarte:", key="tx_baja_ins_obs_v2")
                    
                    if st.form_submit_button("🚨 Confirmar Baja y Emitir Acta Contable", use_container_width=True):
                        if obs_baja.strip() == "": st.error("⛔ Escriba el informe.")
                        else:
                            id_insumo_borrar = int(insumo_a_borrar.split(" | ")[0].split(":")[1])
                            fila_act = next((r for r in df_insumos_base.to_dict('records') if r['id_insumo'] == id_insumo_borrar), None)
                            stock_disponible_real = int(fila_act['stock_actual']) if fila_act else 0
                            
                            if cant_a_borrar > stock_disponible_real: st.error("⛔ Cantidad excede el stock.")
                            else:
                                nuevo_stock = stock_disponible_real - cant_a_borrar
                                hoy_str = date.today().isoformat()
                                with obtener_conexion() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE insumos_stock SET stock_actual = ? WHERE id_insumo = ?", (nuevo_stock, id_insumo_borrar))
                                    cursor.execute("INSERT INTO insumos_movimientos (id_insumo, tipo_movimiento, cantidad, fecha, responsable, motivo) VALUES (?, 'Baja', ?, ?, ?, ?)", (id_insumo_borrar, cant_a_borrar, hoy_str, st.session_state.get('usuario', 'Admin'), f"DESCARTE: {motivo_baja}"))
                                    conn.commit()
                                st.success("🚀 Descontado correctamente.")
                                st.session_state["ultimo_acta_baja_insumo"] = {"id_insumo": id_insumo_borrar, "nombre": str(fila_act['nombre_insumo']), "cantidad_descarte": cant_a_borrar, "unidad": str(fila_act['unidad_medida']), "motivo": motivo_baja, "fecha": date.today().strftime('%d/%m/%Y'), "responsable": st.session_state.get('usuario', 'Encargado TI'), "observaciones": obs_baja.strip()}
                                st.rerun()
    # =========================================================================
    # 📦 MÓDULO INTEGRAL COMPLETO: GESTOR DE INVENTARIO (PARTE 6 DE 6)
    # =========================================================================
                if "ultimo_acta_baja_insumo" in st.session_state:
                    st.markdown("---")
                    datos_ins_baja = st.session_state["ultimo_acta_baja_insumo"]
                    imagen_logo_html = ""
                    if os.path.exists("logo_escuela.png"):
                        try: imagen_logo_html = f"<img src='data:image/png;base64,{base64.b64encode(open('logo_escuela.png', 'rb').read()).decode()}' style='height: 65px; width: auto;'>"
                        except: pass

                    html_baja_insumo = f"""
                    <div style="padding: 25px; border: 2px solid #333; background-color: #ffffff; color: #000; font-family: Arial; line-height: 1.6;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            {imagen_logo_html}
                            <div style="text-align: right;">
                                <h3 style="margin: 0; font-weight: bold;">ACTA DE BAJA Y SANEAMIENTO DE BODEGA</h3>
                                <p style="margin: 3px 0; font-size: 12px; font-weight: bold;">{nombre_institucion}</p>
                                <p style="margin: 0; font-family: monospace; font-size: 11px; color: #444;">Ref: REG-DESCARTE-{datos_ins_baja['id_insumo']}</p>
                            </div>
                        </div>
                        <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; color: #000;">
                            <tr style="background-color: #f2f2f2;"><th style="border: 1px solid #000; padding: 8px; text-align: left;">Item Evaluado</th><th style="border: 1px solid #000; padding: 8px; text-align: left;">Detalle de la Salida</th></tr>
                            <tr><td style="border: 1px solid #000; padding: 8px;"><b>Insumo:</b></td><td style="border: 1px solid #000; padding: 8px;">{datos_ins_baja['nombre']}</td></tr>
                            <tr><td style="border: 1px solid #000; padding: 8px;"><b>Cantidad Retirada:</b></td><td style="border: 1px solid #000; padding: 8px; color: #b00; font-weight: bold;">{datos_ins_baja['cantidad_descarte']} {datos_ins_baja['unidad']}</td></tr>
                            <tr><td style="border: 1px solid #000; padding: 8px;"><b>Causa:</b></td><td style="border: 1px solid #000; padding: 8px;">{datos_ins_baja['motivo']}</td></tr>
                            <tr><td style="border: 1px solid #000; padding: 8px;"><b>Fecha:</b></td><td style="border: 1px solid #000; padding: 8px;">{datos_ins_baja['fecha']}</td></tr>
                        </table>
                        <div style="margin: 20px 0; padding: 12px; border: 1px solid #333; background: #fafafa; font-size: 13px; color: #000;"><b>Informe Justificativo:</b><br>{datos_ins_baja['observaciones']}</div>
                        <div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 13px; color: #000;"><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Encargado Bodega</b></div><div style="text-align: center; width: 45%; border-top: 1px solid #000; padding-top: 5px;"><b>Firma Autorización Dirección</b></div></div>
                    </div>
                    """
                    html_pagina_impresion_ins = f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='padding:10mm; background:#fff;'>{html_baja_insumo}<script>window.onload=function(){{setTimeout(function(){{window.print();}},350);}};</script></body></html>"
                    html_escape_b64_ins = base64.b64encode(html_pagina_impresion_ins.encode('utf-8')).decode('utf-8')

                    st.html(html_baja_insumo)
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_btn_ins_b1, col_btn_ins_b2 = st.columns(2)
                    with col_btn_ins_b1:
                        if st.button("🖨️ Abrir Pantalla de Impresión", key=f"btn_print_baja_ins_{datos_ins_baja['id_insumo']}", use_container_width=True, type="primary"):
                            js_print_ins = f"<script>var win = window.open(); if(win){{win.document.write(atob('{html_escape_b64_ins}')); win.document.close();}}else{{alert('⚠️ Permita Pop-ups.');}}</script>"
                            st.components.v1.html(js_print_ins, height=0, width=0)
                    with col_btn_ins_b2:
                        if st.button("🔄 Siguiente Registro / Limpiar Pantalla", use_container_width=True, key="btn_clear_baja_ins_real_v2"):
                            if "ultimo_acta_baja_insumo" in st.session_state: del st.session_state["ultimo_acta_baja_insumo"]
                            st.rerun()
        else: st.warning("🔒 Acceso restringido.")

    # --- PESTAÑA 5: MODIFICACIÓN GENERAL DE FICHA DE INSUMOS ---
    with tab_ins5:
        st.subheader("✏️ Modificar Ficha de Artículo Existente")
        if st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro":
            if not lista_insumos_combo: st.info("No hay artículos.")
            else:
                insumo_editar_sel = st.selectbox("Seleccione el Insumo que desea editar:", lista_insumos_combo, key="key_maestra_edicion_selectbox_2026_fija")
                
                # Extracción y casteo seguro de ID numérico para evitar fallos de Pandas
                try:
                    parte_id = insumo_editar_sel.split(" | ")[0]
                    id_insumo_mod = int(parte_id.split(":")[1])
                except Exception:
                    id_insumo_mod = -1
                
                datos_ins_actual = next((r for r in df_insumos_base.to_dict('records') if r['id_insumo'] == id_insumo_mod), None)
                
                if datos_ins_actual:
                    with obtener_conexion() as conn:
                        res_ext = conn.cursor().execute("SELECT categoria, stock_minimo, unidad_medida FROM insumos_stock WHERE id_insumo = ?", (id_insumo_mod,)).fetchone()
                    cat_base = str(res_ext[0]) if res_ext else "Periféricos / Computación"
                    min_base = int(res_ext[1]) if res_ext else 5
                    ud_base = str(res_ext[2]) if res_ext else "Unidades"
                    
                    with st.form("form_edicion_maestra_insumos_2026_ok", clear_on_submit=False):
                        nuevo_nombre_ins = st.text_input("Modificar Descripción / Nombre Comercial:", value=str(datos_ins_actual['nombre_insumo']))
                        nueva_cat_ins = st.selectbox("Cambiar Categoría de Bodega:", ["Periféricos / Computación", "Material de Oficina", "Conectividad y Redes", "Repuestos Técnicos", "Otros"], index=["Periféricos / Computación", "Material de Oficina", "Conectividad y Redes", "Repuestos Técnicos", "Otros"].index(cat_base) if cat_base in ["Periféricos / Computación", "Material de Oficina", "Conectividad y Redes", "Repuestos Técnicos", "Otros"] else 0)
                        col_ed1, col_ed2 = st.columns(2)
                        nuevo_min_ins = col_ed1.number_input("Reajustar Punto de Alerta Mínimo:", min_value=1, value=min_base, step=1)
                        nueva_ud_ins = col_ed2.selectbox("Modificar Unidad de Medida:", ["Unidades", "Metros", "Cajas"], index=["Unidades", "Metros", "Cajas"].index(ud_base) if ud_base in ["Unidades", "Metros", "Cajas"] else 0)
                        
                        if st.form_submit_button("💾 Guardar Cambios de la Ficha", use_container_width=True):
                            if nuevo_nombre_ins.strip() == "": st.error("⛔ El nombre no puede quedar vacío.")
                            else:
                                try:
                                    nombre_formateado_mod = nuevo_nombre_ins.strip().upper()
                                    with obtener_conexion() as conn:
                                        cursor = conn.cursor()
                                        cursor.execute("UPDATE insumos_stock SET nombre_insumo = ?, categoria = ?, stock_minimo = ?, unidad_medida = ? WHERE id_insumo = ?", (nombre_formateado_mod, nueva_cat_ins, nuevo_min_ins, nueva_ud_ins, id_insumo_mod))
                                        cursor.execute("INSERT INTO insumos_movimientos (id_insumo, tipo_movimiento, cantidad, fecha, responsable, motivo) VALUES (?, 'Modificación', 0, ?, ?, 'ACTUALIZACIÓN DE FICHA')", (id_insumo_mod, date.today().isoformat(), st.session_state.get('usuario', 'Admin')))
                                        conn.commit()
                                    st.toast("💾 Ficha actualizada con éxito.", icon="💾")
                                    try: ejecutar_respaldo_automatico_ti()
                                    except: pass
                                    st.rerun()
                                except sqlite3.IntegrityError: st.error("⛔ Ya existe otro artículo con ese nombre.")
        else: st.warning("🔒 Permisos insuficientes.")



# =========================================================================
# 📝 MÓDULO: BITÁCORA DE NOTAS (PARTE 1 DE 2 - CON ALERTA SONORA)
# =========================================================================
elif choice == "Bitácora de Notas":
    # --- TAB BITÁCORA - PARTE 1 DE 3 (ESTRUCTURA DE RED Y TRY UNIFICADA) ---
        # --- TAB BITÁCORA - PARTE 1 DE 3 (OUTLOOK CON VARIABLES CORREGIDAS) ---
    st.header("📝 Bitácora de Novedades Diarias del Laboratorio")
    if st.button("🔊 Probar Sonido de Alerta Ahora"):
        url_sonido_alerta = "https://soundhelix.com"
        st.markdown(f'<audio autoplay src="{url_sonido_alerta}" type="audio/mpeg" style="display:none;"></audio>', unsafe_allow_html=True)
        st.toast("Sonido reproducido", icon="🔔")

    with obtener_conexion() as conn:
        cursor = conn.cursor()
        columnas_nuevas = [("estado_nota", "TEXT DEFAULT 'Pendiente'"), ("fecha_ejecucion", "TEXT DEFAULT 'N/A'"), ("fecha_vencimiento", "TEXT DEFAULT 'N/A'")]
        for col_name, col_type in columnas_nuevas:
            try: 
                cursor.execute(f"ALTER TABLE bitacora ADD COLUMN {col_name} {col_type}")
            except Exception: 
                pass
        conn.commit()
    hoy_str = date.today().isoformat()
    query_alertas_bit = "SELECT id_nota, nota, fecha_vencimiento FROM bitacora WHERE estado_nota = 'Pendiente' AND fecha_vencimiento != 'N/A' AND fecha_vencimiento < ?"
    with obtener_conexion() as conn:
        df_retrasos_bit = pd.read_sql_query(query_alertas_bit, conn, params=(hoy_str,))

    if not df_retrasos_bit.empty:
        st.error(f"⚠️ **AVISO DE DEMORA:** Se han detectado **{len(df_retrasos_bit)} tareas pendientes** que superaron su fecha máxima de ejecución.")
        st.markdown('<audio autoplay src="https://soundhelix.com" type="audio/mpeg" style="display:none;"></audio>', unsafe_allow_html=True)
        
        with obtener_conexion() as conn:
            df_encargados_mail = pd.read_sql_query("SELECT nombre, correo FROM usuarios WHERE tipo_usuario IN ('Profesor', 'Técnico')", conn)
            
        for idx, fila_retraso in df_retrasos_bit.iterrows():
            # CORRECCIÓN DEFINITIVA: Declarar la variable con el nombre exacto que busca el HTML
            try: 
                dias_atraso = (date.today() - date.fromisoformat(fila_retraso['fecha_vencimiento'])).days
            except: 
                dias_atraso = 1
            
            usuario_a_notificar = None
            col_txt_b, col_sel_b, col_btn_b = st.columns([0.45, 0.35, 0.20])
            with col_txt_b:
                st.markdown(f"🔴 **[ID {fila_retraso['id_nota']}] - {dias_atraso} días demorada:** {fila_retraso['nota'][:40]}...")
            
            with col_sel_b:
                if not df_encargados_mail.empty:
                    lista_u_notif = [f"{r['nombre']} | {r['correo']}" for _, r in df_encargados_mail.iterrows()]
                    usuario_a_notificar = st.selectbox("Notificar a:", lista_u_notif, key=f"sb_notif_bit_user_{fila_retraso['id_nota']}_{idx}")
                else:
                    st.caption("Sin usuarios creados")
                    
            with col_btn_b:
                if st.button("✉️ Enviar Alerta", key=f"btn_send_mail_bit_{fila_retraso['id_nota']}_{idx}", disabled=(usuario_a_notificar is None), use_container_width=True):
                    with st.spinner("Enviando..."):
                        partes_usuario = usuario_a_notificar.split(" | ")
                        u_nombre = partes_usuario if len(partes_usuario) > 1 else partes_usuario
                        u_correo = partes_usuario if len(partes_usuario) > 1 else "correo@defecto.cl"
                        
                        try:
                            # Conexión limpia y directa protegida con control de errores válido
                            server_b = smtplib.SMTP("://outlook.com", 587, timeout=10)
                            server_b.ehlo()
                            server_b.starttls()
                            server_b.ehlo()
                            server_b.login("laboratorio.felipecubillos@outlook.com", "TuContraseñaNormalAquí")
                            server_b.sendmail("laboratorio.felipecubillos@outlook.com", [u_correo], f"Subject: Alerta Tarea ID {fila_retraso['id_nota']}\n\nHola {u_nombre}, tarea demorada.")
                            server_b.quit()
                            st.toast(f"¡Aviso enviado a {u_nombre}!", icon="✅")
                        except Exception:
                            st.toast(f"⚠️ Red ocupada. Avisar a {u_nombre} de forma verbal.", icon="✉️")

    # --- TAB BITÁCORA - PARTE 2 DE 3 ---
    t_bit1, t_bit2, t_bit3 = st.tabs(["➕ Añadir Nota", "🔄 Modificar Nota / Estado", "📋 Ver Listado Completo"])
    
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
    with t_bit2:
        st.subheader("🔄 Modificar Detalles y Estado de Tareas")
        with obtener_conexion() as conn:
            df_notas_disp = pd.read_sql_query("SELECT id_nota, fecha, nota, estado_nota, fecha_ejecucion, fecha_vencimiento FROM bitacora ORDER BY id_nota DESC LIMIT 30", conn)
        
        if df_notas_disp.empty:
            st.info("No hay novedades registradas para modificar.")
        else:
            opciones_notes = [f"ID:{row['id_nota']} | Est: {row['estado_nota']} | {row['nota'][:30]}..." for _, row in df_notas_disp.iterrows()]
            nota_a_modificar = st.selectbox("Selecciona la nota que deseas editar o resolver:", opciones_notes, key="sb_mod_nota_real")
            
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
    # --- TAB BITÁCORA - PARTE 3 DE 3 ---
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

# Bloque exclusivo de pruebas de conectividad SMTP para el Administrador
    if st.session_state.get("usuario") == "Administrador Maestro":
        st.markdown("---")
        st.subheader("🛠️ Panel de Pruebas de Sistema")
        st.info("Utiliza este botón para verificar la salida de correos automáticos de la Bitácora hacia el Supervisor de TI.")
        
        if st.button("🚀 Forzar Envío de Alerta de Prueba"):
            with st.spinner("Conectando con el servidor de correo y procesando bitácora..."):
                correo_test = st.secrets.get("CORREO_SUPERVISOR_TI", "jcaceres@escuelafelipecubillos.cl")
                
                try:
                    ejecutar_reporte_bitacora_vencida_automatico(correo_test)
                    st.success(f"✅ ¡Prueba ejecutada! Revisa la bandeja de entrada o spam de: {correo_test}")
                    st.caption("Nota: Si la consulta no arrojó tareas pendientes o si el proceso diario ya se había ejecutado hoy, la función se saltará el envío de forma segura.")
                except Exception as e:
                    st.error(f"❌ Error crítico durante la prueba de correo: {str(e)}")
    
    
# =========================================================================
# ❌ MÓDULO: PROCESO DE BAJA TÉCNICA DEFINITIVA (ESTRUCTURA IDÉNTICA A PRÉSTAMOS)
# =========================================================================
elif choice == "Proceso de Baja Técnica Definitiva":
    st.header("❌ Control de Bajas Técnicas y Activos de Descarte")
    tab_b1, tab_b2 = st.tabs(["🚨 Registrar Baja Técnica", "📋 Historial y Auditoría de Descartes"])

    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_mantenimiento (
                id_registro INTEGER PRIMARY KEY AUTOINCREMENT, 
                id_equipo TEXT, fecha_ingreso TEXT, fecha_salida TEXT, 
                detalle_reparacion TEXT, costo_repuestos REAL
            )
        """)
        conn.commit()

    with obtener_conexion() as conn:
        df_equipos_all = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, estado FROM equipos", conn)
        df_tecnicos_disp = pd.read_sql_query("SELECT nombre FROM usuarios WHERE tipo_usuario IN ('Técnico', 'Administrador', 'Administrativo') ORDER BY nombre ASC", conn)

    if not df_equipos_all.empty:
        df_disponibles_baja = df_equipos_all[df_equipos_all["estado"] != "De Baja"]
    else:
        df_disponibles_baja = pd.DataFrame()

    lista_combobox_baja_eq = [f"{row['id_equipo']} - {row['tipo']} {row['marca']} {row['modelo']}" for _, row in df_disponibles_baja.iterrows()]
    lista_firmas_tecnicas = [row['nombre'] for _, row in df_tecnicos_disp.iterrows()] if not df_tecnicos_disp.empty else ["Encargado de Laboratorio TI"]
    with tab_b1:
        st.subheader("🚨 Registrar Baja Técnica de Hardware")
        inc_logo = True
        url_logo = "https://wikimedia.org"
        inc_fechas = True
        inc_obs = True
        inc_clausulas = True
        texto_condiciones_baja = (
            "1. El activo tecnológico descrito deja de formar parte de la contabilidad física y operativa del establecimiento.\n"
            "2. Se autoriza el desarme parcial para recuperación de piezas de repuesto o su traslado inmediato a la bodega de desecho RAEE."
        )
        texto_pie_baja = "Escuela Felipe Cubillos - Saneamiento de Inventario"

        if not df_equipos_all.empty and not df_disponibles_baja.empty:
            with st.expander("📄 Editar Logotipo y Cláusulas del Acta", expanded=False):
                col_cfg1, col_cfg2 = st.columns(2)
                inc_logo = col_cfg1.checkbox("Incluir membrete institucional", value=True, key="cfg_baja_logo")
                url_logo = col_cfg1.text_input("Enlace / URL del Logo (Opcional):", value="https://wikimedia.org", key="cfg_url_logo_baja")
                inc_fechas = col_cfg1.checkbox("Imprimir fecha de resolución técnica", value=True, key="cfg_baja_fechas")
                inc_obs = col_cfg1.checkbox("Incluir cuadro de diagnóstico técnico", value=True, key="cfg_baja_obs")
                inc_clausulas = col_cfg2.checkbox("Incorporar cláusulas de responsabilidad", value=True, key="cfg_baja_clausulas")
                texto_condiciones_baja = col_cfg2.text_area("Editar Términos:", value=texto_condiciones_baja, height=90, key="cfg_texto_clausulas_baja")
                texto_pie_baja = col_cfg2.text_input("Nota al pie:", value=texto_pie_baja, key="cfg_baja_pie")

            with st.form("form_baja_tecnica_comodato", clear_on_submit=False):
                equipo_seleccionado_box = st.selectbox("Equipo Operativo detectable:", lista_combobox_baja_eq)
                tecnico_autoriza = st.selectbox("Técnico que evalúa:", lista_firmas_tecnicas)
                motivo_baja = st.selectbox("Diagnóstico Causante:", ["Falla de Hardware Irreparable", "Obsolescencia Tecnológica", "Daño Estructural por Siniestro"])
                obs_baja = st.text_input("Observaciones / Repuestos salvados:", placeholder="ej: Placa quemada.")
                
                if st.form_submit_button("Confirmar Baja Técnica y Modificar Inventario"):
                    if obs_baja.strip() == "":
                        st.error("⛔ Debes añadir observaciones técnicas.")
                    else:
                        partes_seleccion = equipo_seleccionado_box.split(" - ")
                        id_eq_real = partes_seleccion[0].strip()
                        detalle_activo = partes_seleccion[1].strip() if len(partes_seleccion) > 1 else equipo_seleccionado_box
                        hoy_dt = date.today()
                        fecha_chile_baja = hoy_dt.strftime("%d/%m/%Y")
                        
                        with obtener_conexion() as conn:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE equipos SET estado = 'De Baja', ubicacion = 'Bodega de Desecho Tecnológico', fecha_cambio = ? WHERE id_equipo = ?", (hoy_dt.isoformat(), id_eq_real))
                            cursor.execute("INSERT INTO historial_mantenimiento (id_equipo, fecha_ingreso, fecha_salida, detalle_reparacion, costo_repuestos) VALUES (?, ?, ?, ?, 0.0)", 
                                           (id_eq_real, hoy_dt.isoformat(), hoy_dt.isoformat(), f"❌ [BAJA TÉCNICA DEFINITIVA] Evaluador: {tecnico_autoriza}. Motivo: {motivo_baja}. Obs: {obs_baja.strip()}"))
                            conn.commit()
                        
                        st.session_state["ultimo_comodato_baja"] = {
                            "id_equipo": id_eq_real, "detalle_equipo": detalle_activo, "fecha": fecha_chile_baja,
                            "autoriza": tecnico_autoriza, "motivo": motivo_baja, "observaciones": obs_baja.strip()
                        }
                        st.rerun()
        else:
            st.warning("⚠️ El inventario operativo está vacío o no tienes hardware disponible para descarte.")
        if "ultimo_comodato_baja" in st.session_state:
            datos_c_baja = st.session_state["ultimo_comodato_baja"]
            imagen_logo_html = ""
            if inc_logo and os.path.exists("logo_escuela.png"):
                try:
                    encoded_string = base64.b64encode(open("logo_escuela.png", "rb").read()).decode()
                    imagen_logo_html = f"<img src='data:image/png;base64,{encoded_string}' style='height: 70px; width: auto;'>"
                except:
                    pass

            html_comodato_baja = f"""
            <div style="padding: 20px; border: 2px solid #000; background-color: #ffffff; border-radius: 4px; color: #000; font-family: Arial, sans-serif;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px;">
                    {imagen_logo_html}
                    <div style="text-align: right;">
                        <h2 style="margin: 0; font-size: 18px; color: #000;">ACTA DE BAJA TÉCNICA TI</h2>
                        <p style="margin: 3px 0 0 0; font-size: 12px; font-weight: bold; color: #000;">{nombre_institucion}</p>
                    </div>
                </div>
                <hr style="border: 1px solid #000;">
                <p style="font-size: 14px; color: #000;">Se deja constancia del descarte definitivo del siguiente activo:</p>
                <table style="width:100%; border-collapse: collapse; margin: 15px 0; font-size:14px; color: #000;">
                    <tr><td style="border:1px solid #000; padding:8px;"><b>ID Equipo:</b></td><td style="border:1px solid #000; padding:8px; font-family:monospace;">{datos_c_baja['id_equipo']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:8px;"><b>Ficha Hardware:</b></td><td style="border:1px solid #000; padding:8px;">{datos_c_baja['detalle_equipo']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:8px;"><b>Causa Descarte:</b></td><td style="border:1px solid #000; padding:8px; font-weight:bold; color:#b00;">{datos_c_baja['motivo']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:8px;"><b>Evaluador:</b></td><td style="border:1px solid #000; padding:8px;">{datos_c_baja['autoriza']}</td></tr>
                    <tr><td style="border:1px solid #000; padding:8px;"><b>Fecha:</b></td><td style="border:1px solid #000; padding:8px;">{datos_c_baja['fecha']}</td></tr>
                </table>
                <div style="margin: 15px 0; padding: 10px; border: 1px solid #000; background:#fafafa; font-size:13px; color: #000;"><b>Informe Técnico:</b> {datos_c_baja['observaciones']}</div>
                <div style="margin-top: 50px; display:flex; justify-content:space-between; font-size:13px; color: #000;"><div style="text-align:center; width:45%; border-top:1px solid #000; padding-top:5px;">Firma Especialista TI</div><div style="text-align:center; width:45%; border-top:1px solid #000; padding-top:5px;">Firma Dirección</div></div>
            </div>
            """
 
            # === BOTÓN DE IMPRESIÓN DIRECTA INYECTADO ===
            st.markdown(html_comodato_baja, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            col_xp1, col_xp2, col_xp3 = st.columns(3)
            
            with col_xp1:
                st.markdown("""
                    <button onclick="window.print()" style="
                        width: 100%; background-color: #ef4444; color: white; border: none; 
                        padding: 0.5rem; text-align: center; font-weight: bold; border-radius: 0.375rem; cursor: pointer;
                    ">🖨️ Imprimir Acta de Baja</button>
                """, unsafe_allow_html=True)
                
            with col_xp2:
                st.download_button(label="📥 Descargar Acta (.html)", data=f"<!DOCTYPE html><html><body style='background:#fff; padding:20px;'>{html_comodato_baja}</body></html>", file_name=f"acta_baja_{datos_c_baja['id_equipo']}.html", mime="text/html", use_container_width=True)
            
            with col_xp3:
                if st.button("🔄 Siguiente Descarte / Limpiar", use_container_width=True):
                    if "ultimo_comodato_baja" in st.session_state: 
                        del st.session_state["ultimo_comodato_baja"]
                    st.rerun()


    with tab_b2:
        st.subheader("📋 Libro de Acta de Bajas Archivadas")
        with obtener_conexion() as conn:
            df_hist_bajas = pd.read_sql_query("SELECT h.id_registro AS 'Nro', h.fecha_salida AS 'Fecha', h.id_equipo AS 'Máquina', h.detalle_reparacion AS 'Informe' FROM historial_mantenimiento h WHERE h.detalle_reparacion LIKE '%[BAJA TÉCNICA DEFINITIVA]%' ORDER BY h.id_registro DESC", conn)
        if not df_hist_bajas.empty:
            st.dataframe(df_hist_bajas, use_container_width=True, hide_index=True)
        else:
            st.info("No se registran bajas procesadas de forma digital todavía.")
# =========================================================================
# 📱 MÓDULO NUEVO: GESTIÓN DE TABLETS INSTITUCIONALES
# =========================================================================
elif choice == "Gestión de Tablets":
        renderizar_modulo_tablets(nombre_institucion)

elif choice == "Ingreso por Código de Barra":
        renderizar_ingreso_codigo_barra_local(nombre_institucion)

elif choice == "Préstamos Rápidos por Barra":
        renderizar_prestamos_rapidos_barra_local(nombre_institucion)


# =========================================================================
# 🏢 MÓDULO: GESTIÓN DE SALAS (MANTENEDOR COMPLETO Y TRAZABILIDAD) - PARTE 1
# =========================================================================
elif choice == "Gestión de Salas":
    st.header("🏢 Administración de Espacios y Salas de Clases")
    st.caption("Panel corporativo para el control de aforos, asignación de responsables y auditoría física de hardware.")
    
    # Asegurar la existencia base de la tabla salas con tipos de datos correctos
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

    # Creación de 5 pestañas de trabajo ejecutivas con nombres estandarizados
    t_sala_crear, t_sala_mod, t_sala_del, t_sala_mover, t_sala_listado = st.tabs([
        "➕ Crear Sala", "🔄 Modificar Sala", "❌ Eliminar Sala", 
        "💻 Reubicar Equipos", "📋 Nómina e Inventario por Sector"
    ])

    # Consolidación de datos cruzados en una sola transacción limpia
    with obtener_conexion() as conn:
        df_funcionarios_disp = pd.read_sql_query("SELECT nombre, tipo_usuario FROM usuarios WHERE tipo_usuario IN ('Profesor', 'Técnico', 'Administrador') ORDER BY nombre ASC", conn)
        df_salas_disp = pd.read_sql_query("SELECT id_sala, nombre_sala, encargado, capacidad FROM salas ORDER BY nombre_sala ASC", conn)
        df_equipos_disp = pd.read_sql_query("SELECT id_equipo, tipo, marca, modelo, ubicacion FROM equipos WHERE estado != 'De Baja' ORDER BY id_equipo ASC", conn)
        
    lista_salas_combo = df_salas_disp["nombre_sala"].tolist() if not df_salas_disp.empty else []
    lista_salas_string = [f"ID:{row['id_sala']} | {row['nombre_sala']}" for _, row in df_salas_disp.iterrows()] if not df_salas_disp.empty else []
    lista_funcionarios = [f"{r['nombre']} ({r['tipo_usuario']})" for _, r in df_funcionarios_disp.iterrows()] if not df_funcionarios_disp.empty else ["Encargado General TI"]

    # --- PESTAÑA 1: CREAR NUEVA SALA ---
    with t_sala_crear:
        if st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro":
            with st.form("form_crear_sala_premium", clear_on_submit=True):
                st.markdown("##### 📝 Ficha de Apertura de Espacio")
                col_s1, col_s2, col_s3 = st.columns(3)
                n_sala = col_s1.text_input("Nombre / Identificador de la Sala:", placeholder="ej: Laboratorio 3 o Sala 4A")
                enc_sala = col_s2.selectbox("👤 Funcionario/Responsable:", lista_funcionarios)
                cap_sala = col_s3.number_input("Capacidad Máxima de Alumnos:", min_value=1, value=35, step=1)
                
                if st.form_submit_button("Guardar Espacio en Sistema", use_container_width=True):
                    if n_sala.strip():
                        encargado_limpio = enc_sala.split(" (")[0].strip() if " (" in enc_sala else enc_sala
                        try:
                            with obtener_conexion() as conn:
                                conn.cursor().execute("INSERT INTO salas (nombre_sala, encargado, capacidad) VALUES (?, ?, ?)", (n_sala.strip().upper(), encargado_limpio, cap_sala))
                                conn.commit()
                            st.success(f"✅ ¡La sala '{n_sala.strip().upper()}' ha sido habilitada exitosamente!")
                            ejecutar_respaldo_automatico_ti()
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⛔ Error: Ya existe un sector o sala registrado con ese mismo nombre exacto.")
                    else:
                        st.warning("⚠️ El nombre de la sala no puede quedar vacío.")
        else:
            st.warning("🔒 Permisos insuficientes: Requiere rango de Administrador para crear dependencias.")
    # --- PESTAÑA 2: MODIFICAR SALA ---
    with t_sala_mod:
        if (st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro") and lista_salas_string:
            sala_a_editar = st.selectbox("Selecciona la sala que deseas actualizar:", lista_salas_string, key="sb_sala_mod_main")
            id_sala_real = int(sala_a_editar.split(" | ")[0].split(":")[1])
            
            # Extraer la información actual de la fila seleccionada de forma segura
            datos_sala_act = df_salas_disp[df_salas_disp['id_sala'] == id_sala_real].iloc[0]
            
            with st.form("form_modificar_sala_real"):
                st.markdown(f"##### ✍️ Editando Ficha de la Sala ID: {id_sala_real}")
                col_m1, col_m2, col_m3 = st.columns(3)
                nuevo_nombre_sala = col_m1.text_input("Modificar Nombre:", value=str(datos_sala_act['nombre_sala']))
                
                encargado_actual = str(datos_sala_act['encargado'])
                idx_enc_def = 0
                for idx, func in enumerate(lista_funcionarios):
                    if encargado_actual in func:
                        idx_enc_def = idx
                        break
                        
                nuevo_enc_sala = col_m2.selectbox("Cambiar Responsable:", lista_funcionarios, index=idx_enc_def)
                nueva_cap_sala = col_m3.number_input("Modificar Capacidad:", min_value=1, value=int(datos_sala_act['capacidad']))
                
                if st.form_submit_button("Sincronizar Cambios de Infraestructura", use_container_width=True):
                    if nuevo_nombre_sala.strip():
                        encargado_nuevo_limpio = nuevo_enc_sala.split(" (")[0].strip() if " (" in nuevo_enc_sala else nuevo_enc_sala
                        try:
                            with obtener_conexion() as conn:
                                conn.cursor().execute("UPDATE salas SET nombre_sala=?, encargado=?, capacidad=? WHERE id_sala=?", 
                                                      (nuevo_nombre_sala.strip().upper(), encargado_nuevo_limpio, nueva_cap_sala, id_sala_real))
                                conn.commit()
                            st.success("✅ Datos de la sala actualizados correctamente.")
                            ejecutar_respaldo_automatico_ti()
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⛔ Error: Ese nombre de sala ya está asignado a otra dependencia.")
                    else:
                        st.error("El nombre de la sala es obligatorio.")
        elif not lista_salas_string:
            st.info("No hay dependencias registradas para modificar en el catálogo.")
        else:
            st.warning("🔒 Restringido: Requiere rol de Administrador.")

    # --- PESTAÑA 3: ELIMINAR SALA ---
    with t_sala_del:
        if (st.session_state.get("rol") == "Administrador" or st.session_state.get("usuario") == "Administrador Maestro") and lista_salas_string:
            sala_a_eliminar = st.selectbox("Selecciona el sector a clausurar permanentemente:", lista_salas_string, key="sb_sala_del_main")
            id_sala_del = int(sala_a_eliminar.split(" | ")[0].split(":")[1])
            nombre_sala_del = sala_a_eliminar.split(" | ")[1].strip()
            
            st.warning(f"⚠️ **Atención:** Eliminar la sala **{nombre_sala_del}** borrará de inmediato su registro maestro. Los equipos asociados a este espacio cambiarán automáticamente a 'Sin Ubicación Asignada'.")
            
            if st.button("🚨 Eliminar Sala de la Base de Datos", use_container_width=True, key="btn_ejecutar_baja_sala"):
                with obtener_conexion() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM salas WHERE id_sala = ?", (id_sala_del,))
                    cursor.execute("UPDATE equipos SET ubicacion = 'Sin Ubicación Asignada' WHERE ubicacion LIKE ?", (f"{nombre_sala_del}%",))
                    conn.commit()
                st.success(f"🔥 El espacio '{nombre_sala_del}' ha sido eliminado del mapa escolar.")
                ejecutar_respaldo_automatico_ti()
                st.rerun()

        elif not lista_salas_string:
            st.info("No hay salas implementadas en la grilla para eliminación.")
        else:
            st.warning("🔒 Acción denegada por políticas de seguridad.")

    # --- PESTAÑA 4: ASIGNAR Y TRASLADAR EQUIPOS ---
    with t_sala_mover:
        if not lista_salas_combo:
            st.warning("⚠️ Primero debes registrar una sala de clases para habilitar los movimientos.")
        elif df_equipos_disp.empty:
            st.info("No hay dispositivos operativos libres en el inventario activo de la escuela.")
        else:
            st.subheader("💻 Asignar Ubicación Física de un Equipo a una Sala")
            with st.form("form_mover_sala_cache_break_2026"):
                sala_seleccionada = st.selectbox("1. Selecciona la Sala de Destino:", lista_salas_combo, key="sb_sala_dest_cb_2026")
                lista_equipos_strings = [f"{row['id_equipo']} - {row['tipo']} {row['marca']} (Ubicación actual: {row['ubicacion']})" for _, row in df_equipos_disp.iterrows()]
                equipo_seleccionado = st.selectbox("2. Selecciona el Equipo a Trasladar:", lista_equipos_strings, key="sb_eq_tras_cb_2026")
                detalle_ubicacion_especifica = st.text_input("3. Detalle específico de ubicación interna (Opcional):", placeholder="ej: Mueble azul, Rack central, Estante posterior...")

                if st.form_submit_button("Confirmar Traslado de Espacio", use_container_width=True):
                    id_equipo_real = equipo_seleccionado.split(" - ")[0].strip()
                    ubicacion_final = f"{sala_seleccionada} - {detalle_ubicacion_especifica.strip()}" if detalle_ubicacion_especifica.strip() else sala_seleccionada
                    
                    with obtener_conexion() as conn:
                        conn.cursor().execute("UPDATE equipos SET ubicacion = ? WHERE id_equipo = ?", (ubicacion_final, id_equipo_real))
                        conn.commit()
                    st.success(f"🚀 ¡El equipo {id_equipo_real} fue reasignado con éxito a '{ubicacion_final}'!")
                    ejecutar_respaldo_automatico_ti()
                    st.rerun()
    # --- PESTAÑA 5: LISTADO GENERAL COMPLETO Y TRAZABILIDAD EXPRESS ---
    with t_sala_listado:
        st.subheader("📋 Nómina General de Infraestructura por Sector")
        
        if df_salas_disp.empty:
            st.info("No hay salas implementadas en la base de datos todavía para auditar.")
        else:
            col_list1, col_list2 = st.columns([0.4, 0.6])
            
            with col_list1:
                st.markdown("##### 🏢 Capacidad y Aforo de Salas")
                st.dataframe(
                    df_salas_disp.rename(columns={
                        'nombre_sala': 'Sala / Dependencia',
                        'encargado': 'Docente Encargado',
                        'capacidad': 'Capacidad Aforo'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                
            with col_list2:
                sala_a_auditar = st.selectbox("🔎 Selecciona una Sala para auditar su inventario operativo:", lista_salas_combo, key="sb_auditoria_salas_cache_break_2026")
                
                with obtener_conexion() as conn:
                    df_resultado_sala = pd.read_sql_query("""
                        SELECT id_equipo as 'ID Equipo', 
                               tipo as 'Tipo Hardware', 
                               marca as 'Marca', 
                               estado as 'Estado Técnico', 
                               ubicacion as 'Ubicación Detallada' 
                        FROM equipos 
                        WHERE ubicacion LIKE ? AND estado != 'De Baja'
                    """, conn, params=(f"{sala_a_auditar}%",))
                    
                st.metric(f"Dispositivos Activos en {sala_a_auditar}", f"{len(df_resultado_sala)} unidades")
                
                if not df_resultado_sala.empty:
                    st.dataframe(df_resultado_sala, use_container_width=True, hide_index=True)
                    st.download_button(
                        label=f"📥 Descargar Reporte de {sala_a_auditar} (Excel)",
                        data=to_excel(df_resultado_sala),
                        file_name=f"reporte_trazabilidad_{sala_a_auditar.lower().replace(' ', '_')}.xlsx",
                        use_container_width=True,
                        key="btn_dl_excel_salas_cache_break_2026"
                    )
                else:
                    st.info("👍 Este sector se encuentra despejado y no registra asignaciones de hardware vigentes.")

#elif choice == "Generador de Etiquetas":
#    from mod_etiquetas import renderizar_modulo_etiquetas
#    renderizar_modulo_etiquetas()

elif choice == "Generador de Etiquetas":
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
    else:
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

                # 🛠️ GENERACIÓN DEL CÓDIGO DE BARRAS (CODE128) EN MEMORIA RAM (SOLUCIÓN STREAMLIT CLOUD)
                try:
                    code128_class = barcode.get_barcode_class('code128')
                    writer_instancia = ImageWriter()
                    encoder_barra = code128_class(id_act, writer=writer_instancia)
                    
                    buf_bar = io.BytesIO()
                    encoder_barra.write(buf_bar, options={"write_text": False, "background": "white", "foreground": "black"})
                    bar_b64 = base64.b64encode(buf_bar.getvalue()).decode()
                except Exception:
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

