#!/usr/bin/env bash
# Docker-запуск (требование ТЗ). Офлайн: положи greenplan_docker.tar рядом —
# скрипт сам загрузит образ; иначе соберёт образ один раз (нужен интернет).
cd "$(dirname "$0")" || exit 1
IMG=greenplan:1.0

if ! docker image inspect "$IMG" >/dev/null 2>&1; then
  if [ -f greenplan_docker.tar ]; then
    echo "Loading image from greenplan_docker.tar ..."
    docker load -i greenplan_docker.tar
  else
    echo "Building image (internet needed once) ..."
    docker build -t "$IMG" .
  fi
fi

echo "Server: http://127.0.0.1:8000   Swagger: http://127.0.0.1:8000/docs   (Ctrl+C to stop)"
(sleep 3; xdg-open http://127.0.0.1:8000 >/dev/null 2>&1 || true) &
docker run --rm -p 8000:8000 -e GREENPLAN_HOST=0.0.0.0 -v "$PWD/out:/app/out" "$IMG"