"""
Modulo: pintores
Descripcion: CRUD del catalogo global de pintores.
Permite listar, crear, editar y eliminar pintores que luego
se asignan a los sistemas de cada proyecto.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.utils import get_db_connection
from app.decorators import requiere_rol


pintores_bp = Blueprint('pintores', __name__, url_prefix='/pintores')


@pintores_bp.route('/')
@login_required
@requiere_rol('administrador')
def listado_pintores():
    """Muestra el catalogo completo de pintores ordenados por nombre."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                nombre,
                CONVERT(VARCHAR, fecha_registro, 103) as fecha_formateada
            FROM pintores
            ORDER BY nombre ASC
        """)
        columnas = [column[0] for column in cursor.description]
        pintores = [dict(zip(columnas, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error al listar pintores: {e}")
        pintores = []
    finally:
        conn.close()

    return render_template('pintores/listado_pintores.html', pintores=pintores)


@pintores_bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def crear_pintor():
    """Formulario para registrar un nuevo pintor en el catalogo."""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()

        if not nombre:
            flash("El nombre es obligatorio.", "error")
            return redirect(url_for('pintores.crear_pintor'))

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO pintores (nombre, fecha_registro)
                VALUES (?, GETDATE())
            """, (nombre,))
            conn.commit()
            flash("Pintor registrado exitosamente.", "success")
            return redirect(url_for('pintores.listado_pintores'))
        except Exception as e:
            conn.rollback()
            print(f"Error al crear pintor: {e}")
            flash("Error al registrar el pintor.", "error")
        finally:
            conn.close()

    return render_template('pintores/crear_pintor.html')


@pintores_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def editar_pintor(id):
    """Formulario para editar el nombre de un pintor existente."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, nombre FROM pintores WHERE id = ?", (id,))
        row = cursor.fetchone()

        if not row:
            flash("Pintor no encontrado.", "error")
            return redirect(url_for('pintores.listado_pintores'))

        pintor = {'id': row[0], 'nombre': row[1]}

        if request.method == 'POST':
            nuevo_nombre = request.form.get('nombre', '').strip()
            if not nuevo_nombre:
                flash("El nombre es obligatorio.", "error")
                return render_template('pintores/editar_pintor.html', pintor=pintor)

            cursor.execute("UPDATE pintores SET nombre = ? WHERE id = ?", (nuevo_nombre, id))
            conn.commit()
            flash("Datos actualizados correctamente.", "success")
            return redirect(url_for('pintores.listado_pintores'))
    except Exception as e:
        conn.rollback()
        print(f"Error al editar pintor: {e}")
        flash("Error al actualizar los datos.", "error")
    finally:
        conn.close()

    return render_template('pintores/editar_pintor.html', pintor=pintor)


@pintores_bp.route('/<int:id>/eliminar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def eliminar_pintor(id):
    """Confirmacion y eliminacion de un pintor del catalogo."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, nombre FROM pintores WHERE id = ?", (id,))
        row = cursor.fetchone()

        if not row:
            flash("Pintor no encontrado.", "error")
            return redirect(url_for('pintores.listado_pintores'))

        pintor = {'id': row[0], 'nombre': row[1]}

        if request.method == 'POST':
            cursor.execute("DELETE FROM pintores WHERE id = ?", (id,))
            conn.commit()
            flash("Pintor eliminado del catalogo.", "success")
            return redirect(url_for('pintores.listado_pintores'))
    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar pintor: {e}")
        flash("No se puede eliminar el pintor. Es posible que este asignado a uno o mas sistemas.", "error")
    finally:
        conn.close()

    return render_template('pintores/eliminar_pintor.html', pintor=pintor)
