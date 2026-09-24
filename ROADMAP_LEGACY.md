# ScreenRec — Legacy roadmap

Статус: выпущено в 0.9.3 (`ScreenRec-0.9.3-Windows8-8.1-x64.exe`). Цель — Windows 8/8.1 x64. Windows 7 не поддерживается.

## Windows 8/8.1

- [x] Установить причину `ImportError: DLL load failed while importing QtWidgets`: Qt 6/PySide6 не поддерживает Windows до 10 1809.
- [x] Выбрать связку: Python 3.8 x64 + PySide2 5.15.2.1 + PyInstaller 5.13.2.
- [x] Зафиксировать `requirements-legacy.txt` и `scripts/setup_venv_legacy.bat` (`.venv-legacy`, `py -3.8`).
- [x] Адаптировать код через прослойку `screenrec.qt` (`SCREENREC_QT=PySide2`), без форка исходников.
- [x] Добавить `scripts/build_legacy.bat` и `scripts/launcher_legacy.py`; результат — `dist/legacy/ScreenRec.exe`.
- [x] Включить в EXE Qt5 Multimedia plugins (`wmfengine`, `dsengine`, `qtmedia_audioengine`) для проигрывателя.
- [x] Писать обычный MP4 вместо фрагментированного для совместимости с Qt5/WMF.
- [x] Заменить Windows Graphics Capture (только Windows 10+) на Pillow ImageGrab по прямоугольнику окна.
- [x] Очистка legacy-артефактов: `scripts/clean_artifacts.ps1` удаляет `dist/legacy`.
- [x] Проверить legacy EXE на Windows 8.1. *(проверено пользователем, 0.9.3)*
- [ ] Проверить legacy EXE на Windows 8 (без .1).
- [ ] Добавить отдельный smoke-скрипт для legacy EXE (сейчас — import-smoke в `.venv-legacy` и ручная проверка).

## Известные ограничения

- Захват окна снимает область экрана под окном: перекрывающие окна попадают в кадр, свёрнутое окно не записывается.
- pytest-набор выполняется только в Modern-окружении.
- `--self-test` Legacy EXE на хосте Windows 10/11 падает на проверке проигрывателя Qt5 — это ожидаемо. Критерий приёмки Legacy — ручная проверка пользователем на Windows 8/8.1.
- `scripts/release_windows.bat` собирает только Modern; Legacy для релиза собирается отдельно.
