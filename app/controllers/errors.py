"""
Módulo: errors
Descripción: Manejadores de errores HTTP para la aplicación.
Registra páginas personalizadas para los códigos 403, 404 y 500.
"""

from flask import render_template


def register_error_handlers(app):
    """Registra los manejadores de errores HTTP en la aplicación Flask."""

    @app.errorhandler(403)
    def forbidden(e):
        """Acceso denegado — el usuario no tiene permisos."""
        return render_template('errores/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        """Página no encontrada."""
        return render_template('errores/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        """Error interno del servidor."""
        return render_template('errores/500.html'), 500