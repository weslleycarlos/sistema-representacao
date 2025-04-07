from flask import Flask, render_template, request, redirect, url_for
from empresas import Empresa
from pedidos import Pedido
import requests

app = Flask(__name__)

# Carregar empresa inicial
empresa1 = Empresa("Empresa A", "numerico")
empresa1.carregar_catalogo("dados/empresa1.json")
empresas = {"Empresa A": empresa1}

# Função para consultar CNPJ
def consultar_cnpj(cnpj):
    url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj.replace('.', '').replace('/', '').replace('-', '')}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            dados['cnpj'] = cnpj  # Preserva o CNPJ digitado
            return dados
        else:
            return {"erro": "CNPJ não encontrado ou limite excedido"}
    except Exception as e:
        return {"erro": str(e)}

# Rota inicial
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', empresas=empresas.keys(), dados_loja=None)

# Rota para consultar CNPJ
@app.route('/consultar_cnpj', methods=['POST'])
def consultar_cnpj_route():
    cnpj = request.form['cnpj']
    dados_loja = consultar_cnpj(cnpj)
    return render_template('index.html', empresas=empresas.keys(), dados_loja=dados_loja, request=request)

# Rota para exibir e gerenciar o pedido
@app.route('/pedido', methods=['GET', 'POST'])
def pedido():
    if request.method == 'POST' and 'empresa' in request.form:
        # Criar novo pedido a partir do formulário da página inicial
        empresa_nome = request.form['empresa']
        cnpj = request.form['cnpj']
        razao_social = request.form['razao']
        pedido_atual = Pedido(empresas[empresa_nome], razao_social, cnpj)
        app.config['PEDIDO_ATUAL'] = pedido_atual  # Armazenar temporariamente
    else:
        # Recuperar pedido atual ou criar um padrão se não existir
        pedido_atual = app.config.get('PEDIDO_ATUAL', Pedido(empresas["Empresa A"], "Cliente Padrão", "00.000.000/0000-00"))

    return render_template('pedido.html', pedido=pedido_atual)

# Rota para adicionar item
@app.route('/adicionar_item', methods=['POST'])
def adicionar_item():
    pedido_atual = app.config.get('PEDIDO_ATUAL')
    if pedido_atual:
        codigo = request.form['codigo']
        item = pedido_atual.empresa.get_item(codigo)
        if item:
            qtd = int(request.form.get('qtd', 0))
            pedido_atual.adicionar_item(codigo, {"unico": qtd})  # Exemplo simples com quantidade única
    return redirect(url_for('pedido'))

# Rota para remover item
@app.route('/remover_item/<int:index>')
def remover_item(index):
    pedido_atual = app.config.get('PEDIDO_ATUAL')
    if pedido_atual and 0 <= index < len(pedido_atual.itens):
        pedido_atual.itens.pop(index)
    return redirect(url_for('pedido'))

if __name__ == "__main__":
    app.run(debug=True)