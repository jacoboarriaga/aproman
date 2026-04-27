"""
Módulo: auth
Descripción: Controlador de autenticación (login / logout).
Maneja el inicio y cierre de sesión usando Flask-Login y contraseñas
encriptadas con el formato PBKDF2 de Django.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from passlib.hash import django_pbkdf2_sha256
from app.utils import get_db_connection
from app.models import Usuario

# -----------------------------------------------
# Blueprint: auth
# -----------------------------------------------
auth_bp = Blueprint('auth', __name__)


# -----------------------------------------------
# 1. LOGIN
# -----------------------------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Muestra el formulario de login y autentica al usuario."""
    # Si ya está logueado, mandarlo a su dashboard correspondiente
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, username, password, rol, nombre, is_active, puede_ver_costos 
                FROM usuarios 
                WHERE username = ?
            """, (username,))
            user_row = cursor.fetchone()

            if user_row and user_row.is_active:
                # Verificar la contraseña encriptada (formato Django PBKDF2)
                if django_pbkdf2_sha256.verify(password, user_row.password):
                    usuario_obj = Usuario(
                        id=user_row.id,
                        username=user_row.username,
                        rol=user_row.rol,
                        nombre=user_row.nombre,
                        puede_ver_costos=user_row.puede_ver_costos
                    )
                    login_user(usuario_obj)

                    flash(f'¡Bienvenido {usuario_obj.get_full_name()}!', 'success')
                    return _redirect_by_role(usuario_obj)

            flash('Usuario o contraseña incorrectos', 'error')

        except Exception as e:
            flash(f'Error de conexión: {str(e)}', 'error')
        finally:
            if 'conn' in locals():
                conn.close()

    return render_template('auth/login.html')


# -----------------------------------------------
# 2. LOGOUT
# -----------------------------------------------
@auth_bp.route('/logout')
def logout():
    """Cierra la sesión del usuario y redirige al login."""
    logout_user()
    return redirect(url_for('auth.login'))


# -----------------------------------------------
# FUNCIONES AUXILIARES
# -----------------------------------------------
def _redirect_by_role(user):
    """Redirige al dashboard correspondiente según el rol del usuario."""
    if user.rol == 'agente':
        return redirect(url_for('usuarios.dashboard_agente'))
    elif user.rol == 'administrador':
        return redirect(url_for('usuarios.dashboard_administrador'))
    return redirect(url_for('auth.login'))
