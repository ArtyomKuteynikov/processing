sudo apt update

sudo apt install postgresql postgresql-contrib sudo apt install postgresql postgresql-contrib

sudo apt install postgresql postgresql-contrib
 
sudo systemctl start postgresql.service

sudo -i -u postgres psql

alter user postgres with encrypted password 'L0l!k1510';

create database XLfoodDB;

grant all privileges on database XLfoodDB to postgres;

curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list

sudo apt-get update

sudo apt-get install redis

sudo service redis-server start

redis-cli
