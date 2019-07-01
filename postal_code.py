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
src = r'E:\projects\VESTANO\Vestano\pcodes.xlsx'
#src = '/root/vestano/file.xlsx'

file = utils.exel(src)

sr = cursor.states.find_one({'Name': file.cell(0, 0).value})
if cursor.states.find_one({'Name': file.cell(0, 0).value}):
	print('yes ', sr['Code'])
	records = {}
	records['Code'] = sr['Code']
	records['Name'] = sr['Name']
	records['refPostalCode'] = str(int(file.cell(1, 1).value))
	records['postalCodes'] = []

	for i in range(1, 2):
		n = file.cell(i, 0).value
		for c in range(len(sr['Cities'])):
			if n == sr['Cities'][c]['Name']:
				print(sr['Cities'][c]['Code'])
				p_dict = {
				'Name': sr['Cities'][c]['Name'],
				'postalCode': str(int(file.cell(i, 1).value)),
				'Code':sr['Cities'][c]['Code']
				}
				records['postalCodes'].append(p_dict)

	cursor.postal_codes.insert_one(records)