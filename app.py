from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from bson.objectid import ObjectId

import tkinter as tk
from tkinter import messagebox

import pandas as pd
from flask import send_file
import io

from flask import jsonify
from datetime import datetime
from collections import defaultdict

from flask import request


app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Conexión a MongoDB
client = MongoClient("mongodb+srv://root:root@juan.i7bgn2f.mongodb.net/?retryWrites=true&w=majority&appName=Juan")
db = client["stock_db"]
users_collection = db["users"]
stock_collection = db["stock"]
historial_collection = db['historial']


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username, 'password': password})
        if user:
            session['username'] = username
            return redirect(url_for('menu'))
        else:
            messagebox.showwarning("ADVERTENCIA: Credenciales incorrectas")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/menu')
def menu():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('menu.html', username=session['username'])

@app.route('/visualizar', methods=['GET'])
def visualizar():
    if 'username' not in session:
        return redirect(url_for('login'))

    query = request.args.get('q', '')
    if query:
        items = list(stock_collection.find({
            '$or': [
                {'nombre': {'$regex': query, '$options': 'i'}},
                {'categoria': {'$regex': query, '$options': 'i'}}
            ]
        }))
    else:
        items = list(stock_collection.find())

    return render_template('visualizar.html', items=items, query=query)

@app.route('/datos', methods=['GET', 'POST'])
def datos():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        stock_collection.insert_one({
            'nombre': request.form['nombre'],
            'cantidad': int(request.form['cantidad']),
            'categoria': request.form['categoria'],
            'precio': float(request.form['precio'])
        })
        return redirect(url_for('visualizar'))

    return render_template('datos.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))



# acá abajo están las rutas para editar / eliminar

@app.route('/editar/<item_id>', methods=['GET', 'POST'])
def editar_item(item_id):
    item = stock_collection.find_one({'_id': ObjectId(item_id)})

    if not item:
        return "Ítem no encontrado", 404

    if request.method == 'POST':
        nombre = request.form['nombre']
        categoria = request.form['categoria']
        cantidad = int(request.form['cantidad'])
        precio = float(request.form['precio'])

        stock_collection.update_one(
            {'_id': ObjectId(item_id)},
            {'$set': {
                'nombre': nombre,
                'categoria': categoria,
                'cantidad': cantidad,
                'precio': precio
            }}
        )
        return redirect(url_for('visualizar'))

    return render_template('editar_item.html', item=item)



@app.route('/eliminar/<item_id>', methods=['POST'])
def eliminar_item(item_id):
    try:
        stock_collection.delete_one({'_id': ObjectId(item_id)})
        return redirect(url_for('visualizar'))
    except Exception as e:
        return f"Error eliminando el ítem: {str(e)}", 500


# Acá va la ruta para poder pasar a excel los datos xd

@app.route('/exportar_excel')
def exportar_excel():
    if 'username' not in session:
        return redirect(url_for('login'))

    data = list(stock_collection.find())
    for item in data:
        item['_id'] = str(item['_id'])  # Convertir ObjectId a str para Excel

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Stock')

    output.seek(0)

    return send_file(output,
                     download_name="stock.xlsx",
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


#La ruta para el apartado de gráficas xd

@app.route('/graficas')
def graficas():
    
    meses_traducidos = {
    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
    'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
    'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
    'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
}
    
    if 'username' not in session:
        return redirect(url_for('login'))

    # Stock por categoría
    categorias = defaultdict(int)
    for item in stock_collection.find():
        categorias[item['categoria']] += item['cantidad']

    # Historial
    historial = list(historial_collection.find())
    ventas_por_articulo = defaultdict(int)
    ingresos_por_articulo = defaultdict(int)
    ventas_por_mes = defaultdict(int)  # cantidad total vendida por mes
    ganancia_por_mes = defaultdict(float)  # ganancia total por mes

    precios = {item['nombre']: item['precio'] for item in stock_collection.find()}

    for item in historial:
        nombre = item['nombre']
        cantidad = item['cantidad']
        fecha = item.get('fecha')

        if isinstance(fecha, str):
            fecha = datetime.strptime(fecha, "%Y-%m-%d")

        mes = meses_traducidos[fecha.strftime("%B")]
        if item['tipo'] == 'venta':
            ventas_por_articulo[nombre] += cantidad
            ventas_por_mes[mes] += cantidad
            ganancia_por_mes[mes] += precios.get(nombre, 0) * cantidad
        elif item['tipo'] == 'ingreso':
            ingresos_por_articulo[nombre] += cantidad

    return render_template('graficas.html',
                           categorias=categorias,
                           ventas=ventas_por_articulo,
                           ingresos=ingresos_por_articulo,
                           ganancia_mes=ganancia_por_mes)

    

#filtro por mes

@app.route('/api/grafica')
def api_grafica():
    tipo = request.args.get('tipo')
    mes = request.args.get('mes')

    filtro = {'tipo': tipo}

    # Aplica filtro por mes si se proporciona (esperando 'YYYY-MM')
    if mes:
        if len(mes.split("-")) == 2:  # Validación de formato
            anio, mes_num = mes.split("-")
            mes_num = mes_num.zfill(2)
            filtro['fecha'] = {'$regex': f'^{anio}-{mes_num}'}
        else:
            return jsonify({"error": "Formato de mes inválido, se espera YYYY-MM"}), 400

    # Consulta a MongoDB con filtro ya armado
    registros = list(historial_collection.find(filtro))
    precios = {item['nombre']: item['precio'] for item in stock_collection.find({})}

    conteo = {}
    ganancia = 0

    for reg in registros:
        nombre = reg['nombre']
        cantidad = reg['cantidad']
        conteo[nombre] = conteo.get(nombre, 0) + cantidad

        if tipo == 'venta':
            precio = precios.get(nombre, 0)
            ganancia += cantidad * precio

    total_ingresos = sum(conteo.values()) if tipo == 'ingreso' else None

    return jsonify({
        'labels': list(conteo.keys()),
        'values': list(conteo.values()),
        'ganancia': ganancia if tipo == 'venta' else None,
        'total': total_ingresos
    })



@app.route('/historial')
def historial():
    query = request.args.get('q', '')
    mes = request.args.get('mes', '')

    filtro = {}

    if query:
        filtro['$or'] = [
            {'nombre': {'$regex': query, '$options': 'i'}},
            {'tipo': {'$regex': query, '$options': 'i'}}
        ]

    if mes:
        filtro['fecha'] = {'$regex': f'^{mes}'}

    items = list(historial_collection.find(filtro))
    
    return render_template('historial.html', items=items, query=query, mes=mes, username=session.get('username'))



    

if __name__ == '__main__':
    app.run(debug=True)


