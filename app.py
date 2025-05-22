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


app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Conexión a MongoDB
client = MongoClient("mongodb+srv://root:root@juan.i7bgn2f.mongodb.net/?retryWrites=true&w=majority&appName=Juan")
db = client["stock_db"]
users_collection = db["users"]
stock_collection = db["stock"]

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
    if 'username' not in session:
        return redirect(url_for('login'))

    # Stock por categoría
    productos = list(stock_collection.find())
    categorias = {}
    for prod in productos:
        cat = prod.get('categoria', 'Sin categoría')
        categorias[cat] = categorias.get(cat, 0) + prod.get('cantidad', 0)

    # Historial: ventas e ingresos por artículo
    historial_collection = db["historial"]
    historial_docs = list(historial_collection.find())

    ventas_por_articulo = {}
    ingresos_por_articulo = {}

    for h in historial_docs:
        nombre = h.get('nombre', 'Desconocido')
        cantidad = h.get('cantidad', 0)
        if h.get('tipo') == 'venta':
            ventas_por_articulo[nombre] = ventas_por_articulo.get(nombre, 0) + cantidad
        elif h.get('tipo') == 'ingreso':
            ingresos_por_articulo[nombre] = ingresos_por_articulo.get(nombre, 0) + cantidad

    return render_template(
        'graficas.html',
        categorias=categorias,
        ventas=ventas_por_articulo,
        ingresos=ingresos_por_articulo
    )

#filtro por mes

@app.route('/api/grafica')
def api_grafica():
    tipo = request.args.get('tipo')  # venta o ingreso
    mes = request.args.get('mes')

    filtro = {'tipo': tipo}
    if mes:
        año = 2025
        mes = int(mes)
        inicio = datetime(año, mes, 1)
        if mes == 12:
            fin = datetime(año + 1, 1, 1)
        else:
            fin = datetime(año, mes + 1, 1)
        filtro['fecha'] = {'$gte': inicio.isoformat(), '$lt': fin.isoformat()}

    datos = db['historial'].aggregate([
        {'$match': filtro},
        {'$group': {'_id': '$nombre', 'total': {'$sum': '$cantidad'}}}
    ])

    labels = []
    values = []

    for item in datos:
        labels.append(item['_id'])
        values.append(item['total'])

    return jsonify({'labels': labels, 'values': values})



if __name__ == '__main__':
    app.run(debug=True)


