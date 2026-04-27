"""
Módulo de utilidades para conexiones a bases de datos.
Contiene funciones para crear conexiones a diferentes bases de datos utilizando pyodbc.
"""

import pyodbc
import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def get_db_connection(server=None, database=None, username=None, password=None):
    """
    Retorna una conexión a la base de datos SQL Server.
    
    Parámetros:
        server (str): Dirección IP o nombre del servidor. Si no se proporciona, se toma del .env.
        database (str): Nombre de la base de datos. Si no se proporciona, se toma del .env.
        username (str): Nombre de usuario. Si no se proporciona, se toma del .env.
        password (str): Contraseña. Si no se proporciona, se toma del .env.
    
    Retorna:
        pyodbc.Connection: Conexión a la base de datos.
    
    Lanza:
        Exception: Si ocurre un error al intentar conectarse.
    """
    try:
        # Usar valores predeterminados de las variables de entorno si no se proporcionan
        server = server or os.getenv('DB_SERVER')
        database = database or os.getenv('DB_NAME', 'Aproman')
        username = username or os.getenv('DB_USER')
        password = password or os.getenv('DB_PASSWORD')

        # Cadena de conexión adaptada para ODBC Driver 18 (Requiere TrustServerCertificate)
        conn_str = (
            f'DRIVER={{ODBC Driver 18 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password};'
            f'TrustServerCertificate=yes;Encrypt=yes;'
        )

        # Intentar establecer la conexión
        conn = pyodbc.connect(conn_str)
        # logging.info(f"Conexión exitosa a la base de datos '{database}' en el servidor '{server}'.")
        return conn

    except pyodbc.Error as e:
        print(f"Error de conexión a BD: {e}")
        raise Exception(f"No se pudo conectar a SQL Server. Verifica tus credenciales: {e}")


def get_erp_connection():
    """
    Retorna una conexión a la base de datos ERP (DEMO) en el mismo servidor.
    Usa las mismas credenciales que get_db_connection() pero apunta a la BD 'DEMO'
    donde residen las tablas del inventario (IN_DOCUMENTO, IN_PRODUCTOS, etc.).
    """
    try:
        server   = os.getenv('DB_SERVER')
        database = os.getenv('DB_ERP_NAME', 'DEMO')
        username = os.getenv('DB_USER')
        password = os.getenv('DB_PASSWORD')

        conn_str = (
            f'DRIVER={{ODBC Driver 18 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password};'
            f'TrustServerCertificate=yes;Encrypt=yes;'
        )

        conn = pyodbc.connect(conn_str)
        return conn

    except pyodbc.Error as e:
        print(f"Error de conexión a BD ERP: {e}")
        raise Exception(f"No se pudo conectar al ERP (DEMO). Verifica tus credenciales: {e}")