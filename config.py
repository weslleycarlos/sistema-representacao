import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Definir DB_CONNECTION_STRING
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")
if not DB_CONNECTION_STRING:
    raise ValueError("A variável de ambiente DB_CONNECTION_STRING não foi encontrada. Verifique o arquivo .env ou as configurações do ambiente.")