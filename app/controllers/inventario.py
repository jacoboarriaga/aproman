from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.decorators import requiere_rol
from app.utils import get_db_connection


inventario_bp = Blueprint('inventario', __name__, url_prefix='/inventario')

CATEGORIAS_INVENTARIO = [
    'Producto',
    'Material',
    'Equipo',
    'Herramienta',
    'Consumible',
]

CATEGORIAS_TITULOS = [
    ('Producto', 'Productos'),
    ('Material', 'Materiales'),
    ('Equipo', 'Equipos'),
    ('Herramienta', 'Herramientas'),
    ('Consumible', 'Consumibles'),
]


def normalizar_categoria(categoria):
    if categoria in ['ERP', 'Bodega', 'Pintura'] or not categoria:
        return 'Producto'
    return categoria


def agrupar_por_categoria(items):
    grupos = []
    for categoria, titulo in CATEGORIAS_TITULOS:
        registros = [item for item in items if normalizar_categoria(item.get('categoria')) == categoria]
        if registros:
            grupos.append({'categoria': categoria, 'titulo': titulo, 'items': registros})
    return grupos


def obtener_siguiente_codigo(cursor, prefijo):
    """Sugiere el siguiente codigo interno, por ejemplo M-001 o E-001."""
    cursor.execute("""
        SELECT codigo
        FROM productos
        WHERE UPPER(LTRIM(RTRIM(codigo))) LIKE ?
    """, (prefijo + '-%',))
    mayor = 0
    for row in cursor.fetchall():
        codigo = (row.codigo or '').strip().upper()
        partes = codigo.split('-', 1)
        if len(partes) == 2 and partes[0] == prefijo and partes[1].isdigit():
            mayor = max(mayor, int(partes[1]))
    return "{}-{:03d}".format(prefijo, mayor + 1)


def obtener_bodega_interna(cursor):
    cursor.execute("""
        SELECT TOP 1 id, nombre
        FROM bodegas
        WHERE activa = 1 AND tipo = 'interna'
        ORDER BY id ASC
    """)
    row = cursor.fetchone()
    if not row:
        return None
    return {'id': row.id, 'nombre': row.nombre}


def registrar_entrada_inicial(cursor, producto_id, cantidad, usuario_id, observacion):
    if cantidad <= 0:
        return

    bodega = obtener_bodega_interna(cursor)
    if not bodega:
        raise ValueError("No hay una bodega interna activa para registrar la cantidad inicial.")

    cursor.execute("""
        INSERT INTO movimientos
        (producto_id, bodega_id, tipo, cantidad, observacion, usuario_id, fecha_movimiento)
        VALUES (?, ?, 'ajuste_entrada', ?, ?, ?, GETDATE())
    """, (producto_id, bodega['id'], cantidad, observacion, usuario_id))


@inventario_bp.route('/')
@login_required
@requiere_rol('administrador')
def listado_inventario():
    """Vista principal de existencias disponibles por articulo y bodega."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT producto_id, codigo, cod_producto_erp, codigo_interno, nombre, categoria,
                   unidad_medida, bodega_id, bodega_nombre, stock_disponible
            FROM v_stock_productos
            ORDER BY nombre ASC, bodega_nombre ASC
        """)
        cols = [c[0] for c in cursor.description]
        existencias = [dict(zip(cols, row)) for row in cursor.fetchall()]
        grupos_inventario = agrupar_por_categoria(existencias)
    except Exception as e:
        print(f"Error al cargar inventario: {e}")
        existencias = []
        grupos_inventario = []
        flash("Error al cargar inventario.", "error")
    finally:
        conn.close()

    return render_template(
        'inventario/listado_inventario.html',
        existencias=existencias,
        grupos_inventario=grupos_inventario
    )


@inventario_bp.route('/productos')
@login_required
@requiere_rol('administrador')
def productos_inventario():
    """Compatibilidad: el catalogo queda integrado en Inventario."""
    return redirect(url_for('inventario.listado_inventario'))


@inventario_bp.route('/nuevo-producto', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def nuevo_producto():
    """Registro de nuevo producto."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().upper()
        nombre = request.form.get('nombre', '').strip()
        unidad_medida = 'UND'
        try:
            cantidad_inicial = float(request.form.get('cantidad_inicial') or 0)
        except ValueError:
            conn.close()
            flash("La cantidad inicial debe ser un numero valido.", "warning")
            return redirect(url_for('inventario.nuevo_producto'))

        if cantidad_inicial < 0:
            conn.close()
            flash("La cantidad inicial no puede ser negativa.", "warning")
            return redirect(url_for('inventario.nuevo_producto'))

        if not codigo or not nombre:
            conn.close()
            flash("Codigo y nombre son obligatorios.", "warning")
            return redirect(url_for('inventario.nuevo_producto'))

        try:
            cursor.execute("""
                SELECT TOP 1 id, nombre FROM productos
                WHERE UPPER(LTRIM(RTRIM(codigo))) = ?
            """, (codigo,))
            existente = cursor.fetchone()
            if existente:
                conn.close()
                flash(f"El codigo ya existe: {existente.nombre}. Si necesitas cambiar existencias, realiza un ajuste de existencias.", "warning")
                return redirect(url_for('inventario.nuevo_producto'))

            cursor.execute("""
                INSERT INTO productos
                (codigo, cod_producto_erp, codigo_interno, nombre, categoria, unidad_medida, stock_minimo, activo, fecha_creacion)
                OUTPUT INSERTED.id
                VALUES (?, NULL, NULL, ?, 'Producto', ?, ?, 1, GETDATE())
            """, (codigo, nombre, unidad_medida, 0))
            producto_id = cursor.fetchone()[0]
            registrar_entrada_inicial(
                cursor,
                producto_id,
                cantidad_inicial,
                current_user.id,
                "Ingreso inicial al registrar producto"
            )
            conn.commit()
            conn.close()
            flash("Producto guardado correctamente.", "success")
            return redirect(url_for('inventario.listado_inventario'))
        except Exception as e:
            conn.rollback()
            print(f"Error al crear producto: {e}")
            flash("Error al crear el registro. Revisa si el codigo ya existe.", "error")
            conn.close()

    conn.close()
    return render_template('inventario/nuevo_producto.html')


@inventario_bp.route('/nuevo-material', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def nuevo_material():
    """Registro de nuevo material o consumible."""
    conn = get_db_connection()
    cursor = conn.cursor()
    codigo_sugerido = 'M-001'

    try:
        codigo_sugerido = obtener_siguiente_codigo(cursor, 'M')
    except Exception as e:
        print(f"Error al sugerir codigo de material: {e}")

    if request.method == 'POST':
        codigo = obtener_siguiente_codigo(cursor, 'M')
        nombre = request.form.get('nombre', '').strip()
        unidad_medida = 'UND'
        categoria = request.form.get('categoria', 'Material').strip()
        if categoria not in ['Material', 'Consumible']:
            categoria = 'Material'
        try:
            cantidad_inicial = float(request.form.get('cantidad_inicial') or 0)
        except ValueError:
            conn.close()
            flash("La cantidad inicial debe ser un numero valido.", "warning")
            return redirect(url_for('inventario.nuevo_material'))

        if cantidad_inicial < 0:
            conn.close()
            flash("La cantidad inicial no puede ser negativa.", "warning")
            return redirect(url_for('inventario.nuevo_material'))

        if not nombre:
            conn.close()
            flash("Nombre es obligatorio.", "warning")
            return redirect(url_for('inventario.nuevo_material'))

        try:
            cursor.execute("""
                SELECT TOP 1 id, nombre FROM productos
                WHERE UPPER(LTRIM(RTRIM(codigo))) = ?
            """, (codigo,))
            existente = cursor.fetchone()
            if existente:
                conn.close()
                flash(f"El codigo ya existe: {existente.nombre}. Si necesitas cambiar existencias, realiza un ajuste de existencias.", "warning")
                return redirect(url_for('inventario.nuevo_material'))

            cursor.execute("""
                INSERT INTO productos
                (codigo, cod_producto_erp, codigo_interno, nombre, categoria, unidad_medida, stock_minimo, activo, fecha_creacion)
                OUTPUT INSERTED.id
                VALUES (?, NULL, NULL, ?, ?, ?, ?, 1, GETDATE())
            """, (codigo, nombre, categoria, unidad_medida, 0))
            producto_id = cursor.fetchone()[0]
            registrar_entrada_inicial(
                cursor,
                producto_id,
                cantidad_inicial,
                current_user.id,
                "Ingreso inicial al registrar {}".format(categoria.lower())
            )
            conn.commit()
            conn.close()
            flash("{} guardado correctamente con codigo {}.".format(categoria, codigo), "success")
            return redirect(url_for('inventario.listado_inventario'))
        except Exception as e:
            conn.rollback()
            print(f"Error al crear material: {e}")
            flash("Error al crear el registro.", "error")
            conn.close()

    conn.close()
    return render_template('inventario/nuevo_material.html', codigo_sugerido=codigo_sugerido)


@inventario_bp.route('/nuevo-equipo', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def nuevo_equipo():
    """Registro de nuevo equipo o herramienta."""
    conn = get_db_connection()
    cursor = conn.cursor()
    codigo_sugerido = 'E-001'

    try:
        codigo_sugerido = obtener_siguiente_codigo(cursor, 'E')
    except Exception as e:
        print(f"Error al sugerir codigo de equipo: {e}")

    if request.method == 'POST':
        codigo = obtener_siguiente_codigo(cursor, 'E')
        nombre = request.form.get('nombre', '').strip()
        categoria = request.form.get('categoria', 'Equipo').strip()
        if categoria not in ['Equipo', 'Herramienta']:
            categoria = 'Equipo'
        try:
            cantidad_inicial = float(request.form.get('cantidad_inicial') or 0)
        except ValueError:
            conn.close()
            flash("La cantidad inicial debe ser un numero valido.", "warning")
            return redirect(url_for('inventario.nuevo_equipo'))

        if cantidad_inicial < 0:
            conn.close()
            flash("La cantidad inicial no puede ser negativa.", "warning")
            return redirect(url_for('inventario.nuevo_equipo'))
        
        if not nombre:
            conn.close()
            flash("Nombre es obligatorio.", "warning")
            return redirect(url_for('inventario.nuevo_equipo'))

        try:
            cursor.execute("""
                SELECT TOP 1 id, nombre FROM productos
                WHERE UPPER(LTRIM(RTRIM(codigo))) = ?
            """, (codigo,))
            existente = cursor.fetchone()
            if existente:
                conn.close()
                flash(f"El codigo ya existe: {existente.nombre}. Si necesitas cambiar existencias, realiza un ajuste de existencias.", "warning")
                return redirect(url_for('inventario.nuevo_equipo'))

            cursor.execute("""
                INSERT INTO productos
                (codigo, cod_producto_erp, codigo_interno, nombre, categoria, unidad_medida, stock_minimo, activo, fecha_creacion)
                OUTPUT INSERTED.id
                VALUES (?, NULL, NULL, ?, ?, 'UND', 0, 1, GETDATE())
            """, (codigo, nombre, categoria))
            producto_id = cursor.fetchone()[0]
            registrar_entrada_inicial(
                cursor,
                producto_id,
                cantidad_inicial,
                current_user.id,
                "Ingreso inicial al registrar {}".format(categoria.lower())
            )
            conn.commit()
            conn.close()
            flash("{} guardado correctamente con codigo {}.".format(categoria, codigo), "success")
            return redirect(url_for('inventario.listado_inventario'))
        except Exception as e:
            conn.rollback()
            print(f"Error al crear equipo: {e}")
            flash("Error al crear el registro.", "error")
            conn.close()

    conn.close()
    return render_template('inventario/nuevo_equipo.html', codigo_sugerido=codigo_sugerido)


@inventario_bp.route('/ajuste', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def ajuste_stock():
    """Registra ajustes manuales de entrada o salida en la bodega interna."""
    conn = get_db_connection()
    cursor = conn.cursor()
    bodega = None
    productos = []

    try:
        cursor.execute("""
            SELECT TOP 1 id, nombre
            FROM bodegas
            WHERE activa = 1 AND tipo = 'interna'
            ORDER BY id ASC
        """)
        bodega_row = cursor.fetchone()
        if not bodega_row:
            flash("Debes tener una bodega interna activa para registrar ajustes.", "error")
            return redirect(url_for('inventario.listado_inventario'))

        bodega = {'id': bodega_row.id, 'nombre': bodega_row.nombre}

        cursor.execute("""
            SELECT producto_id, codigo, cod_producto_erp, codigo_interno, nombre, categoria,
                   unidad_medida, stock_disponible
            FROM v_stock_productos
            WHERE bodega_id = ?
            ORDER BY nombre ASC
        """, (bodega['id'],))
        productos = [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]

        if request.method == 'POST':
            producto_id = request.form.get('producto_id', type=int)
            tipo_ajuste = request.form.get('tipo_ajuste', '').strip()
            observacion = request.form.get('observacion', '').strip()[:500] or None
            try:
                cantidad = float(request.form.get('cantidad') or 0)
            except ValueError:
                flash("La cantidad debe ser un numero valido.", "warning")
                return render_template('inventario/ajuste_stock.html', bodega=bodega, productos=productos)

            if not producto_id or tipo_ajuste not in ['entrada', 'salida'] or cantidad <= 0:
                flash("Selecciona registro, tipo de movimiento y una cantidad valida.", "warning")
                return render_template('inventario/ajuste_stock.html', bodega=bodega, productos=productos)

            if not observacion:
                flash("Debes indicar el motivo del ajuste.", "warning")
                return render_template('inventario/ajuste_stock.html', bodega=bodega, productos=productos)

            cursor.execute("""
                SELECT producto_id, nombre, stock_disponible
                FROM v_stock_productos
                WHERE producto_id = ? AND bodega_id = ?
            """, (producto_id, bodega['id']))
            stock_row = cursor.fetchone()
            if not stock_row:
                flash("Registro no encontrado en inventario.", "error")
                return render_template('inventario/ajuste_stock.html', bodega=bodega, productos=productos)

            stock_actual = float(stock_row.stock_disponible or 0)
            if tipo_ajuste == 'salida' and cantidad > stock_actual:
                flash(f"No puedes sacar {cantidad:,.2f}; la existencia disponible de {stock_row.nombre} es {stock_actual:,.2f}.", "warning")
                return render_template('inventario/ajuste_stock.html', bodega=bodega, productos=productos)

            tipo_movimiento = 'ajuste_entrada' if tipo_ajuste == 'entrada' else 'ajuste_salida'
            cursor.execute("""
                INSERT INTO movimientos
                (producto_id, bodega_id, tipo, cantidad, observacion, usuario_id, fecha_movimiento)
                VALUES (?, ?, ?, ?, ?, ?, GETDATE())
            """, (
                producto_id,
                bodega['id'],
                tipo_movimiento,
                cantidad,
                observacion,
                current_user.id
            ))
            conn.commit()
            flash("Ajuste de existencias registrado correctamente.", "success")
            return redirect(url_for('inventario.movimientos_inventario', producto_id=producto_id))

    except Exception as e:
        conn.rollback()
        print(f"Error al registrar ajuste de stock: {e}")
        flash("Error al registrar ajuste de existencias.", "error")
    finally:
        conn.close()

    return render_template('inventario/ajuste_stock.html', bodega=bodega, productos=productos)


@inventario_bp.route('/movimientos')
@login_required
@requiere_rol('administrador')
def movimientos_inventario():
    """Bitacora de entradas, asignaciones, consumos, devoluciones y ajustes."""
    producto_id = request.args.get('producto_id', type=int)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT m.*, p.nombre as producto_nombre, p.unidad_medida, b.nombre as bodega_nombre,
                   s.sistema_nombre, pr.codigo as proyecto_codigo,
                   CONVERT(VARCHAR, m.fecha_movimiento, 103) as fecha_formateada
            FROM movimientos m
            INNER JOIN productos p ON m.producto_id = p.id
            LEFT JOIN bodegas b ON m.bodega_id = b.id
            LEFT JOIN sistemas s ON m.sistema_id = s.id
            LEFT JOIN proyectos pr ON m.proyecto_id = pr.id
            WHERE 1 = 1
        """
        params = []
        if producto_id:
            query += " AND m.producto_id = ?"
            params.append(producto_id)
        query += " ORDER BY m.fecha_movimiento DESC, m.id DESC"

        cursor.execute(query, params)
        cols = [c[0] for c in cursor.description]
        movimientos = [dict(zip(cols, row)) for row in cursor.fetchall()]

        cursor.execute("SELECT id, nombre FROM productos WHERE activo = 1 ORDER BY nombre ASC")
        productos = [{'id': row.id, 'nombre': row.nombre} for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error al cargar movimientos: {e}")
        movimientos = []
        productos = []
        flash("Error al cargar movimientos.", "error")
    finally:
        conn.close()

    return render_template(
        'inventario/movimientos_inventario.html',
        movimientos=movimientos,
        productos=productos,
        producto_id=producto_id
    )
