"""
MÃ³dulo: proyectos
DescripciÃ³n: CRUD completo de proyectos.
Incluye listado con bÃºsqueda, creaciÃ³n con cÃ³digo auto-generado,
detalle con sistemas/materiales/personal, ediciÃ³n, eliminaciÃ³n
y cambio rÃ¡pido de estado.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils import get_db_connection, get_erp_connection
from app.decorators import requiere_rol
import re

# -----------------------------------------------
# Blueprint: proyectos â€” Prefijo: /proyectos
# -----------------------------------------------
proyectos_bp = Blueprint('proyectos', __name__, url_prefix='/proyectos')


# -----------------------------------------------
# 1. LISTADO DE PROYECTOS
# -----------------------------------------------
@proyectos_bp.route('/mis-proyectos')
@login_required
def mis_proyectos():
    """Lista los proyectos del usuario (agente ve solo los suyos, admin/supervisor ven todos)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    busqueda = request.args.get('q', '').strip()
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()
    estado = request.args.get('estado', '').strip()

    try:
        if current_user.rol in ['administrador', 'supervisor']:
            # Admin y supervisor ven TODOS los proyectos
            query = """
                SELECT p.id, p.codigo, p.cliente_nombre, p.estado, p.fecha_creacion, 
                       u.nombre as agente_nombre, u.username
                FROM proyectos p
                LEFT JOIN usuarios u ON p.agente_id = u.id
                WHERE 1=1
            """
            params = []
            if busqueda:
                query += " AND (p.codigo LIKE ? OR p.cliente_nombre LIKE ?)"
                params.extend([f'%{busqueda}%', f'%{busqueda}%'])
            if estado:
                query += " AND p.estado = ?"
                params.append(estado)
            if fecha_desde:
                query += " AND CAST(p.fecha_creacion AS DATE) >= ?"
                params.append(fecha_desde)
            if fecha_hasta:
                query += " AND CAST(p.fecha_creacion AS DATE) <= ?"
                params.append(fecha_hasta)
            query += " ORDER BY p.fecha_creacion DESC"
            cursor.execute(query, params)
        else:
            # El agente solo ve sus propios proyectos
            query = """
                SELECT id, codigo, cliente_nombre, estado, fecha_creacion
                FROM proyectos
                WHERE agente_id = ?
            """
            params = [current_user.id]
            if busqueda:
                query += " AND (codigo LIKE ? OR cliente_nombre LIKE ?)"
                params.extend([f'%{busqueda}%', f'%{busqueda}%'])
            if estado:
                query += " AND estado = ?"
                params.append(estado)
            if fecha_desde:
                query += " AND CAST(fecha_creacion AS DATE) >= ?"
                params.append(fecha_desde)
            if fecha_hasta:
                query += " AND CAST(fecha_creacion AS DATE) <= ?"
                params.append(fecha_hasta)
            query += " ORDER BY fecha_creacion DESC"
            cursor.execute(query, params)

        columnas = [column[0] for column in cursor.description]
        proyectos = [dict(zip(columnas, row)) for row in cursor.fetchall()]

    except Exception as e:
        print(f"Error al cargar proyectos: {e}")
        flash("Error al cargar la lista de proyectos.", "error")
        proyectos = []
    finally:
        conn.close()

    return render_template(
        'proyectos/listado_proyectos.html',
        proyectos=proyectos,
        busqueda=busqueda,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado=estado
    )


# -----------------------------------------------
# API: BUSCAR CLIENTE EN ERP
# -----------------------------------------------
@proyectos_bp.route('/buscar-cliente-erp')
@login_required
def buscar_cliente_erp():
    """Endpoint AJAX: consulta un cliente en el ERP por cÃ³digo y devuelve sus datos."""
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({'error': 'Debe ingresar un cÃ³digo de cliente.'}), 400

    try:
        conn_erp = get_erp_connection()
        cursor_erp = conn_erp.cursor()
        cursor_erp.execute("""
            SELECT COD_CLIENTE,
                   RTRIM(NOMBRE_CLIENTE)       AS NOMBRE_CLIENTE,
                   RTRIM(DIRECCION)            AS DIRECCION,
                   TEL_ENVIO                   AS TELEFONO,
                   RTRIM(NIT_CLIENTE)          AS NIT_CLIENTE,
                   RTRIM(NRC_CLIENTE)          AS NRC_CLIENTE,
                   RTRIM(SALUDO_CONTACTO)      AS CORREO_CLIENTE,
                   RTRIM(NOMBRE_REP_LEGAL)     AS UBICACION_GEOGRAFICA
            FROM sysadm.CLIENTES
            WHERE COD_CLIENTE = ?
        """, (int(codigo),))
        row = cursor_erp.fetchone()
        conn_erp.close()

        if not row:
            return jsonify({'error': f'No se encontrÃ³ ningÃºn cliente con el cÃ³digo {codigo}.'}), 404

        cols = [col[0] for col in cursor_erp.description]
        cliente = dict(zip(cols, row))
        return jsonify({'cliente': cliente})

    except (ValueError, TypeError):
        return jsonify({'error': 'El cÃ³digo de cliente debe ser un nÃºmero entero.'}), 400
    except Exception as e:
        print(f"Error consultando cliente ERP: {e}")
        return jsonify({'error': 'Error al consultar el cliente. Verifica la conexion.'}), 500


# -----------------------------------------------
# 2. CREAR PROYECTO
# -----------------------------------------------
@proyectos_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def crear_proyecto():
    """Formulario de creaciÃ³n con cÃ³digo auto-generado (PRO-00001). El cliente se busca por cÃ³digo ERP."""
    if request.method == 'POST':
        cod_cliente       = request.form.get('cod_cliente', '') or None
        cliente_nombre    = request.form.get('cliente_nombre', '')
        cliente_dui_nit   = request.form.get('cliente_dui_nit', '')
        cliente_nrc       = request.form.get('cliente_nrc', '')
        cliente_telefono  = request.form.get('cliente_telefono', '')
        cliente_email     = request.form.get('cliente_email', '')
        cliente_direccion = request.form.get('cliente_direccion', '')
        cliente_ubicacion = request.form.get('cliente_ubicacion', '')
        estado            = request.form.get('estado', 'pendiente')
        agente_id         = request.form.get('agente_id')

        if not cliente_nombre:
            flash("Debe buscar y seleccionar un cliente antes de guardar.", "error")
            return redirect(url_for('proyectos.crear_proyecto'))

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Generar cÃ³digo auto-incremental (PRO-00015)
            cursor.execute("SELECT ISNULL(MAX(id), 0) FROM proyectos")
            ultimo_id = cursor.fetchone()[0]
            nuevo_codigo = f"PRO-{(ultimo_id + 1):05d}"

            cursor.execute("""
                INSERT INTO proyectos 
                (codigo, cod_cliente, cliente_nombre, cliente_dui_nit, cliente_nrc,
                 cliente_telefono, cliente_email, cliente_direccion, cliente_ubicacion,
                 estado, fecha_creacion, agente_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), ?)
            """, (
                nuevo_codigo, cod_cliente, cliente_nombre, cliente_dui_nit, cliente_nrc,
                cliente_telefono, cliente_email, cliente_direccion, cliente_ubicacion,
                estado, agente_id
            ))

            conn.commit()
            flash(f"Proyecto {nuevo_codigo} creado con Ã©xito.", "success")
            return redirect(url_for('proyectos.mis_proyectos'))

        except Exception as e:
            conn.rollback()
            print(f"Error al guardar: {e}")
            flash("Error de base de datos al intentar guardar el proyecto.", "error")
        finally:
            conn.close()

    # Para llenar el select de agentes
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, nombre, username FROM usuarios WHERE rol = 'agente' ORDER BY nombre ASC")
        col_agentes = [col[0] for col in cursor.description]
        agentes = [dict(zip(col_agentes, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error al obtener agentes: {e}")
        agentes = []
    finally:
        conn.close()

    return render_template('proyectos/crear_proyecto.html', agentes=agentes)


# -----------------------------------------------
# 3. VER DETALLE DEL PROYECTO
# -----------------------------------------------
@proyectos_bp.route('/<int:pk>/')
@login_required
def ver_proyecto(pk):
    """Muestra el detalle completo del proyecto: cliente, sistemas, materiales y totales."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Datos del proyecto con JOIN al agente
        cursor.execute("""
            SELECT 
                p.id, p.codigo, p.cod_cliente, p.cliente_nombre, p.cliente_dui_nit, p.cliente_nrc, 
                p.cliente_telefono, p.cliente_email, p.cliente_direccion, 
                p.cliente_ubicacion, p.estado, p.fecha_creacion,
                CONVERT(VARCHAR, p.fecha_creacion, 103) as fecha_formateada,
                p.agente_id, u.nombre as agente_nombre, u.username
            FROM proyectos p
            LEFT JOIN usuarios u ON p.agente_id = u.id
            WHERE p.id = ?
        """, (pk,))
        row = cursor.fetchone()

        if not row:
            return "Proyecto no encontrado", 404

        columnas = [column[0] for column in cursor.description]
        proyecto = dict(zip(columnas, row))

        # Seguridad: agente solo ve sus propios proyectos
        if current_user.rol == 'agente' and proyecto.get('agente_id') != current_user.id:
            flash("No tienes permiso para ver este proyecto.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        # Productos/gastos se manejan en la nueva logica de inventario.
        materiales = []

        # Total de personal (sumado desde asignaciones en sistemas)
        cursor.execute("""
            SELECT ISNULL(SUM(dap.costo_total), 0)
            FROM detalle_asignacion_pintor dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            WHERE a.proyecto_id = ? AND a.tipo = 'pintor' AND a.estado <> 'anulada'
        """, (pk,))
        total_personal = float(cursor.fetchone()[0] or 0)

        personal = []
        notas = []

        # Sistemas del proyecto
        cursor.execute("""
            SELECT id, sistema_codigo, sistema_nombre, monto_inicial, metros_cuadrados_iniciales,
                   hombres_por_dia_iniciales, producto_terminado_inicial, costo_servicio_m2_inicial,
                   estado, CONVERT(VARCHAR, fecha_creacion, 103) as fecha_creacion
            FROM sistemas
            WHERE proyecto_id = ?
            ORDER BY id DESC
        """, (pk,))
        col_sist = [column[0] for column in cursor.description]
        sistemas = [dict(zip(col_sist, row)) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT ISNULL(SUM(monto), 0)
            FROM gastos
            WHERE proyecto_id = ?
        """, (pk,))
        total_materiales = float(cursor.fetchone()[0] or 0)
        todos_sistemas_completados = all(s['estado'] == 'completado' for s in sistemas) if sistemas else False

    except Exception as e:
        print(f"Error al cargar detalle: {e}")
        flash("Error al cargar el proyecto.", "error")
        return redirect(url_for('proyectos.mis_proyectos'))
    finally:
        conn.close()

    return render_template('proyectos/ver_proyecto.html',
                           proyecto=proyecto,
                           materiales=materiales,
                           personal=personal,
                           sistemas=sistemas,
                           notas=notas,
                           total_materiales=total_materiales,
                           total_personal=total_personal,
                           todos_sistemas_completados=todos_sistemas_completados)


# -----------------------------------------------
# 4. EDITAR PROYECTO
# -----------------------------------------------
@proyectos_bp.route('/<int:pk>/editar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def editar_proyecto(pk):
    """Formulario de ediciÃ³n de los datos del proyecto."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM proyectos WHERE id = ?", (pk,))
        row = cursor.fetchone()

        if not row:
            flash("El proyecto no existe.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        columnas = [column[0] for column in cursor.description]
        proyecto = dict(zip(columnas, row))

        # Seguridad: agente solo edita sus propios proyectos
        if current_user.rol == 'agente' and proyecto['agente_id'] != current_user.id:
            flash("No tienes permiso para editar este proyecto.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        if request.method == 'POST':
            cod_cliente       = request.form.get('cod_cliente', '') or None
            cliente_nombre    = request.form.get('cliente_nombre', '')
            cliente_dui_nit   = request.form.get('cliente_dui_nit', '')
            cliente_nrc       = request.form.get('cliente_nrc', '')
            cliente_telefono  = request.form.get('cliente_telefono', '')
            cliente_email     = request.form.get('cliente_email', '')
            cliente_direccion = request.form.get('cliente_direccion', '')
            cliente_ubicacion = request.form.get('cliente_ubicacion', '')
            estado            = request.form.get('estado')
            agente_id         = request.form.get('agente_id')

            if not cliente_nombre:
                flash("Debe buscar y seleccionar un cliente antes de guardar.", "error")
                return redirect(url_for('proyectos.editar_proyecto', pk=pk))

            cursor.execute("""
                UPDATE proyectos 
                SET cod_cliente=?, cliente_nombre=?, cliente_dui_nit=?, cliente_nrc=?,
                    cliente_telefono=?, cliente_email=?, cliente_direccion=?, cliente_ubicacion=?,
                    estado=?, agente_id=?
                WHERE id=?
            """, (
                cod_cliente, cliente_nombre, cliente_dui_nit, cliente_nrc,
                cliente_telefono, cliente_email, cliente_direccion, cliente_ubicacion,
                estado, agente_id, pk
            ))
            conn.commit()
            flash("Proyecto actualizado correctamente.", "success")
            return redirect(url_for('proyectos.ver_proyecto', pk=pk))

    except Exception as e:
        print(f"Error al editar: {e}")
        flash("Error al intentar editar el proyecto.", "error")
        if request.method == 'POST':
            conn.rollback()

    # Calcular totales para el template
    try:
        cursor.execute("""
            SELECT ISNULL(SUM(monto), 0)
            FROM gastos
            WHERE proyecto_id = ?
        """, (pk,))
        total_materiales = float(cursor.fetchone()[0] or 0)

        # Sumar personal desde asignaciones
        cursor.execute("""
            SELECT ISNULL(SUM(dap.costo_total), 0)
            FROM detalle_asignacion_pintor dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            WHERE a.proyecto_id = ? AND a.tipo = 'pintor' AND a.estado <> 'anulada'
        """, (pk,))
        total_personal = float(cursor.fetchone()[0])
    except Exception as e:
        print(f"Error al calcular totales: {e}")
        total_materiales = 0.0
        total_personal = 0.0
    finally:
        conn.close()

    # Para llenar el select de agentes
    conn_agentes = get_db_connection()
    cursor_agentes = conn_agentes.cursor()
    try:
        cursor_agentes.execute("SELECT id, nombre, username FROM usuarios WHERE rol = 'agente' ORDER BY nombre ASC")
        col_agentes = [col[0] for col in cursor_agentes.description]
        agentes = [dict(zip(col_agentes, row)) for row in cursor_agentes.fetchall()]
    except Exception as e:
        print(f"Error al obtener agentes: {e}")
        agentes = []
    finally:
        conn_agentes.close()

    return render_template('proyectos/editar_proyecto.html', 
                           proyecto=proyecto, 
                           total_personal=total_personal, 
                           total_materiales=total_materiales,
                           agentes=agentes)


# -----------------------------------------------
# 5. ELIMINAR PROYECTO
# -----------------------------------------------
@proyectos_bp.route('/<int:pk>/eliminar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def eliminar_proyecto(pk):
    """ConfirmaciÃ³n y eliminaciÃ³n de un proyecto (cascade en BD)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM proyectos WHERE id = ?", (pk,))
        row = cursor.fetchone()

        if not row:
            flash("El proyecto no existe.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        columnas = [column[0] for column in cursor.description]
        proyecto = dict(zip(columnas, row))

        # Seguridad: agente solo elimina sus propios proyectos
        if current_user.rol == 'agente' and proyecto['agente_id'] != current_user.id:
            flash("No tienes permiso para eliminar este proyecto.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        if request.method == 'POST':
            cursor.execute("DELETE FROM movimientos WHERE proyecto_id = ?", (pk,))
            cursor.execute("DELETE FROM gastos WHERE proyecto_id = ?", (pk,))
            cursor.execute("""
                DELETE dap
                FROM detalle_asignacion_producto dap
                INNER JOIN asignaciones a ON dap.asignacion_id = a.id
                WHERE a.proyecto_id = ?
            """, (pk,))
            cursor.execute("""
                DELETE dap
                FROM detalle_asignacion_pintor dap
                INNER JOIN asignaciones a ON dap.asignacion_id = a.id
                WHERE a.proyecto_id = ?
            """, (pk,))
            cursor.execute("""
                DELETE dae
                FROM detalle_asignacion_equipo dae
                INNER JOIN asignaciones a ON dae.asignacion_id = a.id
                WHERE a.proyecto_id = ?
            """, (pk,))
            cursor.execute("DELETE FROM asignaciones WHERE proyecto_id = ?", (pk,))
            cursor.execute("DELETE FROM proyectos WHERE id = ?", (pk,))
            conn.commit()
            flash("Proyecto eliminado definitivamente.", "success")
            return redirect(url_for('proyectos.mis_proyectos'))

    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar: {e}")
        flash("Error al eliminar el proyecto.", "error")

    # Calcular totales y conteos para la confirmaciÃ³n
    try:
        cursor.execute("""
            SELECT ISNULL(SUM(monto), 0), COUNT(id)
            FROM gastos
            WHERE proyecto_id = ?
        """, (pk,))
        mat_data = cursor.fetchone()
        total_materiales = float(mat_data[0])
        total_materiales_count = int(mat_data[1])

        # Contar personal desde asignaciones
        cursor.execute("""
            SELECT ISNULL(SUM(dap.costo_total), 0), COUNT(dap.id)
            FROM detalle_asignacion_pintor dap
            INNER JOIN asignaciones a ON dap.asignacion_id = a.id
            WHERE a.proyecto_id = ? AND a.tipo = 'pintor' AND a.estado <> 'anulada'
        """, (pk,))
        pers_data = cursor.fetchone()
        total_personal = float(pers_data[0])
        total_personal_count = int(pers_data[1])

        total_notas_count = 0  # Desactivado por ahora
    except Exception as e:
        print(f"Error al calcular totales para eliminar: {e}")
        total_materiales = total_personal = 0.0
        total_materiales_count = total_personal_count = total_notas_count = 0
    finally:
        conn.close()

    return render_template('proyectos/eliminar_proyecto.html',
                           proyecto=proyecto,
                           total_materiales=total_materiales,
                           total_personal=total_personal,
                           total_materiales_count=total_materiales_count,
                           total_personal_count=total_personal_count,
                           total_notas_count=total_notas_count)


# -----------------------------------------------
# 6. CAMBIAR ESTADO RÃPIDO
# -----------------------------------------------
@proyectos_bp.route('/<int:pk>/cambiar-estado', methods=['POST'])
@login_required
@requiere_rol('administrador')
def cambiar_estado(pk):
    """Cicla el estado del proyecto: pendiente â†’ activo â†’ completado â†’ activo."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, estado, agente_id FROM proyectos WHERE id = ?", (pk,))
        proyecto = cursor.fetchone()

        if not proyecto:
            flash("Proyecto no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        # Seguridad
        if current_user.rol == 'agente' and proyecto.agente_id != current_user.id:
            flash("No tienes permisos para modificar este proyecto.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        # Ciclo de estados
        nuevo_estado = proyecto.estado
        msg = ""

        if proyecto.estado == 'pendiente':
            nuevo_estado = 'activo'
            msg = "Proyecto activado correctamente."
        elif proyecto.estado == 'activo':
            nuevo_estado = 'completado'
            msg = "Proyecto completado correctamente."
        elif proyecto.estado == 'completado':
            nuevo_estado = 'activo'
            msg = "â„¹ Proyecto devuelto a activo."

        if nuevo_estado != proyecto.estado:
            cursor.execute("UPDATE proyectos SET estado = ? WHERE id = ?", (nuevo_estado, pk))
            conn.commit()
            flash(msg, "success")

    except Exception as e:
        conn.rollback()
        print(f"Error al cambiar estado: {e}")
        flash("Error al actualizar el estado.", "error")
    finally:
        conn.close()

    return redirect(url_for('proyectos.ver_proyecto', pk=pk))


# -----------------------------------------------
# 7. EXPORTAR A PDF
# -----------------------------------------------
@proyectos_bp.route('/<int:pk>/pdf')
@login_required
def generar_pdf_proyecto(pk):
    """Genera un reporte PDF y lo previsualiza en el navegador."""
    from flask import current_app, send_file
    from app.reports.proyecto import generar_pdf_proyecto_doc
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. Proyecto info
        cursor.execute("""
            SELECT p.id, p.codigo, p.agente_id, p.cod_cliente, p.cliente_nombre, p.cliente_dui_nit,
                   p.cliente_telefono, p.cliente_email, p.cliente_direccion, 
                   p.estado, CONVERT(VARCHAR, p.fecha_creacion, 103) as fecha_formateada,
                   u.nombre as agente_nombre
            FROM proyectos p
            LEFT JOIN usuarios u ON p.agente_id = u.id
            WHERE p.id = ?
        """, (pk,))
        row = cursor.fetchone()
        if not row:
            flash("Proyecto no encontrado.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))
        proyecto = dict(zip([c[0] for c in cursor.description], row))

        # Seguridad: agente solo ve sus propios proyectos
        if current_user.rol == 'agente' and proyecto.get('agente_id') != current_user.id:
            flash("No tienes permiso para generar pdf de este proyecto.", "error")
            return redirect(url_for('proyectos.mis_proyectos'))

        # 2. Sistemas
        cursor.execute("SELECT * FROM sistemas WHERE proyecto_id = ? ORDER BY id ASC", (pk,))
        sistemas = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]

        # Validacion Backend
        if not sistemas or not all(s['estado'] == 'completado' for s in sistemas):
            flash("No se puede generar el PDF hasta que todos los sistemas estÃ©n finalizados.", "error")
            return redirect(url_for('proyectos.ver_proyecto', pk=pk))

        # 3. Datos de cada sistema
        materiales_por_sistema = {}
        personal_por_sistema = {}
        erp_por_sistema = {}

        try:
            from app.utils import get_erp_connection
            conn_erp = get_erp_connection()
            cursor_erp = conn_erp.cursor()
            has_erp = True
        except Exception:
            has_erp = False

        for sis in sistemas:
            sid = sis['id']
            cursor.execute("""
                SELECT g.descripcion, g.monto as costo_material,
                       c.nombre as material_nombre,
                       CONVERT(VARCHAR, g.fecha_gasto, 103) as fecha_formateada
                FROM gastos g
                INNER JOIN categorias_gasto c ON g.categoria_id = c.id
                WHERE g.sistema_id = ?
            """, (sid,))
            materiales_por_sistema[sid] = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT dap.*, t.nombre as pintor_nombre
                FROM detalle_asignacion_pintor dap
                INNER JOIN asignaciones a ON dap.asignacion_id = a.id
                INNER JOIN pintores t ON dap.pintor_id = t.id
                WHERE a.sistema_id = ? AND a.tipo = 'pintor' AND a.estado <> 'anulada'
            """, (sid,))
            personal_por_sistema[sid] = [dict(zip([c[0] for c in cursor.description], r)) for r in cursor.fetchall()]

            erp_por_sistema[sid] = []
            if has_erp:
                desc_busqueda = f"ID:{sis['id']} |%"
                cursor_erp.execute("""
                    SELECT 
                        d.NUM_DOCUMENTO as num_doc,
                        CONVERT(VARCHAR, d.FECHA_DOCUMENTO, 103) as fecha, 
                        det.COD_PRODUCTO as codigo, 
                        RTRIM(p.NOMBRE_PRODUCTO) as nombre,
                        RTRIM(det.UNIDAD_MEDIDA) as um, 
                        det.CANTIDAD as cantidad,
                        p.costo_promedio,
                        pr.PRECIO_UNITARIO as precio_unitario
                    FROM sysadm.IN_DOCUMENTO d
                    JOIN sysadm.IN_DET_DOCUMENTO det
                        ON d.NUM_EMPRESA = det.NUM_EMPRESA
                        AND d.TIPO_DOCUMENTO = det.TIPO_DOCUMENTO
                        AND d.CORRELATIVO = det.CORRELATIVO
                    JOIN sysadm.IN_PRODUCTOS p
                        ON det.COD_PRODUCTO = p.COD_PRODUCTO
                    LEFT JOIN sysadm.IN_PRECIOS_TIPOCLT pr 
                        ON p.COD_PRODUCTO = pr.COD_PRODUCTO AND pr.TIPO_CLIENTE = 10
                    WHERE d.DESCRIPCION LIKE ? AND d.STATUS_DOCUMENTO = 'R'
                    ORDER BY d.FECHA_DOCUMENTO DESC, d.NUM_DOCUMENTO DESC
                """, (desc_busqueda,))
                erp_por_sistema[sid] = [dict(zip([c[0] for c in cursor_erp.description], r)) for r in cursor_erp.fetchall()]

        if has_erp:
            conn_erp.close()

        pdf_buffer = generar_pdf_proyecto_doc(
            proyecto, 
            sistemas, 
            personal_por_sistema, 
            materiales_por_sistema, 
            erp_por_sistema,
            current_app.static_folder,
            mostrar_costos=getattr(current_user, 'puede_ver_costos', False)
        )

        return send_file(
            pdf_buffer,
            as_attachment=False, 
            mimetype='application/pdf',
            download_name=f"Reporte_Proyecto_{proyecto['codigo']}.pdf"
        )

    except Exception as e:
        print(f"Error generando PDF: {e}")
        flash("Error interno generando el reporte PDF.", "error")
        return redirect(url_for('proyectos.ver_proyecto', pk=pk))
    finally:
        conn.close()

