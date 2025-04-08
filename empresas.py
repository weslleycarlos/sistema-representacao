# empresas.py
class Empresa:
    def __init__(self, nome, tipo_grade):
        self.nome = nome
        self.tipo_grade = tipo_grade
        self.catalogo = {}

    def get_item(self, codigo):
        return self.catalogo.get(codigo, None)