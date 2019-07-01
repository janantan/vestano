from pymongo import MongoClient
from sshtunnel import SSHTunnelForwarder
import datetime
import jdatetime
import xlrd
import utils

MONGO_HOST = "185.10.74.26"
MONGO_DB = "vestano"
MONGO_USER = "root"
MONGO_PASS = "9ijnBGT200840"

def config_mongodb(host):
    uri = "mongodb://{}:{}".format(
        host,
        27017
    )
    cur = MongoClient(uri)['vestano']
    return cur

cursor = config_mongodb('127.0.0.1')

server = SSHTunnelForwarder(
    MONGO_HOST,
    ssh_username=MONGO_USER,
    ssh_password=MONGO_PASS,
    remote_bind_address=('127.0.0.1', 27017)
)

server.start()

# server.local_bind_port is assigned local port
client = MongoClient('127.0.0.1', server.local_bind_port)
host_cursor = client[MONGO_DB]

#l_p_r = l_cursor.postal_codes.find()
#for rec in l_p_r:
	#db.postal_codes.insert_one(rec)

server.stop()