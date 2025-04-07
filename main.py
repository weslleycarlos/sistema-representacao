from flask import Flask, render_template, request
from empresas import Empresa
from pedidos import Pedido
import requests

app = Flask(__name__)

# Carregar empresa inicial
empresa1 = Empresa("Empresa A", "numerico")
empresa1.carregar_catalogo("dados/empresa1.json")  # Corrigido: 'empresa1' em vez de '企業1'
empresas = {"Empresa A": empresa1}

def consultar_cnpj(cnpj):
    url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj.replace('.', '').replace('/', '').replace('-', '')}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            dados['cnpj'] = cnpj  # Adiciona o CNPJ original ao retorno
            return dados
        else:
            return {"erro": "CNPJ não encontrado ou limite excedido"}
    except Exception as e:
        return {"erro": str(e)}

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', empresas=empresas.keys(), dados_loja=None)

@app.route('/consultar_cnpj', methods=['POST'])
def consultar_cnpj_route():
    cnpj = request.form['cnpj']
    dados_loja = consultar_cnpj(cnpj)
    return render_template('index.html', empresas=empresas.keys(), dados_loja=dados_loja, request=request)

@app.route('/pedido', methods=['POST'])
def pedido():
    empresa_nome = request.form['empresa']
    cnpj = request.form['cnpj']
    razao_social = request.form['razao']
    pedido_atual = Pedido(empresas[empresa_nome], razao_social, cnpj)
    return render_template('pedido.html', pedido=pedido_atual)

if __name__ == "__main__":
    app.run(debug=True)