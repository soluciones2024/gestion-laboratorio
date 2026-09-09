def inicializar_db():
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS equipos (id_equipo TEXT PRIMARY KEY, tipo TEXT, marca TEXT, modelo TEXT, estado TEXT, ubicacion TEXT, fecha_cambio TEXT, num_documento TEXT, proveedor_origen TEXT, costo_compra REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id_compra INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT, cantidad INTEGER, costo_unitario REAL, proveedor TEXT, fecha TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS prestamos (id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT, id_equipo TEXT, usuario TEXT, rut TEXT, fecha_prestamo TEXT, fecha_limite TEXT, fecha_devolucion TEXT, estado_prestamo TEXT, observaciones TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS infraestructura (id_item INTEGER PRIMARY KEY AUTOINCREMENT, elemento TEXT, ubicacion TEXT, estado TEXT, observaciones TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (rut TEXT PRIMARY KEY, nombre TEXT, correo TEXT, tipo_usuario TEXT)")
        
        # 1. CORREGIDO: Se añade 'estado_nota TEXT' para la base de datos de Streamlit Cloud
        cursor.execute("CREATE TABLE IF NOT EXISTS bitacora (id_nota INTEGER PRIMARY KEY AUTOINCREMENT, nota TEXT, fecha TEXT, hora TEXT, estado_nota TEXT)")
        
        cursor.execute("CREATE TABLE IF NOT EXISTS salas (id_sala INTEGER PRIMARY KEY AUTOINCREMENT, nombre_sala TEXT UNIQUE, encargado TEXT, capacidad INTEGER)")
        
        columnas_nuevas = [("num_documento", "TEXT"), ("proveedor_origen", "TEXT"), ("costo_compra", "REAL")]
        for col, tipo in columnas_nuevas:
            try:
                cursor.execute(f"ALTER TABLE equipos ADD COLUMN {col} {tipo}")
            except sqlite3.OperationalError:
                pass
        
        # 2. CORREGIDO: Fuerza la actualización en tu entorno local por si ya tenías el archivo .db creado
        try:
            cursor.execute("ALTER TABLE bitacora ADD COLUMN estado_nota TEXT")
        except sqlite3.OperationalError:
            pass
            
        conn.commit()
