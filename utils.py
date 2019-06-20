from flask import Flask, render_template, flash, redirect, url_for, session, request, logging, jsonify
import datetime
import string
import re
import json
import collections
import xlrd
from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor
from pymongo import MongoClient
from passlib.hash import sha256_crypt


MONGO_HOST = "localhost"
MONGO_PORT = 27017
DB_NAME = 'vestano'
API_URI = 'http://svc.ebazaar-post.ir/EShopService.svc?WSDL'
test_uri = 'http://127.0.0.1:5000/soap/VestanoWebService?wsdl'
username = 'vestano3247'
password = 'Vestano3247'
#imp = Import('http://schemas.xmlsoap.org/soap/encoding/', location='http://schemas.xmlsoap.org/soap/encoding/')
imp = Import('http://www.w3.org/2001/XMLSchema', location='http://www.w3.org/2001/XMLSchema')
tns = "http://tempuri.org/"
imp.filter.add(tns)

#Config MongoDB
def config_mongodb():
    uri = "mongodb://{}:{}".format(
        MONGO_HOST,
        MONGO_PORT
    )
    cur = MongoClient(uri)[DB_NAME]
    return cur

cursor = config_mongodb()

#Read file from static/contents
def read_contents():
    contents_list = []
    path = 'static/contents/*.html'
    files = glob.glob(path)
    for content in files:
        f = open(content, 'r')
        big_data = f.read()
        f.close()
        contents_list.append(big_data)
    return contents_list

def exel(src):
    workbook = xlrd.open_workbook(src)
    worksheet = workbook.sheet_by_index(0)
    return worksheet

def inventory(cursor):
    result = cursor.vestano_inventory.find()
    inventory = []
    for r in result:
        inventory.append((r['product'], r['product_id'], r['number'], r['record_datetime']))
    return inventory

def accounting(cursor):
    result = cursor.accounting.find()
    record = []
    for r in result:
        #record.append((r['order_id'], r['parcel_code'], int(r['total_cost']), int(r['vestano_post_cost']), int(r['delivery_cost']), int(r['vat_tax']), r['record_datetime']))
        record.append((r['order_id'], int(r['total_cost']), int(r['vestano_post_cost']), r['record_datetime']))
    return record

def states(cursor):
    result = cursor.states.find()
    states = []
    for r in result:
        states.append((r['Code'], r['Name'], r['Cities']))
    return states

def cities(cursor, code):
    result = cursor.states.find_one({'Code': code})
    ans = {'Code':[], 'Name':[]}
    for r in result['Cities']:
        ans['Code'].append(r['Code'])
        ans['Name'].append(r['Name'])
    return ans

def Products(cursor, product):
    result = cursor.vestano_inventory.find_one({'product': product})
    ans = {'price':result['price'], 'weight':result['weight']}
    return ans

def GetCities(stateId):
    client = Client(API_URI)
    #Get list of cities
    cities = client.service.GetCities(
        username = username,
        password = password,
        stateId = stateId
        )
    cities_dict = client.dict(cities)
    cities_list = []
    for item in cities_dict['City']:
        cities_list.append(client.dict(item))
    return cities_list

def GetStates():
    client = Client(API_URI)
    #Get list of states
    states = client.service.GetStates(username = username, password = password)
    states_dict = client.dict(states)
    states_list = []
    for item in states_dict['State']:
        states_list.append(client.dict(item))
    return states_list

def api_test():
    client = Client(test_uri, cache=None)
    client2 = Client(API_URI)
    param_list = []
    param = {
    'username': 'jan',
    'password': '123'
    }
    param_list.append(param)
    print(client2)
    print(client)
    ns0 = client2.factory.create('ns0:ArrayOfTempProducts')
    ns00 = client2.factory.create('ns0:TempProducts')
    ns1 = client.factory.create('ns0:ProductsArray')
    ns11 = client.factory.create('ns0:Products')
    ns2 = client.factory.create('ns2:UserArray')
    ns22 = client.factory.create('ns2:User')
    #ns = client.factory.create('ns1:User_PassArray')
    print(ns1)
    print(ns11)
    #ns.User_Pass.append(param)
    #print(ns)
    ns2.User.append(param)
    #print(ns2)
    #entry_list.stringArray.append(param_list)
    #entry_list.stringArray.append(param)
    #print(entry_list)
    #entry_list = param_list
    #j_param = json.dumps(param_list)
    #print(j_param)
    client.service.datetime(v=ns2)
    #client.service.datetime('jan', '123')


def SoapClient(order):
    #client = Client(API_URI, doctor=ImportDoctor(imp))
    client = Client(API_URI)
    ns0 = client.factory.create('ns0:ArrayOfTempProducts')

    #Get Price
    price = client.service.GetDeliveryPrice(
        username = username,
        password = password,
        cityCode = order['cityCode'],
        price = order['price'],
        weight = order['weight'],
        serviceType = order['serviceType'],
        payType = order['payType']
        )

    bills = client.service.Billing(username = username, password = password)

    #products = {}
    for i in range(len(order['products']['product'])):
        #stuff_id = client.service.AddStuff(
            #username = username,
            #password = password,
            #name = order['products']['product'][i],
            #price = int(order['products']['price'][i]),
            #weight = int(order['products']['weight'][i]),
            #count = int(order['products']['counts'][i]),
            #description = order['description'],
            #percentDiscount = order['percentDiscount']
            #)

        #products = [stuff_id]
        #products = collections.OrderedDict([('Id', stuff_id), ('Count', 1), ('DisCount', 0)])
        #products.append({'Id' : int(stuff_id), 'Count' : 1, 'DisCount' : 0})
        #products = {0: {'Id' : [int(stuff_id)], 'Count' : [1], 'Discount' : [0]}}
        #products = [int(stuff_id), 1, 0]
        #products[str(i)] = {'Id' : int(stuff_id), 'Count' : 1, 'Discount' : 0}
        stuff = {
        'Id' : 716786,
        'Count' : 1,
        'Discount' : 0
        }
        products = ns0.TempProducts.append(stuff)
        print(products)
        #print(bills)
        d_price = {
        'DeliveryPrice':price.PostDeliveryPrice,
        'VatTax':price.VatTax,
        'id':str(stuff_id)
        }
        print(d_price)

    #stuff_id = result.AddStuffResult

    param = {
    'username' : username,
    'password' : password,
    'productsId' : products,
    'cityCode' : order['cityCode'],
    'serviceType' : order['serviceType'],
    'payType' : order['payType'],
    'registerFirstName' : order['firstName'],
    'registerLastName' : order['lastName'],
    'registerAddress' : order['address'],
    'registerPhoneNumber' : order['phoneNumber'],
    'registerMobile' : order['cellNumber'],
    'registerPostalCode' : order['postalCode']
    }

    add_parcel_result = client.service.AddParcel(**param)

    #add_parcel_result = client.service.AddParcel(username, password, products, order['cityCode'],
        #order['serviceType'], order['payType'], order['firstName'], order['lastName'],
        #order['address'], order['phoneNumber'], order['cellNumber'], order['postalCode'])

    #add_parcel_result = client.service.AddParcel(
        #username = username,
        #password = password,
        #productsId = products,
        #cityCode = order['cityCode'],
        #serviceType = order['serviceType'],
        #payType = order['payType'],
        #registerFirstName = order['firstName'],
        #registerLastName = order['lastName'],
        #registerAddress = order['address'],
        #registerPhoneNumber = order['phoneNumber'],
        #registerMobile = order['cellNumber'],
        #registerPostalCode = order['postalCode']
        #)

    parcel_code = {
    'ParcelCode': add_parcel_result.ParcelCode,
    'PostDeliveryPrice': add_parcel_result.PostDeliveryPrice,
    'VatTax': add_parcel_result.VatTax,
    'ErrorCode': add_parcel_result.ErrorCode,
    'Description': add_parcel_result.Description
    }

    ans = {
    'DeliveryPrice':price.PostDeliveryPrice,
    'VatTax':price.VatTax,
    'id':str(stuff_id),
    'parcel_code': parcel_code
    }

    return ans