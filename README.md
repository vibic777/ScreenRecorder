# ScreenRec

**[English](#english)** | **[Русский](#русский)**

Desktop screen recorder built with Python / PySide6.  
Настольное приложение записи экрана на Python / PySide6.

Current version / Текущая версия: **0.7.0** · [Changelog](CHANGELOG.md) · [Release notes](RELEASE.md)

---

<a id="english"></a>

# ScreenRec (English)

Python / PySide6 screen recorder with monitor, region, window, and browser-tab capture, a recording configurator, audio options, and a single-file Windows EXE build.

## Features

- Record a selected monitor to MP4/MKV (H.264) or WebM (VP9) at 15/24/30/60 FPS.
- Three video quality levels; no audio, microphone, system audio, or both.
- Choose the output folder; settings persist between runs.
- Start/stop from the main window, **File** menu, and system tray.
- Closing with the window button minimizes to the tray; recording continues (can be disabled).
- Double-click the tray icon to restore; **Exit** quits the app.
- Quitting while recording asks for confirmation, then finishes encoding.
- Without a system tray, the close button performs a full exit with the same confirmation.
- Notifications can be disabled under **Settings**.

## Run on Windows

Current packaged build: **`releases/0.7.0/ScreenRec.exe`**. A regular build via `build_windows.bat` produces `dist/ScreenRec.exe`. No separate Python, venv, or FFmpeg install is required to run the EXE.

For development from source, use Python 3.11+:

```bat
scripts\setup_venv_windows.bat
scripts\run_windows.bat
```

Or from PowerShell in the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m screenrec.main
```

## Run on Linux

Requires an X11 graphical session, Python 3.11+ with venv, and Qt/XCB system libraries.

```bash
bash scripts/setup_venv_linux.sh
bash scripts/run_linux.sh
```

On Wayland the app reports that recording is not supported in this stage. It does not attempt partial-screen capture through XWayland. Linux still needs verification on the target machine.

## Recording configurator

Open **Recording configurator…** or **Settings → Recording configurator…**.

| Setting | Options |
|---|---|
| Format | MP4 — H.264/AAC; MKV — H.264/AAC; WebM — VP9/Opus |
| Video quality | High, balanced, compact file |
| Frame rate | 15, 24, 30, 60 |
| Audio | **None**, microphone, system audio, microphone + system audio |
| Devices | Default or a specific microphone / playback device |
| Audio quality | 96, 128, 192, 256, 320 kbps |

Defaults: MP4, balanced quality, 30 FPS, **no audio**. That mode does not open audio devices and writes a file without an audio track.  
Enable an audio mode and press **Refresh audio devices** to pick a specific device. **Save** applies settings; **Cancel** keeps the previous ones. The configurator is locked while recording.

Quality uses CRF: H.264 — 18/23/30, VP9 — 24/32/40 (high/balanced/compact).  
Windows audio: PyAudioWPatch/WASAPI. Linux: SoundCard/PulseAudio (including PipeWire Pulse compatibility; still needs Linux verification). If a selected device disappears, the app shows an error instead of silently switching to no audio.

## Build a single EXE

```bat
scripts\setup_venv_windows.bat
scripts\build_windows.bat
```

Output: `dist/ScreenRec.exe` (PyInstaller `--onefile --windowed` from `.venv`). The bundle includes Python, Qt, FFmpeg, audio modules, and app resources. Windows binaries are built on Windows; `bash scripts/build_linux.sh` builds a Linux binary on Linux.

## Storage and encoding

Recordings default to the user’s `Videos/ScreenRec` folder. Settings live in the `ScreenRec` config directory from `platformdirs`. FFmpeg comes from `imageio-ffmpeg` (`IMAGEIO_FFMPEG_EXE` overrides the path if needed).

Capture and encoding run on a worker thread. MP4 is written in fragments to reduce total loss on crash. A normal stop closes the FFmpeg input and waits; a hung encoder is killed after a timeout. Odd frame sizes are padded to even for H.264.

With audio, a temporary `.ScreenRec_….parts` folder holds video and WAV sources, then FFmpeg muxes without re-encoding video. Extra disk space is required (~11 MB/min for stereo 48 kHz WAV).

## Limitations

Hiding ScreenRec does not stop recording. Universal capture of minimized windows is not supported. Cursor overlay and autostart are not implemented yet. The monitor+camera icon has four theme-synced variants.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Two-second smoke recording of the first monitor:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_record.py
```

Standalone EXE checks:

```powershell
.\scripts\smoke_exe.ps1 -Audio both
.\scripts\smoke_exe.ps1 -Audio none -Synthetic
```

## Version and release

Current version: **0.7.0**. Local package: `releases/0.7.0/` (EXE, ZIPs, `manifest.json`, `SHA256SUMS.txt`). Build from a clean commit with `scripts/release_windows.bat`.

GitHub publication is only on an explicit user command. Push sources and attach the EXE with `scripts/publish_github.ps1` (see [RELEASE.md](RELEASE.md)). Extension store uploads and VirusTotal still need a separate command.

## Capture sources (0.3.0)

Use **Recording source** in the main window:

- **Monitor** — pick a display.
- **Region** — pick a monitor, draw a rectangle (drag to move, bottom-right to resize). Enter confirms, Esc cancels. Stored in physical coordinates of one monitor.
- **Window** — pick a window. Windows Graphics Capture keeps recording when overlapped. Expand minimized windows first. Protected content may be unavailable.
- **Browser tab** — Chrome/Edge 116+ with the local extension. Switching tabs does not change the source.

### Tab recording

1. Select the tab source and export the extension from ScreenRec (also shipped as a ZIP in the release).
2. Load it unpacked via `chrome://extensions` or `edge://extensions` (Developer mode).
3. Configure format/quality/audio, start recording, copy the connection code.
4. Open the tab, paste the code in the ScreenRec extension, start capture.
5. Stop in ScreenRec or the extension and wait for encoding. The code changes every session.

Traffic stays on `127.0.0.1` with a random token. **System audio includes other apps; there is no per-tab/window audio isolation.** Linux window capture needs XComposite; Wayland is unsupported.

## Themes (0.3.1)

**Settings → Theme** → Green / Blue / Gray / Black. UI colors and window/tray icons update immediately. Default is blue. All QSS/SVG assets are bundled in the EXE.

## Picture and text overlays (0.4.0)

Open **Picture and text…**. Configure image and/or text rectangles (percent-based), save named templates, then **Apply**. The master checkbox enables the whole layer. Overlays work for all sources/formats/audio modes. Templates are in `templates.json` next to `settings.json`. Images are not copied into the library—keep the original path. Limits: 32 MB / 32M pixels; no SVG or remote URLs.

## Build security

No UPX/obfuscation, no hidden downloads, no admin elevation. Overlay text is drawn via Qt (not shell/FFmpeg filters). Processes use argument lists without a shell. Release builds include dependency checks and SHA-256 sums. No code signing yet; antivirus false positives are possible.

## Filename builder (0.5.0)

Open **File name…**. Optional prefix (default **ScreenRec**), date, time (12/24h), and UUID. Order is fixed: prefix_date_time_UUID. Collisions get `_2`, `_3`, …. Unsafe characters are sanitized; prefix max 80 characters / 128 UTF-8 bytes.

## Logging (0.6.0)

**Settings → Logging…**. Off by default. Enable, choose a file (default `screenrec.log` next to the EXE), pick independent levels TRACE…FATAL, **Save**. Rotation: 5 MB × primary + three backups. Connection tokens, tab contents, and overlay text are not intentionally logged.

## Recordings tab and player (0.7.0)

Switch to **Recordings**. Lists MP4/MKV/WebM in the output folder with search/sort. Selecting a file shows the first frame without autoplay. Playback, seek, volume, speed, expand, fullscreen (F11), and PNG frame capture are included. The player stops and locks while a new recording runs so playback audio is not captured. Uses Qt Multimedia bundled in the EXE.

From 0.7.0 the release script builds into `build/release-<version>` then copies to `releases/<version>`, so a running `dist/ScreenRec.exe` does not block a new release.

---

<a id="русский"></a>

# ScreenRec (Русский)

Приложение записи экрана на Python / PySide6. Реализованы запись монитора, области, окна и вкладки браузера, конфигуратор, звук и сборка в один EXE.

## Возможности

- Запись выбранного монитора в MP4/MKV (H.264) или WebM (VP9), 15/24/30/60 кадров/с.
- Три уровня качества видео; запись без звука, с микрофоном, системным звуком или обоими источниками.
- Выбор папки, сохранение настроек между запусками.
- Запуск и остановка из главного окна, меню «Файл» и системного трея.
- Закрытие крестиком сворачивает окно в трей, запись продолжается. Настройка отключается.
- Двойной щелчок по трею открывает окно; «Выход» завершает приложение.
- При выходе во время записи запрашивается подтверждение, затем завершается кодирование.
- Если системный трей отсутствует, крестик вызывает полноценный выход с тем же подтверждением.
- Уведомления можно отключить в меню «Настройки».

## Запуск на Windows

Готовый текущий релиз: **`releases/0.7.0/ScreenRec.exe`**. Обычная сборка через `build_windows.bat` создаёт `dist/ScreenRec.exe`. Для его запуска Python, venv и отдельный FFmpeg не нужны: всё включено в один файл. Можно скопировать этот EXE в другую папку и запустить.

Для разработки и запуска из исходников нужен Python 3.11 или новее. Первый запуск:

```bat
scripts\setup_venv_windows.bat
scripts\run_windows.bat
```

После настройки можно запускать двойным щелчком `scripts/run_windows.bat`.
Или из PowerShell в корне проекта:

```powershell
.\.venv\Scripts\Activate.ps1
python -m screenrec.main
```

Вызов интерпретатора окружения напрямую также допустим:

```powershell
.\.venv\Scripts\python.exe -m screenrec.main
```

## Запуск на Linux

Нужен графический сеанс X11, Python 3.11+ с поддержкой venv и системные библиотеки Qt/XCB.

```bash
bash scripts/setup_venv_linux.sh
bash scripts/run_linux.sh
```

На Wayland приложение показывает сообщение об отсутствии поддержки записи в этом этапе.
Оно не пытается записывать неполный экран через XWayland. Linux требует отдельной проверки на целевой машине.

## Конфигуратор записи

Откройте кнопку **«Конфигуратор записи…»** или пункт **«Настройки → Конфигуратор записи…»**.

| Параметр | Варианты |
|---|---|
| Формат | MP4 — H.264/AAC; MKV — H.264/AAC; WebM — VP9/Opus |
| Качество видео | Высокое, сбалансированное, компактный файл |
| Частота кадров | 15, 24, 30, 60 |
| Запись звука | **Без звука**, микрофон, системный звук, микрофон + системный звук |
| Устройства | По умолчанию или конкретный микрофон / устройство воспроизведения |
| Качество звука | 96, 128, 192, 256, 320 кбит/с |

По умолчанию: MP4, сбалансированное качество, 30 FPS, **без звука**. Этот режим не открывает аудиоустройства и создаёт файл без аудиодорожки.
Для выбора конкретного устройства включите нужный режим звука и нажмите «Обновить аудиоустройства».
«Сохранить» применяет параметры; «Отмена» оставляет прежние. Текущий формат, качество и звук видны в главном окне.
Во время записи конфигуратор заблокирован. Настройки сохраняются между запусками.

Качество использует CRF: H.264 — 18/23/30, VP9 — 24/32/40 (высокое/сбалансированное/компактное).
Чем выше качество и FPS, тем больше нагрузка и размер файла. WebM может кодироваться медленнее MP4.

Windows: аудиозахват через PyAudioWPatch/WASAPI с частотой и числом каналов самого устройства.
Linux: SoundCard/PulseAudio, в том числе PipeWire с совместимостью PulseAudio; эта ветка ещё требует проверки на Linux.
Если выбранное устройство пропало или недоступно, выводится ошибка; приложение не переключается молча на запись без звука.

## Сборка в один EXE

```bat
scripts\setup_venv_windows.bat
scripts\build_windows.bat
```

Результат: `dist/ScreenRec.exe`. PyInstaller запускается только из `.venv`, с `--onefile --windowed`.
Внутри находятся Python, Qt, FFmpeg, аудиомодуль и ресурсы приложения; консольное окно при обычном запуске не появляется.
При запуске EXE PyInstaller распаковывает встроенные компоненты во временную папку — это штатная работа однофайловой сборки.
Windows-бинарник собирается на Windows; `bash scripts/build_linux.sh` собирает отдельный Linux-бинарник на Linux.

## Хранение и кодирование

По умолчанию записи сохраняются в `Videos/ScreenRec` пользователя; фактический путь
отображается в окне. Изменение папки относится к новым записям. Настройки лежат в
пользовательском каталоге конфигурации `ScreenRec`, определяемом `platformdirs`.

FFmpeg поставляется зависимостью `imageio-ffmpeg`; глобальная установка не нужна
на платформах, для которых доступен пакет с бинарником. При необходимости путь
к своему FFmpeg можно задать переменной `IMAGEIO_FFMPEG_EXE`.

Захват MSS и кодирование выполняются в рабочем потоке. MP4 записывается фрагментами
для снижения риска потери всей записи при аварии. Штатная остановка закрывает вход
FFmpeg и ждёт его завершения; зависший кодировщик принудительно завершается после тайм-аута.
При ошибке частичный файл сохраняется, а приложение показывает его путь. Принудительное
завершение процесса операционной системой не гарантирует сохранность последних кадров.
Нечётные размеры кадра дополняются до чётных для H.264.

При записи со звуком рядом с итоговым файлом создаётся служебная папка `.ScreenRec_….parts`:
в неё поступают видео и WAV источников. После остановки FFmpeg выравнивает начало дорожек,
смешивает выбранные источники и добавляет звук без повторного кодирования видео.
При успешном завершении промежуточные файлы удаляются. При ошибке они сохраняются для восстановления,
а путь показывается в сообщении. Для этой операции требуется дополнительное свободное место;
WAV занимает примерно 11 МБ/мин для стерео 48 кГц, больше для многоканальных устройств.
Задержка захвата зависит от драйвера устройства; длительные сеансы стоит проверить на своём оборудовании.

## Ограничения

Скрытие ScreenRec не останавливает запись. Универсальный захват свёрнутых окон не поддерживается. Курсор и автозапуск ещё не реализованы.
Иконка монитора с видеокамерой имеет четыре варианта, синхронизированных с темой.

## Проверки

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Автотесты используют искусственные кадры и настоящий FFmpeg: проверяют декодирование,
нечётные размеры, запрет перезаписи, ошибку захвата, повторный старт, скрытие окна,
отмену/подтверждение выхода и работу без трея. Qt работает в режиме offscreen;
нативное меню трея проверяется вручную.

Реальная двухсекундная запись первого монитора (сохраняет содержимое экрана локально):

```powershell
.\.venv\Scripts\python.exe scripts\smoke_record.py
```

Файл и JSON-отчёт с его путём остаются в `.test-output/`.

Проверка обоих источников звука:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_record.py --audio both
```

Диагностика собранного EXE (двухсекундная запись, отчёт JSON, автоматический выход):

```powershell
Start-Process -FilePath .\dist\ScreenRec.exe -ArgumentList '--self-test --output .test-output/exe --audio both' -Wait
```

Для искусственного кадра вместо экрана добавьте `--synthetic`; для формата — `--format mkv` или `--format webm`.
Обычный запуск EXE без `--self-test` открывает приложение и ничего не записывает автоматически.

Автономная проверка с копированием одного EXE в отдельную папку и исключением Python из PATH:

```powershell
.\scripts\smoke_exe.ps1 -Audio both
.\scripts\smoke_exe.ps1 -Audio none -Synthetic
.\scripts\smoke_exe.ps1 -Audio microphone -Format mkv -Synthetic
.\scripts\smoke_exe.ps1 -Audio system -Format webm -Synthetic
```

Историческая проверка версии 0.2.0 на Windows, Python 3.13.14: 9 автотестов, включая 9 сочетаний формата/качества,
отсутствие звука, смешивание двух дорожек и декодирование результата. Реальный захват 2560×1080
с микрофоном и системным звуком: 31 кадр / 2,06 секунды, H.264 + AAC stereo.
Зависимости: PySide6 6.11.2, mss 10.2.0, imageio-ffmpeg 0.6.0, platformdirs 4.11.8,
PyAudioWPatch 0.2.12.8, PyInstaller 6.22.3.

Готовый однофайловый EXE также проверен отдельно от исходников и venv с очищенным PATH:
MP4 с реальным экраном и обоими источниками; MP4 без аудио; MKV с микрофоном;
WebM с системным звуком. Все четыре записи декодируются, приложение и дочерние процессы
завершаются. Используется FFmpeg из временной распаковки самого EXE. Размер сборки — около 90 МБ.
Нативное поведение трея и длительные записи остаются предметом ручной проверки.

Ручная проверка: начать запись → закрыть окно крестиком → открыть из трея →
остановить → воспроизвести MP4; повторить запись и выбрать «Выход», сначала отменив,
затем подтвердив завершение.

## Версия и выпуск релиза

Текущая версия — **0.7.0**. [Изменения](CHANGELOG.md) · [Инструкции релиза](RELEASE.md).
Локальный комплект: `releases/0.7.0/` — EXE, ZIP приложения, исходники, manifest.json и SHA256SUMS.txt.
Подготовка из чистого Git-коммита: `scripts/release_windows.bat`.
После завершённых изменений обязательны актуализация проекта, документации и инструкций, проверки, коммит и сборка релиза. Правило закреплено в AGENT.md.

Публикация в GitHub — только по прямой команде пользователя. Локальные коммиты и теги создаются до публикации; EXE выкладывается как GitHub Release asset через `scripts/publish_github.ps1` (см. RELEASE.md). Магазины расширений и внешние сервисы по-прежнему требуют отдельной команды.

## Выбор источника в 0.3.0

В главном окне используйте список «Источник записи».

- Монитор: выберите нужный экран.
- Область: выберите монитор и кнопку выбора области. Протяните прямоугольник мышью; перемещайте его внутри, меняйте размер за нижний правый угол. Enter подтверждает, Esc отменяет. Область сохраняется в физических координатах одного монитора; после перестановки экранов выберите её заново.
- Окно: выберите конкретное окно, при необходимости обновите список. Windows Graphics Capture записывает окно даже при перекрытии. Сначала разверните свёрнутое окно. Если сворачивание остановит кадры, запись завершится с сообщением. Защищённый контент может быть недоступен.
- Вкладка браузера: Chrome/Edge 116+ с локальным расширением. Переключение на другую вкладку не меняет источник.

### Запись вкладки

1. Выберите источник вкладки и экспортируйте расширение кнопкой в ScreenRec (оно встроено в EXE). Альтернатива — ZIP расширения в релизе.
2. Откройте chrome://extensions или edge://extensions, включите режим разработчика, выберите «Загрузить распакованное расширение» и экспортированную папку. Установка выполняется пользователем один раз.
3. Настройте формат, качество и звук в ScreenRec, начните запись и скопируйте показанный код подключения.
4. Откройте нужную вкладку, нажмите значок расширения ScreenRec, вставьте код и начните захват.
5. Остановите запись в ScreenRec или расширении и дождитесь завершения кодирования. Для следующей записи код меняется.

Данные передаются только через 127.0.0.1 со случайным токеном, без облачных сервисов. Расширение снимает видео; звук записывается выбранными устройствами ScreenRec. **Системный звук включает другие приложения; изоляции звука вкладки/окна нет.** Режим «Без звука» доступен всем источникам. Вкладка временно записывается в WebM и затем преобразуется в выбранный формат: нужны место и время на завершение.

Linux: окно требует XComposite и композитного менеджера X11. Изменение размера/сворачивание может завершить запись; эта ветка не проверена на Linux. Wayland не поддерживается.

### Проверка новых источников

13 автотестов включают DPI/координаты области, авторизацию моста, порядок фрагментов, отмену подключения и преобразование вкладки. scripts/smoke_sources.py проверяет настоящее окно под перекрытием и область на Windows. scripts/smoke_browser.py проверяет настоящее расширение при переключении вкладок; требует requirements-dev.txt и Chromium Playwright. Путь браузеров задаётся PLAYWRIGHT_BROWSERS_PATH; используется отдельный тестовый профиль.

EXE: --self-test --window-fixture --output .test-output/exe-window проверяет встроенный захват HWND. JSON-отчёт должен содержать ok: true.

## Темы оформления (0.3.1)

Откройте **Настройки → Тема** и выберите **Зелёная, Синяя, Серая или Чёрная**. Цвета фона, кнопок и акцентов, иконки главного окна и трея меняются сразу. Выбор сохраняется после перезапуска; по умолчанию используется синяя тема. Переключение доступно во время записи и не перезапускает её. Все четыре QSS и SVG включены в один EXE. Значок самого EXE в Проводнике остаётся синим: это статический ресурс файла, а тема меняет иконки работающего приложения. Диагностика --self-test проверяет все четыре темы и сохраняет снимки theme-*.png.

## Картинка и текст поверх записи (0.4.0)

1. Нажмите **«Картинка и текст…»** в главном окне или меню «Настройки».
2. Выберите элемент «Картинка», загрузите PNG/JPEG/BMP/WebP и включите «Показывать этот элемент». PNG с прозрачностью поддерживается; картинка вписывается в прямоугольник с сохранением пропорций.
3. Выберите «Текст», включите его, введите подпись, выберите шрифт, размер и цвет. Текст переносится по ширине и обрезается по высоте блока.
4. Перемещайте каждый прямоугольник мышью, меняйте размер за нижний правый угол. Точные X/Y, ширина, высота и непрозрачность задаются в процентах. Размер шрифта — процент высоты кадра.
5. Для повторного использования задайте имя и нажмите «Сохранить шаблон». Для выбора ранее сохранённого — выберите имя и нажмите «Загрузить». Сохранение под существующим именем обновляет этот шаблон.
6. Нажмите «Применить». Общий флажок «Накладывать картинку / текст» включает или отключает весь слой. «Отмена» не меняет активное наложение; явно сохранённые именованные шаблоны остаются в библиотеке.

Картинка и текст работают одновременно; текст находится поверх картинки. Предпросмотр — макет кадра, а не живой видеопоток. Для монитора/области/окна он использует пропорции выбранного источника, для вкладки до подключения — 16:9. Относительные координаты пересчитываются под фактическое разрешение записи.

Наложения работают для монитора, области, окна и вкладки, со всеми форматами и режимами звука. Редактор блокируется во время записи; настройки относятся к следующему сеансу. Шаблоны хранятся в templates.json рядом с settings.json. Картинки не копируются в библиотеку: сохраните исходный файл по выбранному пути. Недоступная включённая картинка вызывает ошибку.

Поддерживаются две отдельные области (одна картинка и один текст), без сцен, анимации и произвольного числа слоёв OBS. Изображения ограничены 32 МБ и 32 миллионами пикселей. SVG и удалённые URL в наложениях не принимаются.

Проверки: 16 автотестов, включая видеокадры MP4/MKV/WebM, прозрачность, координаты, шаблоны, перетаскивание и запись вкладки. --self-test теперь проверяет наложение в декодированном видео и сохраняет overlay-editor.png.

## Безопасность сборки

Сборка без UPX и обфускации, без скрытых загрузок и запроса прав администратора. Текст рисуется буквально через Qt и не вставляется в команды/фильтры FFmpeg; процессы запускаются списком аргументов без shell. Пути шаблонов не вычисляются из их имён. Проверка зависимостей и SHA-256 включена в выпуск релиза. Это не гарантирует отсутствие ложных срабатываний антивирусов; цифровой подписи пока нет. Загрузка EXE/исходников в VirusTotal или другие внешние сервисы требует отдельной прямой команды пользователя.

## Конструктор имени записи (0.5.0)

Откройте **«Имя файла…»** в главном окне, меню «Настройки» или конфигураторе записи.

- Префикс: свой текст; по умолчанию **ScreenRec**. Можно оставить пустым.
- Галочка даты: включение независимо от времени. Порядки год-месяц-день, день-месяц-год, месяц-день-год; варианты с точками и компактный YYYYMMDD.
- Галочка времени: 24 часа (18-05-09), 12 часов с AM/PM (06-05-09_PM), компактные 24 часа (180509). Двоеточия заменены дефисами для совместимости с Windows.
- Галочка UUID: новый полный UUID для каждой записи или имя без него.
- Предпросмотр показывает результат с выбранным расширением; UUID в примере условный. «По умолчанию» возвращает ScreenRec + дату YYYY-MM-DD + время 24 часа + UUID.

Порядок компонентов фиксирован: префикс, дата, время, UUID; разделитель — подчёркивание. Например: Урок_13-09-2026_06-05-09_PM.mp4. Используется местное время компьютера в начале подготовки сеанса (для вкладки — до подключения расширения). Имя одинаково формируется для всех источников.

«Сохранить» применяет настройки к следующим записям, «Отмена» оставляет предыдущие. Внутри конфигуратора нужно также сохранить сам конфигуратор. Во время записи изменение имени заблокировано.

Если префикс пуст и все компоненты выключены, используется ScreenRec.mp4 (или выбранное расширение). При совпадении добавляются _2, _3 и далее. Имя резервируется на время сеанса, в том числе между экземплярами ScreenRec; FFmpeg дополнительно запрещает перезапись. Незавершённые служебные папки также считаются занятыми именами.

Недопустимые символы и управляющие коды заменяются подчёркиваниями, зарезервированные имена Windows исправляются; предпросмотр показывает результат. Префикс ограничен 80 символами и 128 байтами UTF-8. Нельзя задать путь через префикс. Поля сохраняются в settings.json, старые настройки автоматически получают значения по умолчанию.

Проверки: 19 автотестов, включая полночь/полдень AM/PM, форматы даты, Unicode, сохранение/отмену и параллельные записи без UUID. Диагностика готового EXE проверяет пользовательское имя Custom и сохраняет filename-editor.png.

## Логирование (0.6.0)

Откройте **Настройки → Логирование…**. По умолчанию логгер **выключен**: файл не создаётся, события не дописываются даже при FATAL.

1. Включите «Включить логирование».
2. Выберите файл или оставьте путь по умолчанию — screenrec.log рядом с запущенным EXE. При запуске из исходников — рядом с src/screenrec/main.py.
3. Отметьте нужные уровни: **TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL, FATAL ERROR**. Галочки независимы: DEBUG не включает INFO автоматически. По умолчанию выбраны INFO/WARNING/ERROR/CRITICAL/FATAL; TRACE и DEBUG выключены.
4. Нажмите «Сохранить». Изменения применяются сразу, без перезапуска, в том числе во время записи. «Отмена» сохраняет прежние настройки.
5. Кнопки «Открыть лог» и «Открыть папку» дают доступ к выбранному пути.

Строки содержат местную дату/время, уровень, модуль и сообщение. Пишутся события запуска/выхода, изменения настроек, источника записи, захвата, FFmpeg, звука, наложений, подключения браузера и сохранения. TRACE показывает прогресс захвата раз в пять секунд. Необработанные исключения относятся к FATAL и запускают корректное завершение; отключение галочки влияет только на запись события.

Ротация: файл до 5 МБ и три резервные копии screenrec.log.1–.3 (примерно 20 МБ суммарно; отдельная длинная строка может превысить порог). При недоступном пути используется путь по умолчанию с предупреждением. Если недоступны оба, логирование отключается. Папка должна существовать. При ошибке записи/ротации вывод в файл прекращается с предупреждением, запись видео продолжается. Для одновременных экземпляров программы выбирайте разные лог-файлы: ротация синхронизирована между потоками одного процесса.

Без отмеченных уровней файл может быть создан, но события не пишутся. После отключения уже существующие логи не удаляются. Токены подключения, содержимое вкладок и текст наложений специально не логируются; сообщения об ошибках могут содержать пути файлов. Логи и EXE не отправляются во внешние сервисы без прямой команды пользователя.

Проверки: 22 автотеста, включая независимые уровни, выключенный FATAL, ротацию, запись из потоков, отказ диска и резервный путь. Диагностика --self-test проверяет логгер внутри EXE, создаёт diagnostic.log в указанной тестовой папке и снимок logging-editor.png; это явный тестовый режим.

## Вкладка «Записи» и проигрыватель (0.7.0)

Переключитесь с вкладки **«Запись»** на **«Записи»**. Слева показаны MP4/MKV/WebM из выбранной папки записи: имя, дата изменения и размер. Доступны поиск по имени, сортировка и «Обновить». Подпапки и файлы активных сеансов ScreenRec не показываются.

Выберите файл: справа загрузится первый кадр без автоматического воспроизведения со звуком. Длительность видна под шкалой, разрешение — рядом с именем после чтения метаданных.

- Стандартные кнопки: предыдущая запись, воспроизведение/пауза, стоп, следующая запись. Стоп возвращает позицию и предпросмотр в начало.
- Перемотка: перетаскивание ползунка и кнопки −10/+10 секунд. Стрелки в области плеера — ±5 секунд, Пробел — воспроизведение/пауза.
- Громкость, отключение звука, скорость 0.25×/0.5×/1×/1.5×/2×.
- «Развернуть» скрывает список для большого просмотра; повторное нажатие возвращает его. Границу списка и плеера можно перетаскивать.
- «Полный экран» или F11 открывает просмотр с управлением на весь экран. Esc/F11 возвращает обратно.
- «Снимок кадра…» сохраняет текущий кадр в PNG.
- Предыдущая/следующая работают в текущем порядке видимого списка; автоматического перехода после окончания нет.

После сохранения новая запись появляется в списке и выбирается для просмотра. При переходе на вкладку показывается её кадр; звук самостоятельно не запускается. При начале новой записи плеер останавливается и блокируется до её завершения, чтобы звук воспроизведения не попал в системный аудиозахват. Переход обратно на вкладку записи или сворачивание в трей также останавливает плеер.

Используются Qt Multimedia и встроенные в EXE компоненты воспроизведения. Отдельный проигрыватель не нужен. Проверены H.264 в MP4/MKV, VP9 в WebM и чтение AAC. Поддержка иных файлов зависит от кодеков; повреждённые файлы показывают ошибку внутри плеера. Linux ещё требует отдельной проверки.

Каталог пока без миниатюр в каждой строке, массового сбора метаданных, переименования/удаления и покадрового шага. Длительность/разрешение показываются для выбранного файла. «Открыть папку» позволяет работать с файлами через Проводник.

Проверки: 25 автотестов; реальные декодированные кадры трёх форматов, воспроизведение/пауза/стоп, перемотка, навигация, звук/скорость, повреждённый файл и полный экран. --self-test проверяет плеер в однофайловом EXE и сохраняет player.png и player-frame.png.

Начиная с 0.7.0 скрипт релиза собирает EXE в build/release-<версия> и переносит копию в releases/<версия>. Это позволяет выпустить новую версию, пока старая dist/ScreenRec.exe запущена. Скрипт релиза не заменяет работающий EXE; для проверки запускайте файл из каталога новой версии.
