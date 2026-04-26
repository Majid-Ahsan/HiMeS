# E2E Tests with Real CalDAV Server

End-to-end tests that require a real CalDAV server connection.

## Setup

Set the following environment variables before running e2e tests:

```bash
export CALDAV_URL="https://caldav.yandex.ru/"
export CALDAV_USERNAME="your-username"
export CALDAV_PASSWORD="your-app-password"
```

Or create a `.env.e2e` file (not committed to git) with:

```
CALDAV_URL=https://caldav.yandex.ru/
CALDAV_USERNAME=your-username
CALDAV_PASSWORD=your-app-password
```

Then run tests using Makefile (recommended):

```bash
make test-e2e
```

Or manually:

```bash
set -a
source .env.e2e
set +a
uv run pytest tests/e2e/ -v
```

## Running E2E Tests

Run all e2e tests:

```bash
make test-e2e
# or
uv run pytest tests/e2e/ -v -m e2e
```

Run specific test:

```bash
uv run pytest tests/e2e/test_client_e2e.py::TestCalDAVClientE2E::test_create_and_get_event -v
```

Skip e2e tests (run only unit tests):

```bash
uv run pytest -m "not e2e"
```

## Test Coverage

E2E tests cover:

- Listing calendars
- Creating events with all features (categories, priority, recurrence, attendees)
- Getting events by UID
- Updating events
- Deleting events
- Searching events
- Extended fields in get_events

## Notes

- Tests automatically clean up created events after execution
- Tests use the first available calendar (index 0)
- Tests create events in the future to avoid conflicts
- If credentials are not set, tests will be skipped automatically
- Tests include delays between requests to avoid rate limiting
- Some calendar providers (like Yandex) may have rate limits - if tests fail with 504/timeout errors, wait a few minutes before re-running
- Some features (like categories, RRULE) may be transformed or overridden by the calendar provider
- End-to-end coverage currently runs only against Yandex Calendar; other providers should work but are not exercised here
