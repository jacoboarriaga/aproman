"""
Módulo: models
Descripción: Modelos de datos para la sesión de Flask-Login.
Contiene la clase Usuario que representa al usuario autenticado en memoria.
"""

from flask_login import UserMixin


class Usuario(UserMixin):
    """Representa al usuario autenticado en la sesión de Flask.
    
    No es un modelo ORM — es un objeto plano que Flask-Login usa
    para mantener la identidad del usuario entre peticiones.
    """

    def __init__(self, id, username, rol, nombre, puede_ver_costos=False):
        self.id = id
        self.username = username
        self.rol = rol
        self.nombre = nombre
        self.puede_ver_costos = bool(puede_ver_costos)

    def get_full_name(self):
        """Retorna el nombre completo del usuario, o su username como fallback."""
        nombre_completo = f"{self.nombre or ''}".strip()
        return nombre_completo if nombre_completo else self.username
