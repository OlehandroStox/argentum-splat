"""Bundled offline instructions. Language affects help only, never scene data."""

TOPICS = {
    0: ('Quick start', 'Image / Video', 'Scan import and quality', 'Scan projection',
        'Automatic setup and manual tools', 'LOOK', 'Colour correction',
        'Viewport and performance', 'Advanced / MoGraph', 'Troubleshooting'),
    1: ('Быстрый старт', 'Фото / видео', 'Импорт скана и качество', 'Проекция скана',
        'Автонастройка и ручные инструменты', 'LOOK — внешний вид', 'Цветокоррекция',
        'Вьюпорт и скорость', 'Advanced / MoGraph', 'Решение проблем'),
}

EN = (
"""TWO WAYS TO START

Photo or video: INPUT > Image / Video File, then Generate from Image / Video. The local AI creates a static 3D model from ONE image or selected frame. Use Set Up AI / Extra Formats if the runtime is missing.

Existing 3D scan: SCAN > Splat File. Choose PLY, SPLAT, SPZ, SOG or KSPLAT and an Import Quality. Loading starts after changes settle; Initialise / Reload starts it immediately or retries.

Keep the automatic Redshift and framing options enabled for a new scene. Wait for Ready in Status, then render with Redshift. Coloured viewport points are a fast preview, not the final render.

THREE DIFFERENT COUNTS
Gaussian Count = how many Gaussians the AI generates.
Import Quality = how many existing scan splats are retained.
Preview Points = how many points the editor draws; default 50,000.

Help is available offline. Language / Язык changes only these instructions. Existing scene values are preserved when the plugin is updated.""",

"""INPUT — IMAGE / VIDEO

Image / Video File: PNG, JPG/JPEG, WebP, TIFF, BMP, TGA or GIF; videos include MP4, MOV, MKV, AVI and WebM (decoding depends on the installed backend). Put 3D files in SCAN > Splat File.

Input Mode: Auto detects image/video. Numbered Image Sequence reads a numbered image such as shot_0001.png.
Source Frame / Sequence Offset: 0 is the first video frame, or the selected sequence file; 1 selects the next. A missing numbered frame is reported, not skipped.
Preview Selected Frame: inspect the extracted/prepared image before generation.

Gaussian Count: 65,536 / 131,072 / 262,144 are supported AI output sizes. Higher counts cost more time and memory; they cannot recover all unseen detail.
Generation Steps: more sampling iterations, usually more time; not a guaranteed quality increase.
Seed: changes the generated variation; keep it fixed for comparisons.
Alpha Erosion: shrink the foreground mask. 0 keeps fine edges; increase only to remove background fringes.

Output Folder: destination for generated files; blank uses the local default.
Generate from Image / Video: start local AI generation from one selected frame.
Cancel Processing: stop the current operation; keep the previous complete model.
Set Up AI / Extra Formats: install the isolated runtime and optional converters; downloads can be several GB.
Open Output Folder: open generated files in Explorer.

Video/sequence input does NOT combine views or create animated 3D. Four views in a collage are not a multi-view reconstruction input.""",

"""SCAN — EXISTING 3D DATA

Splat File: Gaussian PLY, SPLAT, SPZ, SOG or KSPLAT. Ordinary mesh/point-only PLY may lack the Gaussian properties required here. Compressed formats can require the optional converter installed by setup.

Import Quality controls Maximum Splats, not SH colour:
LOW: up to 250,000.
MEDIUM: up to 1,000,000.
HIGH (default): up to 4,000,000.
MAX: all opacity-eligible source splats, if memory permits.
CUSTOM: the exact limit entered in Advanced.

Import Budget shows source count and approximate additional RAM, not VRAM. Large native card geometry can require many GB. A 9-million source can use MAX on suitable hardware; no hidden 4-million cap remains. MAX never silently becomes LOW.

Ask for Large Files: show a non-blocking choice before loading a new source above 4 million splats. Cancel leaves the previous complete model. The choice is remembered for that source on this object.

Lower presets take a deterministic sample across the source, which can lose fine detail. Minimum Opacity also removes faint splats. Status / Source Summary report retained and original counts. Even LOW must read and validate the source; loading is not instant.

Initialise / Reload: load/retry after cancellation or file/settings changes. Unchanged prepared data is reused. Do not press it after every camera move.""",

"""SCAN — PROJECTION AND COLOUR DATA

View-Dependent Colour: Off uses base colour. SH 1 / 2 / 3 evaluate increasingly detailed stored spherical harmonics. SH 3 uses all supported coefficients actually present; it cannot invent reflections in SH0 files. Disabled controls mean the loaded source has no SH to evaluate.

Camera-Facing Cards: project the full Gaussian shape toward the active render camera. Enabled by default for source fidelity; camera/lens/output changes require projection updates. Turning it off uses surface-oriented cards, often faster but less accurate for some scans.

Projection Camera: optional explicit override. Leave empty to follow the current camera. A different override can make another render view look wrong; Status warns about this.

SPZ: Unconverted Coordinates: only for SPZ files whose raw coordinate convention you intentionally want to keep. Normally leave off.

Normal Smoothing Passes: smooth neighbouring card normals for lighting/surface cards. Default 0 preserves source detail. Higher values cost preparation time and can soften directional detail; not a universal quality slider.

These settings do not change how many source records are retained. Import Quality is the separate control for that.""",

"""AUTOMATIC SETUP / MANUAL TOOLS

Auto Prepare Redshift on Import: prepare transparency and sampling once for each new source. Leave on for easy first use. Later LOOK/camera changes do not repeatedly reset the render settings.

Auto Frame in Empty Scene: fit a camera only when this is the sole scene object and no existing user camera blocks it. Existing scene content and manually edited cameras are preserved. This estimates a useful overview, not the author's original camera; interiors may need your own camera position.

The following buttons are in SCAN > Manual Tools (normally collapsed):

Source Fidelity - Preserve Detail: restore full available SH, camera-facing projection, smoothing 0, pixel filtering 0.075 and Emission 1 / Diffuse 0 / Subsurface 0. Clears Projection Camera. Useful for older or heavily adjusted objects. Preserves import budget, colour correction and scale; it cannot add missing detail.

Frame Loaded Scan: create and activate a fitted camera for an already loaded scan. Useful after import into an existing scene. Previous cameras remain.

Set Redshift Detail Quality: manually repeat render preparation after changing render settings or disabling auto setup. Transparency depth >=128, manual sample floors 16/128, threshold <=0.01; Automatic Sampling is disabled. Stricter values are preserved. Affects this document and can increase render time; Undo is available.

Create Estimated Source Camera: create a camera from matching AI generation.json metadata, for the square prepared image. Does not activate or replace your current camera. Disabled for scans without that metadata. This is different from fitting scan bounds.""",

"""LOOK — APPEARANCE

Colour Management: sRGB Source to Scene Linear decodes source colours (respecting explicit linear metadata) then converts to the document working space. Treat Source as Linear is for data already linear. The document's display transform and exposure still affect the result.

Highlight Limit: cap corrected RGB values. Default 3 allows values brighter than 1.
SH Strength: amount of stored view-dependent colour, default 1. It is not a reflection/glass shader.
Emission Weight: self-lit captured colour. Default 1 reproduces scan appearance without adding lamps.
Diffuse Weight: response to scene lights, default 0. Increase when deliberately relighting the model.
Subsurface Weight: thin-card diffuse transmission, default 0; not solid-volume skin scattering.

For a faithful scan start at Emission 1, Diffuse 0, Subsurface 0. Captured lighting is already present in the source; adding diffuse lighting can change it substantially.

Weight edits reuse geometry and colour. Colour/SH edits can need a background pass over all loaded splats. Decimal controls step by 0.1; typing permits finer values.""",

"""COLOUR CORRECT

Gamma: midtone response; neutral 1.
Contrast: colour contrast; neutral 0.5.
Hue (degrees): hue rotation; neutral 0 degrees.
Saturation: colour intensity; neutral 1, zero gives greyscale.
Level: multiply colour brightness; neutral 1.

These controls change the loaded source colours, not the document's exposure or view transform. They preserve geometry but still visit every loaded splat, so a multi-million scan needs more processing time.

Updates wait briefly for dragging to stop. The previous complete model stays visible until its replacement is ready. Status remains available; Cancel Processing stops pending work. Redshift may then restart its own progressive accumulation.""",

"""VIEWPORT AND PERFORMANCE

Point Preview: draw coloured points in the editor while Redshift renders the full loaded cards.
Preview Points (0 = All): default 50,000 for NEW objects. Lower it if orbiting is slow; 0 draws every loaded point and can be expensive. Saved objects keep their previous value.

This control does not reduce render quality or full geometry memory. Use Import Quality to reduce the number of loaded splats. A sparse point preview does not mean the final render lost the same points.

Camera-facing projection must update when the camera, lens or render dimensions change. SH colour updates only when the source contains active view-dependent SH. Unchanged input reuses prepared data; there is no need to Reload on every orbit.

Changing only Help language/topic starts no scan, colour or geometry job. Ordinary interactive updates use Status; first loads show the progress/Cancel window.

For speed: lower Preview Points first for editor drawing; use LOW/MEDIUM for lighter geometry; choose HIGH/MAX for final detail if memory allows. Turning Camera-Facing Cards off is a speed/accuracy trade-off, not a guaranteed equivalent render.""",

"""ADVANCED / MOGRAPH

Global Scale: whole-model size; default 100. It does not add detail.
Pixel Footprint (variance; 0 = Off): image-space filtering for perspective camera-facing cards, default 0.075. Higher values broaden/soften tiny splats; 0 disables filtering.
Splat Scale: change individual card sizes without moving centres. Default 1; too large blurs, too small opens holes.
Maximum Splats: the SAME limit as Import Quality. 0 = Full Source; other custom values show CUSTOM. Not a second independent cap.
Minimum Opacity (Reload): discard nearly transparent source records. Default 1/255; lowering retains faint detail at a memory/render cost.
Opacity Multiplier: multiply opacity of retained splats, default 1; cannot restore filtered-out records.
Auto SOG Orientation: conventional SOG Y-down to C4D Y-up. Enabled on new objects. Disable for already reoriented SOG data.
Flip Y Axis: additional manual Y reflection, including Gaussian shape.
Redshift Material: editable node-material link.

Create MoGraph Fracture Rig: create a native Fracture with each card as a segment. Add effectors to the Fracture. Point Preview is disabled for the rig; millions of segments are expensive. Keep a saved source scene for revision.

Projection and SH are calculated before deformers/effectors, not for each transformed segment or reflection ray. The representation is Gaussian polygon cards, not a watertight mesh or native GPU splat rasterizer.

Status / Source Summary: progress, counts, filtering and errors.
Support the author - Boosty: optional external link; the plugin remains free.""",

"""TROUBLESHOOTING

Only dots in the editor: Point Preview is on; render with Redshift to see cards. Raise Preview Points for a denser editor view.

Model absent from render: wait for Ready; check active camera, object render visibility and Redshift. Frame Loaded Scan can make an overview. Source-camera creation alone does not activate that camera.

Blobs, holes or missing fine detail: compare retained/source counts. Try HIGH/MAX if RAM permits, Splat Scale 1, smoothing 0 and the Source Fidelity preset. Check the camera override and opacity threshold. MAX cannot repair a poor source or recover an author's camera.

Black or incomplete transparent layers: enable Auto Prepare Redshift, or use Set Redshift Detail Quality. Let progressive rendering converge. Check the document's colour/view settings for brightness differences.

Interior scan framed from outside: automatic bounds fitting cannot infer a good position inside every building. Move a camera into the captured area. A downloaded SOG does not necessarily include the website's camera path.

Long load / low memory: use a lower Import Quality. Estimates are approximate RAM, not VRAM guarantees. Cancel preserves the previous complete model. LOW still reads/validates the file.

AI runtime missing: run Set Up AI / Extra Formats and inspect Status. Video uses one selected frame; it is not multi-view capture.

Differences from other viewers can remain because card compositing, transparency, camera and colour management differ. More splats do not guarantee identical rendering.""",
)

RU = (
"""ДВА СПОСОБА НАЧАТЬ

Фото или видео: INPUT > Image / Video File, затем Generate from Image / Video. Локальная нейросеть создаст статичную 3D-модель по ОДНОМУ изображению или выбранному кадру. Если компоненты не установлены, нажмите Set Up AI / Extra Formats.

Готовый 3D-скан: SCAN > Splat File. Выберите PLY, SPLAT, SPZ, SOG или KSPLAT и Import Quality. Загрузка начнётся после остановки изменений; Initialise / Reload запускает её сразу или повторяет попытку.

Для новой сцены оставьте автонастройку Redshift и кадрирование включёнными. Дождитесь Ready в Status и запустите Redshift. Цветные точки во вьюпорте — быстрый предпросмотр, а не финальный рендер.

ТРИ РАЗНЫХ КОЛИЧЕСТВА
Gaussian Count — сколько гауссиан создаёт нейросеть.
Import Quality — сколько существующих сплатов скана загружается.
Preview Points — сколько точек рисует редактор; по умолчанию 50 000.

Help работает без интернета. Language / Язык меняет только инструкцию. Обновление плагина сохраняет настройки ранее созданных объектов.""",

"""INPUT — ФОТО / ВИДЕО

Image / Video File: PNG, JPG/JPEG, WebP, TIFF, BMP, TGA, GIF; видео MP4, MOV, MKV, AVI, WebM и другие поддерживаемые декодером форматы. Готовые 3D-файлы выбирайте в SCAN > Splat File.

Input Mode: Auto распознаёт фото/видео. Numbered Image Sequence — нумерованная секвенция, например shot_0001.png.
Source Frame / Sequence Offset: 0 — первый кадр видео или выбранный файл секвенции; 1 — следующий. Пропущенный номер считается ошибкой, а не заменяется соседним.
Preview Selected Frame: посмотреть извлечённый/подготовленный кадр до генерации.

Gaussian Count: 65 536 / 131 072 / 262 144 — поддерживаемые размеры результата AI. Больше требует времени и памяти, но не восстанавливает все невидимые детали.
Generation Steps: число шагов генерации. Больше обычно дольше, но не обязательно лучше.
Seed: вариант результата; для сравнения сохраняйте одинаковый seed.
Alpha Erosion: сужение маски объекта. 0 сохраняет тонкие края; увеличивайте только для удаления каймы фона.

Output Folder: папка результата; пустое поле использует локальную папку по умолчанию.
Generate from Image / Video: генерация по одному выбранному кадру.
Cancel Processing: отмена операции с сохранением предыдущей готовой модели.
Set Up AI / Extra Formats: установка отдельного окружения и конвертеров; загрузка может занимать несколько ГБ.
Open Output Folder: открыть результаты в Проводнике.

Видео/секвенция НЕ объединяются в многоракурсный скан или анимированную 3D-модель. Коллаж из четырёх видов тоже не является таким входом.""",

"""SCAN — ГОТОВЫЕ 3D-ДАННЫЕ

Splat File: Gaussian PLY, SPLAT, SPZ, SOG, KSPLAT. Обычный PLY с сеткой/точками может не содержать необходимых параметров гауссиан. Сжатым форматам может понадобиться конвертер из установки.

Import Quality управляет Maximum Splats, а не цветом SH:
LOW — до 250 000.
MEDIUM — до 1 000 000.
HIGH (по умолчанию) — до 4 000 000.
MAX — все сплаты, прошедшие фильтр прозрачности, если хватает памяти.
CUSTOM — точный лимит, введённый в Advanced.

Import Budget показывает исходное количество и примерную дополнительную RAM, не VRAM. Геометрия карточек может занимать много ГБ. Для файла на 9 млн можно выбрать MAX на подходящем ПК: скрытого ограничения в 4 млн больше нет. MAX не переключается незаметно в LOW.

Ask for Large Files: окно выбора перед новым файлом больше 4 млн сплатов. Оно не блокирует Cinema 4D; Cancel сохраняет предыдущую модель. Выбор запоминается для этого источника на объекте.

Меньшие уровни берут воспроизводимую выборку по всему файлу, поэтому тонкие детали могут пропасть. Minimum Opacity дополнительно отбрасывает почти прозрачные сплаты. Status / Source Summary показывают исходное и оставшееся количество. Даже LOW читает и проверяет исходник.

Initialise / Reload: загрузить или повторить после отмены/изменения файла и настроек. Неизменённые подготовленные данные используются повторно. После каждого движения камеры нажимать не нужно.""",

"""SCAN — ПРОЕКЦИЯ И ЦВЕТ

View-Dependent Colour: Off — базовый цвет. SH 1 / 2 / 3 используют всё более подробные сохранённые сферические гармоники. SH 3 берёт доступные коэффициенты; он не создаёт отражения в файле SH0. Недоступные поля SH означают, что в источнике таких данных нет.

Camera-Facing Cards: проецирует полную форму гауссиан в сторону камеры рендера. По умолчанию включено для точности; изменение камеры, объектива или разрешения требует обновления проекции. Выключение использует карточки по поверхности — часто быстрее, но для части сканов менее точно.

Projection Camera: принудительная камера проекции. Обычно оставляйте пустой, чтобы следовать текущей камере. Несовпадение с камерой рендера может искажать вид; Status предупреждает об этом.

SPZ: Unconverted Coordinates: оставить исходную систему координат SPZ. Нужно только при осознанной работе с такими координатами; обычно выключено.

Normal Smoothing Passes: сглаживание соседних нормалей для освещения/поверхностных карточек. 0 сохраняет детали. Повышение требует времени и может смягчить направленные детали; это не универсальный регулятор качества.

Эти настройки не задают количество загруженных сплатов. Для количества есть отдельный Import Quality.""",

"""АВТОНАСТРОЙКА / РУЧНЫЕ ИНСТРУМЕНТЫ

Auto Prepare Redshift on Import: один раз для нового источника настраивает прозрачность и сэмплинг. Для простого старта оставьте включённым. Последующие изменения LOOK/камеры не сбрасывают настройки рендера постоянно.

Auto Frame in Empty Scene: подбирает камеру, если splat — единственный объект сцены и нет пользовательской камеры. Существующая сцена и вручную изменённые камеры сохраняются. Это оценка общего вида, не исходная камера автора; для интерьера её иногда нужно поставить самостоятельно.

Следующие кнопки находятся в SCAN > Manual Tools (обычно свёрнуто):

Source Fidelity - Preserve Detail: возвращает полный доступный SH, Camera-Facing, сглаживание 0, Pixel Footprint 0.075 и Emission 1 / Diffuse 0 / Subsurface 0. Очищает Projection Camera. Полезно для старого или сильно изменённого объекта. Сохраняет лимит импорта, цветокоррекцию и масштаб; новые детали не создаёт.

Frame Loaded Scan: создаёт и включает камеру, охватывающую загруженную модель. Удобно после импорта в существующую сцену. Старые камеры остаются.

Set Redshift Detail Quality: вручную повторяет подготовку рендера после изменения настроек или отключения автоматики. Глубина прозрачности от 128, ручные сэмплы от 16/128, порог до 0.01; Automatic Sampling выключается. Более строгие значения сохраняются. Меняет текущий документ, может замедлить рендер; есть Undo.

Create Estimated Source Camera: создаёт камеру по соответствующему AI-файлу generation.json для квадратного подготовленного изображения. Не включает её и не заменяет текущую. Для скана без этих данных кнопка недоступна. Это другая задача, чем общий охват границ модели.""",

"""LOOK — ВНЕШНИЙ ВИД

Colour Management: sRGB Source to Scene Linear декодирует цвет источника (с учётом явных линейных метаданных), затем переводит его в рабочее пространство документа. Treat Source as Linear нужен уже линейным данным. Экспозиция и видовой transform документа всё равно влияют на результат.

Highlight Limit: верхний предел RGB после коррекции. По умолчанию 3, сохраняет значения ярче 1.
SH Strength: сила сохранённого зависимого от ракурса цвета, обычно 1. Это не шейдер стекла/отражений.
Emission Weight: собственный записанный цвет. 1 позволяет воспроизвести скан без добавления ламп.
Diffuse Weight: реакция на свет сцены; по умолчанию 0. Повышайте при намеренном переосвещении.
Subsurface Weight: пропускание рассеянного света тонкими карточками, обычно 0. Это не объёмное рассеивание кожи.

Для близкого к исходнику вида начните с Emission 1, Diffuse 0, Subsurface 0. Освещение уже записано в скане, поэтому дополнительный diffuse может сильно изменить его.

Изменение весов использует готовую геометрию и цвет. Коррекция цвета/SH может потребовать фонового прохода по всем сплатам. Шаг десятичных полей — 0.1, вручную можно ввести точнее.""",

"""COLOUR CORRECT — ЦВЕТОКОРРЕКЦИЯ

Gamma: отклик средних тонов; нейтрально 1.
Contrast: контраст; нейтрально 0.5.
Hue (degrees): сдвиг оттенка в градусах; нейтрально 0.
Saturation: насыщенность; нейтрально 1, при 0 — серый цвет.
Level: множитель яркости; нейтрально 1.

Эти поля меняют цвет сплатов, а не экспозицию или view transform документа. Геометрия сохраняется, но коррекция проходит по всем загруженным сплатам: миллионы требуют больше времени.

Обновление ждёт короткую паузу после перетаскивания. Пока новый результат не готов, остаётся предыдущая модель. Status доступен постоянно; Cancel Processing отменяет работу. Затем Redshift может заново накапливать собственный прогрессивный рендер.""",

"""ВЬЮПОРТ И СКОРОСТЬ

Point Preview: цветные точки в редакторе; Redshift получает полную загруженную геометрию карточек.
Preview Points (0 = All): для НОВЫХ объектов по умолчанию 50 000. Уменьшайте, если вращение тормозит. 0 рисует все загруженные точки и может сильно нагрузить редактор. Сохранённые объекты сохраняют своё значение.

Этот параметр не снижает качество рендера и память полной геометрии. Для уменьшения загруженных сплатов есть Import Quality. Редкие точки во вьюпорте не означают такую же потерю в финальном рендере.

Camera-Facing обновляет проекцию при изменении камеры, объектива или размера кадра. Цвет SH обновляется только при наличии активных зависимых от ракурса данных. Неизменённые расчёты повторно используются; Reload после каждого движения не нужен.

Переключение языка/темы Help не запускает загрузку, цвет или геометрию. Обычные интерактивные изменения показываются в Status; первая загрузка — в окне прогресса с Cancel.

Для скорости: уменьшите Preview Points для редактора, LOW/MEDIUM — для облегчения геометрии. HIGH/MAX — для деталей, если хватает памяти. Выключение Camera-Facing — компромисс точности и скорости, а не гарантированно тот же рендер.""",

"""ADVANCED / MOGRAPH

Global Scale: размер всей модели; обычно 100. Детализацию не повышает.
Pixel Footprint (variance; 0 = Off): экранный фильтр для перспективной Camera-Facing проекции; обычно 0.075. Больше расширяет/смягчает мелкие сплаты, 0 отключает фильтр.
Splat Scale: размер отдельных карточек без перемещения центров; обычно 1. Слишком много — размытие, мало — отверстия.
Maximum Splats: ТОТ ЖЕ лимит, что Import Quality. 0 — Full Source; произвольное число отображается как CUSTOM. Это не второе независимое ограничение.
Minimum Opacity (Reload): отбрасывает почти прозрачные записи при чтении. Обычно 1/255; меньше сохраняет слабые детали ценой памяти/рендера.
Opacity Multiplier: умножает прозрачность оставшихся сплатов, обычно 1; удалённые фильтром записи не возвращает.
Auto SOG Orientation: обычная система SOG Y-down в C4D Y-up. Включено у новых объектов; отключите для уже переориентированного SOG.
Flip Y Axis: дополнительное отражение Y вместе с формой гауссиан.
Redshift Material: ссылка на редактируемый узловой материал.

Create MoGraph Fracture Rig: создаёт Fracture, где каждая карточка — сегмент. Добавляйте эффекторы к Fracture. Point Preview отключается; миллионы сегментов дороги. Сохраняйте исходную сцену для дальнейших правок.

Проекция и SH вычисляются до деформеров/эффекторов, не заново для каждого изменённого сегмента или отражённого луча. Модель представлена Gaussian-карточками, а не замкнутой сеткой или нативным GPU splat-рендерером.

Status / Source Summary: прогресс, количества, фильтрация и ошибки.
Support the author - Boosty: добровольная поддержка по внешней ссылке; плагин бесплатный.""",

"""РЕШЕНИЕ ПРОБЛЕМ

В редакторе только точки: включён Point Preview. Карточки видны в Redshift; для более плотного предпросмотра увеличьте Preview Points.

На рендере модели нет: дождитесь Ready, проверьте активную камеру, видимость объекта в рендере и Redshift. Frame Loaded Scan создаст общий вид. Create Estimated Source Camera сам по себе не включает созданную камеру.

Пятна, дыры, пропали тонкие детали: сравните исходное/оставшееся количество. Попробуйте HIGH/MAX при достаточной RAM, Splat Scale 1, сглаживание 0 и Source Fidelity. Проверьте Projection Camera и порог прозрачности. MAX не исправляет плохой источник и не восстанавливает камеру автора.

Чёрные или неполные прозрачные слои: включите Auto Prepare Redshift либо нажмите Set Redshift Detail Quality. Дождитесь сходимости рендера. При разнице яркости проверьте цветовые настройки документа.

Интерьер показан снаружи: подбор по границам не умеет угадывать правильное положение внутри любого здания. Поставьте камеру в отснятую область. Скачанный SOG не обязательно содержит путь камеры с сайта.

Долго грузится / мало памяти: уменьшите Import Quality. Оценка RAM приблизительна и не гарантирует достаточную VRAM. Cancel сохраняет предыдущую готовую модель; LOW всё равно читает/проверяет файл.

Нет AI-окружения: Set Up AI / Extra Formats, затем проверьте Status. Видео использует один кадр, это не многоракурсная съёмка.

Разница с другими просмотрщиками возможна из-за композиции карточек, прозрачности, камеры и управления цветом. Больше сплатов не гарантирует идентичный рендер.""",
)


def language(value):
    return 1 if value == 1 else 0


def text(locale=0, topic=0):
    pages = RU if language(locale) else EN
    index = topic if isinstance(topic, int) and 0 <= topic < len(pages) else 0
    return pages[index]
