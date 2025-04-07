from flask import Flask, render_template, request, redirect, url_for, jsonify
from empresas import Empresa
from pedidos import Pedido
import requests

app = Flask(__name__)

# Carregar empresa inicial
empresa1 = Empresa("Empresa A", "numerico")
empresa1.carregar_catalogo("dados/empresa1.json")
empresas = {"Empresa A": empresa1}

def consultar_cnpj(cnpj):
    url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj.replace('.', '').replace('/', '').replace('-', '')}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            dados['cnpj'] = cnpj
            return dados
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

@app.route('/pedido', methods=['GET', 'POST'])
def pedido():
    if request.method == 'POST' and 'empresa' in request.form:
        empresa_nome = request.form['empresa']
        cnpj = request.form['cnpj']
        razao_social = request.form['razao']
        pedido_atual = Pedido(empresas[empresa_nome], razao_social, cnpj)
        app.config['PEDIDO_ATUAL'] = pedido_atual
    else:
        pedido_atual = app.config.get('PEDIDO_ATUAL', Pedido(empresas["Empresa A"], "Cliente Padrão", "00.000.000/0000-00"))
    return render_template('pedido.html', pedido=pedido_atual)

@app.route('/buscar_item/<empresa_nome>/<codigo>', methods=['GET'])
def buscar_item(empresa_nome, codigo):
    empresa = empresas.get(empresa_nome)
    if empresa:
        item = empresa.get_item(codigo)
        if item:
            return jsonify(item)
    return jsonify({"erro": "Item não encontrado"}), 404

@app.route('/adicionar_item', methods=['POST'])
def adicionar_item():
    pedido_atual = app.config.get('PEDIDO_ATUAL')
    if pedido_atual:
        codigo = request.form['codigo']
        item = pedido_atual.empresa.get_item(codigo)
        if item:
            # Criar dicionário de quantidades, tratando campos vazios como 0
            quantidades = {}
            for tam in item["tamanhos"]:
                valor = request.form.get(f"qtd_{tam}", "0")  # Pega como string
                quantidades[tam] = int(valor) if valor.strip() else 0  # Converte ou usa 0 se vazio
            if any(quantidades.values()):  # Só adiciona se pelo menos uma quantidade for > 0
                pedido_atual.adicionar_item(codigo, quantidades)
    return redirect(url_for('pedido'))

@app.route('/remover_item/<int:index>')
def remover_item(index):
    pedido_atual = app.config.get('PEDIDO_ATUAL')
    if pedido_atual and 0 <= index < len(pedido_atual.itens):
        pedido_atual.itens.pop(index)
    return redirect(url_for('pedido'))

@app.route('/gerenciar_empresas', methods=['GET', 'POST'])
def gerenciar_empresas():
    if request.method == 'POST':
        nome = request.form['nome']
        tipo_grade = request.form['tipo_grade']
        nova_empresa = Empresa(nome, tipo_grade)
        empresas[nome] = nova_empresa
        # Aqui você pode adicionar lógica para salvar o catálogo em um arquivo JSON
    return render_template('gerenciar_empresas.html', empresas=empresas)

if __name__ == "__main__":
    app.run(debug=True)