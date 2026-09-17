# ScreenRec — Legacy roadmap

Статус: ПАУЗА до развёртывания пользователем VM Windows 8. Выполняется на `GPT-5.6 Luna`.

## Windows 7/8/8.1

- [ ] Воспроизвести ошибку `ImportError: DLL load failed while importing QtWidgets` на Windows 7, 8 и 8.1 в VM. _(отложено до VM пользователя)_
- [x] Установить причину: Qt 6/PySide6 не поддерживает старые Windows; текущая modern-сборка рассчитана на Windows 10 1809+ и Windows 11 x64.
- [x] Выбрать базовую связку: Python 3.8 x64 + PySide2 5.15.2.1 + PyInstaller 5.13.2.
- [x] Зафиксировать `requirements-legacy.txt` и `scripts/setup_venv_legacy.bat`.
- [ ] Адаптировать код с PySide6 на PySide2.
- [ ] Добавить скрипт `scripts/build_legacy.bat`.
- [ ] Собрать `ScreenRec-legacy.exe`.
- [ ] Добавить безопасную очистку legacy-артефактов.
- [ ] Проверить запись, звук, источники, браузерную вкладку, проигрыватель и профили.
- [ ] Проверить legacy EXE на Windows 7/8/8.1.

## Блокеры

- Нет Python 3.8 в текущей системе.
- Нет VM Windows 7/8/8.1.
- Код требует адаптации PySide6 → PySide2.
- Legacy-ветка не считается рабочей до проверки на целевых системах.