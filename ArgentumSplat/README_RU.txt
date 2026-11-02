ARGENTUM SPLAT 0.9.2 — Cinema 4D 2027 / Windows / Redshift

УСТАНОВКА
1. Закройте Cinema 4D.
2. Запустите Install.cmd и дождитесь завершения.
3. Откройте C4D: Extensions > ArgentumSplat > Argentum Splat.

Python и компоненты устанавливаются автоматически в отдельное окружение.
Для первой установки нужен интернет и несколько ГБ свободного места.
Для Image нужна NVIDIA Ampere или новее с поддержкой BF16 и совместимым драйвером.
Для установки только импорта: PowerShell > .\Install.ps1 -ImportOnly.
NumPy для ускорения расчётов входит в поставку и распаковывается локально;
при его недоступности используется обычный Python-расчёт.

ПЕРВЫЙ ЗАПУСК
Image — одно фото; Photos — общий скан по ракурсам из папки; Scan — готовый Gaussian-файл. Для Photos один раз нажмите Set Up Photos, затем Reconstruct from Photos.
Готовый скан: SCAN > Splat File, затем выберите Import Quality.
LOW — до 250 тыс., MEDIUM — до 1 млн, HIGH — до 4 млн,
MAX — все прошедшие фильтр сплаты при достаточной памяти.
Дождитесь Ready в Status и запустите Redshift.

HELP
Во вкладке Help выберите Language / Язык и тему.
Open Help Reader открывает большое окно для чтения.
Версия плагина и добровольная поддержка Boosty находятся внизу Help.
Ручное кадрирование и настройка рендера: SCAN > Manual Tools.

Preview Points влияет только на редактор; Import Quality — на геометрию.
Для больших моделей потребуется больше памяти и времени.
Cancel сохраняет предыдущую готовую модель; для повтора нажмите Reload.
Pixel Footprint теперь компенсирует непрозрачность расширенных фильтром
мелких splats, уменьшая их избыточную яркость. 0 отключает этот фильтр.
Redshift использует карточки: плотная прозрачность и смешивание цветов
могут отличаться от SuperSplat даже при полном импорте.

Документация: https://github.com/OlehandroStox/argentum-splat
Поддержать автора: https://boosty.to/olehandrostox/donate
Лицензии: LICENSE_SCOPE.md и backend/THIRD_PARTY_NOTICES.md.
