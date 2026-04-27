from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def requiere_rol(*roles_permitidos):
    """
    Decorador para proteger rutas según el rol.
    El Administrador siempre tiene acceso por defecto.
    Uso: @requiere_rol('agente')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Si no está logueado, lo mandamos al login
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Si es admin, pasa directo. Si no, verificamos si su rol está en los permitidos
            if current_user.rol != 'administrador' and current_user.rol not in roles_permitidos:
                flash('No tienes permisos para acceder a esta página.', 'error')
                # Redirigir al dashboard que le corresponde
                if current_user.rol == 'agente':
                    return redirect(url_for('usuarios.dashboard_agente')) # Ajustaremos estas rutas luego
                return redirect(url_for('auth.login'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator