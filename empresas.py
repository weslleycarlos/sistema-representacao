import json

class Empresa:
    def __init__(self, nome, tipo_grade):
        self.nome = nome
        self.tipo_grade = tipo_grade  # "numerico" ou "alfabetico"
        self.catalogo = {}

    def carregar_catalogo(self, arquivo):
        with open(arquivo, 'r') as f:
            self.catalogo = json.load(f)

    def get_item(self, codigo):
        return self.catalogo.get(codigo, None)