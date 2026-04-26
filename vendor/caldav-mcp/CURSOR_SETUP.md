# Настройка MCP CalDAV в Cursor

## Быстрая настройка

1. Откройте Cursor → Settings → Features → MCP Servers → + Add new global MCP server

2. Сначала установите зависимости в проекте:

```bash
cd /Users/admalov/workspace/mcp-servers/caldav
uv sync --dev
```

3. Добавьте конфигурацию:

### Вариант 1: Использование uv run (Рекомендуется для локальной разработки)

Используйте `uv run` с указанием директории проекта:

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/admalov/workspace/mcp-servers/caldav",
        "mcp-caldav"
      ],
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Важно:** Замените `/Users/admalov/workspace/mcp-servers/caldav` на абсолютный путь к вашей папке проекта.

### Вариант 2: Прямой путь к исполняемому файлу

Если вы установили пакет через `uv sync`:

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "/Users/admalov/workspace/mcp-servers/caldav/.venv/bin/mcp-caldav",
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

### Вариант 3: Использование pip install

Если вы установили через `pip install -e .`:

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "mcp-caldav",
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Примечание:** `uvx` работает только с опубликованными пакетами из PyPI. Для локальной разработки используйте варианты выше.

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/admalov/workspace/mcp-servers/caldav",
        "mcp-caldav"
      ],
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Важно:** Замените `/Users/admalov/workspace/mcp-servers/caldav` на путь к вашей папке проекта.

## Примеры для популярных серверов

### Yandex Calendar

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/admalov/workspace/mcp-servers/caldav",
        "mcp-caldav"
      ],
      "env": {
        "CALDAV_URL": "https://caldav.yandex.ru/",
        "CALDAV_USERNAME": "your-username@yandex.ru",
        "CALDAV_PASSWORD": "your-app-password"
      }
    }
  }
}
```

**Примечание:** Для Yandex нужен пароль приложения, не основной пароль!
Получить можно здесь: https://id.yandex.ru/security/app-passwords

### Nextcloud

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/admalov/workspace/mcp-servers/caldav",
        "mcp-caldav"
      ],
      "env": {
        "CALDAV_URL": "https://your-domain.com/remote.php/dav/calendars/username/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

### ownCloud

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/admalov/workspace/mcp-servers/caldav",
        "mcp-caldav"
      ],
      "env": {
        "CALDAV_URL": "https://your-domain.com/remote.php/dav/calendars/username/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

### Apple iCloud

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/admalov/workspace/mcp-servers/caldav",
        "mcp-caldav"
      ],
      "env": {
        "CALDAV_URL": "https://caldav.icloud.com/",
        "CALDAV_USERNAME": "your-apple-id@icloud.com",
        "CALDAV_PASSWORD": "your-app-specific-password"
      }
    }
  }
}
```

**Примечание:** Для iCloud нужен app-specific пароль.
Создать можно здесь: https://appleid.apple.com/account/manage → App-Specific Passwords

## Проверка подключения

После добавления конфигурации:

1. Перезапустите Cursor
2. Откройте чат с AI ассистентом
3. Попробуйте использовать инструменты:
   - "Покажи мои календари" → должен вызвать `caldav_list_calendars`
   - "Какие события у меня сегодня?" → должен вызвать `caldav_get_today_events`

## Отладка

Если сервер не работает:

1. Убедитесь, что зависимости установлены:

   ```bash
   cd /Users/admalov/workspace/mcp-servers/caldav
   uv sync --dev
   ```

2. Проверьте, что `uv` доступен в PATH:

   ```bash
   which uv
   ```

3. Попробуйте запустить сервер вручную:

   ```bash
   cd /Users/admalov/workspace/mcp-servers/caldav
   uv run mcp-caldav --verbose
   ```

4. Проверьте путь в конфигурации - он должен быть абсолютным

5. Проверьте логи в Cursor (обычно в Developer Tools или MCP Server logs)

6. Убедитесь, что переменные окружения установлены правильно

## Дополнительные опции

Вы можете добавить дополнительные переменные окружения:

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/admalov/workspace/mcp-servers/caldav",
        "mcp-caldav"
      ],
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password",
        "MCP_VERBOSE": "true"
      }
    }
  }
}
```

`MCP_VERBOSE=true` включает подробное логирование для отладки.
