class Pedido:
    def __init__(self, empresa, razao_social, cnpj):
        self.empresa = empresa
        self.razao_social = razao_social
        self.cnpj = cnpj
        self.itens = []

    def adicionar_item(self, codigo, quantidades):
        item = self.empresa.get_item(codigo)
        if item:
            total = sum(quantidades.values()) * item["valor"]
            self.itens.append({
                "codigo": codigo,
                "descritivo": item["descritivo"],
                "valor_unit": item["valor"],
                "quantidades": quantidades,
                "total": total
            })