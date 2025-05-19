from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from bson.objectid import ObjectId

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
        return "Credenciales incorrectas"
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
            'categoria': request.form['categoria']
        })
        return redirect(url_for('visualizar'))
    return render_template('datos.html')

@app.route('/organizar')
def organizar():
    if 'username' not in session:
        return redirect(url_for('login'))
    items = list(stock_collection.find().sort('categoria'))
    return render_template('organizar.html', items=items)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
