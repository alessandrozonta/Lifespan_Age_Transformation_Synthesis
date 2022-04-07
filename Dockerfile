FROM pytorch/pytorch:1.4-cuda10.1-cudnn7-devel

# Installing necessary dependencies
RUN apt update -y; apt install -y wget cmake libsm6 libxext6 libxrender-dev libopenblas-dev liblapack-dev libgl1-mesa-glx \
libglib2.0-0 \
python3 \
python3-pip

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
