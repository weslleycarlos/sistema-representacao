import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Definir DB_CONNECTION_STRING
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")
if not DB_CONNECTION_STRING:
    raise ValueError("A variável de ambiente DB_CONNECTION_STRING não foi encontrada. Verifique o arquivo .env ou as configurações do ambiente.")

# Configurações de e-mail
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
if not SMTP_USER or not SMTP_PASS:
    raise ValueError("SMTP_USER e SMTP_PASS devem ser configurados no .env para envio de e-mails.")