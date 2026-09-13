"""Gera os datasets de exemplo do PyMaster em app/data/datasets/*.csv."""
from __future__ import annotations

import csv
import random
from pathlib import Path

random.seed(42)

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "datasets"
OUT.mkdir(parents=True, exist_ok=True)

CIDADES = ["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre", "Salvador", "Fortaleza", "Recife", "Manaus", "Goiânia"]
ESTADOS = ["SP", "RJ", "MG", "PR", "RS", "BA", "CE", "PE", "AM", "GO"]
BAIRROS = ["Centro", "Jardins", "Vila Nova", "Bela Vista", "Alvorada", "Santa Cruz", "Santo Antônio", "Cidade Baixa", "Ponta Verde", "Boa Viagem"]
NOMES = ["Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Rocha", "Elisa Prado", "Felipe Nunes", "Gabriela Melo", "Henrique Dias", "Isabela Castro", "João Pedro", "Karen Alves", "Lucas Teixeira", "Mariana Farias", "Nicolas Reis", "Olivia Barros", "Paulo Câmara", "Raquel Tavares", "Samuel Duarte", "Tainá Furtado", "Vitor Hugo"]
PRODUTOS = [
    ("Teclado", "Periféricos", 129.90), ("Mouse", "Periféricos", 59.90),
    ("Monitor", "Monitores", 899.00), ("Notebook", "Informática", 3299.00),
    ("Fone Bluetooth", "Áudio", 199.90), ("Webcam", "Câmeras", 249.00),
    ("Impressora", "Impressão", 549.00), ("Cadeira Gamer", "Mobiliário", 1299.00),
    ("Mesa Compacta", "Mobiliário", 449.00), ("Roteador", "Redes", 219.90),
    ("Cabo HDMI", "Cabos", 25.90), ("SSD 512GB", "Armazenamento", 389.00),
    ("Memória RAM 16GB", "Componentes", 449.00), ("Carregador USB-C", "Energia", 79.90),
    ("Hub USB", "Conectividade", 98.00),
]


def nome_fantasia(i: int) -> str:
    return NOMES[i % len(NOMES)]


def write_csv(name: str, header: list, rows: list) -> None:
    path = OUT / name
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {name}: {len(rows):>6} linhas")


print("Gerando datasets em", OUT)

write_csv("produtos.csv", ["id_produto", "nome", "categoria", "preco", "custo", "ativo"], [
    [i, PRODUTOS[i][0], PRODUTOS[i][1], PRODUTOS[i][2],
     round(PRODUTOS[i][2] * random.uniform(0.55, 0.75), 2),
     random.choice(["sim", "sim", "sim", "nao"])]
    for i in range(len(PRODUTOS))
])

write_csv("clientes.csv", ["id_cliente", "nome", "cidade", "estado", "idade", "sexo", "renda", "criado_em"], [
    [i, nome_fantasia(i), random.choice(CIDADES), random.choice(ESTADOS), random.randint(18, 75),
     random.choice(["F", "M"]), random.randint(1800, 15000),
     f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}"]
    for i in range(1, 501)
])

with (OUT / "vendas.csv").open("w", encoding="utf-8", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["id_venda", "data", "id_cliente", "id_produto", "quantidade", "preco_unitario", "total", "canal"])
    for i in range(1, 1201):
        q = random.randint(1, 5)
        p = PRODUTOS[random.randint(1, 15) - 1][2]
        p = round(random.uniform(20, p), 2) if i % 3 else p + random.uniform(0, 1)
        writer.writerow([i, f"{random.randint(2023,2024)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                         random.randint(1, 500), random.randint(1, 15), q, round(p, 2), round(p * q, 2),
                         random.choice(["loja", "loja", "online", "online", "marketplace"])])
    print("  vendas.csv (re-gerado): 1200 linhas")

write_csv("estoque.csv", ["id_produto", "nome", "categoria", "quantidade", "capacidade", "ultima_reposicao"], [
    [i, PRODUTOS[i][0], PRODUTOS[i][1], random.randint(0, 250), random.randint(200, 500),
     f"2024-{random.randint(1,6):02d}-{random.randint(1,28):02d}"]
    for i in range(len(PRODUTOS))
])

write_csv("funcionarios.csv", ["id", "nome", "departamento", "cargo", "salario", "admissao", "idade"], [
    [i, nome_fantasia(i), random.choice(["Vendas", "TI", "Finanças", "RH", "Operações"]),
     random.choice(["Analista", "Coordenador", "Desenvolvedor", "Assistente", "Gerente"]),
     random.randint(2500, 18000), f"{random.randint(2015,2025)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
     random.randint(22, 62)]
    for i in range(1, 301)
])

write_csv("pedidos.csv", ["id_pedido", "id_cliente", "data", "status", "valor", "itens", "frete"], [
    [i, random.randint(1, 500), f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
     random.choice(["entregue", "entregue", "entregue", "enviado", "cancelado", "processando"]),
     round(random.uniform(50, 5000), 2), random.randint(1, 10), round(random.uniform(0, 50), 2)]
    for i in range(1, 901)
])

write_csv("financeiro.csv", ["mes", "ano", "receita", "despesa", "lucro", "margem"], [
    [m, ano, rec := round(random.uniform(80000, 280000), 2), des := round(random.uniform(50000, 220000), 2),
     round(rec - des, 2), round((rec - des) / rec, 3)]
    for (ano, m) in [(a, m) for a in range(2022, 2025) for m in range(1, 13)]
])

write_csv("notas.csv", ["ra", "aluno", "disciplina", "nota1", "nota2", "nota3", "media", "frequencia"], [
    [i, nome_fantasia(i), random.choice(["Matemática", "Programação", "Estatística", "Banco de Dados", "Redes"]),
     n1 := round(random.uniform(2, 10), 1), n2 := round(random.uniform(2, 10), 1), n3 := round(random.uniform(2, 10), 1),
     round((n1 + n2 + n3) / 3, 2), random.randint(65, 100)]
    for i in range(2024001, 2024601)
])

write_csv("imoveis.csv", ["id", "cidade", "bairro", "quartos", "area_m2", "preco", "tipo"], [
    [i, random.choice(CIDADES), random.choice(BAIRROS), random.randint(1, 4),
     random.randint(38, 220), random.randint(190000, 1200000),
     random.choice(["apartamento", "apartamento", "casa"])]
    for i in range(1, 701)
])

write_csv("temperaturas.csv", ["data", "cidade", "min", "max", "precipitacao"], [
    [f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}", random.choice(CIDADES),
     random.randint(-2, 18), random.randint(15, 35), round(random.uniform(0, 40), 1)]
    for i in range(1, 1501)
])

print("Concluído.")