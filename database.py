# database.py
import psycopg2
import json
from empresas import Empresa
from pedidos import Pedido
import os
import bcrypt

DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

def init_db():
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS empresas (
                    nome TEXT PRIMARY KEY,
                    tipo_grade TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS catalogo (
                    empresa_nome TEXT,
                    codigo TEXT,
                    descritivo TEXT,
                    valor REAL,
                    tamanhos TEXT,
                    PRIMARY KEY (empresa_nome, codigo))''')
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos (
                    id SERIAL PRIMARY KEY,
                    empresa_nome TEXT,
                    cnpj TEXT,
                    razao_social TEXT,
                    itens JSONB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    usuario TEXT UNIQUE,
                    senha TEXT)''')
    # Inserir usuário padrão com senha hasheada
    senha_hash = bcrypt.hashpw('12345'.encode('utf-8'), bcrypt.gensalt())
    c.execute("INSERT INTO usuarios (usuario, senha) VALUES ('admin', %s) ON CONFLICT (usuario) DO NOTHING", (senha_hash.decode('utf-8'),))
    conn.commit()
    conn.close()

def carregar_empresas():
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT nome, tipo_grade FROM empresas")
    empresas = {}
    for nome, tipo_grade in c.fetchall():
        empresa = Empresa(nome, tipo_grade)
        c.execute("SELECT codigo, descritivo, valor, tamanhos FROM catalogo WHERE empresa_nome = %s", (nome,))
        catalogo = {row[0]: {"descritivo": row[1], "valor": row[2], "tamanhos": json.loads(row[3])} for row in c.fetchall()}
        empresa.catalogo = catalogo
        empresas[nome] = empresa
    conn.close()
    return empresas

def salvar_pedido(pedido):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    itens_json = json.dumps(pedido.itens)
    c.execute("INSERT INTO pedidos (empresa_nome, cnpj, razao_social, itens) VALUES (%s, %s, %s, %s) RETURNING id",
              (pedido.empresa.nome, pedido.cnpj, pedido.razao_social, itens_json))
    pedido_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return pedido_id

def carregar_ultimo_pedido(empresas):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT empresa_nome, cnpj, razao_social, itens FROM pedidos ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        empresa_nome, cnpj, razao_social, itens_json = row
        pedido = Pedido(empresas[empresa_nome], razao_social, cnpj)
        pedido.itens = json.loads(itens_json)
        return pedido
    return None

def salvar_empresa(nome, tipo_grade):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("INSERT INTO empresas (nome, tipo_grade) VALUES (%s, %s) ON CONFLICT (nome) DO UPDATE SET tipo_grade = %s",
              (nome, tipo_grade, tipo_grade))
    conn.commit()
    conn.close()

# Novas funções para o catálogo
def carregar_catalogo(empresa_nome):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT codigo, descritivo, valor, tamanhos FROM catalogo WHERE empresa_nome = %s", (empresa_nome,))
    catalogo = [
        {"codigo": row[0], "descritivo": row[1], "valor": row[2], "tamanhos": json.loads(row[3])}
        for row in c.fetchall()
    ]
    conn.close()
    return catalogo

def salvar_item_catalogo(empresa_nome, codigo, descritivo, valor, tamanhos):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    tamanhos_json = json.dumps(tamanhos)
    c.execute("""
        INSERT INTO catalogo (empresa_nome, codigo, descritivo, valor, tamanhos) 
        VALUES (%s, %s, %s, %s, %s) 
        ON CONFLICT (empresa_nome, codigo) 
        DO UPDATE SET descritivo = %s, valor = %s, tamanhos = %s
    """, (empresa_nome, codigo, descritivo, valor, tamanhos_json, descritivo, valor, tamanhos_json))
    conn.commit()
    conn.close()

def remover_item_catalogo(empresa_nome, codigo):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("DELETE FROM catalogo WHERE empresa_nome = %s AND codigo = %s", (empresa_nome, codigo))
    conn.commit()
    conn.close()