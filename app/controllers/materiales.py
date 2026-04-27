"""
Módulo: materiales
Descripción: CRUD del catálogo global de materiales.
Permite listar, crear, editar y eliminar materiales que luego
se pueden asignar a proyectos y sistemas.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.utils import get_db_connection
from app.decorators import requiere_rol

# -----------------------------------------------
# Blueprint: materiales — Prefijo: /materiales
# -----------------------------------------------
materiales_bp = Blueprint('materiales', __name__, url_prefix='/materiales')


# -----------------------------------------------
# 1. LISTADO DE MATERIALES
# -----------------------------------------------
@materiales_bp.route('/', methods=['GET'])
@login_required
@requiere_rol('administrador')
def listado_materiales():
    """Muestra el catálogo completo de materiales ordenados por ID descendente."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM materiales ORDER BY id DESC")
        columnas = [column[0] for column in cursor.description]
        materiales = [dict(zip(columnas, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error al obtener catálogo de materiales: {e}")
        materiales = []
        flash("Error al obtener los materiales.", "error")
    finally:
        conn.close()

    return render_template('materiales/listado_materiales.html', materiales=materiales)


# -----------------------------------------------
# 2. CREAR MATERIAL
# -----------------------------------------------
@materiales_bp.route('/agregar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def crear_material():
    """Formulario para registrar un nuevo material en el catálogo."""
    if request.method == 'POST':
        nombre = request.form.get('nombre').strip()

        if not nombre:
            flash("El nombre del material es obligatorio.", "error")
            return redirect(url_for('materiales.crear_material'))

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO materiales (nombre)
                VALUES (?)
            """, (nombre,))
            conn.commit()
            flash("Material registrado exitosamente en el catálogo.", "success")
            return redirect(url_for('materiales.listado_materiales'))
        except Exception as e:
            conn.rollback()
            print(f"Error al crear material: {e}")
            flash("Ocurrió un error al registrar el material.", "error")
        finally:
            conn.close()

    return render_template('materiales/crear_material.html')


# -----------------------------------------------
# 3. EDITAR MATERIAL
# -----------------------------------------------
@materiales_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def editar_material(id):
    """Formulario para editar el nombre de un material existente."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, nombre, fecha_ingreso FROM materiales WHERE id = ?", (id,))
        row = cursor.fetchone()

        if not row:
            flash("Material no encontrado.", "error")
            return redirect(url_for('materiales.listado_materiales'))

        material = {'id': row[0], 'nombre': row[1], 'fecha_ingreso': row[2]}

        if request.method == 'POST':
            nuevo_nombre = request.form.get('nombre').strip()

            if not nuevo_nombre:
                flash("El nombre del material es obligatorio.", "error")
                return render_template('materiales/editar_material.html', material=material)

            cursor.execute("UPDATE materiales SET nombre = ? WHERE id = ?", (nuevo_nombre, id))
            conn.commit()
            flash("Datos del material actualizados correctamente.", "success")
            return redirect(url_for('materiales.listado_materiales'))
    except Exception as e:
        conn.rollback()
        print(f"Error al editar material: {e}")
        flash("Error al actualizar los datos.", "error")
    finally:
        conn.close()

    return render_template('materiales/editar_material.html', material=material)


# -----------------------------------------------
# 4. ELIMINAR MATERIAL
# -----------------------------------------------
@materiales_bp.route('/<int:id>/eliminar', methods=['GET', 'POST'])
@login_required
@requiere_rol('administrador')
def eliminar_material(id):
    """Confirmación y eliminación de un material del catálogo."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, nombre FROM materiales WHERE id = ?", (id,))
        row = cursor.fetchone()

        if not row:
            flash("Material no encontrado.", "error")
            return redirect(url_for('materiales.listado_materiales'))

        material = {'id': row[0], 'nombre': row[1]}

        if request.method == 'POST':
            cursor.execute("DELETE FROM materiales WHERE id = ?", (id,))
            conn.commit()
            flash("Material eliminado exitosamente del catálogo.", "success")
            return redirect(url_for('materiales.listado_materiales'))
    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar material: {e}")
        flash("Ocurrió un error al intentar eliminar el material.", "error")
    finally:
        conn.close()

    return render_template('materiales/eliminar_material.html', material=material)