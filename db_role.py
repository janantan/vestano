#coding: utf-8
from pymongo import MongoClient
from passlib.hash import sha256_crypt
import datetime
import jdatetime
import xlrd
import random2
import utils

def config_mongodb():
    uri = "mongodb://{}:{}".format(
        'localhost',
        27017
    )
    cur = MongoClient(uri)['vestano']
    return cur

cursor = config_mongodb()

cursor = utils.config_mongodb()
src = r'E:\projects\VESTANO\Vestano\file.xlsx'
#src = '/root/vestano/file.xlsx'

file = utils.exel(src)

for i in range(1, file.nrows):
	records = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
	pid = file.cell(i, 0).value
	records['productId'] = pid[3:]
	records['productName'] = file.cell(i, 1).value
	records['price'] = int(file.cell(i, 2).value)
	records['percentDiscount'] = int(file.cell(i, 3).value)	
	records['weight'] = int(file.cell(i, 4).value)
	records['count'] = int(file.cell(i, 5).value)
	records['recordDate'] = file.cell(i, 6).value
	records['description'] = file.cell(i, 7).value
	records['vendor'] = u'روژیاپ'
	records['record'] = []
	add = {}
	add['action'] = 'add'
	add['datetime'] = records['datetime']
	add['count'] = records['count']
	add['person'] = 'firs_init'
	records['record'].append(add)
	#print(records)

	cursor.vestano_inventory.insert_one(records)

utils.init_status_inventory()
