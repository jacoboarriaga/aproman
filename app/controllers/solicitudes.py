from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.decorators import requiere_rol
from app.utils import get_db_connection, get_erp_connection


solicitudes_bp = Blueprint('solicitudes', __name__, url_prefix='/solicitudes')


@solicitudes_bp.route('/')
@login_required
@requiere_rol('administrador')
def listado_solicitudes():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.*, b.nombre as bodega_destino,
                   u.nombre as solicitado_por_nombre,
                   CONVERT(VARCHAR, s.fecha_solicitud, 103) as fecha_solicitud_fmt,
                   CONVERT(VARCHAR, s.fecha_recibido, 103) as fecha_recibido_fmt,
                   ISNULL(SUM(ds.cantidad_solicitada), 0) as total_solicitado,
                   ISNULL(SUM(ds.cantidad_recibida), 0) as total_recibido
            FROM solicitudes s
            INNER JOIN bodegas b ON s.bodega_destino_id = b.id
            INNER JOIN usuarios u ON s.solicitado_por = u.id
            LEFT JOIN detalle_solicitud ds ON s.id = ds.solicitud_id
            GROUP BY s.id, s.num_documento_erp, s.correlativo_erp, s.cod_bodega_erp,
                     s.bodega_destino_id, s.estado, s.observaciones, s.solicitado_por,
                     s.recibido_por, s.fecha_solicitud, s.fecha_recibido, b.nombre, u.nombre
            ORDER BY s.fecha_solicitud DESC, s.id DESC
        """)
        cols = [c[0] for c in cursor.description]
        solicitudes = [dict(zip(cols, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error al listar solicitudes: {e}")
        solicitudes = []
        flash("Error al cargar solicitudes.", "error")
    finally:
        conn.close()

    return render_template('solicitudes/listado_solicitudes.html', solicitudes=solicitudes)


@solicitudes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def crear_solicitud():
    bodegas_erp = []
    empleados = []
    bodega_interna = None
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT TOP 1 id, nombre FROM bodegas WHERE activa = 1 AND tipo = 'interna' ORDER BY id ASC")
        bodega_row = cursor.fetchone()
        if bodega_row:
            bodega_interna = {'id': bodega_row.id, 'nombre': bodega_row.nombre}
        else:
            flash("Debes tener una bodega interna activa para recibir productos despues de solicitarlos.", "error")

        try:
            conn_erp = get_erp_connection()
            cursor_erp = conn_erp.cursor()
            cursor_erp.execute("""
                SELECT COD_BODEGA, NOMBRE_BODEGA, Correlativo_Doc
                FROM sysadm.IN_BODEGAS
                WHERE BODEGA_INACTIVA = 'N'
                    AND COD_BODEGA = 1
                ORDER BY COD_BODEGA
            """)
            bodegas_erp = [
                {'cod': row[0], 'nombre': row[1], 'correlativo_doc': row[2]}
                for row in cursor_erp.fetchall()
            ]

            cursor_erp.execute("""
                SELECT COD_EMPLEADO,
                       RTRIM(NOMBRES_EMPLEADO) + ' ' + RTRIM(APELLIDOS_EMPLEADO) AS nombre_completo
                FROM sysadm.EMPLEADO
                WHERE COD_EMPLEADO = 2
                ORDER BY NOMBRES_EMPLEADO
            """)
            empleados = [{'cod': row[0], 'nombre': row[1]} for row in cursor_erp.fetchall()]
        except Exception as e:
            print(f"Error al cargar datos ERP para solicitud: {e}")
            flash("Error al cargar datos de bodega.", "error")
        finally:
            if 'conn_erp' in locals():
                conn_erp.close()

        if request.method == 'POST':
            if not bodega_interna:
                flash("No hay bodega interna activa para recibir esta solicitud.", "error")
                return redirect(url_for('solicitudes.listado_solicitudes'))

            cod_bodega = request.form.get('cod_bodega', '').strip()
            empleado_recibe = request.form.get('empleado_recibe', '').strip()
            observaciones = request.form.get('observaciones', '').strip()[:500] or None
            codigos = request.form.getlist('codigo[]')
            cantidades = request.form.getlist('cantidad[]')
            unidades = request.form.getlist('unidad_medida[]')

            lineas = []
            for cod, cantidad, unidad in zip(codigos, cantidades, unidades):
                if cod and cantidad and float(cantidad) > 0:
                    lineas.append((cod.strip().upper(), float(cantidad), (unidad or '').strip()))

            if not cod_bodega or not empleado_recibe or not lineas:
                flash("Debes seleccionar bodega, empleado y agregar al menos un producto.", "warning")
                return render_template('solicitudes/crear_solicitud.html',
                                       bodegas_erp=bodegas_erp,
                                       empleados=empleados,
                                       bodega_interna=bodega_interna)

            conn_erp2 = get_erp_connection()
            cursor_erp2 = conn_erp2.cursor()
            detalle_local = []

            try:
                cursor_erp2.execute("""
                    SELECT status_inv
                    FROM PERIODOS_CIERRE
                    WHERE anio = YEAR(GETDATE())
                      AND periodo = MONTH(GETDATE())
                """)
                periodo_row = cursor_erp2.fetchone()
                if not periodo_row or periodo_row[0] == 'C':
                    raise ValueError("El periodo contable actual de inventario se encuentra cerrado o no existe.")

                cursor_erp2.execute("""
                    SELECT RTRIM(NOMBRES_EMPLEADO) + ' ' + RTRIM(APELLIDOS_EMPLEADO)
                    FROM sysadm.EMPLEADO WHERE COD_EMPLEADO = ?
                """, (empleado_recibe,))
                emp_row = cursor_erp2.fetchone()
                nombre_emp_recibe = emp_row[0][:50] if emp_row else 'EMPLEADO'

                usuario_ingreso = (current_user.username or 'sysadm')[:10]
                descripcion = "APROMAN INVENTARIO | BODEGA INTERNA"[:150]

                cursor_erp2.execute("""
                    UPDATE sysadm.in_parametros
                    SET correlativo = ISNULL(correlativo, 0) + 1
                    OUTPUT inserted.correlativo
                """)
                correlativo = cursor_erp2.fetchone()[0]

                cursor_erp2.execute("""
                    UPDATE sysadm.in_numeracion_emp
                    SET num_actual = ISNULL(num_actual, 0) + 1
                    OUTPUT inserted.num_actual
                    WHERE num_empresa = 1 AND tipo_documento = 150
                """)
                num_documento = cursor_erp2.fetchone()[0]

                cursor_erp2.execute("""
                    UPDATE sysadm.IN_BODEGAS
                    SET Correlativo_Doc = ISNULL(Correlativo_Doc, 0) + 1
                    OUTPUT inserted.Correlativo_Doc
                    WHERE COD_BODEGA = ?
                """, (cod_bodega,))
                bod_row = cursor_erp2.fetchone()
                bodega_corr = bod_row[0] if bod_row else 1

                cursor_erp2.execute("""
                    INSERT INTO sysadm.IN_DOCUMENTO (
                        NUM_EMPRESA, TIPO_DOCUMENTO, COD_BODEGA, NUM_CUENTA, CORRELATIVO,
                        DESCRIPCION, NUM_DOCUMENTO, FECHA_DOCUMENTO, STATUS_DOCUMENTO,
                        USUARIO_INGRESO, FECHA_INGRESO,
                        EMPLEADO_ENTREGA, NOMBRE_EMP_ENTREGA,
                        EMPLEADO_RECIBE, NOMBRE_EMP_RECIBE,
                        IMPRESO, ANULADO, Bodega_Corr
                    ) VALUES (
                        1, 150, ?, '11060407', ?,
                        ?, ?, GETDATE(), 'R',
                        ?, GETDATE(),
                        1, 'ADMINISTRADOR SYSTEM',
                        ?, ?,
                        'N', 'N', ?
                    )
                """, (
                    cod_bodega, correlativo,
                    descripcion, num_documento,
                    usuario_ingreso,
                    empleado_recibe, nombre_emp_recibe,
                    bodega_corr
                ))

                for num_linea, (cod, cantidad, unidad) in enumerate(lineas):
                    cursor_erp2.execute("""
                        SELECT RTRIM(NOMBRE_PRODUCTO) as nombre,
                               RTRIM(UNIDAD_MEDIDA) as unidad_medida,
                               ISNULL(costo_promedio, 0) as costo_promedio
                        FROM sysadm.IN_PRODUCTOS
                        WHERE COD_PRODUCTO = ?
                    """, (cod,))
                    prod_row = cursor_erp2.fetchone()
                    if not prod_row:
                        raise ValueError(f"Producto {cod} no encontrado en bodega.")

                    unidad_mov = unidad or (prod_row[1].strip() if prod_row[1] else '')
                    costo_promedio = float(prod_row[2] or 0)
                    costo_movimiento = cantidad * costo_promedio

                    cursor_erp2.execute("""
                        SELECT PRECIO_UNITARIO
                        FROM sysadm.IN_PRECIOS_TIPOCLT
                        WHERE COD_PRODUCTO = ? AND TIPO_CLIENTE = 10
                    """, (cod,))
                    precio_row = cursor_erp2.fetchone()
                    precio_unitario = float(precio_row[0]) if precio_row else 0.0

                    cursor_erp2.execute("""
                        INSERT INTO sysadm.IN_DET_DOCUMENTO (
                            NUM_EMPRESA, TIPO_DOCUMENTO, CORRELATIVO, NUM_LINEA,
                            UNIDAD_MEDIDA, COD_PRODUCTO, CANTIDAD, PRECIO_UNITARIO,
                            NUM_CUENTA, unidad_medida_tran, cantidad_tran, Peso
                        ) VALUES (
                            1, 150, ?, ?,
                            ?, ?, ?, ?,
                            '11060407', ?, ?, 0.000000
                        )
                    """, (
                        correlativo, num_linea,
                        unidad_mov, cod, cantidad, costo_promedio,
                        unidad_mov, cantidad
                    ))

                    cursor_erp2.execute("""
                        UPDATE sysadm.IN_PRODUCTOS_X_BOD
                        SET UNIDADES_DISPONIBL = UNIDADES_DISPONIBL - ?,
                            MONTO_TOTAL = MONTO_TOTAL - ?
                        WHERE COD_PRODUCTO = ? AND COD_BODEGA = ?
                    """, (cantidad, costo_movimiento, cod, cod_bodega))

                    cursor_erp2.execute("""
                        UPDATE sysadm.IN_PRODUCTOS
                        SET UNIDADES_DISPONIBL = UNIDADES_DISPONIBL - ?
                        WHERE COD_PRODUCTO = ?
                    """, (cantidad, cod))

                    cursor_erp2.execute("""
                        UPDATE sysadm.in_productos_x_mes
                        SET movimiento_salida = movimiento_salida + ?,
                            monto_salida = monto_salida + ?
                        WHERE NUM_EMPRESA = 1
                          AND COD_BODEGA = ?
                          AND COD_PRODUCTO = ?
                          AND fecha_referencia = DATEADD(d, -1, DATEADD(m, DATEDIFF(m, 0, GETDATE()) + 1, 0))
                    """, (cantidad, costo_movimiento, cod_bodega, cod))

                    if cursor_erp2.rowcount == 0:
                        raise ValueError(f"No se ha inicializado el registro mensual para {cod} en bodega {cod_bodega}.")

                    detalle_local.append({
                        'cod': cod,
                        'nombre': prod_row[0].strip() if prod_row[0] else cod,
                        'unidad': unidad_mov,
                        'cantidad': cantidad,
                        'costo_promedio': costo_promedio,
                        'precio_unitario': precio_unitario
                    })

                conn_erp2.commit()
            except Exception:
                conn_erp2.rollback()
                raise
            finally:
                conn_erp2.close()

            cursor.execute("""
                INSERT INTO solicitudes
                (num_documento_erp, correlativo_erp, cod_bodega_erp, bodega_destino_id,
                 estado, observaciones, solicitado_por, fecha_solicitud)
                OUTPUT inserted.id
                VALUES (?, ?, ?, ?, 'solicitada', ?, ?, GETDATE())
            """, (num_documento, correlativo, cod_bodega, bodega_interna['id'], observaciones, current_user.id))
            solicitud_id = cursor.fetchone()[0]

            for item in detalle_local:
                cursor.execute("""
                    SELECT id
                    FROM productos
                    WHERE UPPER(LTRIM(RTRIM(codigo))) = ?
                """, (item['cod'],))
                prod_local = cursor.fetchone()
                if prod_local:
                    producto_id = prod_local.id
                    cursor.execute("""
                        UPDATE productos
                        SET codigo = ?, cod_producto_erp = ?, codigo_interno = NULL,
                            nombre = ?, categoria = ISNULL(categoria, 'Producto'),
                            unidad_medida = ?, activo = 1
                        WHERE id = ?
                    """, (item['cod'], item['cod'], item['nombre'], item['unidad'], producto_id))
                else:
                    cursor.execute("""
                        INSERT INTO productos
                        (codigo, cod_producto_erp, codigo_interno, nombre, categoria, unidad_medida, stock_minimo, activo, fecha_creacion)
                        OUTPUT inserted.id
                        VALUES (?, ?, NULL, ?, 'Producto', ?, 0, 1, GETDATE())
                    """, (item['cod'], item['cod'], item['nombre'], item['unidad']))
                    producto_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO detalle_solicitud
                    (solicitud_id, producto_id, cod_producto_erp, nombre_producto, unidad_medida,
                     cantidad_solicitada, cantidad_recibida, costo_promedio, precio_unitario)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """, (
                    solicitud_id,
                    producto_id,
                    item['cod'],
                    item['nombre'],
                    item['unidad'],
                    item['cantidad'],
                    item['costo_promedio'],
                    item['precio_unitario']
                ))

            conn.commit()
            flash(f"Solicitud generada exitosamente. Documento #{num_documento}. Confirma recibido cuando entre a Bodega AproMan.", "success")
            return redirect(url_for('solicitudes.listado_solicitudes'))

    except Exception as e:
        conn.rollback()
        print(f"Error al crear solicitud: {e}")
        flash(f"Error al crear solicitud: {e}", "error")
    finally:
        conn.close()

    return render_template('solicitudes/crear_solicitud.html',
                           bodegas_erp=bodegas_erp,
                           empleados=empleados,
                           bodega_interna=bodega_interna)


@solicitudes_bp.route('/api/producto')
@login_required
@requiere_rol('administrador')
def api_producto():
    codigo = request.args.get('codigo', '').strip().upper()
    bodega = request.args.get('bodega', '').strip()

    if not codigo or not bodega:
        return jsonify({'error': 'Codigo y bodega son requeridos'}), 400

    conn_erp = get_erp_connection()
    cursor_erp = conn_erp.cursor()
    try:
        cursor_erp.execute("""
            SELECT
                a.COD_PRODUCTO,
                RTRIM(a.NOMBRE_PRODUCTO) AS nombre,
                b.PRECIO_UNITARIO,
                RTRIM(a.UNIDAD_MEDIDA) AS unidad_medida,
                xb.UNIDADES_DISPONIBL
            FROM sysadm.IN_PRODUCTOS AS a
            JOIN sysadm.IN_PRECIOS_TIPOCLT AS b ON a.COD_PRODUCTO = b.COD_PRODUCTO
            JOIN sysadm.IN_PRODUCTOS_X_BOD AS xb ON a.COD_PRODUCTO = xb.COD_PRODUCTO
            WHERE a.COD_TIPO_PRODUCTO = 1
              AND a.COD_CLASIFICACION NOT LIKE '1.1.1.%'
              AND a.COD_PRODUCTO LIKE '%-%'
              AND a.COD_PRODUCTO NOT LIKE '%p%'
              AND b.TIPO_CLIENTE = 10
              AND a.COD_PRODUCTO = ?
              AND xb.COD_BODEGA = ?
        """, (codigo, bodega))
        row = cursor_erp.fetchone()
        if not row:
            return jsonify({'error': 'Producto no encontrado en esta bodega'}), 404
        return jsonify({
            'codigo': row[0],
            'nombre': row[1],
            'precio': float(row[2]),
            'unidad_medida': row[3].strip() if row[3] else '',
            'existencias': float(row[4]) if row[4] is not None else 0
        })
    except Exception as e:
        print(f"Error en solicitudes.api_producto: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500
    finally:
        conn_erp.close()


@solicitudes_bp.route('/<int:id>/confirmar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def confirmar_solicitud(id):
    solicitud = None
    detalles = []
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.*, b.nombre as bodega_destino
            FROM solicitudes s
            INNER JOIN bodegas b ON s.bodega_destino_id = b.id
            WHERE s.id = ?
        """, (id,))
        row = cursor.fetchone()
        if not row:
            flash("Solicitud no encontrada.", "error")
            return redirect(url_for('solicitudes.listado_solicitudes'))
        solicitud = dict(zip([c[0] for c in cursor.description], row))

        cursor.execute("""
            SELECT ds.*, p.nombre as producto_nombre
            FROM detalle_solicitud ds
            INNER JOIN productos p ON ds.producto_id = p.id
            WHERE ds.solicitud_id = ?
            ORDER BY ds.id ASC
        """, (id,))
        detalles = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]

        if request.method == 'POST':
            recibidas = request.form.getlist('cantidad_recibida[]')
            detalle_ids = request.form.getlist('detalle_id[]')
            hubo_parcial = False

            for detalle_id, cantidad_recibida in zip(detalle_ids, recibidas):
                cantidad = float(cantidad_recibida or 0)
                detalle = next((d for d in detalles if int(d['id']) == int(detalle_id)), None)
                if not detalle:
                    continue
                pendiente = float(detalle['cantidad_solicitada'] or 0) - float(detalle['cantidad_recibida'] or 0)
                if cantidad < 0 or cantidad > pendiente:
                    raise ValueError("Cantidad recibida invalida para uno de los productos.")
                if cantidad < pendiente:
                    hubo_parcial = True
                if cantidad > 0:
                    cursor.execute("""
                        UPDATE detalle_solicitud
                        SET cantidad_recibida = cantidad_recibida + ?
                        WHERE id = ?
                    """, (cantidad, detalle_id))
                    cursor.execute("""
                        INSERT INTO movimientos
                        (producto_id, bodega_id, tipo, cantidad, solicitud_id, detalle_solicitud_id,
                         observacion, usuario_id, fecha_movimiento)
                        VALUES (?, ?, 'entrada', ?, ?, ?, 'Recepcion de solicitud', ?, GETDATE())
                    """, (
                        detalle['producto_id'],
                        solicitud['bodega_destino_id'],
                        cantidad,
                        solicitud['id'],
                        detalle_id,
                        current_user.id
                    ))

            cursor.execute("""
                SELECT
                    SUM(cantidad_solicitada) as solicitada,
                    SUM(cantidad_recibida) as recibida
                FROM detalle_solicitud
                WHERE solicitud_id = ?
            """, (id,))
            totales = cursor.fetchone()
            nuevo_estado = 'recibida' if float(totales.recibida or 0) >= float(totales.solicitada or 0) else 'recibida_parcial'
            if hubo_parcial and nuevo_estado != 'recibida':
                nuevo_estado = 'recibida_parcial'

            cursor.execute("""
                UPDATE solicitudes
                SET estado = ?, recibido_por = ?, fecha_recibido = GETDATE()
                WHERE id = ?
            """, (nuevo_estado, current_user.id, id))

            conn.commit()
            flash("Recepcion registrada en inventario.", "success")
            return redirect(url_for('solicitudes.listado_solicitudes'))

    except Exception as e:
        conn.rollback()
        print(f"Error al confirmar solicitud: {e}")
        flash(f"Error al confirmar recibido: {e}", "error")
        return redirect(url_for('solicitudes.listado_solicitudes'))
    finally:
        conn.close()

    return render_template('solicitudes/confirmar_solicitud.html', solicitud=solicitud, detalles=detalles)
