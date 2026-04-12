FROM python:3.11-slim

# System deps for whisper + audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node.js installieren (benötigt für Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI installieren
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install mcp-server-time --break-system-packages

COPY . .

# Non-root user (Claude CLI verweigert --dangerously-skip-permissions als root)
RUN useradd -m -u 1000 himes

# Persistent dirs + fix permissions for all app files
RUN mkdir -p /app/data /app/logs && chown -R himes:himes /app

USER himes

EXPOSE 8080

CMD ["python", "-m", "core.orchestrator"]
