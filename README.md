# omp-agent-persona — developer-персона для Oh My Pi (omp)

**Парадигма: минимальный надёжный контекст.** Персона — это не конвейер,
который гоняет каждый запрос через SDD-цикл и все гейты, а минимум
структуры, который вмешивается, когда задача реально этого требует.
По умолчанию агент делает работу напрямую (правка → тест → коммит);
SDD-цикл, quality-гейты и субагенты подключаются по размеру задачи,
а не «на всякий случай». Уход от оверинженеринга — принцип №0 в
`AGENTS.md`: процесс-шаг заслуживает место только исправлением сбоя,
который случился на самом деле.

Состав: eng-gates (детерминированные quality-гейты), навыки
reversing / writing-docs / coordinating, референс-агенты omp.
Для домашнего использования с любыми доступными провайдерами моделей.

## Когда какая тяжёлая артиллерия включается

Дефолт — прямой путь. Всё остальное — эскалация по размеру задачи:

```mermaid
flowchart TD
    R["запрос"] --> D{"размер?"}
    D -->|"правка одного юнита"| Q["правка → тест → коммит"]
    D -->|"3+ задач / несколько владельцев"| B["brainstorming → writing-plans"]
    B --> S["subagent-driven-development: волны sdd-агентов"]
    S --> T["gate fast после каждого юнита"]
    T --> G["gate full перед done"]
    G --> F["sdd-final-reviewer: ревью всей ветки"]
    F --> M["finishing-a-development-branch"]
    Q --> M
```

Составные части:

| Слой | Что делает | Где живёт |
|---|---|---|
| Разведка | параллельные `scout`-агенты (один `task`-вызов, скаут на направление) перед планированием большой задачи | бандл omp + superpowers |
| Дизайн и план | `brainstorming` → `writing-plans`: вопросы по одному, короткий дизайн, план `docs/plans/<date>-<name>.md` с волнами | плагин superpowers |
| Реализация | `subagent-driven-development`: свежий `sdd-implementer` на задачу (TDD, коммит, report-file), параллельные волны в git-worktree | плагин superpowers |
| Ревью кода | `sdd-reviewer` (спека+качество, structured output), `sdd-rereviewer` (вердикт по правкам), `sdd-escalation-implementer` (3-й раунд фикс), `sdd-final-reviewer` (вся ветка) | плагин superpowers |
| Quality-гейты | `gate fast` на юните, `gate full` перед done; guard'ы от ослабления гейтов | `skills/eng-gates/` этого репо |
| Финал | `finishing-a-development-branch`: merge / PR / discard | плагин superpowers |

Ключевая идея: контроллер (сессия) не пишет код - он супервайзит свежих
субагентов с изолированным контекстом на каждую задачу. Результат агента
валидируется **детерминированными инструментами**, а не мнением модели.

## Инструменты для quality-чеков

Матрица по языкам и этапам (полная версия - в `AGENTS.md`):

| Что проверяем | Rust | Python | JS/TS | Этап |
|---|---|---|---|---|
| Формат | rustfmt | ruff format | eslint/prettier | fast |
| Линт | clippy `-D warnings` | ruff check | eslint `--max-warnings 0` | fast |
| Типы | clippy | pyright strict | tsc `--noEmit` | fast |
| Тесты | cargo-nextest | pytest `-q -x` | vitest run | fast |
| Границы модулей | workspace-крейты + cargo-deny (bans) | import-linter | dependency-cruiser | fast |
| Мёртвый код и зависимости | cargo-machete | deptry | knip | full |
| Публичный API | cargo-semver-checks (только published-крейты) | - | api-extractor (только библиотеки) | full |
| Сложность | clippy::cognitive_complexity | ruff C901/PLR091x | eslint complexity | fast |
| CRAP-скор | crapper (ub-набор) | crapper | crapper | full, точечно |
| Дубликация | dryer | dryer | dryer | full, точечно |
| Мутационное тестирование | cargo-mutants или mutator | mutmut или mutator | Stryker или mutator | full, точечно |
| Микробенчмарки | divan (CodSpeed-режим) или criterion | pytest-codspeed или pytest-benchmark | tinybench | full, только hot-path |
| Профилирование (не гейт) | flamegraph, DHAT, samply | py-spy, scalene, memray | node `--cpu-prof` | по подозрению |

Правила баланса:

- **fast (90% юнитов)** - формат+линт+типы+тесты+границы, секунды, только
  изменённые файлы. Не начинать следующий юнит, пока fast красный.
- **full (перед done/ревью/пушем)** - плюс мёртвый код, semver/api-extractor
  (только публичные API), CRAP/дубликация/мутации точечно (худший файл, не
  весь репо), бенчмарки только если юнит трогал hot-path.
- **Профилировщики никогда не в гейтах**: wall-clock на шумной машине - не
  гейт. Детерминированные альтернативы: CodSpeed simulation, gungraun
  (Linux), сохранённый baseline + budget.
- **Не стакать линтеры**: ruff закрывает формат+линт+сложность Python;
  eslint - JS/TS. Второй линтер поверх - излишек.
- CI (шаблон `ci-github.yml` в скилле): fast на PR, full на merge в main.

## Состав репозитория

- `persona-dev.yml` — конфиг-оверлей (`omp --config persona-dev.yml`).
- `persona-dev-prompt.md` — приложение к системному промпту
  (`--append-system-prompt`): явные разрешения на `gate.py approve` и
  `install-tools.sh --python --ub`.
- `AGENTS.md` — контекст-файл: принципы (включая №0 — простота важнее
  процесса), правила эскалации workflow по размеру задачи, многоагентная
  сеть (A2A), группы скиллов. Матрица инструментов вынесена в
  `skills/eng-gates/references/gates.md` и грузится по требованию.
- `skills/eng-gates/` — скилл гейтов целиком: `gate.py`, `install-tools.sh`,
  шаблоны конфигов (rust/python/ts/common), CI-шаблон.
- `skills/reversing/` — реверс-инжиниринг артефактов без исходников:
  bunfs/Mach-O/ELF, минифицированные бандлы, бинарные форматы, протоколы.
  Метод: гипотеза → проверка скриптом → сверка с upstream-кодом формата.
- `skills/writing-docs/` — правила готовой документации с первого черновика:
  русский без калек, факты с источниками, таблицы для значений.
- `skills/coordinating/` — координация мультиагентной работы: разложение на
  параллельные юниты без общей записи, волны, статус-таблицы, эскалация.
- `agents/` — референс-копии бандлованных агентов omp (scout, reviewer,
  security-reviewer, sonic, task) для кастомизации.
- `scripts/omp-dev.sh` — лаунчер: `--config … --append-system-prompt …`.
- `docs/token-costs.md` — анализ токен-затрат для моделей.

## Установка (любая машина)

```bash
# 1. omp должен быть установлен (https://github.com/can1357/oh-my-pi)
omp --version

# 2. плагин superpowers: SDD-агенты и скиллы
omp plugin install @loneexile/omp-superpowers

# 3. эта персона - скопировать/склонировать куда угодно, затем:
./scripts/omp-dev.sh            # или добавить в шелл функцию:
# omp-dev() { command /path/to/this/repo/scripts/omp-dev.sh "$@"; }

# 4. инструменты гейтов (один раз, при первом кодовом юните):
bash skills/eng-gates/scripts/install-tools.sh --python --ub
```

5. Флаги SDD-инфраструктуры (в `~/.omp/agent/config.yml`):
   `task.enableLsp: true`, `astGrep.enabled: true` (активируют lsp/ast_grep
   у sdd-*-субагентов), `task.enableEffort: true` (диспетчеризация с
   `effort: "hi"` на high-risk ревью), `task.showResolvedModelBadge: true`
   (видно, какая модель реально бежала). Модели sdd-мест маппятся через
   `task.agentModelOverrides` - см. `docs/token-costs.md`.

Требования: Python ≥3.11 для gate.py (tomllib); рекомендуется uv.

### Глобальная установка без лаунчера

Вместо `omp-dev.sh` персону можно включить для всех сессий:

```bash
cp AGENTS.md ~/.omp/agent/AGENTS.md
cp persona-dev-prompt.md ~/.omp/agent/APPEND_SYSTEM.md
cp -r skills/eng-gates skills/reversing skills/writing-docs skills/coordinating ~/.omp/agent/skills/
```

### Windows

- `python3` - заглушка Microsoft Store: запускать gate.py через `python`
  или `uv run python`.
- gate.py находит `node_modules/.bin/*.cmd` и `.venv/Scripts`.
- ub-набор (crapper/dryer/mutator) не работает: их лаунчеры - POSIX sh с
  `.venv/bin`; `install-tools.sh --ub` их пропускает, gate.py отчитывается
  `missing tool`.

## Наслоение контекста

omp грузит **глобальный** контекст из `~/.omp/agent/AGENTS.md` в каждой
сессии плюс **проектный** `AGENTS.md` из cwd. `AGENTS.md` этого репо -
проектный слой. На чистой домашней машине глобального файла нет: работайте
в чекауте репо (или его родительском каталоге), либо скопируйте `AGENTS.md`
в `~/.omp/agent/AGENTS.md`, чтобы правила стали глобальными.

## Проверка, что всё загрузилось

```bash
./scripts/omp-dev.sh -p --no-session 'List the agent type names your `task` tool offers, comma-separated'
# ожидание: sdd-*, reviewer, scout, security-reviewer, sonic, task, …
```

## Анализ токен-затрат

Измерено 2026-10-31 (omp 18.14.0): первый запрос `omp -p` в git-репо с
персоной и без. Детали, разбивка и рычаги - в `docs/token-costs.md`.

| Модель | Без персоны | С персоной | Дельта |
| :--- | :--- | :--- | :--- |
| claude-opus-5-5 | 15.6k | 22.6k | +7.0k (+45%) |
| kimi k3.1-pro | 9.1k | 13.6k | +4.5k (+49%) |

| Потребитель | ~Токенов | Частота | Рычаг |
| :--- | :--- | :--- | :--- |
| Контекст `AGENTS.md` | 1.5k | Каждый запрос | Матрица инструментов вынесена в скилл |
| Bootstrap superpowers | 1.5k | Каждый запрос | Принадлежит плагину; не отключать в dev-персоне |
| Описания скиллов (16) | 0.5k | Каждый запрос | `ignoredSkills` для нечитаемых |
| Промпты SDD-этапов | 0.6–1.5k | Диспетчеризация | Фиксированы этапом; не раздувать брифы |
| Бриф + контекст субагента | **Главный драйвер** | На задачу | Один бриф = одна задача; батчить однотипные правки |

Больше персоны стоят длина контекста (каждый ход платит за весь кеш -
ограничить `compaction.thresholdTokens`) и посторонние контекст-файлы
(`~/AGENTS.md` грузится во все сессии вне git-репо).

Ключевой фактор стоимости: количество вызовов × объем контекста.
Дешевые модели часто требуют в 2–3 раза больше итераций для решения сложных задач, что в итоге делает их дороже. Замеры на реальном ре-ревью подтверждают это: обработка Flash заняла 100 секунд и 4 хода, тогда как Sonnet справился за 50 секунд в один ход.
Рекомендация: mid-tier модели - базовый стандарт для код-ревью и реализации;
дешевые - только для транскрипции. Шаблоны маппинга (включая схему
«тимлид opus / исполнители kimi, grok») - в `docs/token-costs.md`.


## Лицензия

MIT для собственных файлов репо. Скрипты eng-gates включены как есть из
локальной дистрибуции скилла. Плагин superpowers - апстрим
(@loneexile/omp-superpowers, MIT), здесь не вендорятся и ставятся через omp.