FROM python:3.11.5-bullseye
ENV env_settings=prod
WORKDIR /app
COPY . /app
ENV TZ=Europe/Istanbul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN sed -i -E 's/MinProtocol[=\ ]+.*/MinProtocol = TLSv1.0/g' /etc/ssl/openssl.cnf
RUN pip install --upgrade pip setuptools
RUN pip install --default 1000 -r requirements.txt
EXPOSE 4000
EXPOSE 3000
