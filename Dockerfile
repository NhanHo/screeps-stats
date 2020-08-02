FROM python:3.8
MAINTAINER nhanho0105@gmail.com

COPY . /screeps-stats
COPY .screeps_settings.yaml /screeps-stats
WORKDIR /screeps-stats
RUN pip install -r requirements.txt
ENV ELASTICSEARCH 1

RUN git clone https://github.com/vishnubob/wait-for-it

CMD python screeps_etl/screepsstats.py
