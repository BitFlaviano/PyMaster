# PyMaster

Aprenda Python dominando dados — uma plataforma local, completa e orientada a perfis.

Você não aprende decorando código: o PyMaster é um curso + tutor inteligente + laboratório + jogo.
Cada **perfil** tem XP, nível, domínio por conceito, repetição espaçada e conquistas próprias —
tudo salvo **somente neste dispositivo** (SQLite local).

## Como rodar

**Windows:** dê dois cliques em `run.bat` (cria o venv, instala dependências, gera os datasets na
primeira vez e sobe o servidor) e abra <http://127.0.0.1:8000>.

**Manual:**

```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\generate_datasets.py
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Perfis

- Na primeira abertura, um questionário diagnóstico define seu nível inicial.
- No seletor de perfis você cria quantos perfis quiser; cada um tem progresso **independente**.
- Perfis podem ter um **PIN** opcional de proteção (com PIN, só entra digitando-o).
- Troque de perfil pelo menu no canto superior direito, a qualquer momento.
- Gerenciamento completo (renomear, avatar, PIN, excluir) fica em **Ajustes → Perfis**.

## Recursos

- **Trilha adaptativa** — 2 níveis, 13 conceitos, 13 lições e 43 exercícios
  (escolha, completar, prever saída, ordenar, achar o erro, corrigir, escrever, depurar).
- **Laboratório real** — escreva e execute Python com pandas/lendo os datasets de exemplo,
  de forma isolada (imports sensíveis bloqueados, timeout, saída limitada, sem escrita em disco).
- **Visualizador passo a passo** — veja seu código rodando linha a linha, com quadro de variáveis.
- **Feedback inteligente** — erros comuns (nome errado, lógica, sintaxe) viram dicas úteis.
- **Revisão espaçada** — intervalos 1→2→4→7→14→30 dias por conceito.
- **Gamificação** — XP com multiplicadores (primeira tentativa, revisão), níveis/títulos,
  streak diário e conquistas.
- **Certificado de conclusão** — ao dominar todos os conceitos de todos os módulos
  (status DOMINADO), um certificado com frente moderna e verso com histórico de módulos,
  porcentagens e conquistas é emitido.
- **Mapa de domínio** e dashboard com próximo passo recomendado.
- **10 datasets de exemplo** (vendas, clientes, notas, imóveis, etc.) para praticar análise de dados.
- **Visual moderno** — tema escuro/claro, ajuste de tamanho de texto, modo "reduzir animações".

## Testes

```
.venv\Scripts\python.exe -m pytest
```

22+ testes de ponta a ponta: sandbox, conteúdo, perfis (independência e PIN),
exercícios, laboratório, páginas e assets.

## Estrutura

```
app/
  config.py            # configurações, limites do sandbox
  db.py / models.py    # SQLite local (SQLModel)
  security.py          # hash de senha/PIN + cookie de sessão
  engine/
    content.py         # currículo (YAML) e registry
    sandbox.py/_runner.py  # executor isolado
    check.py           # correção por tipo de exercício
    progression.py     # domínio adaptativo e desbloqueio
    review.py          # repetição espaçada
    xp.py / badges.py  # gamificação
    certificate.py     # certificado de conclusão (emissão e histórico)
    diagnostic.py      # onboarding adaptativo
  router/              # páginas, fragmentos HTMX e API JSON
  templates/           # Jinja2
  static/css/styles.css  # design system (dark/light)
  static/js/app.js     # editor, visualizador, laboratório
scripts/generate_datasets.py  # regenera os CSVs de exemplo
```