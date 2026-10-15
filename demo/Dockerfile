FROM python:3.12-slim

WORKDIR /app

# Copy the library first so Docker can cache dependencies.
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Copy the demo.
COPY demo/ ./demo/

# Install the library + demo deps.
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir -r demo/requirements.txt

EXPOSE 8000

# Default: dry-run mode so the container works without AWS creds.
ENV BEDROCK_DEMO_DRY_RUN=1

CMD ["uvicorn", "demo.app:app", "--host", "0.0.0.0", "--port", "8000"]
