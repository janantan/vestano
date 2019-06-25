#coding: utf-8
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

def temp_orders(cursor):
    result = cursor.temp_orders.find()
    temp = []
    for r in result:
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        temp.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['serviceType'], r['registerCellNumber']))
    return temp

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

def details(cursor, code):
    city = ""
    price = 0
    count = 0
    discount = 0
    r = cursor.temp_orders.find_one({'orderId': code})
    state_result = cursor.states.find_one({'Code': r['stateCode']})
    for rec in state_result['Cities']:
        if r['cityCode'] == rec['Code']:
            city = rec['Name']
            break
    for p in r['products']:
        price = price + p['price']*p['count']
        count = count + p['count']
        discount = discount + p['percentDiscount']

    details = (r['orderId'], r['vendorName'], r['record_time']+' - '+r['record_date'],
        r['registerFirstName']+' '+r['registerLastName'], r['registerCellNumber'], r['registerPostalCode'],
        r['serviceType'], r['payType'], state_result['Name']+' - '+city+' - '+r['registerAddress'],
        r['products'],count, price, discount, code)
    return details

def typeOfServicesToString(serviceType, payType):
    if serviceType==1:
        sType = u'پست پیشتاز'
    elif serviceType==2:
        sType = u'پست سفارشی'
    elif serviceType==3:
        sType = u'مطبئع'

    if payType==88:
        pType = u'ارسال رایگان'
    elif payType==1:
        pType = u'پرداخت در محل'
    elif payType==2:
        pType = u'پرداخت آنلاین'

    return (sType, pType)

def typeOfServicesToCode(serviceType, payType):
    if serviceType == u'پست پیشتاز':
        sType = 1
    elif serviceType == u'پست سفارشی':
        sType = 2
    elif serviceType == u'مطبئع':
        sType = 3

    if payType == u'ارسال رایگان':
        pType = 88
    elif payType == u'پرداخت در محل':
        pType = 1
    elif payType == u'پرداخت آنلاین':
        pType = 2

    return (sType, pType)

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

def ReadyToShip(parcelCode):
    client = Client(API_URI)
    param = {
    'username' : username,
    'password' : password,
    'parcelCode' : parcelCode
    }
    print(param)
    client.service.ReadyToShip(**param)

def test_temp_order(temp_order):
    client = Client(test_uri, cache=None)
    #print(client)
    products = client.factory.create('ns0:ProductsArray')
    order = temp_order
    order['username'] = 'jan'
    order['password'] = '123'
    for i in range(len(temp_order['products'])):
        products.Products.append(temp_order['products'][i])
    order['products'] = products
    print('**************')
    result = client.service.NewOrder(**order)
    return result

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
    for i in range (3):
        ns2.User.append(param)
    print(ns2)
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
    products = client.factory.create('ns0:ArrayOfTempProducts')

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
    for i in range(len(order['products'])):
        #stuff_id = client.service.AddStuff(
            #username = username,
            #password = password,
            #name = order['products']['productName'][i],
            #price = int(order['products']['price'][i]),
            #weight = int(order['products']['weight'][i]),
            #count = int(order['products']['count'][i]),
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
        'Id' : 716085,
        'Count' : 2,
        'DisCount' : 0
        }
        products.TempProducts.append(stuff)
        print(products)
        #print(bills)
        d_price = {
        'DeliveryPrice':price.PostDeliveryPrice,
        'VatTax':price.VatTax
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

    print(param)

    add_parcel_result = client.service.AddParcel(**param)

    parcel_code = {
    'ParcelCode': add_parcel_result.ParcelCode,
    'PostDeliveryPrice': add_parcel_result.PostDeliveryPrice,
    'VatTax': add_parcel_result.VatTax,
    'ErrorCode': add_parcel_result.ErrorCode
    }

    return parcel_code