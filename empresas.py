class Empresa:
    def __init__(self, nome, tipo_grade):
        self.nome = nome
        self.tipo_grade = tipo_grade
        self.catalogo = {}

    def adicionar_item(self, codigo, descritivo, valor):
        self.catalogo[codigo] = {"descritivo": descritivo, "valor": valor}