"""
Módulo: __init__ (App Factory)
Descripción: Configuración central de la aplicación Flask.
Registra blueprints, configura Flask-Login y define la ruta raíz.
"""

import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from dotenv import load_dotenv

# Gestor de sesiones (se inicializa antes de crear la app)
login_manager = LoginManager()


def create_app():
    """Crea y configura la instancia de la aplicación Flask."""
    load_dotenv()

    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-aproman')

    # Configurar Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'error'

    # -----------------------------------------------
    # Registro de Blueprints
    # -----------------------------------------------
    from .controllers.auth import auth_bp
    app.register_blueprint(auth_bp)

    from .controllers.usuarios import usuarios_bp
    app.register_blueprint(usuarios_bp)

    from .controllers.proyectos import proyectos_bp
    app.register_blueprint(proyectos_bp)

    from .controllers.inventario import inventario_bp
    app.register_blueprint(inventario_bp)

    from .controllers.solicitudes import solicitudes_bp
    app.register_blueprint(solicitudes_bp)

    from .controllers.materiales import materiales_bp
    app.register_blueprint(materiales_bp)

    from .controllers.pintores import pintores_bp
    app.register_blueprint(pintores_bp)

    from .controllers.sistemas import sistemas_bp
    app.register_blueprint(sistemas_bp)

    # Manejadores de errores HTTP
    from .controllers.errors import register_error_handlers
    register_error_handlers(app)

    # -----------------------------------------------
    # Carga de sesión de usuario
    # -----------------------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        """Recupera el usuario de la BD a partir de su ID de sesión."""
        from app.utils import get_db_connection
        from app.models import Usuario

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, rol, nombre, puede_ver_costos FROM usuarios WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return Usuario(
                    id=row.id,
                    username=row.username,
                    rol=row.rol,
                    nombre=row.nombre,
                    puede_ver_costos=row.puede_ver_costos
                )
        except Exception as e:
            print(f"Error cargando sesión: {e}")

        return None

    # Ruta raíz — redirige al login
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # Rutas para PWA (Service Worker y Manifest)
    @app.route('/sw.js')
    def serve_sw():
        return app.send_static_file('sw.js')

    @app.route('/manifest.json')
    def serve_manifest():
        return app.send_static_file('manifest.json')

    return app
