# database.py (versão final)
import sqlite3
import json
from empresas import Empresa
from pedidos import Pedido

def init_db():
    conn = sqlite3.connect('sistema.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS empresas
                 (nome TEXT PRIMARY KEY, tipo_grade TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS catalogo
                 (empresa_nome TEXT, codigo TEXT, descritivo TEXT, valor REAL, tamanhos TEXT,
                  PRIMARY KEY (empresa_nome, codigo),
                  FOREIGN KEY (empresa_nome) REFERENCES empresas(nome))''')
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa_nome TEXT, cnpj TEXT,
                  razao_social TEXT, itens TEXT,
                  FOREIGN KEY (empresa_nome) REFERENCES empresas(nome))''')
    conn.commit()
    conn.close()

def migrar_dados_iniciais():
    conn = sqlite3.connect('sistema.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM empresas WHERE nome = 'Empresa A'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO empresas (nome, tipo_grade) VALUES (?, ?)", ("Empresa A", "numerico"))
        with open('dados/empresa1.json', 'r') as f:
            catalogo = json.load(f)
            for codigo, item in catalogo.items():
                tamanhos_json = json.dumps(item["tamanhos"])
                c.execute("INSERT INTO catalogo (empresa_nome, codigo, descritivo, valor, tamanhos) VALUES (?, ?, ?, ?, ?)",
                          ("Empresa A", codigo, item["descritivo"], item["valor"], tamanhos_json))
    conn.commit()
    conn.close()

def carregar_empresas():
    conn = sqlite3.connect('sistema.db')
    c = conn.cursor()
    c.execute("SELECT nome, tipo_grade FROM empresas")
    empresas = {}
    for nome, tipo_grade in c.fetchall():
        empresa = Empresa(nome, tipo_grade)
        c.execute("SELECT codigo, descritivo, valor, tamanhos FROM catalogo WHERE empresa_nome = ?", (nome,))
        catalogo = {row[0]: {"descritivo": row[1], "valor": row[2], "tamanhos": json.loads(row[3])} for row in c.fetchall()}
        empresa.catalogo = catalogo
        empresas[nome] = empresa
    conn.close()
    return empresas

def salvar_pedido(pedido):
    conn = sqlite3.connect('sistema.db')
    c = conn.cursor()
    itens_json = json.dumps(pedido.itens)
    c.execute("INSERT INTO pedidos (empresa_nome, cnpj, razao_social, itens) VALUES (?, ?, ?, ?)",
              (pedido.empresa.nome, pedido.cnpj, pedido.razao_social, itens_json))
    conn.commit()
    conn.close()
    return c.lastrowid

def carregar_ultimo_pedido(empresas):  # Adicionado parâmetro 'empresas'
    conn = sqlite3.connect('sistema.db')
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