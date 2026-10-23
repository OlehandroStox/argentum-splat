ARGENTUM SPLAT 0.8.2-dev — Cinema 4D 2027 / Windows / Redshift

УСТАНОВКА
1. Закройте Cinema 4D.
2. Запустите Install.cmd и дождитесь завершения.
3. Откройте C4D: Extensions > ArgentumSplat > Argentum Splat.

Python и компоненты устанавливаются автоматически в отдельное окружение.
Для первой установки нужен интернет и несколько ГБ свободного места.
Для AI нужна NVIDIA Ampere или новее с поддержкой BF16 и совместимым драйвером.
Для установки только импорта: PowerShell > .\Install.ps1 -ImportOnly.

ПЕРВЫЙ ЗАПУСК
Фото/видео: INPUT > Image / Video File > Generate from Image / Video.
Готовый скан: SCAN > Splat File, затем выберите Import Quality.
LOW — до 250 тыс., MEDIUM — до 1 млн, HIGH — до 4 млн,
MAX — все прошедшие фильтр сплаты при достаточной памяти.
Дождитесь Ready в Status и запустите Redshift.

HELP
Во вкладке Help выберите Language / Язык и тему.
Open Help Reader открывает большое окно для чтения.
Версия плагина и добровольная поддержка Boosty находятся внизу Help.
Ручное кадрирование и настройка рендера: SCAN > Manual Tools.

Видео и секвенции используют один кадр для одной статичной модели.
Preview Points влияет только на редактор; Import Quality — на геометрию.
Для больших моделей потребуется больше памяти и времени.

Документация: https://github.com/OlehandroStox/argentum-splat
Поддержать автора: https://boosty.to/olehandrostox/donate
Лицензии: LICENSE_SCOPE.md и backend/THIRD_PARTY_NOTICES.md.
