# GreenPlan AI — Docker-сборка (МосТех.ОС / Linux, требование ТЗ)

## Запуск
- Онлайн (образ соберётся сам):
  - Linux: `./run_docker.sh`
  - Windows: `run_docker.bat`
- Офлайн: положи `greenplan_docker.tar` рядом с этим файлом — скрипт сам выполнит
  `docker load` и запустит контейнер.
- Вручную: `docker build -t greenplan:1.0 .` затем
  `docker run --rm -p 8000:8000 -e GREENPLAN_HOST=0.0.0.0 greenplan:1.0`
- Compose: `docker compose up --build`

## Проверка
- Интерфейс: http://127.0.0.1:8000
- Swagger:   http://127.0.0.1:8000/docs
- Результаты прогонов: папка `out/` (примонтирована в контейнер)

## Офлайн-перенос образа на целевую машину
```bash
docker build -t greenplan:1.0 .
docker save greenplan:1.0 -o greenplan_docker.tar   # на сборочной машине
# перенести tar + папку проекта; на целевой: ./run_docker.sh