from flask import Flask, render_template, request
from empresas import Empresa
from pedidos import Pedido

app = Flask(__name__)

# Carregar empresa inicial
empresa1 = Empresa("Empresa A", "numerico")
empresa1.carregar_catalogo("dados/empresa1.json")
empresas = {"Empresa A": empresa1}

@app.route('/')
def index():
    return render_template('index.html', empresas=empresas.keys())

@app.route('/pedido', methods=['POST'])
def pedido():
    empresa_nome = request.form['empresa']  # Corrigido: usar empresa_nome
    cnpj = request.form['cnpj']
    razao_social = request.form['razao']
    pedido_atual = Pedido(empresas[empresa_nome], razao_social, cnpj)
    return render_template('pedido.html', pedido=pedido_atual)

if __name__ == "__main__":
    app.run(debug=True)