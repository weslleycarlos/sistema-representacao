import psycopg2
import json
from empresas import Empresa
from pedidos import Pedido, Item
import bcrypt
from config import DB_CONNECTION_STRING
import logging

logger = logging.getLogger(__name__)

def init_db():
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    
    # Tabela empresas (representadas)
    c.execute('''CREATE TABLE IF NOT EXISTS empresas (
                    nome TEXT PRIMARY KEY,
                    tipo_grade TEXT,
                    endereco TEXT,
                    email TEXT,
                    telefone TEXT)''')
    c.execute("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS endereco TEXT")
    c.execute("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS email TEXT")
    c.execute("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS telefone TEXT")
    
    # Tabela catalogo
    c.execute('''CREATE TABLE IF NOT EXISTS catalogo (
                    empresa_nome TEXT,
                    codigo TEXT,
                    descritivo TEXT,
                    valor REAL,
                    tamanhos TEXT,
                    PRIMARY KEY (empresa_nome, codigo),
                    FOREIGN KEY (empresa_nome) REFERENCES empresas(nome))''')
    
    # Tabela lojas (compradoras)
    c.execute('''CREATE TABLE IF NOT EXISTS lojas (
                    cnpj TEXT PRIMARY KEY,
                    razao_social TEXT,
                    endereco TEXT,
                    email TEXT,
                    telefone TEXT)''')
    
    # Tabela formas_pagamento
    c.execute('''CREATE TABLE IF NOT EXISTS formas_pagamento (
                    id SERIAL PRIMARY KEY,
                    nome TEXT UNIQUE)''')
    
    # Tabela pedidos
    c.execute('''CREATE TABLE IF NOT EXISTS pedidos (
                    id SERIAL PRIMARY KEY,
                    empresa_nome TEXT,
                    cnpj_loja TEXT,
                    data_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    forma_pagamento_id INTEGER,
                    desconto REAL DEFAULT 0,
                    itens JSONB,
                    FOREIGN KEY (empresa_nome) REFERENCES empresas(nome),
                    FOREIGN KEY (cnpj_loja) REFERENCES lojas(cnpj),
                    FOREIGN KEY (forma_pagamento_id) REFERENCES formas_pagamento(id))''')
    c.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS cnpj_loja TEXT")
    c.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS data_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    c.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS forma_pagamento_id INTEGER")
    c.execute("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS desconto REAL DEFAULT 0")
    c.execute("ALTER TABLE pedidos ADD FOREIGN KEY (empresa_nome) REFERENCES empresas(nome) ON DELETE CASCADE")
    c.execute("ALTER TABLE pedidos ADD FOREIGN KEY (cnpj_loja) REFERENCES lojas(cnpj) ON DELETE CASCADE")
    c.execute("ALTER TABLE pedidos ADD FOREIGN KEY (forma_pagamento_id) REFERENCES formas_pagamento(id) ON DELETE SET NULL")
    
    # Tabela usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    usuario TEXT UNIQUE,
                    senha TEXT)''')
    
    # Inserir usuário padrão
    senha_hash = bcrypt.hashpw('12345'.encode('utf-8'), bcrypt.gensalt())
    c.execute("INSERT INTO usuarios (usuario, senha) VALUES ('admin', %s) ON CONFLICT (usuario) DO NOTHING", (senha_hash.decode('utf-8'),))
    
    # Inserir forma de pagamento padrão
    c.execute("INSERT INTO formas_pagamento (nome) VALUES ('Boleto') ON CONFLICT (nome) DO NOTHING")
    
    conn.commit()
    conn.close()

def carregar_empresas():
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT nome, tipo_grade, endereco, email, telefone FROM empresas")
    empresas_dict = {}
    for row in c.fetchall():
        empresas_dict[row[0]] = Empresa(nome=row[0], tipo_grade=row[1], endereco=row[2], email=row[3], telefone=row[4])
    conn.close()
    for empresa in empresas_dict.values():
        empresa.catalogo = carregar_catalogo(empresa.nome)
        logger.info(f"Catálogo carregado para {empresa.nome}: {empresa.catalogo}")
    return empresas_dict




def salvar_empresa(nome, tipo_grade, endereco='', email='', telefone=''):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("INSERT INTO empresas (nome, tipo_grade, endereco, email, telefone) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (nome) DO UPDATE SET tipo_grade = %s, endereco = %s, email = %s, telefone = %s",
              (nome, tipo_grade, endereco, email, telefone, tipo_grade, endereco, email, telefone))
    conn.commit()
    conn.close()


def salvar_pedido(pedido):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    # Salvar loja se não existir
    c.execute("INSERT INTO lojas (cnpj, razao_social) VALUES (%s, %s) ON CONFLICT (cnpj) DO UPDATE SET razao_social = %s",
              (pedido.cnpj, pedido.razao_social, pedido.razao_social))
    # Salvar pedido
    c.execute("INSERT INTO pedidos (empresa_nome, cnpj_loja, data_compra, forma_pagamento_id, desconto, itens) VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s) RETURNING id",
              (pedido.empresa.nome, pedido.cnpj, pedido.forma_pagamento_id, pedido.desconto, json.dumps([item.to_dict() for item in pedido.itens])))
    pedido.id = c.fetchone()[0]
    conn.commit()
    conn.close()

def carregar_ultimo_pedido(empresas):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT id, empresa_nome, cnpj_loja, data_compra, forma_pagamento_id, desconto, itens FROM pedidos ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if row:
        empresa = empresas.get(row[1])
        if empresa:
            pedido = Pedido(empresa, cnpj=row[2], razao_social='')  # Razão social será carregada da tabela lojas
            pedido.id = row[0]
            pedido.data_compra = row[3]
            pedido.forma_pagamento_id = row[4]
            pedido.desconto = row[5]
            pedido.itens = [Item(codigo=item["codigo"], quantidades=item["quantidades"]) for item in json.loads(row[6])]
            return pedido
    return None

# ... (resto do código do database.py)


# Novas funções para o catálogo
def carregar_catalogo(empresa_nome):
    conn = psycopg2.connect(DB_CONNECTION_STRING)
    c = conn.cursor()
    c.execute("SELECT codigo, descritivo, valor, tamanhos FROM catalogo WHERE empresa_nome = %s", (empresa_nome,))
    catalogo = {}
    for row in c.fetchall():
        # Limpar a string de tamanhos removendo aspas extras e colchetes
        tamanhos_str = row[3].replace('["', '').replace('"]', '').replace('"', '').strip()
        tamanhos = [tam.strip() for tam in tamanhos_str.split(",")]
        catalogo[row[0]] = {
            "descritivo": row[1],
            "valor": float(row[2]),
            "tamanhos": tamanhos  # Lista limpa: ["2", "4", "6"]
        }
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