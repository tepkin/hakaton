#!/usr/bin/env bash
# Запускать ОДИН РАЗ на сборочной машине, где установлен libredwg-tools.
# Копирует dwg2dxf и его shared-библиотеки в tools/, чтобы целевым машинам
# (и Docker-образу при COPY tools/) не нужны были sudo/apt/интернет.
set -euo pipefail
cd "$(dirname "$0")"

EXE=$(command -v dwg2dxf || true)
[ -n "$EXE" ] || { echo "dwg2dxf not found here. Install libredwg-tools on THIS machine first."; exit 1; }

mkdir -p lib
cp -L "$EXE" ./dwg2dxf.bin

# копируем зависимые .so, кроме базовых системных (libc/ld/libm/libdl/libpthread)
ldd "$EXE" | awk '/=>/ {print $3}' | grep -v '^$' | while read -r so; do
  case "$so" in
    */libc.so*|*/ld-linux*|*/libdl.so*|*/libm.so*|*/libpthread.so*) ;;
    *) cp -L "$so" lib/ ;;
  esac
done

# обёртка с LD_LIBRARY_PATH — её и находит приложение как tools/dwg2dxf
cat > dwg2dxf <<'EOF'
#!/bin/sh
HERE="$(cd "$(dirname "$0")" && pwd)"
LD_LIBRARY_PATH="$HERE/lib:${LD_LIBRARY_PATH:-}" exec "$HERE/dwg2dxf.bin" "$@"
EOF
chmod +x dwg2dxf dwg2dxf.bin

echo "Packed: tools/dwg2dxf (wrapper) + tools/dwg2dxf.bin + tools/lib/"
echo "Target machines need nothing: the app auto-detects tools/dwg2dxf."