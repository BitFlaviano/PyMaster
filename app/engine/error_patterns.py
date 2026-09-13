"""Análise de erros comuns: transforma falhas em feedback pedagógico."""
from __future__ import annotations

import re

from app.engine.content import Exercise


def analyze_code_error(exercise: Exercise, code: str, error: dict | None = None) -> str | None:
    """Retorna um feedback direcionado quando o código tem problemas conhecidos."""
    lines = code.splitlines()

    # 1. Blocos sem ':' no final
    for i, line in enumerate(lines, start=1):
        s = line.strip()
        if re.match(r"^(if|elif|else|for|while|def|class|try|except|finally)\b", s):
            if s.endswith(":") is False and not s.endswith("#"):
                return (
                    f"Linha {i}: depois de `if`, `for`, `while`, `def` etc. "
                    "o Python exige dois-pontos `:` no final da linha."
                )

    # 2. Uso de '=' dentro de condição (confusão com '==')
    for i, line in enumerate(lines, start=1):
        m = re.match(r"^\s*if\s+(.*)$", line)
        if m and re.search(r"[^=!<>]=[^=]", m.group(1)):
            return (
                f"Linha {i}: você usou `=` dentro da condição. "
                "`=` atribui valor; para comparar, use `==`."
            )

    # 3. print concatenando str com outra coisa
    for i, line in enumerate(lines, start=1):
        if "print(" not in line:
            continue
        tail = re.search(r"print\((.*)\)", line)
        if not tail:
            continue
        body = tail.group(1)
        if re.search(r'"[^"]*"\s*\+|\'[^\']*\'\s*\+', body) and re.search(r"\+\s*[\w\]]", body):
            return (
                f"Linha {i}: `texto + variável` mistura tipos. "
                "Use f-string: `print(f\"...{variavel}\")` ou separe com vírgula."
            )

    # 4. Variável usada antes de ser definida (apenas quando a execução REAL falhou)
    if error is not None:
        defined: set[str] = set()
        for i, line in enumerate(lines, start=1):
            # remove literais de string (inclusive f-strings) para não confundir
            # o texto do prompt/mensagem com nomes de variáveis
            body = re.sub(r"([\"'])(?:\\.|(?!\1).)*\1", "", line)
            # identifica TODOS os alvos da atribuição da linha (inclusive desempacotamento)
            assign = re.match(r"^\s*([A-Za-z_][^=]*?)\s*=\s*[^=]", line)
            targets: set[str] = set()
            if assign:
                targets = set(re.findall(r"\b([A-Za-z_]\w*)\b", assign.group(1)))
            pattern = re.findall(r"\b([a-z_]\w*)\b", body)
            predefined = {"print", "input", "int", "str", "float", "bool", "range", "len",
                          "f", "r", "b", "u", "if", "for", "in", "and", "or", "not",
                          "True", "False", "None", "while", "else", "elif", "break",
                          "continue", "def", "return", "import", "from", "class",
                          "lambda", "is", "exit", "as"}
            for name in pattern:
                if (name not in defined and name not in predefined and name not in targets
                        and i < 50
                        and not re.match(rf"^\s*{name}\s*=", line)):
                    # só sinaliza se a linha parece usar expressão
                    if re.search(rf"({name}\s*[+\-*/=%<>(])|(print\(.*{name}|return.*{name})", body):
                        return (
                            f"Linha {i}: a variável `{name}` está sendo usada antes de ser "
                            "criada. Atribua um valor a ela antes de usá-la."
                        )
            for t in targets:
                defined.add(t)

    # 5. Erros de execução conhecidos (a partir da exceção)
    if error and error.get("class"):
        tips = {
            "NameError": "Erro de nome: uma variável não foi definida antes de ser usada.",
            "ZeroDivisionError": "Você tentou dividir por zero. Confira os valores das variáveis.",
            "IndexError": "Você acessou uma posição que não existe na lista (índice fora do limite).",
            "KeyError": "Você usou uma chave que não existe neste dicionário.",
            "ValueError": "Não foi possível converter o valor recebido para o tipo esperado.",
            "TypeError": "Você misturou tipos incompatíveis (por exemplo, texto com número).",
            "EOFError": "O código chamou `input()` mais vezes do que as entradas disponíveis.",
        }
        cls = error.get("class")
        msg = str(error.get("message", ""))
        if cls in tips:
            line_info = f" na linha {error['line']}" if error.get("line") else ""
            tip = tips[cls]
            if "concat str" in msg or "can only concatenate" in msg or "unsupported operand" in msg:
                tip = "Linha provavelmente mistura texto com número. Use f-string ou separe com vírgula."
            return f"{tip}{line_info}"
        return None

    return None


def friendly_file_error(error: dict | None) -> str | None:
    if not error:
        return None
    cls = error.get("class", "")
    msg = str(error.get("message", ""))
    if cls == "PermissionError":
        return msg
    return None