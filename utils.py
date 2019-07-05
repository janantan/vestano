#coding: utf-8
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging, jsonify
import datetime
import string
import re
import json
import collections
import xlrd
import datetime
import jdatetime
from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor
from pymongo import MongoClient
from passlib.hash import sha256_crypt


MONGO_HOST = "localhost"
MONGO_PORT = 27017
DB_NAME = 'vestano'
API_URI = 'http://svc.ebazaar-post.ir/EShopService.svc?WSDL'
#VESTANO_API = 'http://vestanops.com/soap/VestanoWebService?wsdl'
VESTANO_API = 'http://localhost:5000/soap/VestanoWebService?wsdl'
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

def today_orders(cursor):
    result = cursor.temp_orders.find()
    today = []
    for r in result:
        if r['datetime'] == jdatetime.datetime.today().strftime('%Y/%m/%d'):
            state_result = cursor.states.find_one({'Code': r['stateCode']})
            today.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
                state_result['Name'],r['record_date'],r['record_time'], r['serviceType'], r['registerCellNumber']))
    result2 = cursor.orders.find()
    for r2 in result2:
        if r2['datetime'] == jdatetime.datetime.today().strftime('%Y/%m/%d'):
            state_result = cursor.states.find_one({'Code': r2['stateCode']})
            today.append((r2['orderId'], r2['vendorName'], r2['registerFirstName']+' '+r2['registerLastName'],
                state_result['Name'],r2['record_date'],r2['record_time'], r2['serviceType'], r2['registerCellNumber']))
    count = len(today)
    return {'today': today, 'count': count}

def canceled_orders(cursor):
    result = cursor.canceled_orders.find()
    cnl = []
    for r in result:
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        cnl.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['serviceType'], r['registerCellNumber']))
    return cnl

def readyToShip_orders(cursor):
    result = cursor.ready_to_ship.find()
    rts = []
    for r in result:
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        rts.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['serviceType'], r['registerCellNumber']))
    return rts

def inventory(cursor):
    result = cursor.vestano_inventory.find()
    inventory = []
    for r in result:
        #temp_orders = cursor.temp_orders.find()
        #for trec in temp_orders:
            #for j in range(len(trec['products'])):
                #if trec['products'][j]['productId'] == r['productId']:
                    #r['status'][str(trec['status'])]+= trec['products'][j]['count']
                    #cursor.vestano_inventory.update_many(
                        #{'productId': r['productId']},
                        #{'$set':{'status': r['status']}}
                        #)
        #product_result = cursor.orders.find()
        #for rec in product_result:
            #for i in range(len(rec['products'])):
                #if rec['products'][i]['productId'] == r['productId']:
                    #r['status'][str(rec['status'])]+= rec['products'][i]['count']
                    #cursor.vestano_inventory.update_many(
                        #{'productId': r['productId']},
                        #{'$set':{'status': r['status']}}
                        #)
        st = r['status']
        other_status_count = sum(st.values())-st['80']-st['2']-st['81']-st['7']-st['71']-st['11']-st['82']
        inventory.append((r['productName'], r['productId'], r['count'], r['datetime'],
            r['percentDiscount'], r['status'], other_status_count))
    return inventory

def accounting(cursor):
    result = cursor.accounting.find()
    record = []
    for r in result:
        #record.append((r['order_id'], r['parcel_code'], int(r['total_cost']), int(r['vestano_post_cost']), int(r['delivery_cost']), int(r['vat_tax']), r['record_datetime']))
        record.append((r['order_id'], int(r['total_cost']), int(r['vestano_post_cost']), r['record_datetime']))
    return record

def inventory_onclick(cursor, Id, item):
    if item == "inventory_count":
        repo_rec = cursor.repo_records.find_one({'productId': Id})
        result = (repo_rec['action'], repo_rec['datetime_rec'], repo_rec['counts'], repo_rec['receiver'],
            repo_rec['vendorsAgent'])
    elif item == 'productId':
        pass
    elif item == 'on_process':
        rec = details(cursor, Id)
        if not rec:
            return None
        result = (rec[0], rec[9], rec[2], rec[3], rec[4], rec[8], rec[6], rec[7])
    elif item == 'ready_to_ship':
        pass
    elif item == 'posted_from_vestano':
        pass
    elif item == 'distributed':
        pass
    elif item == 'ponied_up':
        pass
    elif item == 'returned':
        pass
    elif item == 'wait_for_stuff':
        pass
    elif item == 'other':
        pass


def details(cursor, orderId, code):
    city = ""
    price = 0
    count = 0
    discount = 0
    if code == 'temp':
        r = cursor.temp_orders.find_one({'orderId': orderId})
    if code == 'rts':
        r = cursor.ready_to_ship.find_one({'orderId': orderId})
    elif code == 'today':
        r = cursor.temp_orders.find_one({'orderId': orderId})
        if not r:
            r = cursor.orders.find_one({'orderId': orderId})
    elif code == 'cnl':
        r = cursor.canceled_orders.find_one({'orderId': orderId})
    if not r:
        return None
    state_result = cursor.states.find_one({'Code': r['stateCode']})
    for rec in state_result['Cities']:
        if r['cityCode'] == rec['Code']:
            city = rec['Name']
            break

    status = statusToString(r['status'])

    i = 0
    for p in r['products']:
        price = price + p['price']*p['count']
        count = count + p['count']
        discount = discount + p['percentDiscount']
        vinvent = cursor.vestano_inventory.find_one({'productId': p['productId']})
        r['products'][i]['inventory_count'] = vinvent['count']
        i += 1

    details = (r['orderId'], r['vendorName'], r['record_time']+' - '+r['record_date'],
        r['registerFirstName']+' '+r['registerLastName'], r['registerCellNumber'], r['registerPostalCode'],
        r['serviceType'], r['payType'], state_result['Name']+' - '+city+' - '+r['registerAddress'],
        r['products'],count, price, discount, orderId, status)
    return details

def inventory_details(cursor, status, productId):
    other = 0
    r_list = []
    product_result = []
    if int(status) == 80:
        product_result = cursor.temp_orders.find()
    elif int(status) == 82:
        product_result = cursor.pending_orders.find()
    elif int(status) in [2, 81, 7, 71, 11]:
        product_result = cursor.orders.find()
    else:
        other = 1
    for rec in product_result:
        if rec['status'] == int(status):
            for i in range(len(rec['products'])):
                r_dict = {}
                if rec['products'][i]['productId'] == productId:
                    state_result = cursor.states.find_one({'Code': rec['stateCode']})
                    for r in state_result['Cities']:
                        if rec['cityCode'] == r['Code']:
                            city = r['Name']
                            break
                    r_dict['orderId'] = rec['orderId']
                    r_dict['parcelCode'] = rec['parcelCode']
                    r_dict['datetime'] = rec['record_date']
                    r_dict['name'] = rec['registerFirstName']+' '+rec['registerLastName']
                    r_dict['cellNumber'] = rec['registerCellNumber']
                    r_dict['serviceType'] = rec['serviceType']
                    r_dict['payType'] = rec['payType']
                    r_dict['destination'] = state_result['Name']+' - '+city
                    r_dict['count'] = rec['products'][i]['count']
                    r_dict['productsCost'] = rec['products'][i]['price']
                    r_dict['status'] = statusToString(rec['status'])
                    r_list.append(r_dict)

    if other:
        product_result = cursor.orders.find()
        for rec in product_result:
            if rec['status'] not in [2, 81, 7, 71, 11, 80, 82]:
                for i in range(len(rec['products'])):
                    r_dict = {}
                    if rec['products'][i]['productId'] == productId:
                        state_result = cursor.states.find_one({'Code': rec['stateCode']})
                        for r in state_result['Cities']:
                            if rec['cityCode'] == r['Code']:
                                city = r['Name']
                                break
                        r_dict['orderId'] = rec['orderId']
                        r_dict['parcelCode'] = rec['parcelCode']
                        r_dict['datetime'] = rec['record_date']
                        r_dict['name'] = rec['registerFirstName']+' '+rec['registerLastName']
                        r_dict['cellNumber'] = rec['registerCellNumber']
                        r_dict['serviceType'] = rec['serviceType']
                        r_dict['payType'] = rec['payType']
                        r_dict['destination'] = state_result['Name']+' - '+city
                        r_dict['count'] = rec['products'][i]['count']
                        r_dict['productsCost'] = rec['products'][i]['price']
                        r_dict['status'] = statusToString(rec['status'])
                        r_list.append(r_dict)

    return r_list


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

def statusToString(statusCode):
    if statusCode==0:
        statusString = u'تحت بررسی'
    if statusCode==1:
        statusString = u'انصرافی'
    if statusCode==2:
        statusString = u'آماده ارسال'
    if statusCode==3:
        statusString = u'اشتباه در آماده به ارسال'
    if statusCode==4:
        statusString = u'عدم حضور مدیر'
    if statusCode==5:
        statusString = u'ارسال شده'
    if statusCode==6:
        statusString = u'عدم قبول'
    if statusCode==7:
        statusString = u'توزیع شده'
    if statusCode==8:
        statusString = u'باجه معطله '
    if statusCode==9:
        statusString = u'توقیفی'
    if statusCode==10:
        statusString = u'پیش برگشتی'
    if statusCode==11:
        statusString = u'برگشتی'
    if statusCode==70:
        statusString = u'تایید مالی'
    if statusCode==71:
        statusString = u'تسویه حساب'
    if statusCode==80:
        statusString = u'در صف پردازش'
    if statusCode==81:
        statusString = u'ارسال شده از وستانو'
    if statusCode==82:
        statusString = u'در انتظار کالا'

    return statusString    

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
    result = cursor.vestano_inventory.find_one({'productId': product})
    ans = {
    'productName': result['productName'],
    'productId': product,
    'count': result['count'],
    'vendor': result['vendor'],
    'price': result['price'],
    'weight': result['weight'],
    'discount': result['percentDiscount']
    }
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

def updateCities(cursor):
    state_result = cursor.states.find()
    for r in state_result:
        cursor.states.update_many(
            {'Code': r['Code']},
            {'$set':{
            'Cities': GetCities(r['Code'])
            }
            }
            )

def GetStates():
    client = Client(API_URI)
    #Get list of states
    states = client.service.GetStates(username = username, password = password)
    states_dict = client.dict(states)
    states_list = []
    for item in states_dict['State']:
        states_list.append(client.dict(item))
    return states_list

def GetStatus(cursor):
    client = Client(API_URI)
    change_flag = 0
    status_records = cursor.status.find()
    for rec in status_records:
        status = client.service.GetStatus(username = username, password = password,
            parcelCode=rec['parcelCode'])
        orders_records = cursor.orders.find_one({'parcelCode': rec['parcelCode']})
        if not orders_records:
            return change_flag
        if status == 2:
            return change_flag
        if orders_records['status'] != status:
            prev_status = orders_records['status']
            cursor.orders.update_many(
                {'parcelCode': rec['parcelCode']},
                {'$set':{
                'status': status,
                'lastUpdate' : datetime.datetime.now(),
                'status_updated' : True
                }
                }
                )
            for i in range(len(orders_records['products'])):
                vinvent = cursor.vestano_inventory.find_one({'productId':orders_records['products'][i]['productId']})
                vinvent['status'][str(status)]+= orders_records['products'][i]['count']
                vinvent['status'][str(prev_status)]-= orders_records['products'][i]['count']
                print(vinvent['status'])
                cursor.vestano_inventory.update_many(
                    {'productId': vinvent['productId']},
                    {'$set':{'status': vinvent['status']}}
                    )
            change_flag = 1
        if (status == 11) or (status == 71):
            cursor.status.remove({'parcelCode': rec['parcelCode']})
        elif rec['status'] != status:
            cursor.status.update_many(
                {'parcelCode': rec['parcelCode']},
                {'$set':{
                'status': status,
                'lastUpdate' : datetime.datetime.now()
                }
                }
                )
    return change_flag

        #print(status)
    #print(client.service.GetStatus(username = username, password = password,
            #parcelCode='21868000011930748946'))

def GetStatus_one(cursor, parcelCode):
    client = Client(API_URI)
    status = client.service.GetStatus(username = username, password = password,
            parcelCode=parcelCode)
    return status

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
    client = Client(VESTANO_API, cache=None)
    print(client)
    print('&&&&&&&&&&&&&&&&&&&&')
    #print(Client(API_URI))
    #codes = client.factory.create('ns0:CodesArray')
    #print(codes)
    #states = client.service.GetCities(username = 'jan', password = '123', stateCode=9)
    #print(states)
    #states_dict = client.dict(states)
    #for i in range(len(states.Codes)):
        #print(states.Codes[i].Code)

    products = client.factory.create('ns1:ProductsArray')
    order = temp_order
    order['username'] = 'jan'
    order['password'] = '123'
    for i in range(len(temp_order['products'])):
        print(temp_order['products'][i])
        products.Products.append(temp_order['products'][i])
    order['products'] = products
    print('**************')
    result = client.service.NewOrder(**order)
    print('api result: ', result)
    return result

def api_test():
    client = Client(VESTANO_API, cache=None)
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

def AddStuff(record):
    client = Client(API_URI)
    stuff_id = client.service.AddStuff(
        username = username,
        password = password,
        name = record['productName'],
        price = int(record['price']),
        weight = int(record['weight']),
        count = int(record['count']),
        description = record['description'],
        percentDiscount = int(record['percentDiscount'])
        )
    return stuff_id


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

    #bills = client.service.Billing(username = username, password = password)
    for i in range(len(order['products'])):

        stuff = {
        'Id' : int(order['products'][i]['productId']),
        'Count' : order['products'][i]['count'],
        'DisCount' : order['products'][i]['percentDiscount']
        }
        products.TempProducts.append(stuff)

    d_price = {
    'DeliveryPrice':price.PostDeliveryPrice,
    'VatTax':price.VatTax
    }
    #print(d_price)

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

    parcel_code = {
    'ParcelCode': add_parcel_result.ParcelCode,
    'PostDeliveryPrice': add_parcel_result.PostDeliveryPrice,
    'VatTax': add_parcel_result.VatTax,
    'ErrorCode': add_parcel_result.ErrorCode
    }

    print('add_parcel_result: ', parcel_code)

    return parcel_code

def init_status_inventory():
    status = {}
    status['1'] = 0
    status['2'] = 0
    status['3'] = 0
    status['4'] = 0
    status['5'] = 0
    status['6'] = 0
    status['7'] = 0
    status['8'] = 0
    status['9'] = 0
    status['10'] = 0
    status['11'] = 0
    status['70'] = 0
    status['71'] = 0
    status['80'] = 0
    status['81'] = 0
    status['82'] = 0
    for rec in cursor.vestano_inventory.find():
        cursor.vestano_inventory.update_many(
            {'productId': rec['productId']},
            {'$set':{
            'status': status
            }
            }
            )

def add_empty_status():
    status = {}
    status['1'] = 0
    status['2'] = 0
    status['3'] = 0
    status['4'] = 0
    status['5'] = 0
    status['6'] = 0
    status['7'] = 0
    status['8'] = 0
    status['9'] = 0
    status['10'] = 0
    status['11'] = 0
    status['70'] = 0
    status['71'] = 0
    status['80'] = 0
    status['81'] = 0
    status['82'] = 0
    return status