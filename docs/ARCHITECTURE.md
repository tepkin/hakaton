# Архитектура GreenPlan AI

Пайплайн: DXF -> dxf_ingest (слои->геометрия) -> norm_engine (буферы по НПА) ->
gen_engine (воспроизводимая расстановка точек) -> budget_controller (лимит ТСН) ->
interp_engine (обоснования по НПА) -> dxf_export (слои GREEN_AI_*).

Компоненты:
- app/core/* — ядро (без веб-зависимостей);
- app/web/server.py — FastAPI + Swagger (/docs), статика web/;
- app/cli.py — CLI: run / serve / doctor;
- data/*.json — нормы, стоимости, ассортимент, конфиг (без БД).

Слои DXF: исходные не изменяются; результат на GREEN_AI_TREES / GREEN_AI_SHRUBS /
GREEN_AI_ZONES_ALLOWED / GREEN_AI_ZONES_FORBIDDEN.

Интерпретируемость: по каждой посадке — проверки (факт vs норма), НПА и пункт;
отклонённые кандидаты тоже объясняются.

Развёртывание: Docker (Dockerfile / docker-compose.yml) или локально run.bat / run.sh.
Офлайн: внешних вызовов нет; интернет опционален и не требуется.