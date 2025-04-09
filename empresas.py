class Empresa:
    def __init__(self, nome, tipo_grade, catalogo=None, endereco='', email='', telefone=''):
        self.nome = nome
        self.tipo_grade = tipo_grade
        self.catalogo = catalogo if catalogo is not None else {}
        self.endereco = endereco
        self.email = email
        self.telefone = telefone

    def adicionar_item(self, codigo, descritivo, valor, tamanhos):
        self.catalogo[codigo] = {
            "descritivo": descritivo,
            "valor": valor,
            "tamanhos": tamanhos
        }

    def get_item(self, codigo):
        return self.catalogo.get(codigo)