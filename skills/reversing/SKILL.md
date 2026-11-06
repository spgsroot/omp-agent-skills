---
name: reversing
description: Use when reverse-engineering compiled or bundled software — Bun/Node single-executables (bunfs), Mach-O/ELF binaries, minified JS bundles, binary container formats, network protocols. Extracts embedded assets, reconstructs serialization formats, maps unknown structures against upstream sources (e.g. Bun StandaloneModuleGraph.rs for bunfs). Use for "как это устроено внутри" questions about any artifact you cannot read as source.
---

# Реверс-инжиниринг артефактов

Метод: артефакт → гипотеза структуры → проверка на живом файле → сверка с
первоисточником (upstream-код того же формата) → документ-отчёт с координатами
(file:offset) для воспроизводимости.

## Когда применять

- Compiled single-exe (Bun `--compile`, node SEA): bunfs-граф, embedded assets;
- Mach-O / ELF: секции (`otool -l` / `readelf -S`), строки, embedded blobs;
- Минифицированные JS-бандлы: именование, чанки, sourcemaps, string tables;
- Бинарные форматы: магии, трейлеры, фиксированные смещения, длина-префиксы;
- Протоколы: захват → декод → сверка со спецификацией/реализацией.

## Порядок работы

1. **Разведка формата**: `file`, `strings`, hex-просмотр головы/хвоста. Искать
   магики и маркеры (например `\n---- Bun! ----\n` перед трейлером bunfs).
2. **Гипотеза структуры**: смещения/длины/порядок полей. Проверять каждую
   гипотезу python-скриптом на живом файле — не на глаз.
3. **Сверка с первоисточником**: сериализатор формата почти всегда есть в
   upstream (Bun — `StandaloneModuleGraph.rs`, `to_bytes`/`from_bytes` пары).
   GitHub raw-file читать напрямую, не искать.
4. **Извлечение**: embedded модули/ассеты на диск; ничего не патчить без
   отдельного решения (патч — отдельная задача с equal-length правилами).
5. **Отчёт**: карта формата (таблица полей с file:offset), метод воспроизводства
   (команды/скрипт), найденные точки интереса (endpoints, ключи, механики).

## Проверенные приёмы (из bunfs-рева claude-code 2.1.311)

- Трейлер перед magic несёт Offsets-структуру; таблица модулей — фиксированный
  размер записи; `contents` несжатого исходника отдельно от байткода.
- `strings` всего бинарника → маркеры (URL, env-имена) → grep по извлечённым
  модулям даёт file:line точки интереса.
- Скрипт распаковки пишется один раз и коммитится рядом с отчётом —
  это и есть метод воспроизводства.

## Чего не делать

- Не дизассемблировать процессоры без нужды: 90% вопросов закрывается
  структурным анализом (строки + формат + upstream-сверка).
- Не модифицировать исследуемый файл до завершения анализа.
- Отчёт — с координатами; утверждения без file:offset — [INFERENCE].