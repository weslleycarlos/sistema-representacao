class Item:
    def __init__(self, codigo, quantidades):
        self.codigo = codigo
        self.quantidades = quantidades

    def to_dict(self):
        return {"codigo": self.codigo, "quantidades": self.quantidades}

class Pedido:
    def __init__(self, empresa, razao_social, cnpj, forma_pagamento_id=1, desconto=0.0):
        self.id = None
        self.empresa = empresa
        self.razao_social = razao_social
        self.cnpj = cnpj
        self.data_compra = None
        self.forma_pagamento_id = forma_pagamento_id
        self.desconto = desconto
        self.itens = []

    def adicionar_item(self, codigo, quantidades):
        self.itens.append(Item(codigo, quantidades))