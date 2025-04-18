from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from empresas import Empresa
from pedidos import Pedido, Item
from database import init_db, carregar_empresas, salvar_pedido, carregar_ultimo_pedido, salvar_empresa, carregar_catalogo, salvar_item_catalogo, remover_item_catalogo
import requests
import os
import logging
import psycopg2
import json
from functools import wraps
import bcrypt
from config import DB_CONNECTION_STRING, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
import smtplib
from email.mime.text import MIMEText
from flask import send_from_directory

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "P@ssw0rd2025")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(f"DB_CONNECTION_STRING carregada: {DB_CONNECTION_STRING}")

init_db()
empresas = carregar_empresas()

conn = psycopg2.connect(DB_CONNECTION_STRING)
c = conn.cursor()
c.execute("SELECT id, nome FROM formas_pagamento")
formas_pagamento = [{"id": row[0], "nome": row[1]} for row in c.fetchall()]
conn.close()

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

def enviar_email_pedido(pedido):
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP_USER ou SMTP_PASS não configurados. E-mail não será enviado.")
        flash("Envio de e-mail desativado: configurações SMTP ausentes.", "warning")
        return
    try:
        logger.info(f"Tentando enviar e-mail para {pedido.email} via {SMTP_HOST}:{SMTP_PORT}")
        assunto = f"Pedido #{pedido.id} - {pedido.empresa.nome}"
        corpo = f"""Novo Pedido Criado
ID do Pedido: {pedido.id}
Empresa Representada: {pedido.empresa.nome}
CNPJ da Loja: {pedido.cnpj}
Razão Social: {pedido.razao_social}
Data: {pedido.data_compra}

Itens:
"""
        total_geral = 0
        for item in pedido.itens:
            codigo = item.codigo
            catalogo_item = pedido.empresa.catalogo.get(codigo, {})
            descritivo = catalogo_item.get("descritivo", "Desconhecido")
            valor_unit = catalogo_item.get("valor", 0)
            quantidades = item.quantidades
            total_item = sum(qtd * valor_unit for tam, qtd in quantidades.items())
            total_geral += total_item
            corpo += f"- {codigo} - {descritivo}: {quantidades} (Total: R$ {total_item:.2f})\n"
        
        desconto_percentual = pedido.desconto  # Agora em percentual (ex.: 10 para 10%)
        desconto_valor = total_geral * (desconto_percentual / 100)
        total_liquido = total_geral - desconto_valor
        
        corpo += f"""
Total Geral: R$ {total_geral:.2f}
Desconto: {desconto_percentual:.2f}% (R$ {desconto_valor:.2f})
Total Líquido: R$ {total_liquido:.2f}
Forma de Pagamento: {next((fp['nome'] for fp in formas_pagamento if fp['id'] == pedido.forma_pagamento_id), 'Desconhecida')}
"""
        msg = MIMEText(corpo)
        msg['Subject'] = assunto
        msg['From'] = SMTP_USER
        msg['To'] = pedido.email
        logger.info("Iniciando conexão SMTP com TLS...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            logger.info(f"Autenticando como {SMTP_USER}...")
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
            logger.info(f"E-mail enviado para {pedido.email} com sucesso.")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Falha na autenticação SMTP: {str(e)}", exc_info=True)
        flash("Erro de autenticação ao enviar o e-mail. Verifique as credenciais SMTP.", "danger")
    except smtplib.SMTPException as e:
        logger.error(f"Erro SMTP ao enviar e-mail: {str(e)}", exc_info=True)
        flash("Erro ao enviar o e-mail devido a um problema no servidor SMTP.", "danger")
    except Exception as e:
        logger.error(f"Erro inesperado ao enviar e-mail: {str(e)}", exc_info=True)
        flash("Erro inesperado ao enviar o e-mail do pedido.", "danger")
        
@app.route('/pedido', methods=['POST'])
@login_required
def pedido():
    try:
        empresa_selecionada = session.get('empresa_selecionada')
        if not empresa_selecionada:
            flash("Selecione uma empresa antes de continuar.", "warning")
            return redirect(url_for('selecionar_empresa'))
        
        # Obter dados do formulário
        cnpj = request.form['cnpj']
        razao_social = request.form['razao']
        telefone = request.form.get('telefone', '')
        email = request.form.get('email', '')
        endereco = request.form.get('endereco', '')
        forma_pagamento_id = int(request.form['forma_pagamento'])
        desconto = float(request.form.get('desconto', 0.0))
        
        # Processar itens
        itens = []
        codigos = request.form.getlist('codigo[]')
        for i, codigo in enumerate(codigos):
            if codigo:
                item = empresas[empresa_selecionada].get_item(codigo)
                if item:
                    tamanhos = item["tamanhos"]
                    quantidades = {tam: int(request.form.get(f"qtd_{i}_{tam}", "0") or "0") for tam in tamanhos}
                    if any(qtd > 0 for qtd in quantidades.values()):
                        itens.append({"codigo": codigo, "quantidades": quantidades})
        
        # Criar e salvar pedido
        pedido_atual = Pedido(
            empresas[empresa_selecionada], 
            razao_social, 
            cnpj, 
            forma_pagamento_id, 
            desconto,
            telefone=telefone,
            email=email,
            endereco=endereco
        )
        
        for item in itens:
            pedido_atual.adicionar_item(item["codigo"], item["quantidades"])
        
   
        salvar_pedido(pedido_atual)
        
        if pedido_atual.email:
            enviar_email_pedido(pedido_atual)
        
        flash("Novo pedido criado com sucesso!", "success")
        
        # Buscar os pedidos atualizados diretamente do banco
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        c = conn.cursor()
        c.execute("""
            SELECT p.id, p.empresa_nome, p.cnpj_loja, p.data_compra, p.forma_pagamento_id, p.desconto, p.itens, l.razao_social
            FROM pedidos p
            JOIN lojas l ON p.cnpj_loja = l.cnpj
            WHERE p.empresa_nome = %s
            ORDER BY p.id DESC
        """, (empresa_selecionada,))
        pedidos_raw = c.fetchall()
        conn.close()
        
        # Processar os pedidos como você já faz
        catalogo = empresas[empresa_selecionada].catalogo
        pedidos = []
        for row in pedidos_raw:
            itens = json.loads(row[6])
            total_geral = 0
            for item in itens:
                codigo = item['codigo']
                quantidades = item['quantidades']
                valor_unit = empresas[empresa_selecionada].catalogo.get(codigo, {}).get('valor', 0)
                total_geral += valor_unit * sum(quantidades.values())
            desconto_percentual = row[5]
            desconto_valor = total_geral * (desconto_percentual / 100)
            total_liquido = total_geral - desconto_valor
            pedidos.append({
                "id": row[0],
                "empresa_nome": row[1],
                "cnpj_loja": row[2],
                "data_compra": row[3],
                "forma_pagamento_id": row[4],
                "desconto": desconto_percentual,
                "desconto_valor": desconto_valor,
                "itens": itens,
                "razao_social": row[7],
                "total_geral": total_geral,
                "total_liquido": total_liquido
            })
        
        # Renderizar o template com os pedidos atualizados
        return render_template('lista_pedidos.html', 
                            catalogo_data=catalogo, 
                            pedidos=pedidos, 
                            empresa_selecionada=empresa_selecionada, 
                            empresas=empresas, 
                            formas_pagamento=formas_pagamento)
        
    except Exception as e:
        logger.error(f"Erro ao processar pedido: {str(e)}", exc_info=True)
        flash("Erro ao processar o pedido. Por favor, tente novamente.", "danger")
        return redirect(url_for('lista_pedidos'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('.', 'favicon.ico')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('.', 'sw.js')


@app.route('/buscar_catalogo/<empresa>', methods=['GET'])
@login_required
def buscar_catalogo(empresa):
    if empresa in empresas:
        return jsonify(empresas[empresa].catalogo)
    return jsonify({"erro": "Empresa não encontrada"}), 404

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
        return {"error": "CNPJ não encontrado ou limite excedido"}
    except Exception as e:
        return {"error": str(e)}

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
    c.execute("""
        SELECT p.id, p.empresa_nome, p.cnpj_loja, p.data_compra, p.forma_pagamento_id, p.desconto, p.itens, l.razao_social
        FROM pedidos p
        JOIN lojas l ON p.cnpj_loja = l.cnpj
        WHERE p.empresa_nome = %s
        ORDER BY p.id DESC
    """, (empresa_selecionada,))
    pedidos_raw = c.fetchall()
    conn.close()
    # Corrigir a obtenção do catálogo
    catalogo = empresas[empresa_selecionada].catalogo  # Usar o catálogo diretamente do objeto empresa
    pedidos = []
    for row in pedidos_raw:
        itens = json.loads(row[6])
        total_geral = 0
        for item in itens:
            codigo = item['codigo']
            quantidades = item['quantidades']
            valor_unit = empresas[empresa_selecionada].catalogo.get(codigo, {}).get('valor', 0)
            total_geral += valor_unit * sum(quantidades.values())
        desconto_percentual = row[5]  # Agora em percentual
        desconto_valor = total_geral * (desconto_percentual / 100)
        total_liquido = total_geral - desconto_valor
        pedidos.append({
            "id": row[0],
            "empresa_nome": row[1],
            "cnpj_loja": row[2],
            "data_compra": row[3],
            "forma_pagamento_id": row[4],
            "desconto": desconto_percentual,
            "desconto_valor": desconto_valor,
            "itens": itens,
            "razao_social": row[7],
            "total_geral": total_geral,
            "total_liquido": total_liquido
        })
    return render_template('lista_pedidos.html', catalogo_data=catalogo, pedidos=pedidos, empresa_selecionada=empresa_selecionada, empresas=empresas, formas_pagamento=formas_pagamento)

@app.route('/remover_item/<int:index>')
@login_required
def remover_item(index):
    pedido_atual = carregar_ultimo_pedido(empresas)
    if pedido_atual and 0 <= index < len(pedido_atual.itens):
        pedido_atual.itens.pop(index)
        salvar_pedido(pedido_atual)
    return redirect(url_for('lista_pedidos'))

TIPOS_GRADE = ["numerico", "alfabetico", "misto"]

@app.route('/ping', methods=['HEAD', 'GET'])
def ping():
    return '', 200

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
    empresas[empresa_nome].catalogo = carregar_catalogo(empresa_nome)  # Recarregar apenas o catálogo da empresa
    flash("Item removido do catálogo com sucesso!", "success")
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