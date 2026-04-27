"""
MÃ³dulo: usuarios
DescripciÃ³n: Dashboards por rol de usuario.
Cada rol (administrador, agente) tiene su propio dashboard
con estadÃ­sticas y proyectos recientes filtrados segÃºn sus permisos.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from passlib.hash import django_pbkdf2_sha256
from app.decorators import requiere_rol
from app.utils import get_db_connection

# -----------------------------------------------
# Blueprint: usuarios
# -----------------------------------------------
usuarios_bp = Blueprint('usuarios', __name__)


# -----------------------------------------------
# 1. DASHBOARD ADMINISTRADOR
# -----------------------------------------------
@usuarios_bp.route('/dashboard/administrador')
@requiere_rol('administrador')
def dashboard_administrador():
    """Dashboard con estadÃ­sticas globales, ranking de agentes y proyectos recientes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # EstadÃ­sticas generales
        cursor.execute("SELECT COUNT(*) FROM proyectos")
        total_proyectos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE estado = 'pendiente'")
        total_pendientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE estado = 'activo'")
        total_activos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE estado = 'completado'")
        total_completados = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE rol = 'agente'")
        total_agentes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sistemas")
        total_sistemas = cursor.fetchone()[0]

        # Ãšltimos 10 proyectos con datos del agente (sin p.nombre que no existe)
        cursor.execute("""
            SELECT TOP 10 p.id, p.codigo, p.estado,
                   CONVERT(VARCHAR, p.fecha_creacion, 103) as fecha_formateada,
                   u.username, u.nombre as agente_nombre, p.cliente_nombre
            FROM proyectos p
            INNER JOIN usuarios u ON p.agente_id = u.id
            ORDER BY p.fecha_creacion DESC
        """)
        columnas_recientes = [column[0] for column in cursor.description]
        proyectos_recientes = [dict(zip(columnas_recientes, row)) for row in cursor.fetchall()]

        # Ranking de agentes por cantidad de proyectos
        cursor.execute("""
            SELECT TOP 10 u.id, u.username, u.nombre, COUNT(p.id) as total
            FROM usuarios u
            INNER JOIN proyectos p ON u.id = p.agente_id
            WHERE u.rol = 'agente'
            GROUP BY u.id, u.username, u.nombre
            ORDER BY total DESC
        """)
        columnas_ranking = [column[0] for column in cursor.description]
        agentes_ranking = [dict(zip(columnas_ranking, row)) for row in cursor.fetchall()]

    except Exception as e:
        print(f"Error en dashboard admin: {e}")
        total_proyectos = total_pendientes = total_activos = total_completados = total_agentes = total_sistemas = 0
        proyectos_recientes = agentes_ranking = []
    finally:
        conn.close()

    return render_template('dashboards/administrador.html',
                           total_proyectos=total_proyectos,
                           total_pendientes=total_pendientes,
                           total_activos=total_activos,
                           total_completados=total_completados,
                           total_agentes=total_agentes,
                           total_sistemas=total_sistemas,
                           proyectos_recientes=proyectos_recientes,
                           agentes_ranking=agentes_ranking)


# -----------------------------------------------
# 2. DASHBOARD AGENTE
# -----------------------------------------------
@usuarios_bp.route('/dashboard/agente')
@requiere_rol('agente', 'administrador')
def dashboard_agente():
    """Dashboard con estadÃ­sticas filtradas solo para el agente logueado."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # EstadÃ­sticas filtradas por agente
        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE agente_id = ?", (current_user.id,))
        total_proyectos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE agente_id = ? AND estado = 'pendiente'", (current_user.id,))
        total_pendientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE agente_id = ? AND estado = 'activo'", (current_user.id,))
        total_activos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE agente_id = ? AND estado = 'completado'", (current_user.id,))
        total_completados = cursor.fetchone()[0]

        # Proyectos recientes del agente (sin p.nombre que no existe)
        cursor.execute("""
            SELECT TOP 10 id, codigo, estado,
                   CONVERT(VARCHAR, fecha_creacion, 103) as fecha_formateada,
                   cliente_nombre 
            FROM proyectos 
            WHERE agente_id = ? 
            ORDER BY fecha_creacion DESC
        """, (current_user.id,))
        columnas_agente = [column[0] for column in cursor.description]
        proyectos_recientes = [dict(zip(columnas_agente, row)) for row in cursor.fetchall()]

        # Notificaciones (desactivadas por ahora)
        notificaciones_pendientes = 0

    except Exception as e:
        print(f"Error en dashboard agente: {e}")
        total_proyectos = total_pendientes = total_activos = total_completados = notificaciones_pendientes = 0
        proyectos_recientes = []
    finally:
        conn.close()

    return render_template('dashboards/agente.html',
                           total_proyectos=total_proyectos,
                           total_pendientes=total_pendientes,
                           total_activos=total_activos,
                           total_completados=total_completados,
                           proyectos_recientes=proyectos_recientes,
                           notificaciones_pendientes=notificaciones_pendientes)


# -----------------------------------------------
# 3. GESTIÃ“N DE USUARIOS (CRUD) - Solo Admin
# -----------------------------------------------
@usuarios_bp.route('/usuarios')
@requiere_rol('administrador')
def listado_usuarios():
    """Muestra la lista de todos los usuarios del sistema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Obtenemos los usuarios y contamos sus proyectos asignados
        cursor.execute("""
            SELECT u.id, u.username, u.nombre, u.email, u.rol, u.is_active, u.puede_ver_costos,
                   CONVERT(VARCHAR, u.fecha_registro, 103) as fecha_registro,
                   (SELECT COUNT(*) FROM proyectos p WHERE p.agente_id = u.id) as total_proyectos
            FROM usuarios u
            ORDER BY u.nombre ASC
        """)
        columnas = [column[0] for column in cursor.description]
        usuarios = [dict(zip(columnas, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error listando usuarios: {e}")
        usuarios = []
        flash('Error al cargar la lista de usuarios.', 'error')
    finally:
        conn.close()

    return render_template('usuarios/listado_usuarios.html', usuarios=usuarios)


@usuarios_bp.route('/usuarios/crear', methods=['GET', 'POST'])
@requiere_rol('administrador')
def crear_usuario():
    """Muestra el formulario para crear un usuario y lo procesa."""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        rol = request.form.get('rol', 'agente')
        puede_ver_costos = 1 if request.form.get('puede_ver_costos') == '1' else 0
        
        # Validaciones bÃ¡sicas
        if not nombre or not username or not password:
            flash('Por favor completa todos los campos requeridos.', 'warning')
            return redirect(url_for('usuarios.crear_usuario'))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Validar que no exista el username
            cursor.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
            if cursor.fetchone():
                flash('Ese nombre de usuario ya estÃ¡ en uso. Elige otro.', 'error')
                return redirect(url_for('usuarios.crear_usuario'))

            # Encriptar password
            hashed_password = django_pbkdf2_sha256.hash(password)

            cursor.execute("""
                INSERT INTO usuarios (username, password, nombre, email, rol, is_active, puede_ver_costos, fecha_registro)
                VALUES (?, ?, ?, ?, ?, 1, ?, GETDATE())
            """, (username, hashed_password, nombre, email, rol, puede_ver_costos))
            
            conn.commit()
            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('usuarios.listado_usuarios'))
            
        except Exception as e:
            conn.rollback()
            print(f"Error creando usuario: {e}")
            flash('Error interno al crear el usuario.', 'error')
        finally:
            conn.close()

    return render_template('usuarios/crear_usuario.html')


@usuarios_bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@requiere_rol('administrador')
def editar_usuario(id):
    """Muestra y procesa el formulario de ediciÃ³n de un usuario."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Modo POST (procesar form)
        if request.method == 'POST':
            nombre = request.form.get('nombre', '').strip()
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            rol = request.form.get('rol')
            puede_ver_costos = 1 if request.form.get('puede_ver_costos') == '1' else 0

            if not nombre or not username:
                flash('El nombre y el usuario son obligatorios.', 'warning')
                return redirect(url_for('usuarios.editar_usuario', id=id))

            # Verificar colisiÃ³n de username (que el nuevo username no sea de otro)
            cursor.execute("SELECT id FROM usuarios WHERE username = ? AND id != ?", (username, id))
            if cursor.fetchone():
                flash('El nombre de usuario ya estÃ¡ asignado a otra cuenta.', 'error')
                return redirect(url_for('usuarios.editar_usuario', id=id))

            if password:
                # Actualizar incluyendo password
                hashed_password = django_pbkdf2_sha256.hash(password)
                cursor.execute("""
                    UPDATE usuarios 
                    SET username = ?, password = ?, nombre = ?, email = ?, rol = ?, puede_ver_costos = ?
                    WHERE id = ?
                """, (username, hashed_password, nombre, email, rol, puede_ver_costos, id))
            else:
                # Actualizar sin tocar password
                cursor.execute("""
                    UPDATE usuarios 
                    SET username = ?, nombre = ?, email = ?, rol = ?, puede_ver_costos = ?
                    WHERE id = ?
                """, (username, nombre, email, rol, puede_ver_costos, id))
                
            conn.commit()
            flash('Usuario actualizado correctamente.', 'success')
            return redirect(url_for('usuarios.listado_usuarios'))

        # Modo GET (mostrar form)
        cursor.execute("SELECT id, username, nombre, email, rol, is_active, puede_ver_costos FROM usuarios WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            flash('Usuario no encontrado.', 'error')
            return redirect(url_for('usuarios.listado_usuarios'))
            
        columnas = [column[0] for column in cursor.description]
        usuario = dict(zip(columnas, row))
        
        return render_template('usuarios/editar_usuario.html', usuario=usuario)

    except Exception as e:
        if request.method == 'POST':
            conn.rollback()
        print(f"Error gestionando ediciÃ³n de usuario: {e}")
        flash('OcurriÃ³ un error con el usuario.', 'error')
        return redirect(url_for('usuarios.listado_usuarios'))
    finally:
        conn.close()


@usuarios_bp.route('/usuarios/<int:id>/eliminar', methods=['POST'])
@requiere_rol('administrador')
def eliminar_usuario(id):
    """
    Elimina fÃ­sicamente al usuario si no tiene proyectos.
    Si ya tiene proyectos asignados, opta por desactivarlo (soft-delete).
    No permite auto-eliminaciÃ³n.
    """
    if id == current_user.id:
        flash('No puedes eliminar o desactivar tu propia cuenta desde aquÃ­.', 'error')
        return redirect(url_for('usuarios.listado_usuarios'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verificar cuÃ¡ntos proyectos tiene
        cursor.execute("SELECT COUNT(*) FROM proyectos WHERE agente_id = ?", (id,))
        proyectos_count = cursor.fetchone()[0]

        if proyectos_count == 0:
            # EliminaciÃ³n fÃ­sica
            cursor.execute("DELETE FROM usuarios WHERE id = ?", (id,))
            flash('Usuario eliminado permanentemente del sistema.', 'success')
        else:
            # Soft Delete (Desactivar) por seguridad referencial
            cursor.execute("UPDATE usuarios SET is_active = 0 WHERE id = ?", (id,))
            flash(f'El usuario tiene {proyectos_count} proyectos asignados. La cuenta fue desactivada por seguridad histÃ³rica en lugar de eliminada.', 'info')
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error eliminando usuario: {e}")
        flash('Error intentando eliminar el usuario.', 'error')
    finally:
        conn.close()

    return redirect(url_for('usuarios.listado_usuarios'))


@usuarios_bp.route('/usuarios/<int:id>/toggle_estado', methods=['POST'])
@requiere_rol('administrador')
def toggle_estado(id):
    """Ruta rÃ¡pida para reactivar o inhabilitar un usuario (is_active toggle)"""
    if id == current_user.id:
        flash('No puedes desactivar tu propia cuenta.', 'error')
        return redirect(url_for('usuarios.listado_usuarios'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT is_active, nombre FROM usuarios WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row:
            is_active = row.is_active
            nombre_usr = row.nombre
            nuevo_estado = 0 if is_active else 1
            
            cursor.execute("UPDATE usuarios SET is_active = ? WHERE id = ?", (nuevo_estado, id))
            conn.commit()
            
            estado_desc = "activado" if nuevo_estado else "desactivado"
            flash(f'El usuario {nombre_usr} ha sido {estado_desc}.', 'success')
        else:
            flash('Usuario no encontrado', 'error')
            
    except Exception as e:
        conn.rollback()
        print(f"Error en toggle de estado u: {e}")
        flash('Error actualizando el estado.', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('usuarios.listado_usuarios'))

