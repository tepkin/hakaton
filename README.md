# GreenPlan AI — автопроектирование озеленения (DXF/DWG -> DXF)

Пайплайн: вход DXF/DWG -> ограничения и допустимые зоны (СП 42.13330.2016, 743-ПП, 623-ПП/МГСН)
-> план посадок на отдельных слоях GREEN_AI_* -> интерпретации (НПА+пункт) -> смета/бюджет.

## Запуск
    pip install -r requirements.txt
    python -m app.cli doctor                 # проверка окружения и конвертера DWG
    python -m app.cli run in.dxf --out out   # прогон
    python -m app.cli serve                  # веб: http://127.0.0.1:8000 (/docs — Swagger)
    # Docker: docker compose up --build

## DWG (встроено)
Конвертер LibreDWG (dwg2dxf) кладётся в tools/ один раз:
    tools/fetch_converter.sh   (Linux)   tools/fetch_converter.bat (Windows)
Дальше продукт работает с DWG офлайн. Порядок поиска: tools/ -> конфиг -> PATH.

## Повторный расчёт / параметры
    --seed, --territory, --budget-mode, --budget-value, --budget-policy
Результат каждого прогона — отдельно (out/), интерпретации — interpretation.json.