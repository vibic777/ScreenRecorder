# Локальный релиз ScreenRec 0.3.0

Запустите ScreenRec.exe, выберите монитор, область, окно или вкладку и настройте конфигуратор. По умолчанию звук выключен. Python и отдельный FFmpeg не нужны. Для вкладки установите расширение вручную по README.md: экспортируйте из EXE или распакуйте ZIP.

Windows x64: один EXE включает Python, Qt, FFmpeg, захват окон, звук и файлы расширения. Linux-бинарника нет; Linux X11 требует проверки. Свёрнутые/защищённые окна не гарантируются. Системный звук включает другие приложения.

## Комплект

releases/0.3.0/: ScreenRec.exe, ZIP приложения с папкой browser-extension, отдельный ZIP расширения, ZIP исходников, документация, requirements-windows-lock.txt, manifest.json и SHA256SUMS.txt. Манифест содержит точный коммит. Проверка: Get-FileHash -Algorithm SHA256 <файл>.

## Выпуск

1. Обновить код, AGENT.md, README.md, CHANGELOG.md и RELEASE.md. Обновить версию в pyproject.toml и манифесте расширения.
2. Настроить venv через scripts/setup_venv_windows.bat. Выполнить python -m pip check и python -m unittest discover -s tests -v.
3. Проверить новые источники scripts/smoke_sources.py и scripts/smoke_browser.py (требует requirements-dev.txt и Chromium Playwright). При изменении звука использовать scripts/smoke_exe.ps1.
4. Проверить diff, создать локальный коммит. Рабочее дерево должно быть чистым.
5. Запустить scripts/release_windows.bat: проверки, сборка одного EXE, автономная синтетическая запись, архивы, манифест и SHA-256.
6. Проверить EXE с --self-test --window-fixture --output .test-output/exe-window и прочитать JSON-отчёт. Обычный запуск автоматически ничего не записывает.
7. После успешных проверок создать локальный аннотированный тег git tag -a v0.3.0 -m "ScreenRec 0.3.0".

Готовые версии не перезаписываются. После ошибки остаётся .pending. Артефакты, venv и тестовые записи не коммитятся.

**Никогда не публиковать код, коммиты, теги, релизы или расширение в GitHub и других внешних сервисах без отдельной прямой команды пользователя.**
