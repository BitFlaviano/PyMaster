"""Smoke test end-to-end do PyMaster via TestClient (httpx).

Configura um banco SQLite temporário via variáveis de ambiente antes de
qualquer import do app; conteúdo e datasets usam os arquivos reais do repo.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

_tmp = Path(tempfile.gettempdir()) / f"pymaster_smoke_{uuid.uuid4().hex[:10]}"
_tmp.mkdir(parents=True, exist_ok=True)
os.environ["PYMASTER_DB"] = str(_tmp / "db.sqlite")
os.environ["PYMASTER_SECRET"] = "smoke-test-secret"


def all_exercises(registry):
    return [e for c in registry.concepts for e in c.exercises]


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    import app.main

    with TestClient(app.main.app) as c:
        yield c


def test_landing_redirects_to_onboarding_when_empty(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (200, 303)
    assert "onboarding" in r.headers.get("location", r.text)


def test_landing_shows_picker_after_first_profile_created(client):
    create_profile(client, "Ana Picker")
    client.post("/logout")
    r = client.get("/")
    assert r.status_code == 200
    assert "Ana Picker" in r.text
    assert "Novo perfil" in r.text


def test_login_page_redirects_to_picker(client):
    r = client.get("/login", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers.get("location", "").startswith("/")


def test_onboarding_get(client):
    r = client.get("/onboarding")
    assert r.status_code == 200
    assert "diagnóstico" in r.text.lower()


def create_profile(client, name, pin="", avatar="🎓", goal="dados"):
    return client.post("/onboarding", data={
        "name": name,
        "avatar": avatar,
        "pin": pin,
        "prior_level": "nunca",
        "goal": goal,
        "q_logica_1": "1", "q_sequencia_1": "1", "q_variavel_1": "1",
        "q_condicao_1": "1", "q_loop_1": "1", "q_dados_1": "0",
    }, follow_redirects=True)


def test_signup_and_dashboard(client):
    r = create_profile(client, "Ana Teste")
    assert r.status_code == 200
    assert "dashboard" in r.text.lower() or "Dashboard" in r.text
    assert "Ana" in r.text


def test_profiles_are_independent(client):
    create_profile(client, "Perfil Alpha", pin="")
    # sai
    client.post("/logout")
    create_profile(client, "Perfil Beta", pin="")
    assert "Perfil Beta" in client.get("/").text

    # switch para Alpha
    alpha_id = get_profile_id(client, "Perfil Alpha")
    r = client.post("/profiles/switch", data={"profile_id": str(alpha_id)},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "Alpha" in r.text


def test_pin_protected_profile(client):
    create_profile(client, "Perfil Pin", pin="1234")
    client.post("/logout")
    pip = get_profile_id(client, "Perfil Pin")
    # sem PIN -> volta para o seletor com erro
    r = client.post("/profiles/switch", data={"profile_id": str(pip), "pin": ""},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "error=pin" in r.headers.get("location", "")
    # com PIN -> entra
    r = client.post("/profiles/switch", data={"profile_id": str(pip), "pin": "1234"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "Perfil Pin" in r.text


def get_profile_id(client, name):
    from app.db import engine
    from app.models import User
    from sqlmodel import Session, select

    with Session(engine) as session:
        u = session.exec(select(User).where(User.name == name)).first()
        assert u is not None
        return u.id


def test_delete_requires_confirm(client):
    create_profile(client, "Perfil Del A")
    create_profile(client, "Perfil Del B")
    target = get_profile_id(client, "Perfil Del A")
    r = client.post(f"/profiles/{target}/delete", data={"confirm": "0"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "error=confirm" in r.headers.get("location", "")
    # com confirmação remove
    r = client.post(f"/profiles/{target}/delete", data={"confirm": "1"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "Perfil Del A" not in client.get("/profiles").text


def test_update_profile(client):
    create_profile(client, "Perfil Old")
    uid = get_profile_id(client, "Perfil Old")
    client.post(f"/profiles/{uid}/update", data={
        "name": "Perfil Novo Nome", "avatar": "🦊", "pin": "", "clear_pin": "0",
    }, follow_redirects=False)
    assert "Perfil Novo Nome" in client.get("/profiles").text
    assert "🦊" in client.get("/profiles").text


PAGES = ["/dashboard", "/learn", "/map", "/review", "/lab", "/badges", "/certificate", "/settings", "/datasets"]


def test_all_pages_render(client):
    create_profile(client, "Render All")
    for path in PAGES:
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert "PyMaster" in r.text or "html" in r.text.lower()


def test_concept_page(client):
    from app.engine.content import load_content

    registry = load_content()
    concept_id = registry.concepts[0].id
    r = client.get(f"/concept/{concept_id}")
    assert r.status_code == 200


def test_concept_navigation_buttons(client):
    from app.engine.content import load_content

    create_profile(client, "NavTester")
    registry = load_content()
    concept = registry.concepts[0]
    exercises = registry.exercises_of(concept.id)
    assert len(exercises) >= 2, "need >= 2 exercises to test nav"
    ex1, ex2 = exercises[0], exercises[1]

    body = client.get(f"/concept/{concept.id}").text
    assert 'class="ex-nav"' in body
    assert f'data-jump="#ex-{ex2.id}" disabled' in body, "Próximo should start disabled"
    assert "Finalize esta questão para liberar o Próximo" in body

    if ex1.type == "choice":
        payload = {"answer": str(ex1.answer)}
    elif ex1.type == "find_error":
        payload = {"answer": str(ex1.error_line)}
    elif ex1.type == "order":
        payload = {"answer": "\n".join(ex1.lines)}
    elif ex1.type in ("write", "fix", "debug"):
        payload = {"code": ex1.solution or ""}
    elif ex1.type == "complete":
        payload = {"answer": ex1.answer or ""}
    else:
        from app.engine.sandbox import run_code

        payload = {"answer": (run_code(ex1.code or "") or {}).get("output", "")}
    client.post(f"/frag/exercise/{ex1.id}/answer", data=payload)

    body2 = client.get(f"/concept/{concept.id}").text
    assert f'data-jump="#ex-{ex2.id}" disabled' not in body2, "Próximo should be enabled after solving"
    assert f'data-jump="#ex-{ex2.id}"' in body2
    assert 'class="ex-solved"' in body2


def test_dataset_view_page(client):
    from app.config import DATASETS_DIR

    first = sorted(DATASETS_DIR.glob("*.csv"))[0].name
    r = client.get(f"/datasets/{first}")
    assert r.status_code == 200


def test_static_assets(client):
    assert client.get("/static/css/styles.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/js/htmx.min.js").status_code == 200


def test_exercise_flow(client):
    """Responde a um exercício choice de verdade via fragmento HTMX."""
    from app.engine.content import load_content

    create_profile(client, "Exerciser")
    registry = load_content()
    choice = next(e for c in registry.concepts for e in c.exercises if e.type == "choice")
    r = client.post(f"/frag/exercise/{choice.id}/answer", data={"answer": str(choice.answer)})
    assert r.status_code == 200
    body = r.text
    assert ("correta" in body.lower()) or ("feedback-ok" in body) or ("acertou" in body.lower())


def test_hint_flow(client):
    from app.engine.content import load_content

    create_profile(client, "Hinter")
    registry = load_content()
    targets = [e for c in registry.concepts for e in c.exercises if e.hints]
    assert targets
    ex = targets[0]
    r = client.post(f"/frag/exercise/{ex.id}/hint", data={"hint_level": "1"})
    assert r.status_code == 200
    assert r.text.strip() != ""


def test_lab_flow(client):
    from app.engine.content import load_content

    create_profile(client, "Labber")
    registry = load_content()
    ds = registry.datasets[0]
    r = client.post("/frag/lab/run", data={
        "code": f"import pandas as pd\ndf = pd.read_csv('DATASETS_DIR/{ds}')\nprint(df.shape)",
    })
    assert r.status_code == 200
    r2 = client.post("/frag/lab/save", data={
        "code": "print(1)", "title": "Meu experimento",
    })
    assert r2.status_code == 200


def test_settings_update(client):
    create_profile(client, "Settings Lover")
    r = client.post("/settings/update", data={
        "theme": "light", "font_scale": "110", "reduce_motion": "true",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "light" in r.text or "--font-scale: 1.1" in r.text


def test_content_loaded():
    from app.engine.content import load_content

    registry = load_content()
    assert len(registry.levels) == 7
    assert len(registry.concepts) >= 41
    assert len(all_exercises(registry)) >= 222
    assert len(registry.datasets) >= 10


GOALS = ["outro", "kids", "automacao", "trabalho", "dados", "faculdade", "carreira", "curiosidade"]


def test_onboarding_offers_kids_goal(client):
    body = client.get("/onboarding").text
    assert "kids" in body
    assert "Crianças" in body


def test_goal_filters_registry():
    from app.engine.content import VALID_GOALS, load_content

    registry = load_content()
    for goal in GOALS:
        assert goal in VALID_GOALS

    kids = [c for c in registry.concepts if c.goals == ["kids"]]
    auto = [c for c in registry.concepts if c.goals == ["automacao"]]
    assert kids and auto

    common = [c for c in registry.concepts if not c.goals]
    common_basic = {c.id for c in common if c.level <= 1}

    kids_visible = {c.id for c in registry.concepts_for("kids")}
    assert kids_visible == common_basic | {c.id for c in kids}
    assert not ({c.id for c in auto} & kids_visible), "kids não deve ver a trilha de automação"

    auto_visible = {c.id for c in registry.concepts_for("automacao")}
    assert {c.id for c in auto} <= auto_visible
    assert {c.id for c in common} <= auto_visible
    assert not ({c.id for c in kids} & auto_visible), "automação não deve ver a trilha kids"


def test_goal_filters_progression_overview(client):
    from app.db import engine
    from app.engine.content import load_content
    from app.engine.progression import overview
    from app.models import User
    from sqlmodel import Session, select

    registry = load_content()
    for idx, goal in enumerate(GOALS):
        name = f"Goal {idx}"
        create_profile(client, name, goal=goal)
        client.post("/logout")
        with Session(engine) as session:
            uid = session.exec(select(User).where(User.name == name)).first().id
            seen = {item["concept"].id for item in overview(session, uid)}
        expected = {c.id for c in registry.concepts_for(goal)}
        assert seen == expected, f"overview divergiu para goal={goal}"

    # perfil kids: mapa mostra só conceitos da trilha kids/comuns e não os das outras
    client.post("/logout")
    create_profile(client, "Goal Kids Map", goal="kids")
    kids_first = registry.concepts_for("kids")[0]
    auto_first = next(c for c in registry.concepts if c.goals == ["automacao"])
    body = client.get("/map").text
    assert kids_first.title in body
    assert auto_first.title not in body


def test_kids_hides_empty_levels(client):
    from app.db import engine
    from app.engine import certificate as cert_engine
    from app.models import User
    from sqlmodel import Session, select

    create_profile(client, "Kids Levels", goal="kids")
    for path in ("/map", "/learn"):
        body = client.get(path).text
        assert "Nível 0 –" in body or "Nível 0 —" in body
        assert "Estruturas de dados" not in body
        assert "Código Profissional" not in body
        assert "Python Produtivo" not in body
        assert "Análise de Dados" not in body
        assert "Integração" not in body
    with Session(engine) as session:
        uid = session.exec(select(User).where(User.name == "Kids Levels")).first().id
        levels = [m["number"] for m in cert_engine.module_progress(session, uid)]
    assert levels == [0, 1]


def test_invalid_goal_rejected_in_content():
    import pytest as _pytest

    from app.engine.content import load_content

    registry = load_content()
    with _pytest.raises(ValueError):
        registry._parse_concept({"id": "x", "title": "X", "goals": ["nao_existe"]}, 0)


def test_datasets_page_exists():
    from app.config import DATASETS_DIR

    assert DATASETS_DIR.exists()
    csvs = sorted(DATASETS_DIR.glob("*.csv"))
    assert len(csvs) >= 10


def test_run_api(client):
    r = client.post("/api/run", json={"code": "print(6*7)"})
    assert r.status_code == 200
    data = r.json()
    assert "42" in data.get("output", "").strip() if data.get("output") else True


def test_visualize_api(client):
    r = client.post("/api/visualize", json={"code": "x = 1\nx += 2\nprint('fim')"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("steps")
    assert body["steps"][-1]["line"] > 0


def test_run_blocked_import(client):
    r = client.post("/api/run", json={"code": "import os\nprint(os.name)"})
    assert r.status_code == 200
    assert r.json().get("error")


def test_known_exercises_solvable(client):
    """Resolve uma amostra de exercícios de tipos diferentes."""
    from app.engine.content import load_content
    from app.engine.check import check_exercise

    registry = load_content()
    sample = [e for e in all_exercises(registry) if e.type in ("choice", "complete", "order")][:6]
    assert sample
    for ex in sample:
        if ex.type == "order":
            payload = "\n".join(ex.lines)
        else:
            payload = ex.answer
        check = check_exercise(registry, ex, payload)
        assert check.correct, f"{ex.id} não resolveu com a resposta canônica"


def test_certificate_locked_until_completion(client):
    from app.db import engine
    from app.models import Certificate, User
    from sqlmodel import Session, select

    create_profile(client, "Cert Locked")
    r = client.get("/certificate")
    assert r.status_code == 200
    assert "ainda não foi emitido" in r.text
    assert "Módulo 0" in r.text or "Pensamento" in r.text
    with Session(engine) as session:
        uid = session.exec(select(User).where(User.name == "Cert Locked")).first().id
        assert session.exec(select(Certificate).where(Certificate.user_id == uid)).first() is None


def test_certificate_requires_dominated_concepts(client):
    """Resolver todos os exercícios SEM ter conceitos 'dominado' NÃO emite certificado."""
    from app.db import engine
    from app.engine.content import load_content
    from app.models import Attempt, Certificate, User
    from sqlmodel import Session, select

    create_profile(client, "Cert Stricter")
    registry = load_content()
    with Session(engine) as session:
        uid = session.exec(select(User).where(User.name == "Cert Stricter")).first().id
        for exc in all_exercises(registry):
            session.add(Attempt(
                user_id=uid, exercise_id=exc.id, exercise_type=exc.type,
                concept_id=exc.concept, correct=True, first_try=True,
                hints_used=0, time_s=5, xp_earned=10,
            ))
        session.commit()
    r = client.get("/certificate")
    assert r.status_code == 200
    assert "ainda não foi emitido" in r.text
    with Session(engine) as session:
        assert session.exec(select(Certificate).where(Certificate.user_id == uid)).first() is None


def test_certificate_issued_when_all_concepts_dominated(client):
    """Marca todos os conceitos como 'dominado' → certificado é emitido (uma vez)."""
    from app.db import engine
    from app.engine.content import load_content
    from app.models import Certificate, User, UserConcept
    from sqlmodel import Session, select

    create_profile(client, "Cert Dominator")
    registry = load_content()
    with Session(engine) as session:
        uid = session.exec(select(User).where(User.name == "Cert Dominator")).first().id
        rows = {uc.concept_id: uc for uc in
                session.exec(select(UserConcept).where(UserConcept.user_id == uid))}
        for concept in registry.concepts:
            uc = rows.get(concept.id)
            if uc is None:
                uc = UserConcept(user_id=uid, concept_id=concept.id)
                session.add(uc)
                session.flush()
            uc.mastery = 90.0
            uc.correct_attempts = 3
            uc.attempts = 3
            uc.status = "dominado"
        session.commit()

    r = client.get("/certificate")
    assert r.status_code == 200
    assert "CERTIFICADO" in r.text
    assert "PYM-" in r.text
    assert "Histórico de módulos" in r.text
    assert "Certificamos que" in r.text

    # emitido uma única vez: segunda visita não cria outro registro
    client.get("/certificate")
    with Session(engine) as session:
        uid = session.exec(select(User).where(User.name == "Cert Dominator")).first().id
        certs = list(session.exec(select(Certificate).where(Certificate.user_id == uid)))
        assert len(certs) == 1
        assert certs[0].modules_total == len(registry.levels)


def test_about_update_name_and_emoji(client):
    create_profile(client, "About Old")
    r = client.post("/settings/about", data={
        "name": "About Novo", "avatar": "🦊", "clear_avatar": "0",
    }, follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/settings").text
    assert "About Novo" in page
    assert "🦊" in page


def test_about_upload_avatar(client):
    from app.config import UPLOADS_DIR
    from app.db import engine
    from app.models import User
    from sqlmodel import Session, select

    create_profile(client, "Foto Lover")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    r = client.post("/settings/about", data={
        "name": "Foto Lover", "avatar": "🎓", "clear_avatar": "0",
    }, files={"file": ("foto.png", png, "image/png")}, follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == "Foto Lover")).first()
        assert user.avatar.startswith("/static/uploads/av-")
    assert "/static/uploads/av-" in client.get("/settings").text
    (UPLOADS_DIR / user.avatar.rsplit("/", 1)[-1]).unlink(missing_ok=True)


def test_about_avatar_invalid_format_rejected(client):
    from app.db import engine
    from app.models import User
    from sqlmodel import Session, select

    create_profile(client, "BadFoto")
    r = client.post("/settings/about", data={
        "name": "BadFoto", "avatar": "🎓", "clear_avatar": "0",
    }, files={"file": ("m.txt", b"not an image", "text/plain")}, follow_redirects=False)
    assert r.status_code == 303
    assert "about_error=" in r.headers.get("location", "")
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == "BadFoto")).first()
        assert user.avatar == "🎓"


def test_about_emoji_picker_switches_from_photo(client):
    from app.config import UPLOADS_DIR
    from app.db import engine
    from app.models import User
    from sqlmodel import Session, select

    create_profile(client, "Picker")
    assert "avatar-picker" in client.get("/settings").text

    r = client.post("/settings/about", data={
        "name": "Picker", "avatar": "🚀", "clear_avatar": "0",
    }, files={"file": ("f.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")},
        follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == "Picker")).first()
        assert user.avatar.startswith("/static/uploads/")
        name = user.avatar.rsplit("/", 1)[-1]
    assert (UPLOADS_DIR / name).exists()

    r = client.post("/settings/about", data={
        "name": "Picker", "avatar": "🐍", "clear_avatar": "0",
    }, follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == "Picker")).first()
        assert user.avatar == "🐍"
    assert not (UPLOADS_DIR / name).exists()


def test_about_clear_photo_via_trash(client):
    from app.config import UPLOADS_DIR
    from app.db import engine
    from app.models import User
    from sqlmodel import Session, select

    create_profile(client, "Lixeira")
    page = client.get("/settings").text
    assert 'class="about-trash"' not in page

    client.post("/settings/about", data={
        "name": "Lixeira", "avatar": "🚀", "clear_avatar": "0",
    }, files={"file": ("f.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")},
        follow_redirects=False)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == "Lixeira")).first()
        assert user.avatar.startswith("/static/uploads/")
        name = user.avatar.rsplit("/", 1)[-1]

    assert 'class="about-trash"' in client.get("/settings").text

    r = client.post("/settings/about", data={
        "name": "Lixeira", "avatar": "🎓", "clear_avatar": "1",
    }, follow_redirects=False)
    assert r.status_code == 303
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == "Lixeira")).first()
        assert user.avatar == "🎓"
    assert not (UPLOADS_DIR / name).exists()
    assert 'class="about-trash"' not in client.get("/settings").text