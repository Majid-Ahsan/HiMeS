# CalDAV Provider Notes

## Yandex Calendar

**Server URL**: `https://caldav.yandex.ru/`

### ⚠️ Known Limitations

**Rate Limiting**: Yandex Calendar artificially slows down WebDAV operations (60 seconds per MB since 2021).

**Symptoms**:
- Frequent 504 Gateway Timeout errors
- Especially common when creating/updating events
- Operations may take significantly longer than expected

**Recommendations**:

1. **For Write Operations** (create/update/delete):
   - Add manual delays (at least 2–5 seconds) between requests
   - Wait several minutes before retrying failed operations
   - Batch writes carefully to avoid triggering throttling

2. **For Read Operations**:
   - Reading events is generally more reliable
   - Still may experience delays with large calendars

3. **Best Practices**:
   - Avoid rapid successive write operations
   - Add delays between operations (2-5 seconds minimum)
   - Consider using Google Calendar or Nextcloud for write-heavy workloads

### Configuration

The `CalDAVClient` does not implement automatic retry logic. If you experience throttling, add manual `sleep` calls between operations or schedule writes during off-peak hours.

> **Testing status**: The project’s end-to-end tests run against Yandex Calendar. Other CalDAV providers follow the same protocol and should work, but they have not been exercised end-to-end yet.

### Alternative Providers

If you need more reliable write operations, consider:

- **Google Calendar**: More reliable, better rate limits
- **Nextcloud**: Self-hosted, full control over rate limits
- **iCloud Calendar**: Good reliability, standard CalDAV support

## Other Providers

### Google Calendar

**Server URL**: `https://apidata.googleusercontent.com/caldav/v2/`

- Generally more reliable than Yandex
- Better rate limiting
- Standard CalDAV support

### Nextcloud

**Server URL**: `https://your-nextcloud-instance.com/remote.php/dav/calendars/`

- Self-hosted option
- Full control over rate limits
- Excellent CalDAV support

### iCloud Calendar

**Server URL**: `https://caldav.icloud.com/`

- Reliable service
- Standard CalDAV support
- Good for personal use
