from flask import Flask, render_template, request, redirect, url_for, jsonify
from empresas import Empresa
from pedidos import Pedido
from database import init_db, carregar_empresas, salvar_pedido, carregar_ultimo_pedido, salvar_empresa, carregar_catalogo, salvar_item_catalogo, remover_item_catalogo
import requests
import os
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()
empresas = carregar_empresas()

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
    logger.info("Acessando a rota inicial")
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
        salvar_pedido(pedido_atual)
    else:
        pedido_atual = carregar_ultimo_pedido(empresas) or Pedido(empresas["Empresa A"], "Cliente Padrão", "00.000.000/0000-00")
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
    pedido_atual = carregar_ultimo_pedido(empresas)
    if pedido_atual:
        codigo = request.form['codigo']
        item = pedido_atual.empresa.get_item(codigo)
        if item:
            quantidades = {tam: int(request.form.get(f"qtd_{tam}", "0") or "0") for tam in item["tamanhos"]}
            if any(quantidades.values()):
                pedido_atual.adicionar_item(codigo, quantidades)
                salvar_pedido(pedido_atual)
    return redirect(url_for('pedido'))

@app.route('/remover_item/<int:index>')
def remover_item(index):
    pedido_atual = carregar_ultimo_pedido(empresas)
    if pedido_atual and 0 <= index < len(pedido_atual.itens):
        pedido_atual.itens.pop(index)
        salvar_pedido(pedido_atual)
    return redirect(url_for('pedido'))

@app.route('/gerenciar_empresas', methods=['GET', 'POST'])
def gerenciar_empresas():
    if request.method == 'POST':
        if 'nome' in request.form and 'tipo_grade' in request.form:  # Adicionar/editar empresa
            nome = request.form['nome']
            tipo_grade = request.form['tipo_grade']
            salvar_empresa(nome, tipo_grade)
        elif 'empresa_nome' in request.form and 'codigo' in request.form:  # Adicionar/editar item do catálogo
            empresa_nome = request.form['empresa_nome']
            codigo = request.form['codigo']
            descritivo = request.form['descritivo']
            valor = float(request.form['valor'])
            tamanhos = request.form['tamanhos'].split(',')  # Espera tamanhos como "2,4,6"
            salvar_item_catalogo(empresa_nome, codigo, descritivo, valor, tamanhos)
        global empresas
        empresas = carregar_empresas()
    
    # Carregar catálogos para todas as empresas
    catalogos = {nome: carregar_catalogo(nome) for nome in empresas.keys()}
    return render_template('gerenciar_empresas.html', empresas=empresas, catalogos=catalogos)

@app.route('/remover_item_catalogo/<empresa_nome>/<codigo>', methods=['POST'])
def remover_item_catalogo_route(empresa_nome, codigo):
    remover_item_catalogo(empresa_nome, codigo)
    global empresas
    empresas = carregar_empresas()
    return redirect(url_for('gerenciar_empresas'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)