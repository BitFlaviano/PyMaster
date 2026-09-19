"""Motor de conteúdo — load, validação e consultas sobre o currículo YAML."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import CONTENT_DIR

log = logging.getLogger("pymaster.content")

VALID_TYPES = {
    "choice", "complete", "predict", "order", "find_error",
    "fix", "write", "debug",
}
VALID_DIFFICULTY = {"easy", "medium", "hard"}
VALID_BLOCK_TYPES = {
    "text", "code", "visual", "exercise_ref", "callout", "dataset_note",
}
VALID_GOALS = {
    "trabalho", "faculdade", "dados", "automacao",
    "curiosidade", "carreira", "kids", "outro",
}

DIFFICULTY_LABEL = {"easy": "Fácil", "medium": "Médio", "hard": "Difícil"}
DIFFICULTY_XP = {"easy": 15, "medium": 25, "hard": 40}


@dataclass
class LessonBlock:
    type: str
    body: str | None = None
    code: str | None = None
    kind: str | None = None          # para blocos visual: pipeline|memory|sequence|branch|frame|dataframe
    exercise_id: str | None = None
    title: str | None = None


@dataclass
class ExerciseHint:
    level: int = 1
    text: str = ""


@dataclass
class HiddenTest:
    name: str = ""
    input: str = ""
    expected: str = ""
    must_not_contain: str = ""


@dataclass
class Exercise:
    id: str
    type: str
    concept: str
    difficulty: str = "easy"
    xp: int = 0
    time_estimate: int = 120
    prompt: str = ""
    code: str | None = None
    options: list[str] = field(default_factory=list)
    answer: str | None = None          # índice (choice) ou texto (complete)
    lines: list[str] = field(default_factory=list)
    error_line: int | None = None
    buggy_code: str | None = None
    hints: list[str] = field(default_factory=list)
    tests: list[HiddenTest] = field(default_factory=list)
    solution: str | None = None
    must_include: list[str] = field(default_factory=list)
    allow_imports: list[str] = field(default_factory=list)
    common_error: str | None = None


@dataclass
class Concept:
    id: str
    level: int
    title: str
    summary: str = ""
    color: str = "#3b82f6"
    lessons: list = field(default_factory=list)      # list[Lesson]
    exercises: list = field(default_factory=list)    # list[Exercise]
    goals: list = field(default_factory=list)        # trilhas (objetivos) em que aparece


@dataclass
class Lesson:
    id: str
    concept: str
    title: str
    blocks: list[LessonBlock] = field(default_factory=list)


@dataclass
class Level:
    number: int
    slug: str
    title: str
    subtitle: str = ""


class ContentRegistry:
    def __init__(self) -> None:
        self.levels: list[Level] = []
        self.concepts: list[Concept] = []
        from app.config import EXAMPLE_DATASETS

        self.datasets: list[str] = EXAMPLE_DATASETS
        self._concepts_by_id: dict[str, Concept] = {}
        self._exercises_by_id: dict[str, Exercise] = {}
        self._lessons_by_id: dict[str, Lesson] = {}
        self._exercises_by_concept: dict[str, list[Exercise]] = {}
        self._lessons_by_concept: dict[str, list[Lesson]] = {}

    def load_all(self) -> None:
        for path in sorted(Path(CONTENT_DIR).glob("*.yaml")):
            try:
                self._load_file(path)
            except Exception as exc:  # noqa: BLE001
                log.exception("Falha ao carregar conteúdo %s: %s", path, exc)
        self.levels.sort(key=lambda lv: lv.number)
        self.concepts.sort(key=lambda c: (c.level, len(self.levels)))

    def _load_file(self, path: Path) -> None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        level_no = int(raw.get("level", 0))
        level = Level(
            number=level_no,
            slug=raw.get("slug", f"nivel-{level_no}"),
            title=raw.get("title", f"Nível {level_no}"),
            subtitle=raw.get("subtitle", ""),
        )
        if not any(lv.number == level_no for lv in self.levels):
            self.levels.append(level)
        for cdef in raw.get("concepts", []):
            concept = self._parse_concept(cdef, level_no)
            self._concepts_by_id[concept.id] = concept
            self.concepts.append(concept)
        self._check_duplicates()
        if not self.levels:
            raise ValueError(f"{path.name} sem nível")

    def _parse_concept(self, cdef: dict, level_no: int) -> Concept:
        goals = [str(g) for g in cdef.get("goals", [])]
        invalid = [g for g in goals if g not in VALID_GOALS]
        if invalid:
            raise ValueError(
                f"objetivos inválidos {invalid} em {cdef.get('id')} "
                f"(permitidos: {sorted(VALID_GOALS)})"
            )
        concept = Concept(
            id=str(cdef["id"]),
            level=level_no,
            title=str(cdef["title"]),
            summary=str(cdef.get("summary", "")),
            color=str(cdef.get("color", "#3b82f6")),
            goals=goals,
        )
        for ldef in cdef.get("lessons", []):
            lesson = self._parse_lesson(ldef, concept.id)
            lesson.concept = concept.id
            concept.lessons.append(lesson)
            self._lessons_by_id[lesson.id] = lesson
            self._lessons_by_concept.setdefault(concept.id, []).append(lesson)
        for edef in cdef.get("exercises", []):
            exercise = self._parse_exercise(edef, concept.id)
            concept.exercises.append(exercise)
            self._exercises_by_id[exercise.id] = exercise
            self._exercises_by_concept.setdefault(concept.id, []).append(exercise)
        return concept

    def _parse_lesson(self, ldef: dict, concept_id: str) -> Lesson:
        lesson = Lesson(
            id=str(ldef["id"]),
            concept=concept_id,
            title=str(ldef.get("title", ldef["id"])),
        )
        for bdef in ldef.get("blocks", []):
            btype = bdef.get("type")
            if btype not in VALID_BLOCK_TYPES:
                raise ValueError(f"bloco inválido '{btype}' em {ldef['id']}")
            lesson.blocks.append(
                LessonBlock(
                    type=btype,
                    body=bdef.get("body"),
                    code=bdef.get("code"),
                    kind=bdef.get("kind"),
                    exercise_id=bdef.get("exercise_id"),
                    title=bdef.get("title"),
                )
            )
        return lesson

    def _parse_exercise(self, edef: dict, concept_id: str) -> Exercise:
        etype = edef.get("type")
        if etype not in VALID_TYPES:
            raise ValueError(f"tipo de exercício inválido '{etype}' em {edef.get('id')}")
        difficulty = edef.get("difficulty", "easy")
        if difficulty not in VALID_DIFFICULTY:
            raise ValueError(f"dificuldade inválida '{difficulty}' em {edef.get('id')}")
        tests = []
        for tdef in edef.get("tests", []):
            tests.append(
                HiddenTest(
                    name=str(tdef.get("name", "Teste")),
                    input=str(tdef.get("input", "")),
                    expected=str(tdef.get("expected", "")),
                    must_not_contain=str(tdef.get("must_not_contain", "")),
                )
            )
        return Exercise(
            id=str(edef["id"]),
            type=etype,
            concept=concept_id,
            difficulty=difficulty,
            xp=int(edef.get("xp", DIFFICULTY_XP[difficulty])),
            time_estimate=int(edef.get("time_estimate", 120)),
            prompt=str(edef.get("prompt", "")),
            code=edef.get("code"),
            options=[str(o) for o in edef.get("options", [])],
            answer=edef.get("answer"),
            lines=[str(l) for l in edef.get("lines", [])],
            error_line=edef.get("error_line"),
            buggy_code=edef.get("buggy_code"),
            hints=[str(h) for h in edef.get("hints", [])],
            tests=tests,
            solution=edef.get("solution"),
            must_include=[str(m) for m in edef.get("must_include", [])],
            allow_imports=[str(a) for a in edef.get("allow_imports", [])],
            common_error=edef.get("common_error"),
        )

    def _check_duplicates(self) -> None:
        seen: dict[str, str] = {}
        for concept in self.concepts:
            for lesson in concept.lessons:
                self._assert_unique(seen, lesson.id, "lição")
            for exercise in concept.exercises:
                self._assert_unique(seen, exercise.id, "exercício")

    @staticmethod
    def _assert_unique(seen: dict[str, str], item_id: str, kind: str) -> None:
        if item_id in seen:
            raise ValueError(f"{kind} duplicado: {item_id}")
        seen[item_id] = item_id

    # ---- Consultas ----
    def concept(self, cid: str) -> Concept | None:
        return self._concepts_by_id.get(cid)

    def exercise(self, eid: str) -> Exercise | None:
        return self._exercises_by_id.get(eid)

    def lesson(self, lid: str) -> Lesson | None:
        return self._lessons_by_id.get(lid)

    def exercises_of(self, cid: str) -> list[Exercise]:
        return self._exercises_by_concept.get(cid, [])

    def lessons_of(self, cid: str) -> list[Lesson]:
        return self._lessons_by_concept.get(cid, [])

    def concepts_of_level(self, level_no: int) -> list[Concept]:
        return [c for c in self.concepts if c.level == level_no]

    def concepts_for(self, goal: str | None = None) -> list[Concept]:
        """Conceitos visíveis para um objetivo do onboarding.

        Conceitos sem `goals` são comuns (todas as trilhas). Conceitos com
        `goals` só aparecem para quem escolheu um daqueles objetivos. A trilha
        'kids' recebe o currículo comum básico (níveis 0-1) mais os próprios
        temas de programação para crianças.
        """
        g = goal or ""
        if g == "kids":
            return [
                c for c in self.concepts
                if (c.level <= 1 and not c.goals) or c.goals == ["kids"]
            ]
        return [c for c in self.concepts if not c.goals or g in c.goals]

    def level(self, level_no: int) -> Level | None:
        for lv in self.levels:
            if lv.number == level_no:
                return lv
        return None

    def global_order(self, concept_id: str) -> int:
        for i, c in enumerate(self.concepts):
            if c.id == concept_id:
                return i
        return -1

    def absolute_exercise_order(self, eid: str) -> int:
        order = 0
        for concept in self.concepts:
            for exc in concept.exercises:
                if exc.id == eid:
                    return order
                order += 1
        return -1


registry = ContentRegistry()


def load_content() -> ContentRegistry:
    if not registry.concepts:
        registry.load_all()
    return registry