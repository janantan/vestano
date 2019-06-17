from pymongo import MongoClient
from passlib.hash import sha256_crypt
import datetime
import jdatetime
import xlrd
import random2
import utils

cursor = utils.config_mongodb()
#src = r'E:\projects\VESTANO\file.xlsx'
src = r'E:\projects\VESTANO\file.xlsx'

file = utils.exel(src)

for i in range(1, file.nrows):
	records = {'record_datetime' : jdatetime.datetime.now().strftime('%d / %m / %Y')}
	records['order_id'] = str(int(file.cell(i, 0).value))
	records['customer'] = file.cell(i, 1).value
	records['phone'] = file.cell(i, 2).value
	records['address'] = file.cell(i, 3).value
	records['product'] = file.cell(i, 4).value
	records['paid_cost'] = file.cell(i, 5).value
	records['vestano_post_cost'] = file.cell(i, 6).value
	records['total_cost'] = file.cell(i, 7).value
	records['remarks'] = file.cell(i, 8).value

	cursor.accounting.insert_one(records)
	#cursor.rozhyap_inventory.insert_one(records)


#for i in range(1, file.nrows):
	#if cursor.vestano_inventory.find_one({"product": file.cell(i, 1).value}):
		#r = cursor.vestano_inventory.find_one({"product": file.cell(i, 1).value})
		#cursor.vestano_inventory.update_many(
            #{"product": file.cell(i, 1).value},
            #{'$set': {
            #"product": file.cell(i, 1).value,
            #'price' : int(file.cell(i, 2).value),
            #'weight' : file.cell(i, 4).value,
            #'remarks' : file.cell(i, 7).value
            #}
            #}
            #)
	#else:
		#records = {'record_datetime' : jdatetime.datetime.now().strftime('%d / %m / %y')}
		#records['product_id'] = str(random2.randint(1000000, 9999999))
		#records['product'] = file.cell(i, 1).value
		#records['number'] = int(file.cell(i, 5).value)
		#records['delivery_date'] = file.cell(i, 6).value
		#records['price'] = int(file.cell(i, 2).value)
		#records['weight'] = file.cell(i, 4).value
		#records['remarks'] = file.cell(i, 7).value

		#cursor.vestano_inventory.insert_one(records)

	#records = {'record_datetime' : jdatetime.datetime.now().strftime('%d / %m / %Y')}
	#records['product_id'] = str(random2.randint(1000000, 9999999))
	#records['product'] = file.cell(i, 0).value
	#records['number'] = int(file.cell(i, 1).value)
	#records['delivery_date'] = file.cell(i, 2).value

	#cursor.vestano_inventory.insert_one(records)
	#cursor.rozhyap_inventory.insert_one(records)