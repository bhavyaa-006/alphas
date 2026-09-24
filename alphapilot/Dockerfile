FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    ALPHAPILOT_DOCKER=1 \
    ALPHAPILOT_HOME=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ACE_API__Gold_ (ace_lib.py, helpful_functions.py) - put the folder WorldQuant
# gave you next to this Dockerfile before building, see README.
COPY ACE_API__Gold_/ /app/ace/
ENV PYTHONPATH=/app/ace

COPY alphapilot/ /app/alphapilot/
COPY packs/ /app/packs/
COPY setup.py /app/

RUN pip install --no-cache-dir -e .

VOLUME ["/data"]

ENTRYPOINT ["alphapilot"]
CMD ["menu"]
