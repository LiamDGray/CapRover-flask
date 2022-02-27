#Create a Ubuntu base image with Python 3 and Redis installed.
#See also https://pythonspeed.com/articles/activate-virtualenv-dockerfile/

FROM python:3.10-slim-bullseye

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV VIRTUAL_ENV=/opt/venv
# trunk-ignore(hadolint/DL3008)
RUN : \
 && apt-get update \
 && apt-get -y --no-install-recommends install curl gnupg redis \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv $VIRTUAL_ENV \
 && curl https://cli-assets.heroku.com/install-ubuntu.sh | /bin/bash
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /

# Install dependencies:
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#Expose the required port
EXPOSE 5000

# Run the application:
COPY server.py .
COPY worker.py .
COPY dict2.py .
COPY Procfile .
CMD ["/bin/bash", "start.sh"]
