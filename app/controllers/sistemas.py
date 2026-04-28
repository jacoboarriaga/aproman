"""
MÃ³dulo: sistemas
DescripciÃ³n: GestiÃ³n de sistemas dentro de un proyecto.
Cada proyecto puede tener multiples sistemas (tipos de pintura/servicio)
con sus propios costos, pintores asignados y estado independiente.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import get_db_connection, get_erp_connection
from app.decorators import requiere_rol

# -----------------------------------------------
# Blueprint: sistemas â€” Prefijo: /sistemas
# -----------------------------------------------
sistemas_bp = Blueprint('sistemas', __name__, url_prefix='/sistemas')


# -----------------------------------------------
# 1. CREAR SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/crear/<int:proyecto_id>', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def crear_sistema(proyecto_id):
    """Formulario para agregar un nuevo sistema a un proyecto."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Validar que el proyecto exista
    cursor.execute("SELECT id, codigo, cliente_nombre, agente_id FROM proyectos WHERE id = ?", (proyecto_id,))
    proyecto = cursor.fetchone()

    if not proyecto:
        flash("El proyecto no existe.", "error")
        conn.close()
        return redirect(url_for('proyectos.mis_proyectos'))

    # Verificar permisos
    if current_user.rol == 'agente' and proyecto.agente_id != current_user.id:
        flash("No tienes permiso para agregar sistemas a este proyecto.", "error")
        conn.close()
        return redirect(url_for('proyectos.mis_proyectos'))

    if request.method == 'POST':
        sistema_codigo = request.form.get('sistema_codigo')
        monto_inicial = float(request.form.get('monto_inicial') or 0)
        metros_cuadrados = float(request.form.get('metros_cuadrados_iniciales') or 0)
        hombres_por_dia = int(request.form.get('hombres_por_dia_iniciales') or 0)
        producto_terminado = float(request.form.get('producto_terminado_inicial') or 0)
        estado = request.form.get('estado') or 'pendiente'

        # Costo de servicio = monto_inicial Ã— metros_cuadrados
        costo_servicio = monto_inicial * metros_cuadrados

        # Obtener el nombre del sistema desde la vista v_sistemas
        cursor.execute("SELECT sistema FROM v_sistemas WHERE codigo = ?", (sistema_codigo,))
        sis_row = cursor.fetchone()
        sistema_nombre = sis_row.sistema if sis_row else "Sistema Desconocido"

        try:
            cursor.execute("""
                INSERT INTO sistemas (
                    proyecto_id, sistema_codigo, sistema_nombre, monto_inicial, metros_cuadrados_iniciales,
                    hombres_por_dia_iniciales, producto_terminado_inicial, costo_servicio_m2_inicial,
                    estado, agente_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                proyecto_id, sistema_codigo, sistema_nombre, monto_inicial, metros_cuadrados,
                hombres_por_dia, producto_terminado, costo_servicio, estado, current_user.id
            ))
            conn.commit()
            flash(f"Sistema '{sistema_nombre}' aÃ±adido exitosamente.", "success")
            return redirect(url_for('proyectos.ver_proyecto', pk=proyecto_id))
        except Exception as e:
            conn.rollback()
            print(f"Error al crear sistema: {e}")
            flash("OcurriÃ³ un error al guardar el sistema.", "error")
        finally:
            conn.close()

    # GET: Preparar formulario con lista de sistemas disponibles
    try:
        cursor.execute("SELECT TOP (1000) codigo, sistema FROM v_sistemas ORDER BY sistema ASC")
        sistemas_disponibles = cursor.fetchall()
    except Exception as e:
        print(f"Error al obtener lista de sistemas: {e}")
        sistemas_disponibles = []

    conn.close()

    return render_template('sistemas/crear_sistema.html',
                           proyecto=proyecto,
                           sistemas_disponibles=sistemas_disponibles)


# -----------------------------------------------
# 2. VER DETALLE DEL SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/<int:id>')
@login_required
def ver_sistema(id):
    """Muestra el detalle del sistema con resumen financiero y pintores asignados."""
    puede_ver_costos = getattr(current_user, 'puede_ver_costos', False)
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Datos del sistema con info del proyecto padre
        cursor.execute("""
            SELECT s.*, p.codigo as proyecto_codigo, p.cliente_nombre as proyecto_cliente, p.agente_id
            FROM sistemas s
            INNER JOIN proyectos p ON s.proyecto_id = p.id
            WHERE s.id = ?
        """, (id,))
        row = cursor.fetchone()

        if not row:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        columnas = [column[0] for column in cursor.description]
        sistema = dict(zip(columnas, row))

        # Pintores asignados al sistema usando la nueva cabecera general de asignaciones
        cursor.execute("""
            SELECT dap.*, a.sistema_id, a.proyecto_id, a.estado as asignacion_estado,
                   a.fecha_asignacion as fecha_registro,
                   CONVERT(VARCHAR, a.fecha_asignacion, 103) as fecha_formateada,
                   t.nombre as pintor_nombre
            FROM detalle_asignacion_pintor dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            INNER JOIN pintores t ON dap.pintor_id = t.id
            WHERE a.sistema_id = ? AND a.tipo = 'pintor' AND a.estado <> 'anulada'
            ORDER BY dap.id DESC
        """, (id,))
        col_pers = [column[0] for column in cursor.description]
        personal = [dict(zip(col_pers, r)) for r in cursor.fetchall()]

        total_personal = sum(float(p['costo_total'] or 0) for p in personal)

        # Inventario asignado desde bodega interna
        cursor.execute("""
            SELECT dap.*, a.estado as asignacion_estado,
                   a.fecha_asignacion as fecha_registro,
                   CONVERT(VARCHAR, a.fecha_asignacion, 103) as fecha_formateada,
                   p.nombre as producto_nombre, p.codigo, p.cod_producto_erp, p.categoria, p.unidad_medida,
                   (dap.cantidad_asignada - dap.cantidad_consumida - dap.cantidad_devuelta) as cantidad_pendiente
            FROM detalle_asignacion_producto dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            INNER JOIN productos p ON dap.producto_id = p.id
            WHERE a.sistema_id = ? AND a.tipo = 'producto' AND a.estado <> 'anulada'
            ORDER BY dap.id DESC
        """, (id,))
        col_prod = [column[0] for column in cursor.description]
        productos_asignados = [dict(zip(col_prod, r)) for r in cursor.fetchall()]

        # Gastos variables del sistema
        cursor.execute("""
            SELECT g.*, c.nombre as categoria_nombre,
                   CONVERT(VARCHAR, g.fecha_gasto, 103) as fecha_formateada
            FROM gastos g
            INNER JOIN categorias_gasto c ON g.categoria_id = c.id
            WHERE g.sistema_id = ?
            ORDER BY g.fecha_gasto DESC, g.id DESC
        """, (id,))
        col_gastos = [column[0] for column in cursor.description]
        gastos = [dict(zip(col_gastos, r)) for r in cursor.fetchall()]

        total_gastos = sum(float(g['monto'] or 0) for g in gastos)

    except Exception as e:
        print(f"Error al cargar sistema: {e}")
        flash("Error al cargar detalles del sistema.", "error")
        return redirect(url_for('proyectos.mis_proyectos'))
    finally:
        conn.close()

    return render_template('sistemas/ver_sistema.html',
                           sistema=sistema,
                           personal=personal,
                           total_personal=total_personal,
                           total_materiales=total_gastos,
                           total_gastos=total_gastos,
                           productos_asignados=productos_asignados,
                           gastos=gastos,
                           puede_ver_costos=puede_ver_costos)


# -----------------------------------------------
# 3. EDITAR SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def editar_sistema(id):
    """Formulario de ediciÃ³n de los valores iniciales de un sistema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.*, p.codigo as proyecto_codigo, p.cliente_nombre as proyecto_cliente, p.agente_id
            FROM sistemas s
            INNER JOIN proyectos p ON s.proyecto_id = p.id
            WHERE s.id = ?
        """, (id,))
        row = cursor.fetchone()

        if not row:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        columnas = [column[0] for column in cursor.description]
        sistema = dict(zip(columnas, row))

        if request.method == 'POST':
            monto_inicial = float(request.form.get('monto_inicial') or 0)
            metros_cuadrados = float(request.form.get('metros_cuadrados_iniciales') or 0)
            hombres_por_dia = int(request.form.get('hombres_por_dia_iniciales') or 0)
            producto_terminado = float(request.form.get('producto_terminado_inicial') or 0)
            costo_servicio = monto_inicial * metros_cuadrados

            cursor.execute("""
                UPDATE sistemas 
                SET monto_inicial = ?, metros_cuadrados_iniciales = ?, 
                    hombres_por_dia_iniciales = ?, producto_terminado_inicial = ?,
                    costo_servicio_m2_inicial = ?
                WHERE id = ?
            """, (monto_inicial, metros_cuadrados, hombres_por_dia, producto_terminado, costo_servicio, id))
            conn.commit()

            flash("Sistema actualizado correctamente.", "success")
            return redirect(url_for('sistemas.ver_sistema', id=id))

    except Exception as e:
        conn.rollback()
        print(f"Error al editar sistema: {e}")
        flash("Error al actualizar el sistema.", "error")
    finally:
        conn.close()

    return render_template('sistemas/editar_sistema.html', sistema=sistema)


# -----------------------------------------------
# 4. CAMBIAR ESTADO DEL SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/<int:id>/cambiar-estado', methods=['POST'])
@login_required
@requiere_rol('administrador')
def cambiar_estado(id):
    """Cicla el estado del sistema: pendiente â†’ activo â†’ completado â†’ pendiente."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT s.id, s.estado, s.proyecto_id FROM sistemas s WHERE s.id = ?", (id,))
        sistema = cursor.fetchone()

        if not sistema:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        nuevo_estado = sistema.estado
        msg = ""

        if sistema.estado == 'pendiente':
            nuevo_estado = 'activo'
            msg = "Sistema activado correctamente."
        elif sistema.estado == 'activo':
            flash("Para completar un sistema debes ingresar sus valores finales.", "error")
            return redirect(url_for('sistemas.ver_sistema', id=id))
        elif sistema.estado == 'completado':
            nuevo_estado = 'activo'
            msg = "Sistema reabierto (activo). Recuerda volver a finalizarlo al terminar tus modificaciones."
        if nuevo_estado != sistema.estado:
            cursor.execute("UPDATE sistemas SET estado = ? WHERE id = ?", (nuevo_estado, id))
            conn.commit()
            flash(msg, "success")

    except Exception as e:
        conn.rollback()
        print(f"Error al cambiar estado de sistema: {e}")
        flash("Error al actualizar el estado.", "error")
    finally:
        conn.close()

    return redirect(url_for('sistemas.ver_sistema', id=id))

# -----------------------------------------------
# 4.3 ELIMINAR SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@requiere_rol('administrador')
def eliminar_sistema(id):
    """Elimina el sistema solo si no tiene asignaciones, gastos ni productos internos."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Obtener el sistema y nombre/cÃ³digo para comprobar en el ERP
        cursor.execute("""
            SELECT s.sistema_nombre, p.codigo as proyecto_codigo, s.proyecto_id 
            FROM sistemas s
            INNER JOIN proyectos p ON s.proyecto_id = p.id
            WHERE s.id = ?
        """, (id,))
        sistema = cursor.fetchone()

        if not sistema:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        # Validar dependencias locales nuevas
        cursor.execute("SELECT COUNT(*) FROM asignaciones WHERE sistema_id = ? AND estado <> 'anulada'", (id,))
        count_asignaciones = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM gastos WHERE sistema_id = ?", (id,))
        count_gastos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM movimientos WHERE sistema_id = ?", (id,))
        count_movimientos = cursor.fetchone()[0]

        if count_asignaciones > 0 or count_gastos > 0 or count_movimientos > 0:
            flash("No puedes eliminar un sistema que ya tiene asignaciones, gastos o movimientos registrados.", "error")
            return redirect(url_for('sistemas.ver_sistema', id=id))

        # Validar dependencias ERP
        try:
            from app.utils import get_erp_connection
            conn_erp = get_erp_connection()
            cursor_erp = conn_erp.cursor()
            
            descripcion_busqueda = f"ID:{id} |%"
            cursor_erp.execute("SELECT COUNT(*) FROM sysadm.IN_DOCUMENTO WHERE DESCRIPCION LIKE ?", (descripcion_busqueda,))
            count_erp = cursor_erp.fetchone()[0]
            
            if count_erp > 0:
                flash("No puedes eliminar un sistema que ya cuenta con solicitudes de producto de pintura.", "error")
                return redirect(url_for('sistemas.ver_sistema', id=id))
        except Exception as e_erp:
            print(f"Error al conectar con ERP para verificar eliminaciÃ³n: {e_erp}")
            flash("No pudimos conectar con bodega para confirmar las solicitudes. EliminaciÃ³n bloqueada por seguridad.", "error")
            return redirect(url_for('sistemas.ver_sistema', id=id))

        # Eliminar
        cursor.execute("DELETE FROM sistemas WHERE id = ?", (id,))
        conn.commit()
        flash("Sistema eliminado con Ã©xito.", "success")
        return redirect(url_for('proyectos.ver_proyecto', pk=sistema.proyecto_id))

    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar sistema: {e}")
        flash("OcurriÃ³ un error al intentar eliminar el sistema.", "error")
        return redirect(url_for('sistemas.ver_sistema', id=id))
    finally:
        conn.close()

# -----------------------------------------------
# 4.5 FINALIZAR SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/<int:id>/finalizar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def finalizar_sistema(id):
    """Cierra el sistema pidiendo los valores finales precisos y calculados."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM sistemas WHERE id = ?", (id,))
        row = cursor.fetchone()
        
        if not row:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        cols = [column[0] for column in cursor.description]
        sistema = dict(zip(cols, row))

        # Para que solo se pueda finalizar si esta activo
        if sistema['estado'] != 'activo':
            flash("Solo puedes finalizar sistemas que estÃ©n activos.", "error")
            return redirect(url_for('sistemas.ver_sistema', id=id))

        if request.method == 'POST':
            monto_final = request.form.get('monto_final', type=float) or 0.0
            metros_finales = request.form.get('metros_cuadrados_finales', type=float) or 0.0
            hombres_finales = request.form.get('hombres_por_dia_finales', type=int) or 0
            producto_final = request.form.get('producto_terminado_final', type=float) or 0.0
            costo_m2_final = request.form.get('costo_servicio_m2_final', type=float) or 0.0

            cursor.execute("""
                UPDATE sistemas
                SET estado = 'completado',
                    monto_final = ?,
                    metros_cuadrados_finales = ?,
                    hombres_por_dia_finales = ?,
                    producto_terminado_final = ?,
                    costo_servicio_m2_final = ?,
                    fecha_finalizacion = GETDATE()
                WHERE id = ?
            """, (monto_final, metros_finales, hombres_finales, producto_final, costo_m2_final, id))
            conn.commit()
            flash("El sistema ha sido completado y sus valores finales guardados.", "success")
            return redirect(url_for('sistemas.ver_sistema', id=id))

        cursor.execute("""
            SELECT ISNULL(SUM(dap.costo_total), 0)
            FROM detalle_asignacion_pintor dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            WHERE a.sistema_id = ? AND a.tipo = 'pintor' AND a.estado <> 'anulada'
        """, (id,))
        total_personal = cursor.fetchone()[0]

    except Exception as e:
        print(f"Error al finalizar sistema: {e}")
        flash("Hubo un error al procesar la solicitud.", "error")
        total_personal = 0
    finally:
        conn.close()

    return render_template('sistemas/finalizar_sistema.html', sistema=sistema, total_personal=total_personal)


# -----------------------------------------------
# 5. ASIGNAR PINTOR AL SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/<int:sistema_id>/pintor/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def asignar_pintor(sistema_id):
    """Formulario para asignar un pintor del catalogo a un sistema activo."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sistema = None
    pintores = []

    try:
        cursor.execute(
            "SELECT id, estado, proyecto_id, sistema_nombre FROM sistemas WHERE id = ?",
            (sistema_id,)
        )
        sis_row = cursor.fetchone()

        if not sis_row:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        if sis_row.estado != 'activo':
            flash("Solo puedes asignar pintores a sistemas activos.", "warning")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

        sistema = {'id': sis_row.id, 'nombre': sis_row.sistema_nombre, 'proyecto_id': sis_row.proyecto_id}

        # Lista de pintores disponibles
        cursor.execute("SELECT id, nombre FROM pintores ORDER BY nombre ASC")
        pintores = [{'id': row[0], 'nombre': row[1]} for row in cursor.fetchall()]

        if request.method == 'POST':
            pintor_id = request.form.get('pintor_id')
            pago_dia = float(request.form.get('pago_dia', 0))
            dias_trabajados = float(request.form.get('dias_trabajados', 1))
            fechas_especificas = request.form.get('fechas_especificas', '')

            costo_total = pago_dia * dias_trabajados

            cursor.execute("""
                INSERT INTO asignaciones
                (proyecto_id, sistema_id, tipo, estado, creado_por, fecha_asignacion)
                OUTPUT inserted.id
                VALUES (?, ?, 'pintor', 'activa', ?, GETDATE())
            """, (sis_row.proyecto_id, sistema_id, current_user.id))
            asignacion_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO detalle_asignacion_pintor
                (asignacion_id, pintor_id, pago_dia, dias_trabajados, costo_total, fechas_especificas)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (asignacion_id, pintor_id, pago_dia, dias_trabajados, costo_total, fechas_especificas))

            conn.commit()
            flash("Pintor asignado exitosamente al sistema.", "success")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

    except Exception as e:
        conn.rollback()
        print(f"Error al asignar pintor al sistema: {e}")
        flash("Error al realizar la asignaciÃ³n.", "error")
    finally:
        conn.close()

    if not sistema:
        return redirect(url_for('proyectos.mis_proyectos'))

    return render_template('sistemas/asignar_pintor.html',
                           sistema=sistema,
                           pintores=pintores)


# -----------------------------------------------
# 6. EDITAR ASIGNACION DE PINTOR
# -----------------------------------------------
@sistemas_bp.route('/pintor/asignacion/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def editar_asignacion_pintor(id):
    """Formulario para editar o eliminar una asignacion de pintor en un sistema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    asignacion = None

    try:
        # Traer el detalle de asignacion con datos del pintor y sistema
        cursor.execute("""
            SELECT dap.*, a.sistema_id, a.proyecto_id, a.estado as asignacion_estado,
                   t.nombre as pintor_nombre, s.sistema_nombre, s.estado as sistema_estado
            FROM detalle_asignacion_pintor dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            INNER JOIN pintores t ON dap.pintor_id = t.id
            INNER JOIN sistemas s ON a.sistema_id = s.id
            WHERE dap.id = ?
        """, (id,))
        row = cursor.fetchone()

        if not row:
            flash("AsignaciÃ³n no encontrada.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        columnas = [column[0] for column in cursor.description]
        asignacion = dict(zip(columnas, row))

        if asignacion['sistema_estado'] != 'activo':
            flash("No puedes editar asignaciones de un sistema que no estÃ¡ activo.", "warning")
            return redirect(url_for('sistemas.ver_sistema', id=asignacion['sistema_id']))

        if request.method == 'POST':
            accion = request.form.get('accion', 'guardar')

            if accion == 'eliminar':
                # Retirar pintor del sistema
                cursor.execute("UPDATE asignaciones SET estado = 'anulada', fecha_cierre = GETDATE() WHERE id = ?", (asignacion['asignacion_id'],))
                conn.commit()
                flash("Pintor retirado del sistema correctamente.", "success")
                return redirect(url_for('sistemas.ver_sistema', id=asignacion['sistema_id']))
            else:
                # Actualizar datos de la asignacion
                pago_dia = float(request.form.get('pago_dia', 0))
                dias_trabajados = float(request.form.get('dias_trabajados', 1))
                fechas_especificas = request.form.get('fechas_especificas', '')

                costo_total = pago_dia * dias_trabajados

                cursor.execute("""
                    UPDATE detalle_asignacion_pintor
                    SET pago_dia = ?, dias_trabajados = ?, costo_total = ?, fechas_especificas = ?
                    WHERE id = ?
                """, (pago_dia, dias_trabajados, costo_total, fechas_especificas, id))

                conn.commit()
                flash("AsignaciÃ³n actualizada exitosamente.", "success")
                return redirect(url_for('sistemas.ver_sistema', id=asignacion['sistema_id']))

    except Exception as e:
        conn.rollback()
        print(f"Error al editar asignacion de pintor: {e}")
        flash("Error al actualizar la asignacion.", "error")
        return redirect(url_for('proyectos.mis_proyectos'))
    finally:
        conn.close()

    return render_template('sistemas/editar_asignacion_pintor.html', asignacion=asignacion)


# -----------------------------------------------
# 7. ASIGNAR MATERIAL AL SISTEMA
# -----------------------------------------------
@sistemas_bp.route('/<int:sistema_id>/material/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def asignar_material(sistema_id):
    """Asigna productos disponibles de la bodega interna a un sistema activo."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sistema = None
    productos = []
    registros_tipo = []
    bodega = None
    tipo_inventario = request.args.get('tipo', 'producto').strip().lower()
    tipos_inventario = {
        'producto': {
            'titulo': 'Producto',
            'categorias': ['PRODUCTO', 'PINTURA', 'BODEGA', 'ERP', ''],
            'prefijos': []
        },
        'material': {
            'titulo': 'Material',
            'categorias': ['MATERIAL', 'MATERIALES', 'CONSUMIBLE', 'CONSUMIBLES'],
            'prefijos': ['M-%']
        },
        'equipo': {
            'titulo': 'Equipo',
            'categorias': ['EQUIPO', 'EQUIPOS', 'HERRAMIENTA', 'HERRAMIENTAS'],
            'prefijos': ['E-%']
        }
    }
    if tipo_inventario not in tipos_inventario:
        tipo_inventario = 'producto'

    try:
        cursor.execute(
            "SELECT id, estado, proyecto_id, sistema_nombre FROM sistemas WHERE id = ?",
            (sistema_id,)
        )
        sis_row = cursor.fetchone()

        if not sis_row:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        if sis_row.estado != 'activo':
            flash("Solo puedes asignar inventario a sistemas activos.", "warning")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

        sistema = {'id': sis_row.id, 'nombre': sis_row.sistema_nombre, 'proyecto_id': sis_row.proyecto_id}

        cursor.execute("""
            SELECT TOP 1 id, nombre
            FROM bodegas
            WHERE activa = 1 AND tipo = 'interna'
            ORDER BY id ASC
        """)
        bodega_row = cursor.fetchone()
        if not bodega_row:
            flash("Debes crear una bodega interna activa antes de asignar inventario.", "error")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

        bodega = {'id': bodega_row.id, 'nombre': bodega_row.nombre}

        tipo_config = tipos_inventario[tipo_inventario]
        categorias = tipo_config['categorias']
        prefijos = tipo_config['prefijos']
        condiciones = ["UPPER(LTRIM(RTRIM(ISNULL(categoria, '')))) IN ({})".format(', '.join(['?'] * len(categorias)))]
        params_filtro = list(categorias)
        for _ in prefijos:
            condiciones.append("UPPER(LTRIM(RTRIM(ISNULL(codigo, '')))) LIKE ?")
        params_filtro.extend(prefijos)

        cursor.execute("""
            SELECT producto_id as id, codigo, nombre, categoria, cod_producto_erp, unidad_medida, stock_disponible
            FROM v_stock_productos
            WHERE bodega_id = ?
              AND ({})
            ORDER BY nombre ASC
        """.format(' OR '.join(condiciones)), [bodega['id']] + params_filtro)
        registros_tipo = [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()]
        productos = [p for p in registros_tipo if float(p.get('stock_disponible') or 0) > 0]

        if request.method == 'POST':
            producto_id = request.form.get('producto_id')
            cantidad = float(request.form.get('cantidad') or 0)
            observaciones = request.form.get('observaciones', '').strip()[:500] or None

            if not producto_id or cantidad <= 0:
                flash("Debes seleccionar un registro e indicar una cantidad valida.", "warning")
                return render_template('sistemas/asignar_material.html',
                                       sistema=sistema, productos=productos, bodega=bodega,
                                       tipo_inventario=tipo_inventario, tipos_inventario=tipos_inventario,
                                       registros_tipo=registros_tipo)

            cursor.execute("""
                SELECT stock_disponible
                FROM v_stock_productos
                WHERE producto_id = ? AND bodega_id = ?
            """, (producto_id, bodega['id']))
            stock_row = cursor.fetchone()
            stock_disponible = float(stock_row.stock_disponible) if stock_row else 0.0

            if cantidad > stock_disponible:
                flash("La cantidad solicitada supera las existencias disponibles.", "warning")
                return render_template('sistemas/asignar_material.html',
                                       sistema=sistema, productos=productos, bodega=bodega,
                                       tipo_inventario=tipo_inventario, tipos_inventario=tipos_inventario,
                                       registros_tipo=registros_tipo)

            cursor.execute("""
                INSERT INTO asignaciones
                (proyecto_id, sistema_id, tipo, bodega_origen_id, estado, observaciones, creado_por, fecha_asignacion)
                OUTPUT inserted.id
                VALUES (?, ?, 'producto', ?, 'activa', ?, ?, GETDATE())
            """, (sis_row.proyecto_id, sistema_id, bodega['id'], observaciones, current_user.id))
            asignacion_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO detalle_asignacion_producto
                (asignacion_id, producto_id, cantidad_asignada, cantidad_consumida, cantidad_devuelta)
                OUTPUT inserted.id
                VALUES (?, ?, ?, 0, 0)
            """, (asignacion_id, producto_id, cantidad))
            detalle_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO movimientos
                (producto_id, bodega_id, tipo, cantidad, asignacion_id, detalle_asignacion_producto_id,
                 proyecto_id, sistema_id, observacion, usuario_id, fecha_movimiento)
                VALUES (?, ?, 'asignacion', ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """, (producto_id, bodega['id'], cantidad, asignacion_id, detalle_id,
                  sis_row.proyecto_id, sistema_id, observaciones, current_user.id))

            conn.commit()
            flash("{} asignado exitosamente al sistema.".format(tipos_inventario[tipo_inventario]['titulo']), "success")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

    except Exception as e:
        conn.rollback()
        print(f"Error al asignar inventario al sistema: {e}")
        flash("Error al realizar la asignacion de inventario.", "error")
    finally:
        conn.close()

    if not sistema or not bodega:
        return redirect(url_for('proyectos.mis_proyectos'))

    return render_template('sistemas/asignar_material.html',
                           sistema=sistema,
                           productos=productos,
                           bodega=bodega,
                           tipo_inventario=tipo_inventario,
                           tipos_inventario=tipos_inventario,
                           registros_tipo=registros_tipo)


# -----------------------------------------------
# 8. EDITAR ASIGNACIÃ“N DE MATERIAL
# -----------------------------------------------
@sistemas_bp.route('/material/asignacion/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def editar_asignacion_material(id):
    """Registra consumo, devolucion o anulacion de una asignacion de producto."""
    conn = get_db_connection()
    cursor = conn.cursor()
    asignacion = None

    try:
        cursor.execute("""
            SELECT dap.*, a.sistema_id, a.proyecto_id, a.bodega_origen_id, a.estado as asignacion_estado,
                   s.sistema_nombre, s.estado as sistema_estado,
                   p.nombre as producto_nombre, p.unidad_medida, p.codigo, p.cod_producto_erp
            FROM detalle_asignacion_producto dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            INNER JOIN sistemas s ON a.sistema_id = s.id
            INNER JOIN productos p ON dap.producto_id = p.id
            WHERE dap.id = ?
        """, (id,))
        row = cursor.fetchone()

        if not row:
            flash("Asignacion de producto no encontrada.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        columnas = [column[0] for column in cursor.description]
        asignacion = dict(zip(columnas, row))

        if asignacion['sistema_estado'] != 'activo':
            flash("No puedes editar asignaciones de un sistema que no esta activo.", "warning")
            return redirect(url_for('sistemas.ver_sistema', id=asignacion['sistema_id']))

        if request.method == 'POST':
            accion = request.form.get('accion', 'guardar')

            if accion == 'eliminar':
                pendiente = float(asignacion['cantidad_asignada'] or 0) - float(asignacion['cantidad_consumida'] or 0) - float(asignacion['cantidad_devuelta'] or 0)
                if pendiente > 0:
                    cursor.execute("""
                        INSERT INTO movimientos
                        (producto_id, bodega_id, tipo, cantidad, asignacion_id, detalle_asignacion_producto_id,
                         proyecto_id, sistema_id, observacion, usuario_id, fecha_movimiento)
                        VALUES (?, ?, 'devolucion', ?, ?, ?, ?, ?, 'Anulacion de asignacion', ?, GETDATE())
                    """, (asignacion['producto_id'], asignacion['bodega_origen_id'], pendiente,
                          asignacion['asignacion_id'], id, asignacion['proyecto_id'],
                          asignacion['sistema_id'], current_user.id))
                cursor.execute("UPDATE detalle_asignacion_producto SET cantidad_devuelta = cantidad_asignada - cantidad_consumida WHERE id = ?", (id,))
                cursor.execute("UPDATE asignaciones SET estado = 'anulada', fecha_cierre = GETDATE() WHERE id = ?", (asignacion['asignacion_id'],))
                conn.commit()
                flash("Producto retirado del sistema correctamente.", "success")
                return redirect(url_for('sistemas.ver_sistema', id=asignacion['sistema_id']))

            nueva_consumida = float(request.form.get('cantidad_consumida') or 0)
            nueva_devuelta = float(request.form.get('cantidad_devuelta') or 0)
            observacion = request.form.get('observacion', '').strip()[:500] or None

            asignada = float(asignacion['cantidad_asignada'] or 0)
            consumida_anterior = float(asignacion['cantidad_consumida'] or 0)
            devuelta_anterior = float(asignacion['cantidad_devuelta'] or 0)

            if nueva_consumida < 0 or nueva_devuelta < 0 or nueva_consumida + nueva_devuelta > asignada:
                flash("La suma de consumo y devolucion no puede superar lo asignado.", "warning")
                return render_template('sistemas/editar_asignacion_material.html', asignacion=asignacion)

            delta_consumo = nueva_consumida - consumida_anterior
            delta_devolucion = nueva_devuelta - devuelta_anterior

            if delta_consumo < 0 or delta_devolucion < 0:
                flash("Por trazabilidad, no se puede reducir consumo o devolucion ya registrada. Usa un ajuste desde inventario si necesitas corregir.", "warning")
                return render_template('sistemas/editar_asignacion_material.html', asignacion=asignacion)

            cursor.execute("""
                UPDATE detalle_asignacion_producto
                SET cantidad_consumida = ?, cantidad_devuelta = ?
                WHERE id = ?
            """, (nueva_consumida, nueva_devuelta, id))

            if delta_consumo > 0:
                cursor.execute("""
                    INSERT INTO movimientos
                    (producto_id, bodega_id, tipo, cantidad, asignacion_id, detalle_asignacion_producto_id,
                     proyecto_id, sistema_id, observacion, usuario_id, fecha_movimiento)
                    VALUES (?, NULL, 'consumo', ?, ?, ?, ?, ?, ?, ?, GETDATE())
                """, (asignacion['producto_id'], delta_consumo, asignacion['asignacion_id'],
                      id, asignacion['proyecto_id'], asignacion['sistema_id'],
                      observacion, current_user.id))

            if delta_devolucion > 0:
                cursor.execute("""
                    INSERT INTO movimientos
                    (producto_id, bodega_id, tipo, cantidad, asignacion_id, detalle_asignacion_producto_id,
                     proyecto_id, sistema_id, observacion, usuario_id, fecha_movimiento)
                    VALUES (?, ?, 'devolucion', ?, ?, ?, ?, ?, ?, ?, GETDATE())
                """, (asignacion['producto_id'], asignacion['bodega_origen_id'], delta_devolucion,
                      asignacion['asignacion_id'], id, asignacion['proyecto_id'],
                      asignacion['sistema_id'], observacion, current_user.id))

            if nueva_consumida + nueva_devuelta == asignada:
                cursor.execute("UPDATE asignaciones SET estado = 'cerrada', fecha_cierre = GETDATE() WHERE id = ?", (asignacion['asignacion_id'],))

            conn.commit()
            flash("Asignacion de producto actualizada exitosamente.", "success")
            return redirect(url_for('sistemas.ver_sistema', id=asignacion['sistema_id']))

    except Exception as e:
        conn.rollback()
        print(f"Error al editar asignacion producto: {e}")
        flash("Error al actualizar la asignacion de producto.", "error")
        return redirect(url_for('proyectos.mis_proyectos'))
    finally:
        conn.close()

    return render_template('sistemas/editar_asignacion_material.html', 
                           asignacion=asignacion)


# -----------------------------------------------
# 8.5 REGISTRAR GASTO VARIABLE
# -----------------------------------------------
@sistemas_bp.route('/<int:sistema_id>/gasto/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def registrar_gasto(sistema_id):
    """Registra costos variables como comida, transporte o combustible."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sistema = None
    categorias = []

    try:
        cursor.execute(
            "SELECT id, estado, proyecto_id, sistema_nombre FROM sistemas WHERE id = ?",
            (sistema_id,)
        )
        sis_row = cursor.fetchone()

        if not sis_row:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        if sis_row.estado != 'activo':
            flash("Solo puedes registrar gastos en sistemas activos.", "warning")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

        sistema = {
            'id': sis_row.id,
            'nombre': sis_row.sistema_nombre,
            'proyecto_id': sis_row.proyecto_id
        }

        cursor.execute("""
            SELECT id, nombre
            FROM categorias_gasto
            WHERE activa = 1
            ORDER BY nombre ASC
        """)
        categorias = [{'id': row.id, 'nombre': row.nombre} for row in cursor.fetchall()]

        if request.method == 'POST':
            categoria_id = request.form.get('categoria_id')
            descripcion = request.form.get('descripcion', '').strip()[:300]
            monto = float(request.form.get('monto') or 0)
            fecha_gasto = request.form.get('fecha_gasto') or None

            if not categoria_id or not descripcion or monto < 0:
                flash("Categoria, descripcion y monto valido son obligatorios.", "warning")
                return render_template(
                    'sistemas/registrar_gasto.html',
                    sistema=sistema,
                    categorias=categorias
                )

            cursor.execute("""
                INSERT INTO gastos
                (proyecto_id, sistema_id, categoria_id, descripcion, monto, fecha_gasto, registrado_por, fecha_registro)
                VALUES (?, ?, ?, ?, ?, ISNULL(?, GETDATE()), ?, GETDATE())
            """, (
                sis_row.proyecto_id,
                sistema_id,
                categoria_id,
                descripcion,
                monto,
                fecha_gasto,
                current_user.id
            ))
            conn.commit()
            flash("Gasto variable registrado correctamente.", "success")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

    except Exception as e:
        conn.rollback()
        print(f"Error al registrar gasto variable: {e}")
        flash("Error al registrar gasto variable.", "error")
    finally:
        conn.close()

    if not sistema:
        return redirect(url_for('proyectos.mis_proyectos'))

    return render_template('sistemas/registrar_gasto.html',
                           sistema=sistema,
                           categorias=categorias)


# -----------------------------------------------
# 9. SOLICITAR PRODUCTO
# -----------------------------------------------
@sistemas_bp.route('/<int:sistema_id>/solicitar-pintura', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def solicitar_pintura(sistema_id):
    """El nuevo flujo de solicitudes vive en el modulo de solicitudes generales."""
    flash("Las solicitudes ahora se hacen desde Inventario > Solicitudes. Luego asigna el producto al sistema desde bodega.", "info")
    return redirect(url_for('solicitudes.crear_solicitud'))

    # Flujo anterior conservado temporalmente como referencia durante la migracion.
    # --- Verificar que el sistema existe y estÃ¡ activo (BD Aproman) ---
    conn_ap = get_db_connection()
    cursor_ap = conn_ap.cursor()
    try:
        cursor_ap.execute(
            "SELECT id, estado, proyecto_id, sistema_nombre FROM sistemas WHERE id = ?",
            (sistema_id,)
        )
        sis_row = cursor_ap.fetchone()

        if not sis_row:
            flash("Sistema no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        if sis_row.estado != 'activo':
            flash("SÃ³lo puedes solicitar productos para sistemas activos.", "warning")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

        # --- Traer el cÃ³digo del proyecto para la descripciÃ³n del documento ---
        cursor_ap.execute("SELECT codigo FROM proyectos WHERE id = ?", (sis_row.proyecto_id,))
        proy_row = cursor_ap.fetchone()
        proyecto_codigo = proy_row.codigo if proy_row else 'PRY-000'

    except Exception as e:
        print(f"Error al verificar sistema: {e}")
        flash("Error al cargar el sistema.", "error")
        return redirect(url_for('proyectos.mis_proyectos'))
    finally:
        conn_ap.close()

    sistema = {
        'id':         sis_row.id,
        'nombre':     sis_row.sistema_nombre,
        'proyecto_id': sis_row.proyecto_id,
        'proyecto_codigo': proyecto_codigo
    }

    # --- Cargar datos auxiliares desde el ERP ---
    conn_erp = get_erp_connection()
    cursor_erp = conn_erp.cursor()
    try:
        # Lista de bodegas activas
        cursor_erp.execute("""
            SELECT COD_BODEGA, NOMBRE_BODEGA, Correlativo_Doc
            FROM sysadm.IN_BODEGAS
            WHERE BODEGA_INACTIVA = 'N'
                AND COD_BODEGA = 1 -- Solo bodega principal para evitar confusiÃ³n
            ORDER BY COD_BODEGA
        """)
        bodegas = [
            {'cod': row[0], 'nombre': row[1], 'correlativo_doc': row[2]}
            for row in cursor_erp.fetchall()
        ]

        # Lista de empleados para el select de "quiÃ©n recibe"
        cursor_erp.execute("""
            SELECT COD_EMPLEADO,
                   RTRIM(NOMBRES_EMPLEADO) + ' ' + RTRIM(APELLIDOS_EMPLEADO) AS nombre_completo
            FROM sysadm.EMPLEADO
            WHERE COD_EMPLEADO = 2 -- Solo el empleado DE PROCOLOR para evitar confusiÃ³n (FRANCISCO ARTEAGA)
            ORDER BY NOMBRES_EMPLEADO
        """)
        empleados = [
            {'cod': row[0], 'nombre': row[1]}
            for row in cursor_erp.fetchall()
        ]

    except Exception as e:
        print(f"Error al cargar datos ERP: {e}")
        flash("Error al cargar datos de bodega.", "error")
        bodegas   = []
        empleados = []
    finally:
        conn_erp.close()

    # ----------- POST: procesar la solicitud -----------
    if request.method == 'POST':
        cod_bodega        = request.form.get('cod_bodega', '').strip()
        empleado_recibe   = request.form.get('empleado_recibe', '')
        observaciones     = request.form.get('observaciones', '')

        codigos    = request.form.getlist('codigo[]')
        cantidades = request.form.getlist('cantidad[]')
        unidades   = request.form.getlist('unidad_medida[]')

        if not cod_bodega or not codigos:
            flash("Debes seleccionar una bodega y agregar al menos un producto.", "warning")
            return render_template('sistemas/solicitar_productos.html',
                                   sistema=sistema, bodegas=bodegas, empleados=empleados)

        conn_erp2 = get_erp_connection()
        cursor_erp2 = conn_erp2.cursor()
        
        try:
            # === 0. Validar PerÃ­odos Cierre ===
            cursor_erp2.execute("""
                SELECT status_inv 
                FROM PERIODOS_CIERRE 
                WHERE anio = YEAR(GETDATE()) 
                  AND periodo = MONTH(GETDATE())
            """)
            periodo_row = cursor_erp2.fetchone()
            if not periodo_row or periodo_row[0] == 'C':
                raise ValueError("El periodo contable actual de inventario se encuentra cerrado (o no existe). No se puede registrar la salida.")

            # === 1. Validar nombre responsable ===
            cursor_erp2.execute("""
                SELECT RTRIM(NOMBRES_EMPLEADO) + ' ' + RTRIM(APELLIDOS_EMPLEADO)
                FROM sysadm.EMPLEADO WHERE COD_EMPLEADO = ?
            """, (empleado_recibe,))
            emp_row = cursor_erp2.fetchone()
            nombre_emp_recibe = emp_row[0][:50] if emp_row else 'EMPLEADO'
            
            usuario_ingreso = (current_user.username or 'sysadm')[:10]
            descripcion = f"ID:{sistema['id']} | {sistema['nombre']} | PROYECTO: {proyecto_codigo}"[:150]

            # === 2. ActualizaciÃ³n Segura de Correlativos (Bloqueos Concurrentes con OUTPUT) ===
            
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

            # === 3. InserciÃ³n de Cabecera (IN_DOCUMENTO) ===
            cursor_erp2.execute("""
                INSERT INTO sysadm.IN_DOCUMENTO (
                    NUM_EMPRESA, TIPO_DOCUMENTO, COD_BODEGA, NUM_CUENTA, CORRELATIVO,
                    DESCRIPCION, NUM_DOCUMENTO, FECHA_DOCUMENTO, STATUS_DOCUMENTO,
                    USUARIO_INGRESO, FECHA_INGRESO,
                    EMPLEADO_ENTREGA, NOMBRE_EMP_ENTREGA,
                    EMPLEADO_RECIBE,  NOMBRE_EMP_RECIBE,
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

            # === 4. InserciÃ³n de Detalle e Inventarios ===
            for num_linea, (cod, cantidad, unidad) in enumerate(zip(codigos, cantidades, unidades)):
                if not cod or not cantidad:
                    continue
                
                cant_float = float(cantidad)
                
                # Obtener costo_promedio para el cÃ¡lculo financiero de la salida
                cursor_erp2.execute("""
                    SELECT ISNULL(costo_promedio, 0) 
                    FROM sysadm.IN_PRODUCTOS 
                    WHERE COD_PRODUCTO = ?
                """, (cod,))
                cp_row = cursor_erp2.fetchone()
                costo_promedio = float(cp_row[0]) if cp_row else 0.0
                
                costo_movimiento = cant_float * costo_promedio

                # Insertar Detalle
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
                    unidad, cod, cant_float, costo_promedio,
                    unidad, cant_float
                ))

                # Actualizar Stock por Bodega y valor en dinero
                cursor_erp2.execute("""
                    UPDATE sysadm.IN_PRODUCTOS_X_BOD
                    SET UNIDADES_DISPONIBL = UNIDADES_DISPONIBL - ?,
                        MONTO_TOTAL = MONTO_TOTAL - ?
                    WHERE COD_PRODUCTO = ? AND COD_BODEGA = ?
                """, (cant_float, costo_movimiento, cod, cod_bodega))

                # Actualizar Stock MÃ³dulo General
                cursor_erp2.execute("""
                    UPDATE sysadm.IN_PRODUCTOS
                    SET UNIDADES_DISPONIBL = UNIDADES_DISPONIBL - ?
                    WHERE COD_PRODUCTO = ?
                """, (cant_float, cod))

                # Actualizar HistÃ³rico PeriÃ³dico Mensual
                cursor_erp2.execute("""
                    UPDATE sysadm.in_productos_x_mes
                    SET movimiento_salida = movimiento_salida + ?,
                        monto_salida = monto_salida + ?
                    WHERE NUM_EMPRESA = 1
                      AND COD_BODEGA = ?
                      AND COD_PRODUCTO = ?
                      AND fecha_referencia = DATEADD(d, -1, DATEADD(m, DATEDIFF(m, 0, GETDATE()) + 1, 0))
                """, (cant_float, costo_movimiento, cod_bodega, cod))
                
                # Validar existencia del registro mensual
                if cursor_erp2.rowcount == 0:
                    raise ValueError(f"No se ha inicializado el registro mensual para {cod} en bodega {cod_bodega}.")

            # === 5. Confirmar Toda La TransacciÃ³n ===
            conn_erp2.commit()
            flash(f"Solicitud generada exitosamente. Documento #{num_documento} â€” Correlativo {correlativo}.", "success")
            return redirect(url_for('sistemas.ver_sistema', id=sistema_id))

        except Exception as e:
            conn_erp2.rollback()
            print(f"Error ERP: {e}")
            flash(f"Error al procesar la solicitud: {e}", "error")
        finally:
            conn_erp2.close()

    return render_template('sistemas/solicitar_productos.html',
                           sistema=sistema,
                           bodegas=bodegas,
                           empleados=empleados)


# -----------------------------------------------
# 10. API â€” Buscar producto por cÃ³digo y bodega
# -----------------------------------------------
@sistemas_bp.route('/api/producto')
@login_required
def api_producto():
    """
    Endpoint AJAX para buscar un producto del ERP por cÃ³digo y bodega.
    Retorna JSON con: nombre, precio, existencias y unidad de medida.
    """
    codigo = request.args.get('codigo', '').strip().upper()
    bodega = request.args.get('bodega', '').strip()

    if not codigo or not bodega:
        return jsonify({'error': 'CÃ³digo y bodega son requeridos'}), 400

    conn_erp = get_erp_connection()
    cursor_erp = conn_erp.cursor()
    try:
        cursor_erp.execute("""
            SELECT
                a.COD_PRODUCTO,
                RTRIM(a.NOMBRE_PRODUCTO)  AS nombre,
                b.PRECIO_UNITARIO,
                RTRIM(a.UNIDAD_MEDIDA)    AS unidad_medida,
                xb.UNIDADES_DISPONIBL
            FROM sysadm.IN_PRODUCTOS         AS a
            JOIN sysadm.IN_PRECIOS_TIPOCLT   AS b  ON a.COD_PRODUCTO = b.COD_PRODUCTO
            JOIN sysadm.IN_PRODUCTOS_X_BOD   AS xb ON a.COD_PRODUCTO = xb.COD_PRODUCTO
            WHERE a.COD_TIPO_PRODUCTO    = 1
              AND a.COD_CLASIFICACION NOT LIKE '1.1.1.%'
              AND a.COD_PRODUCTO        LIKE '%-%'
              AND a.COD_PRODUCTO    NOT LIKE '%p%'
              AND b.TIPO_CLIENTE        = 10
              AND a.COD_PRODUCTO        = ?
              AND xb.COD_BODEGA         = ?
        """, (codigo, bodega))

        row = cursor_erp.fetchone()
        if not row:
            return jsonify({'error': 'Producto no encontrado en esta bodega'}), 404

        return jsonify({
            'codigo':        row[0],
            'nombre':        row[1],
            'precio':        float(row[2]),
            'unidad_medida': row[3].strip() if row[3] else '',
            'existencias':   float(row[4]) if row[4] is not None else 0
        })

    except Exception as e:
        print(f"Error en api_producto: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500
    finally:
        conn_erp.close()

