ARGENTUM SPLAT 0.4.0 — Cinema 4D 2027 / Windows / Redshift

Бесплатная предварительная версия с открытым исходным кодом.
Проект: https://github.com/OlehandroStox/argentum-splat
Русский справочник: https://github.com/OlehandroStox/argentum-splat/blob/main/README.ru.md

Под Status: Support the author - Boosty — добровольная поддержка автора.
https://boosty.to/olehandrostox/donate

УСТАНОВКА
Закройте Cinema 4D. Распакуйте весь архив и запустите Install.cmd.
Либо скопируйте папку ArgentumSplat целиком в plugins пользовательской
папки настроек Cinema 4D 2027. Перезапустите Cinema 4D.
Extensions → ArgentumSplat → Argentum Splat.

Для AI нажмите Set Up AI / Extra Formats и дождитесь завершения в Status.
Нужны Windows x64, Python 3.10–3.12 и NVIDIA Ampere или новее с BF16 CUDA.
Первая установка скачивает несколько гигабайт. C4D Python не изменяется.
Для импорта PLY/SPLAT/SPZ v2/v3 веса AI не требуются.

Input File → фото → 65,536 Gaussians / 20 steps / Alpha Erosion 0 →
Load / Generate from Input. После завершения: Source Fidelity — Preserve
Detail, камера на объект, затем запустить IPR в RS Render View.
Set Redshift Detail Quality повышает глубину прозрачности и сэмплинг,
но может увеличить время рендера. Status показывает ошибки.

ЗАГРУЗКА БОЛЬШИХ СКАНОВ
Splat File → Initialise / Reload: чтение и вычисления идут в фоне,
геометрия собирается короткими порциями. Окно показывает этап и время.
Cancel или крестик отменяют операцию; предыдущая готовая модель остаётся.
Повторный Reload неизменённого файла использует уже подготовленные данные.
Для удобной работы: Point Preview on, Preview Points 10 000; Camera-Facing
Cards off исключает перестройку геометрии при смене ракурса. SH и изменения
LOOK обновляются после остановки изменений. Рендер использует полную модель
с учётом Maximum Splats. Первое чтение файла из миллионов splats требует времени.

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
