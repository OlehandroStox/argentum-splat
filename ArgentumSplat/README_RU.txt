ARGENTUM SPLAT 0.6.2 — Cinema 4D 2027 / Windows / Redshift

Бесплатная предварительная версия с открытым исходным кодом.
Проект: https://github.com/OlehandroStox/argentum-splat
Русский справочник: https://github.com/OlehandroStox/argentum-splat/blob/main/README.ru.md

Под Status: Support the author - Boosty — добровольная поддержка автора.
https://boosty.to/olehandrostox/donate

УСТАНОВКА
Закройте Cinema 4D. Распакуйте весь архив и запустите Install.cmd.
Он установит плагин, конвертер, отдельный Python и зависимости/веса AI.
Если найдены несколько папок настроек C4D, выберите свою. Дождитесь итогового
сообщения установки, затем запустите Cinema 4D:
Extensions → ArgentumSplat → Argentum Splat.

Python вручную устанавливать не нужно. Рабочая AI-среда сохраняется;
при необходимости скачивается проверенный отдельный Python 3.12.15.
Права администратора не нужны, системный PATH и Python в C4D не меняются.
Первая установка требует интернета, нескольких гигабайт места и времени.
Повторный запуск использует уже готовые компоненты.

Для AI нужны Windows x64 и NVIDIA Ampere или новее с BF16 CUDA и совместимым
драйвером. GPU проверяется до больших загрузок. Драйвер устанавливайте сами;
отдельный CUDA Toolkit не нужен. Для импорта PLY/SPLAT/SPZ v2/v3 AI не нужен.
При ошибке AI установленный плагин остаётся доступен. Прочитайте итоговое
сообщение, устраните указанную причину и снова запустите Install.cmd.
Логи: %LOCALAPPDATA%\ArgentumSplat\installer\logs
Итог: %LOCALAPPDATA%\ArgentumSplat\runtime\setup-result.json

Для установки без AI: из PowerShell в этой папке выполните
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -ImportOnly
Это установит плагин и конвертер сканов. -CoreOnly копирует только плагин.

Ручной вариант: скопируйте папку ArgentumSplat целиком в plugins папки
настроек C4D 2027. Затем в C4D нажмите Set Up AI / Extra Formats для
автоматической настройки зависимостей и дождитесь завершения в Status.
Не устанавливайте несколько копий в разные пути поиска плагинов C4D.

Input File → фото → 65,536 Gaussians / 20 steps / Alpha Erosion 0 →
Load / Generate from Input. Новые объекты уже используют Source Fidelity:
камера на объект, затем запустить IPR в RS Render View. Для старых объектов
пресет применяется кнопкой Source Fidelity — Preserve Detail по желанию.
Auto Prepare Redshift on Import один раз подготавливает Redshift для нового
файла. Можно отключить; последующие ручные настройки не сбрасываются.
Set Redshift Detail Quality повышает глубину прозрачности и сэмплинг,
но может увеличить время рендера. Status показывает ошибки.

ЗАГРУЗКА БОЛЬШИХ СКАНОВ
Splat File → Initialise / Reload: чтение и вычисления идут в фоне,
геометрия собирается короткими порциями. Окно показывает этап и время.
Cancel или крестик отменяют операцию; предыдущая готовая модель остаётся.
Повторный Reload неизменённого файла использует уже подготовленные данные.
Для удобной работы: Point Preview on, Preview Points 10 000; Camera-Facing
Cards off исключает перестройку геометрии при смене ракурса. SH и изменения
LOOK обновляются после остановки изменений без всплывающего окна; ход работы
остаётся в Status, отмена доступна через Cancel Processing. Свет не вызывает
пересчёт скана. Рендер использует модель с учётом Maximum Splats.
Новые объекты сохраняют до 3 000 000 splats при пороге прозрачности 1/255:
Emission 1, Diffuse 0, Subsurface 0, SH3, Camera-Facing Cards on, Pixel
Footprint 0.075, Normal Smoothing 0. Старые значения в сценах сохраняются. Для больших сканов подготовка и обновление ракурса всё ещё требуют
времени и памяти. Point Preview не уменьшает количество splats в рендере.

Видео и секвенции: один выбранный кадр → одна статическая модель.
Это не объединение ракурсов и не анимированная 4D-модель.
Point Preview влияет только на рисование точек; полная геометрия остаётся
в памяти и доступна Redshift. Подробности — в документации проекта.

ВРЕМЕННЫЕ ID
Object 1000007, Command 1000008, Message 1000009 — development ID.
Они могут конфликтовать с другими плагинами. Постоянные Maxon ID и миграция
пока не готовы. Проверяйте в отдельной папке настроек C4D; не меняйте ID
вручную в сценах, которые нужно сохранить совместимыми.

ПОДДЕРЖАТЬ АВТОРА
https://boosty.to/olehandrostox/donate — добровольные чаевые.
Скачивание и функции этой версии бесплатны.

Интеграция: MIT, OlehandroStox / ARGENTUM. TripoSplat: Tripo AI / VAST AI Research.
Built with DINOv3. Сторонние компоненты сохраняют собственные лицензии.
Читайте LICENSE.txt, backend/THIRD_PARTY_NOTICES.md и backend/licenses/.
Независимая разработка, не связанная с Maxon.
