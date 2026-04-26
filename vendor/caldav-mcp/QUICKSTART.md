# Quick Start Guide

## Быстрый старт с uv

### 1. Установка uv

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Установка зависимостей

```bash
cd caldav
uv sync --dev
```

Это создаст виртуальное окружение `.venv` и установит все зависимости.

### 3. Настройка переменных окружения

Создайте файл `.env`:

```bash
cat > .env << EOF
CALDAV_URL=https://caldav.example.com/
CALDAV_USERNAME=your-username
CALDAV_PASSWORD=your-password
EOF
```

**Примечание**: Замените URL и учетные данные на ваши. Некоторые серверы (например, iCloud, Yandex) требуют app-specific пароли. Проверьте документацию вашего провайдера календаря.

### 4. Запуск сервера

```bash
uv run mcp-caldav
```

Или с опциями:

```bash
uv run mcp-caldav --verbose
```

### 5. Запуск тестов

```bash
make test          # Unit tests
make test-e2e      # E2E tests (requires .env.e2e)
make test-cov      # With coverage
```

## Полезные команды uv

- `uv sync --dev` - Установить все зависимости (включая dev)
- `uv sync` - Установить только production зависимости
- `uv run <command>` - Запустить команду в виртуальном окружении
- `uv add <package>` - Добавить новую зависимость
- `uv remove <package>` - Удалить зависимость
- `uv lock` - Обновить lock файл

## Использование без установки (uvx)

Вы можете запустить сервер напрямую без установки:

```bash
uvx mcp-caldav
```

Это автоматически установит и запустит сервер во временном окружении.
