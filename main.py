from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from empresas import Empresa
from pedidos import Pedido
from database import init_db, carregar_empresas, salvar_pedido, carregar_ultimo_pedido, salvar_empresa, carregar_catalogo, salvar_item_catalogo, remover_item_catalogo
import requests
import os
import logging
import psycopg2
import bcrypt
import json
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "P@ssw0rd2025")
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()
empresas = carregar_empresas()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Por favor, faça login para acessar esta página.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def verificar_credenciais(usuario, senha):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT senha FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = c.fetchone()
    conn.close()
    if resultado and bcrypt.checkpw(senha.encode('utf-8'), resultado[0].encode('utf-8')):
        return True
    return False

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']
        if verificar_credenciais(usuario, senha):
            session['logged_in'] = True
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for('selecionar_empresa'))
        else:
            flash("Usuário ou senha incorretos.", "danger")
    return render_template('login.html')



@app.route('/selecionar_empresa', methods=['GET', 'POST'])
@login_required
def selecionar_empresa():
    if request.method == 'POST':
        empresa_nome = request.form['empresa']
        if empresa_nome in empresas:
            session['empresa_selecionada'] = empresa_nome
            flash(f"Empresa {empresa_nome} selecionada!", "success")
            return redirect(url_for('index'))
        else:
            flash("Empresa inválida.", "danger")
    return render_template('selecionar_empresa.html', empresas=empresas.keys())

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('empresa_selecionada', None)
    flash("Você saiu do sistema.", "info")
    return redirect(url_for('login'))

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

@app.route('/consultar_cnpj', methods=['POST'])
@login_required
def consultar_cnpj_route():
    cnpj = request.form['cnpj']
    dados = consultar_cnpj(cnpj)
    return jsonify(dados)

@app.route('/', methods=['GET'])
@login_required
def index():
    empresa_selecionada = session.get('empresa_selecionada', list(empresas.keys())[0])
    return render_template('index.html', empresas=empresas.keys(), dados_loja=None, empresa_selecionada=empresa_selecionada)

@app.route('/lista_pedidos', methods=['GET'])
@login_required
def lista_pedidos():
    empresa_selecionada = session.get('empresa_selecionada')
    if not empresa_selecionada:
        flash("Selecione uma empresa antes de continuar.", "warning")
        return redirect(url_for('selecionar_empresa'))
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT id, empresa_nome, cnpj, razao_social, itens FROM pedidos WHERE empresa_nome = %s ORDER BY id DESC", (empresa_selecionada,))
    pedidos_raw = c.fetchall()
    conn.close()
    
    pedidos = []
    for row in pedidos_raw:
        itens = json.loads(row[4])
        total = 0
        for item in itens:
            codigo = item['codigo']
            quantidades = item['quantidades']
            valor_unit = empresas[empresa_selecionada].catalogo.get(codigo, {}).get('valor', 0)
            total += valor_unit * sum(quantidades.values())
        pedidos.append({
            "id": row[0],
            "empresa_nome": row[1],
            "cnpj": row[2],
            "razao_social": row[3],
            "itens": itens,
            "total": total
        })
    return render_template('lista_pedidos.html', pedidos=pedidos, empresa_selecionada=empresa_selecionada, empresas=empresas)

@app.route('/pedido', methods=['POST'])
@login_required
def pedido():
    empresa_selecionada = session.get('empresa_selecionada')
    if not empresa_selecionada:
        flash("Selecione uma empresa antes de continuar.", "warning")
        return redirect(url_for('selecionar_empresa'))
    if request.method == 'POST':
        cnpj = request.form['cnpj']
        razao_social = request.form['razao']
        itens = []
        codigos = request.form.getlist('codigo[]')
        for i, codigo in enumerate(codigos):
            if codigo:
                item = empresas[empresa_selecionada].get_item(codigo)
                if item:
                    quantidades = {tam: int(request.form.get(f"qtd_{i}_{tam}", "0") or "0") for tam in item["tamanhos"]}
                    if any(quantidades.values()):
                        itens.append({"codigo": codigo, "quantidades": quantidades})
        if not itens:
            flash("Adicione pelo menos um item ao pedido.", "warning")
            return redirect(url_for('lista_pedidos'))
        pedido_atual = Pedido(empresas[empresa_selecionada], razao_social, cnpj)
        for item in itens:
            pedido_atual.adicionar_item(item["codigo"], item["quantidades"])
        salvar_pedido(pedido_atual)
        flash("Novo pedido criado com sucesso!", "success")
    return redirect(url_for('lista_pedidos'))

@app.route('/buscar_item/<empresa_nome>/<codigo>', methods=['GET'])
@login_required
def buscar_item(empresa_nome, codigo):
    empresa = empresas.get(empresa_nome)
    if empresa:
        item = empresa.get_item(codigo)
        if item:
            return jsonify(item)
    return jsonify({"erro": "Item não encontrado"}), 404

@app.route('/adicionar_item', methods=['POST'])
@login_required
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
    return redirect(url_for('lista_pedidos'))

@app.route('/remover_item/<int:index>')
@login_required
def remover_item(index):
    pedido_atual = carregar_ultimo_pedido(empresas)
    if pedido_atual and 0 <= index < len(pedido_atual.itens):
        pedido_atual.itens.pop(index)
        salvar_pedido(pedido_atual)
    return redirect(url_for('lista_pedidos'))

TIPOS_GRADE = ["numerico", "alfabetico", "misto"]

@app.route('/gerenciar_empresas', methods=['GET', 'POST'])
@login_required
def gerenciar_empresas():
    if request.method == 'POST':
        if 'nome' in request.form and 'tipo_grade' in request.form:
            nome = request.form['nome']
            tipo_grade = request.form['tipo_grade']
            if tipo_grade not in TIPOS_GRADE:
                flash("Tipo de grade inválido.", "danger")
            else:
                salvar_empresa(nome, tipo_grade)
                flash("Empresa salva com sucesso!", "success")
        elif 'empresa_nome' in request.form and 'codigo' in request.form:
            empresa_nome = request.form['empresa_nome']
            codigo = request.form['codigo']
            descritivo = request.form['descritivo']
            valor = float(request.form['valor'])
            tamanhos = request.form['tamanhos'].split(',')
            salvar_item_catalogo(empresa_nome, codigo, descritivo, valor, tamanhos)
            flash("Item salvo com sucesso!", "success")
        global empresas
        empresas = carregar_empresas()
    catalogos = {nome: carregar_catalogo(nome) for nome in empresas.keys()}
    empresa_selecionada = session.get('empresa_selecionada', list(empresas.keys())[0])
    return render_template('gerenciar_empresas.html', empresas=empresas, catalogos=catalogos, empresa_selecionada=empresa_selecionada, tipos_grade=TIPOS_GRADE)

@app.route('/remover_item_catalogo/<empresa_nome>/<codigo>', methods=['POST'])
@login_required
def remover_item_catalogo_route(empresa_nome, codigo):
    remover_item_catalogo(empresa_nome, codigo)
    global empresas
    empresas = carregar_empresas()
    return redirect(url_for('gerenciar_empresas'))

@app.route('/gerenciar_grades', methods=['GET', 'POST'])
@login_required
def gerenciar_grades():
    if request.method == 'POST':
        novo_tipo = request.form['novo_tipo']
        if novo_tipo and novo_tipo not in TIPOS_GRADE:
            TIPOS_GRADE.append(novo_tipo)
            flash(f"Tipo de grade '{novo_tipo}' adicionado!", "success")
        else:
            flash("Tipo de grade inválido ou já existente.", "danger")
    return render_template('gerenciar_grades.html', tipos_grade=TIPOS_GRADE)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)