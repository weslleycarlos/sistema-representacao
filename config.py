import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Definir DB_CONNECTION_STRING
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")
if not DB_CONNECTION_STRING:
    raise ValueError("A variável de ambiente DB_CONNECTION_STRING não foi encontrada. Verifique o arquivo .env ou as configurações do ambiente.")


SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")  # Valor padrão
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))          # Valor padrão
SMTP_USER = os.getenv("SMTP_USER")                    # Sem valor padrão, mas sem raise imediato
SMTP_PASS = os.getenv("SMTP_PASS")                    # Sem valor padrão, mas sem raise imediato

# Verificação movida para o momento de uso, se necessário
if not DB_CONNECTION_STRING:
    raise ValueError("DB_CONNECTION_STRING deve ser configurado no .env ou no ambiente.")