FROM python:3.11-slim AS base

LABEL maintainer="Pedro Arte Labs"
LABEL description="PACME — Pedro Arte Creative Mind Engine"

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir -e .

COPY config/ config/
COPY prompts/ prompts/
COPY memory/core_dna/ memory/core_dna/
COPY memory/evolving_dna/ memory/evolving_dna/

RUN mkdir -p memory/episodic memory/semantic memory/creative \
    memory/rejected memory/successful memory/experiments \
    memory/graveyard memory/canon memory/dead_letter memory/.state \
    logs outputs input

ENTRYPOINT ["python", "-m", "creative_brain.cli.main"]
CMD ["demo"]
