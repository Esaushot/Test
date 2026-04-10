import sqlite3
import os
import csv
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'clave_secreta_uptis_2026'

# Configuración de carpetas y archivos permitidos
UPLOAD_FOLDER = 'static/uploads'
BIBLIOTECA_FOLDER = 'static/biblioteca'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BIBLIOTECA_FOLDER'] = BIBLIOTECA_FOLDER

# Crear carpetas si no existen
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(BIBLIOTECA_FOLDER):
    os.makedirs(BIBLIOTECA_FOLDER)

def get_db_connection():
    conn = sqlite3.connect('database.db', timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    conn = get_db_connection()
    
    # Tabla de Usuarios
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            certificado_url TEXT,
            curp_url TEXT,
            acta_url TEXT,
            domicilio_url TEXT,
            foto_infantil_url TEXT,
            ine_alumno_url TEXT,
            ine_tutor_url TEXT,
            tipo_sangre TEXT
        )
    ''')
    
    # SOLUCIÓN AUTOMÁTICA PARA COLUMNAS FALTANTES ORIGINALES
    columnas_nuevas = ['foto_infantil_url', 'ine_alumno_url', 'ine_tutor_url']
    for col in columnas_nuevas:
        try:
            conn.execute(f'ALTER TABLE usuarios ADD COLUMN {col} TEXT')
        except sqlite3.OperationalError:
            pass

    # Tabla de Materias
    conn.execute('''
        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_materia TEXT NOT NULL,
            docente_id INTEGER,
            dia TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            hora_fin TEXT NOT NULL,
            cupo_max INTEGER NOT NULL,
            cupo_actual INTEGER DEFAULT 0,
            FOREIGN KEY (docente_id) REFERENCES usuarios (id) ON DELETE SET NULL
        )
    ''')
    
    # Tabla de Inscripciones
    conn.execute('''
        CREATE TABLE IF NOT EXISTS inscripciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER,
            materia_id INTEGER,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(alumno_id, materia_id),
            FOREIGN KEY (alumno_id) REFERENCES usuarios (id) ON DELETE CASCADE,
            FOREIGN KEY (materia_id) REFERENCES materias (id) ON DELETE CASCADE
        )
    ''')
    
    # Tabla de Libros
    conn.execute('''
        CREATE TABLE IF NOT EXISTS libros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            autor TEXT NOT NULL,
            categoria TEXT NOT NULL,
            archivo_url TEXT NOT NULL,
            subido_por INTEGER,
            fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subido_por) REFERENCES usuarios (id) ON DELETE SET NULL
        )
    ''')
    
    # Tabla de Preguntas del Examen
    conn.execute('''
        CREATE TABLE IF NOT EXISTS preguntas_examen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pregunta TEXT NOT NULL
        )
    ''')
    
    # Tabla de Respuestas de los Alumnos
    conn.execute('''
        CREATE TABLE IF NOT EXISTS respuestas_examen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pregunta_id INTEGER,
            alumno_id INTEGER,
            respuesta TEXT NOT NULL,
            FOREIGN KEY (pregunta_id) REFERENCES preguntas_examen (id) ON DELETE CASCADE,
            FOREIGN KEY (alumno_id) REFERENCES usuarios (id) ON DELETE CASCADE
        )
    ''')

    # --- NUEVAS COLUMNAS PARA KÁRDEX Y CALIFICACIONES ---
    columnas_usuarios = [('cuatrimestre', 'INTEGER DEFAULT 1')]
    columnas_materias = [('cuatrimestre', 'INTEGER DEFAULT 1')]
    columnas_inscripciones = [('calificacion', 'REAL DEFAULT NULL')]

    for col, tipo in columnas_usuarios:
        try: conn.execute(f'ALTER TABLE usuarios ADD COLUMN {col} {tipo}')
        except sqlite3.OperationalError: pass

    for col, tipo in columnas_materias:
        try: conn.execute(f'ALTER TABLE materias ADD COLUMN {col} {tipo}')
        except sqlite3.OperationalError: pass

    for col, tipo in columnas_inscripciones:
        try: conn.execute(f'ALTER TABLE inscripciones ADD COLUMN {col} {tipo}')
        except sqlite3.OperationalError: pass

    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verificar_cruce_horario(alumno_id, nueva_materia_id):
    conn = get_db_connection()
    nueva_materia = conn.execute('SELECT dia, hora_inicio, hora_fin FROM materias WHERE id = ?', (nueva_materia_id,)).fetchone()
    
    if not nueva_materia:
        conn.close()
        return False

    materias_inscritas = conn.execute('''
        SELECT m.hora_inicio, m.hora_fin 
        FROM materias m 
        JOIN inscripciones i ON m.id = i.materia_id 
        WHERE i.alumno_id = ? AND m.dia = ?
    ''', (alumno_id, nueva_materia['dia'])).fetchall()
    
    conn.close()

    for materia in materias_inscritas:
        if (nueva_materia['hora_inicio'] < materia['hora_fin'] and 
            nueva_materia['hora_fin'] > materia['hora_inicio']):
            return True
    return False

# --- RUTAS PRINCIPALES ---

@app.route('/')
def index():
    if 'user_id' in session:
        if session['rol'] == 'admin': return redirect(url_for('dashboard_admin'))
        if session['rol'] == 'docente': return redirect(url_for('dashboard_docente'))
        return redirect(url_for('dashboard_alumno'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE correo = ?', (correo,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['rol'] = user['rol']
            session['nombre'] = user['nombre']
            
            if user['rol'] == 'admin': return redirect(url_for('dashboard_admin'))
            if user['rol'] == 'docente': return redirect(url_for('dashboard_docente'))
            return redirect(url_for('dashboard_alumno'))
        
        flash('Correo o contraseña incorrectos')
    return render_template('login.html')

# --- RUTA: BIBLIOTECA ---

@app.route('/biblioteca', methods=['GET', 'POST'])
def biblioteca():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    if request.method == 'POST' and session.get('rol') in ['admin', 'docente']:
        titulo = request.form.get('titulo')
        autor = request.form.get('autor')
        categoria = request.form.get('categoria')
        file = request.files.get('libro_pdf')

        if file and allowed_file(file.filename):
            filename = secure_filename(f"libro_{titulo}_{file.filename}")
            file.save(os.path.join(app.config['BIBLIOTECA_FOLDER'], filename))
            
            conn.execute('''
                INSERT INTO libros (titulo, autor, categoria, archivo_url, subido_por) 
                VALUES (?, ?, ?, ?, ?)
            ''', (titulo, autor, categoria, filename, session['user_id']))
            conn.commit()
            flash('Libro agregado exitosamente a la biblioteca.')

    categoria_filtro = request.args.get('cat')
    if categoria_filtro:
        libros = conn.execute('SELECT * FROM libros WHERE categoria = ? ORDER BY id DESC', (categoria_filtro,)).fetchall()
    else:
        libros = conn.execute('SELECT * FROM libros ORDER BY id DESC').fetchall()
        
    conn.close()
    return render_template('biblioteca.html', libros=libros, categoria_actual=categoria_filtro)

@app.route('/biblioteca/borrar/<int:libro_id>')
def borrar_libro(libro_id):
    if 'user_id' not in session or session.get('rol') not in ['admin', 'docente']:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    libro = conn.execute('SELECT * FROM libros WHERE id = ?', (libro_id,)).fetchone()
    
    if libro:
        if session['rol'] == 'admin' or libro['subido_por'] == session['user_id']:
            try:
                file_path = os.path.join(app.config['BIBLIOTECA_FOLDER'], libro['archivo_url'])
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass

            conn.execute('DELETE FROM libros WHERE id = ?', (libro_id,))
            conn.commit()
            flash('Material eliminado correctamente.')
        else:
            flash('No tienes permisos para eliminar este material.')
            
    conn.close()
    return redirect(url_for('biblioteca'))

# --- DASHBOARDS Y GESTIÓN ---

@app.route('/admin')
def dashboard_admin():
    if session.get('rol') != 'admin': return redirect(url_for('login'))
    
    query = request.args.get('search', '')
    conn = get_db_connection()
    
    if query:
        usuarios = conn.execute('SELECT * FROM usuarios WHERE nombre LIKE ? OR correo LIKE ?', 
                              ('%' + query + '%', '%' + query + '%')).fetchall()
    else:
        usuarios = conn.execute('SELECT * FROM usuarios').fetchall()
    
    conn.close()
    return render_template('admin.html', usuarios=usuarios, query=query)

@app.route('/admin/avanzar_cuatrimestre/<int:alumno_id>')
def avanzar_cuatrimestre(alumno_id):
    if session.get('rol') != 'admin': return redirect(url_for('login'))
    conn = get_db_connection()
    user = conn.execute('SELECT cuatrimestre FROM usuarios WHERE id = ?', (alumno_id,)).fetchone()
    
    if user and user['cuatrimestre'] < 9:
        conn.execute('UPDATE usuarios SET cuatrimestre = cuatrimestre + 1 WHERE id = ?', (alumno_id,))
        conn.commit()
        flash('El alumno ha avanzado al siguiente cuatrimestre exitosamente.')
    else:
        flash('El alumno ya ha concluido todos los cuatrimestres o hubo un error.')
    conn.close()
    return redirect(url_for('dashboard_admin'))

@app.route('/docente', methods=['GET', 'POST'])
def dashboard_docente():
    if session.get('rol') != 'docente': return redirect(url_for('login'))
    conn = get_db_connection()
    
    if request.method == 'POST' and 'nombre' in request.form:
        nombre = request.form['nombre']
        dia = request.form['dia']
        inicio = request.form['inicio']
        fin = request.form['fin']
        cupo = request.form['cupo']
        cuatrimestre = request.form['cuatrimestre']
        
        conn.execute('''
            INSERT INTO materias (nombre_materia, docente_id, dia, hora_inicio, hora_fin, cupo_max, cuatrimestre)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nombre, session['user_id'], dia, inicio, fin, cupo, cuatrimestre))
        conn.commit()
        flash('Materia publicada con éxito')

    materias = conn.execute('SELECT * FROM materias WHERE docente_id = ?', (session['user_id'],)).fetchall()
    
    alumnos_por_materia = {}
    for m in materias:
        alumnos = conn.execute('''
            SELECT u.nombre, u.correo, i.id as inscripcion_id, i.calificacion 
            FROM usuarios u
            JOIN inscripciones i ON u.id = i.alumno_id
            WHERE i.materia_id = ?
        ''', (m['id'],)).fetchall()
        alumnos_por_materia[m['id']] = alumnos
        
    conn.close()
    return render_template('docente.html', materias=materias, alumnos_por_materia=alumnos_por_materia)

@app.route('/subir_calificaciones', methods=['POST'])
def subir_calificaciones():
    if session.get('rol') != 'docente': return redirect(url_for('login'))
    conn = get_db_connection()
    
    for key, value in request.form.items():
        if key.startswith('calif_') and value.strip() != '':
            insc_id = key.split('_')[1]
            conn.execute('UPDATE inscripciones SET calificacion = ? WHERE id = ?', (float(value), insc_id))
            
    conn.commit()
    conn.close()
    flash('Calificaciones guardadas exitosamente en el Kárdex de los alumnos.')
    return redirect(url_for('dashboard_docente'))

@app.route('/alumno')
def dashboard_alumno():
    if session.get('rol') != 'alumno': return redirect(url_for('login'))
    
    conn = get_db_connection()
    alumno = conn.execute('SELECT cuatrimestre FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()
    cuatrimestre_actual = alumno['cuatrimestre'] if alumno else 1

    oferta = conn.execute('''
        SELECT m.*, u.nombre as docente FROM materias m
        JOIN usuarios u ON m.docente_id = u.id
        WHERE m.cupo_actual < m.cupo_max AND m.cuatrimestre = ?
    ''', (cuatrimestre_actual,)).fetchall()
    
    historial = conn.execute('''
        SELECT m.*, i.calificacion FROM materias m
        JOIN inscripciones i ON m.id = i.materia_id
        WHERE i.alumno_id = ?
        ORDER BY m.cuatrimestre DESC, m.nombre_materia ASC
    ''', (session['user_id'],)).fetchall()
    
    horario_semanal = { 'Lunes': [], 'Martes': [], 'Miércoles': [], 'Jueves': [], 'Viernes': [] }
    inscritas_actuales = []
    
    for h in historial:
        if h['cuatrimestre'] == cuatrimestre_actual:
            inscritas_actuales.append(h)
            if h['dia'] in horario_semanal:
                horario_semanal[h['dia']].append(h)
            
    conn.close()
    return render_template('alumno.html', oferta=oferta, inscritas=inscritas_actuales, horario_semanal=horario_semanal, historial=historial, cuatrimestre_actual=cuatrimestre_actual)

# --- ACCIONES DE INSCRIPCIÓN Y ARCHIVOS ---

@app.route('/inscribir/<int:materia_id>')
def inscribir(materia_id):
    if session.get('rol') != 'alumno': return redirect(url_for('login'))
    
    if verificar_cruce_horario(session['user_id'], materia_id):
        flash('Error: Tienes un cruce de horario con otra materia.')
        return redirect(url_for('dashboard_alumno'))
        
    conn = get_db_connection()
    materia = conn.execute('SELECT cupo_actual, cupo_max FROM materias WHERE id = ?', (materia_id,)).fetchone()
    
    if materia and materia['cupo_actual'] < materia['cupo_max']:
        try:
            conn.execute('INSERT INTO inscripciones (alumno_id, materia_id) VALUES (?, ?)', (session['user_id'], materia_id))
            conn.execute('UPDATE materias SET cupo_actual = cupo_actual + 1 WHERE id = ?', (materia_id,))
            conn.commit()
            flash('Inscripción exitosa')
        except sqlite3.IntegrityError:
            flash('Ya estás inscrito en esta materia')
    else:
        flash('Lo sentimos, ya no hay cupo')
        
    conn.close()
    return redirect(url_for('dashboard_alumno'))

@app.route('/subir_documentos', methods=['POST'])
def subir_documentos():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    usuario_id = request.form.get('usuario_id') if session['rol'] == 'admin' else session['user_id']
    conn = get_db_connection()
    
    try:
        tipo_sangre = request.form.get('tipo_sangre')
        if tipo_sangre:
            conn.execute('UPDATE usuarios SET tipo_sangre = ? WHERE id = ?', (tipo_sangre, usuario_id))

        documentos = ['certificado', 'curp', 'acta', 'domicilio', 'foto_infantil', 'ine_alumno', 'ine_tutor']
        
        for doc in documentos:
            file = request.files.get(doc)
            if file and allowed_file(file.filename):
                filename = secure_filename(f"user{usuario_id}_{doc}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                columna = f"{doc}_url"
                conn.execute(f'UPDATE usuarios SET {columna} = ? WHERE id = ?', (filename, usuario_id))
                
        conn.commit()
        flash('Documentos actualizados correctamente')
    except Exception as e:
        flash(f'Error al subir archivos: {str(e)}')
    finally:
        conn.close()
        
    return redirect(request.referrer)

@app.route('/admin/crear_usuario', methods=['POST'])
def crear_usuario():
    if session.get('rol') != 'admin': return redirect(url_for('login'))
    
    nombre = request.form['nombre']
    correo = request.form['correo']
    password = generate_password_hash(request.form['password'])
    rol = request.form['rol']
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO usuarios (nombre, correo, password, rol) VALUES (?, ?, ?, ?)',
                     (nombre, correo, password, rol))
        conn.commit()
        flash('Usuario creado exitosamente')
    except sqlite3.IntegrityError:
        flash('El correo ya está registrado')
    finally:
        conn.close()
    return redirect(url_for('dashboard_admin'))

@app.route('/borrar_materia/<int:materia_id>')
def borrar_materia(materia_id):
    if session.get('rol') != 'docente': return redirect(url_for('login'))
    
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM inscripciones WHERE materia_id = ?', (materia_id,))
        conn.execute('DELETE FROM materias WHERE id = ? AND docente_id = ?', 
                     (materia_id, session['user_id']))
        conn.commit()
        flash('Materia y registros de inscripción eliminados correctamente.')
    except Exception as e:
        flash(f'Error al eliminar la materia: {str(e)}')
    finally:
        conn.close()
        
    return redirect(url_for('dashboard_docente'))

@app.route('/borrar_usuario/<int:usuario_id>')
def borrar_usuario(usuario_id):
    if session.get('rol') != 'admin': return redirect(url_for('login'))
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM inscripciones WHERE alumno_id = ?', (usuario_id,))
        conn.execute('UPDATE materias SET docente_id = NULL WHERE docente_id = ?', (usuario_id,))
        conn.execute('UPDATE libros SET subido_por = NULL WHERE subido_por = ?', (usuario_id,))
        conn.execute('DELETE FROM usuarios WHERE id = ?', (usuario_id,))
        conn.commit()
        flash('Usuario eliminado')
    except Exception as e:
        flash(f'Error al eliminar: {str(e)}')
    finally:
        conn.close()
    return redirect(url_for('dashboard_admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/exportar_asistencia/<int:materia_id>')
def exportar_asistencia(materia_id):
    if session.get('rol') != 'docente': return redirect(url_for('login'))
    
    conn = get_db_connection()
    materia = conn.execute('SELECT nombre_materia FROM materias WHERE id = ?', (materia_id,)).fetchone()
    alumnos = conn.execute('''
        SELECT u.nombre, u.correo FROM usuarios u
        JOIN inscripciones i ON u.id = i.alumno_id
        WHERE i.materia_id = ?
        ORDER BY u.nombre ASC
    ''', (materia_id,)).fetchall()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Nombre del Alumno', 'Correo Electrónico', 'Fecha:', 'Fecha:', 'Fecha:', 'Fecha:'])
    
    for alumno in alumnos:
        cw.writerow([alumno['nombre'], alumno['correo'], '', '', '', ''])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=Asistencia_{materia['nombre_materia']}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# --- RUTAS: EXAMEN DIAGNÓSTICO ---

@app.route('/examen', methods=['GET', 'POST'])
def examen():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    rol = session.get('rol')
    
    if rol in ['admin', 'docente']:
        preguntas = conn.execute('SELECT * FROM preguntas_examen').fetchall()
        conn.close()
        return render_template('examen.html', preguntas=preguntas)
        
    elif rol == 'alumno':
        ya_respondio = conn.execute('SELECT COUNT(*) FROM respuestas_examen WHERE alumno_id = ?', (session['user_id'],)).fetchone()[0] > 0
        
        if request.method == 'POST' and not ya_respondio:
            for key, value in request.form.items():
                if key.startswith('pregunta_'):
                    pregunta_id = key.split('_')[1]
                    conn.execute('INSERT INTO respuestas_examen (pregunta_id, alumno_id, respuesta) VALUES (?, ?, ?)',
                                 (pregunta_id, session['user_id'], value))
            conn.commit()
            flash('Examen enviado correctamente. ¡Gracias!')
            conn.close()
            return redirect(url_for('examen'))
            
        preguntas = conn.execute('SELECT * FROM preguntas_examen').fetchall()
        conn.close()
        return render_template('examen.html', preguntas=preguntas, ya_respondio=ya_respondio)

@app.route('/examen/agregar_pregunta', methods=['POST'])
def agregar_pregunta():
    if session.get('rol') not in ['admin', 'docente']: return redirect(url_for('login'))
    pregunta = request.form.get('pregunta')
    if pregunta:
        conn = get_db_connection()
        conn.execute('INSERT INTO preguntas_examen (pregunta) VALUES (?)', (pregunta,))
        conn.commit()
        conn.close()
        flash('Pregunta agregada exitosamente.')
    return redirect(url_for('examen'))

@app.route('/examen/borrar_pregunta/<int:id>')
def borrar_pregunta(id):
    if session.get('rol') not in ['admin', 'docente']: return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM preguntas_examen WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Pregunta eliminada.')
    return redirect(url_for('examen'))

@app.route('/examen/resultados')
def resultados_examen():
    if session.get('rol') not in ['admin', 'docente']: return redirect(url_for('login'))
    conn = get_db_connection()
    alumnos_db = conn.execute('''
        SELECT DISTINCT u.id, u.nombre, u.correo 
        FROM usuarios u 
        JOIN respuestas_examen r ON u.id = r.alumno_id
    ''').fetchall()
    
    resultados = []
    for al in alumnos_db:
        respuestas = conn.execute('''
            SELECT p.pregunta, r.respuesta 
            FROM respuestas_examen r
            JOIN preguntas_examen p ON r.pregunta_id = p.id
            WHERE r.alumno_id = ?
        ''', (al['id'],)).fetchall()
        resultados.append({'nombre': al['nombre'], 'correo': al['correo'], 'respuestas': respuestas})
        
    conn.close()
    return render_template('resultados_examen.html', resultados=resultados)

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=5000)