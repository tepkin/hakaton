# Конвертер DWG (встроен в продукт)

GreenPlan конвертирует DWG через LibreDWG (dwg2dxf). Конвертер кладётся в эту папку
один раз (с интернетом), дальше продукт работает с DWG офлайн.

Как получить конвертер:
- Linux / МосТех.ОС: ./fetch_converter.sh  (или apt install libredwg-tools)
- Windows:          fetch_converter.bat   (скачать LibreDWG, извлечь dwg2dxf.exe сюда)

После этого в папке появится dwg2dxf (или dwg2dxf.exe) — продукт подхватит его
автоматически (порядок: tools/ -> конфиг dwg.converter_path -> системный PATH).