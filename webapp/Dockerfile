FROM ubuntu:22.10
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update 

RUN apt install -y software-properties-common

RUN add-apt-repository ppa:alessandro-strada/ppa

RUN apt update 

RUN apt install -y ffmpeg libsm6 libxext6

#RUN apt install -y google-drive-ocamlfuse

RUN apt install -y python3.11

RUN apt install -y python3-pip

RUN apt install -y curl

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

#RUN mkdir /mnt/gdrive

COPY . /app
WORKDIR /app

#CMD ["python3", "=m", "ptvsd", "--port", "", "main_webapp.py"]
#CMD ["python3", "main_webapp.py"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
