ARG REPOSITORY_URL=""
FROM ${REPOSITORY_URL:+$REPOSITORY_URL/base/}python:3.12.11-slim AS python-base

ENV PIP_NO_CACHE_DIR=off \
    PYTHONUNBUFFERED=1 \
    LC_ALL=C \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_PATH=/opt/poetry \
    PERL5LIB=/usr/local/lib/perl5 \
    VENV_PATH=/app/.venv \
    PYTHONPATH="$PYTHONPATH:/app"
ENV PATH="/usr/lib/libreoffice/program:$POETRY_PATH/bin:$VENV_PATH/bin:$PATH"

FROM python-base AS poetry
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    libgl1 \
    libglib2.0-0 \
    libgtk2.0-dev \
    curl \
    git \
    # deps for building python deps
    build-essential \
    # LibreOffice for .doc to .docx conversion (headless)
    libreoffice-writer \
    libreoffice-core \
    libreoffice-common \
    # cleanup
    && rm -rf /var/lib/apt/lists/* \
    # Create symlink for soffice to make it available in PATH
    && ln -sf /usr/lib/libreoffice/program/soffice /usr/bin/soffice \
    && pip install pip==21.2.4 \
    && curl -sSL https://install.python-poetry.org | POETRY_HOME=$POETRY_PATH python3 - \
    && poetry --version \
    && poetry config virtualenvs.in-project true

COPY ./cpanmin.pl /bin/cpanm
RUN chmod +x /bin/cpanm \
    && cpanm App::cpm \
    && cpanm Module::Build \
    && cd /usr \
    && cpm install Plack \
    && cpm install \
    Carp \
    Encode \
    Getopt::Long \
    IO::String \
    Pod::Usage \
    Email::Sender \
    Email::MIME \
    Email::MIME::ContentType \
    Email::Simple \
    Email::Address \
    OLE::Storage_Lite \
    && cd / \
    && git clone https://github.com/mvz/email-outlook-message-perl.git \
    && cd /email-outlook-message-perl \
    && perl Build.PL \
    && ./Build \
    && ./Build install

FROM poetry AS build
WORKDIR /app
COPY ./vendors ./vendors
COPY poetry.lock pyproject.toml ./

RUN poetry install --no-interaction --no-ansi --no-root --only main && rm -rf ~/.cache/pypoetry/

FROM build AS develop

RUN poetry install --no-interaction --no-ansi --no-root && rm -rf ~/.cache/pypoetry/
COPY . ./

FROM python-base AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
    # LibreOffice for .doc to .docx conversion (headless)
    libreoffice-writer \
    libreoffice-core \
    libreoffice-common \
    # cleanup
    && rm -rf /var/lib/apt/lists/* \
    # Create symlink for soffice to make it available in PATH
    && ln -sf /usr/lib/libreoffice/program/soffice /usr/bin/soffice

COPY --from=build $VENV_PATH $VENV_PATH
COPY . ./
