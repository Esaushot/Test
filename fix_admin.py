import sqlite3
from werkzeug.security import generate_password_hash

def fix_admin():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # 1. Borramos si existe un admin previo para evitar conflictos de "Unique"
    cursor.execute("DELETE FROM usuarios WHERE correo = 'admin@uptis.edu.mx'")

    # 2. Insertamos el admin con los campos EXACTOS de tu tabla
    # nombre, correo, password, rol, y los demás como NULL
    nombre = "Control Administrativo"
    correo = "admin@uptis.edu.mx"
    password = generate_password_hash("admin123")
    rol = "admin" # IMPORTANTE: Debe ser minúsculas como en tu lógica de app.py

    try:
        cursor.execute('''
            INSERT INTO usuarios (nombre, correo, password, rol) 
            VALUES (?, ?, ?, ?)
        ''', (nombre, correo, password, rol))
        
        conn.commit()
        print("✅ ADMIN REPARADO EXITOSAMENTE")
        print(f"Correo: {correo}")
        print(f"Password: admin123")
    except Exception as e:
        print(f"❌ Error al crear admin: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    fix_admin()