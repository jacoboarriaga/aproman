from passlib.hash import django_pbkdf2_sha256
from app.utils import get_db_connection

def crear_superusuario():
    print("Creando usuario Administrador...")
    
    # Datos del nuevo usuario
    username = 'sysadm'
    password_plana = 'Sa_procolo2026$$'
    nombre = 'Administrador'
    rol = 'administrador'
    
    # 1. Encriptar la contraseña con el formato exacto que espera Flask/Django
    password_encriptada = django_pbkdf2_sha256.hash(password_plana)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 2. Insertar en la nueva tabla 'usuarios'
        cursor.execute("""
            INSERT INTO usuarios (username, password, nombre, email, rol, is_active, fecha_registro)
            VALUES (?, ?, ?, ?, ?, 1, GETDATE())
        """, (username, password_encriptada, nombre, 'admin@aplicacionesprocolor.com', rol))
        
        conn.commit()
        print(f"¡Éxito! Usuario '{username}' creado correctamente.")
        print(f"Contraseña: {password_plana}")
        print("Ya puedes iniciar sesión en APROMAN.")
        
    except Exception as e:
        conn.rollback()
        print(f"Hubo un error al crear el usuario: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    crear_superusuario()