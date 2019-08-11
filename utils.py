#coding: utf-8
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging, jsonify
import datetime
import string
import re
import json
import collections
import xlrd
import xlwt
import datetime
import jdatetime
from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor
from pymongo import MongoClient
from passlib.hash import sha256_crypt
import config


MONGO_HOST = "localhost"
MONGO_PORT = 27017
DB_NAME = 'vestano'
API_URI = 'http://svc.ebazaar-post.ir/EShopService.svc?WSDL'
VESTANO_API = 'http://vestanops.com/soap/VestanoWebService?wsdl'
#VESTANO_API = 'http://localhost:5000/soap/VestanoWebService?wsdl'
username = 'vestano3247'
password = 'Vestano3247'

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
    if session['role'] == 'vendor_admin':
        result = cursor.temp_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.temp_orders.find()
    temp = []
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        temp.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return temp

def today_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.today_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.today_orders.find()
    today = []
    for r in result:
        if r['datetime'] != jdatetime.datetime.today().strftime('%Y/%m/%d'):
            cursor.today_orders.remove({'orderId': r['orderId']})

    if session['role'] == 'vendor_admin':
        result = cursor.today_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.today_orders.find()
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        today.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return today

def canceled_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.canceled_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.canceled_orders.find()
    cnl = []
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        cnl.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return cnl

def readyToShip_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.ready_to_ship.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.ready_to_ship.find()
    rts = []
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        rts.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return rts

def guarantee_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.guarantee_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.guarantee_orders.find()
    grnt = []
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        grnt.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return grnt

def pending_orders(cursor):
    #remove 7 days before orders
    if session['role'] == 'vendor_admin':
        result = cursor.pending_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.pending_orders.find()
    d = jdatetime.datetime.today() - jdatetime.timedelta(days=7)
    seven_days_before = d.strftime('%Y/%m/%d')
    for r in result:
        if r['datetime'] < seven_days_before:
            for i in range(len(r['products'])):
                vinvent = cursor.vestano_inventory.find_one({'productId':r['products'][i]['productId']})
                vinvent['status']['82'] -= r['products'][i]['count']
                cursor.vestano_inventory.update_many(
                    {'productId': vinvent['productId']},
                    {'$set':{'status': vinvent['status']}}
                    )
            cursor.pending_orders.remove({'orderId': r['orderId']})
            cursor.deleted_orders.insert_one(r)

    if session['role'] == 'vendor_admin':
        result = cursor.pending_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.pending_orders.find()
    pnd = []
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        pnd.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return pnd

def all_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.orders.find()
    all_list = []
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        all_list.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return all_list

def inventory(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.vestano_inventory.find({'vendor': session['vendor_name']})
    else:
        result = cursor.vestano_inventory.find()
    inventory = []
    for r in result:
        st = r['status']
        other_status_count = sum(st.values())-st['80']-st['2']-st['81']-st['7']-st['71']-st['11']-st['82']-st['83']
        
        inventory.append((r['productName'], r['productId'], r['count'], r['datetime'],
            r['percentDiscount'], r['status'], other_status_count, r['vendor']))
    return inventory

def for_edit_case_inventory(cursor):
    inventory = []
    result = cursor.case_inventory.find()
    for r in result:
        st = r['status']
        other_status_count = sum(st.values())-st['80']-st['2']-st['81']-st['7']-st['71']-st['11']-st['82']
        inventory.append((r['productName'], r['productId'], r['count'], r['datetime'],
            r['percentDiscount'], r['status'], other_status_count))
    return inventory

def case_inventory(cursor):
    result = cursor.case_inventory.find()
    inventory = []
    for r in result:
        st = r['status']
        other_status_count = sum(st.values())-st['80']-st['2']-st['81']-st['7']-st['71']-st['11']-st['82']
        inventory.append((r['productName'], r['productId'], r['count'], r['datetime'],
            r['percentDiscount'], r['status'], other_status_count))
    return inventory

def removeFromInventory(cursor, orderId):
    order_result = cursor.orders.find_one({'orderId': orderId})
    for rec in order_result['products']:
        if order_result['vendorName'] == u'سفارش موردی':
            p = cursor.case_inventory.find_one({'productId': rec['productId']})
            if 'pack_products' in p.keys():
                for pp in p['pack_products']:
                    vinvent = cursor.case_inventory.find_one({'productId': pp['productId']})
                    cursor.case_inventory.update_many(
                        {'productId': pp['productId']},
                        {'$set':{
                        'count': vinvent['count'] - (rec['count']*pp['count'])
                        }
                        }
                        )
                    cursor.case_inventory.update_many(
                        {'productId': rec['productId']},
                        {'$set':{
                        'count': p['count'] - rec['count']
                        }
                        }
                        )
            
            else:
                cursor.case_inventory.update_many(
                    {'productId': rec['productId']},
                    {'$set':{
                    'count': p['count'] - rec['count']
                    }
                    }
                    )
        else:
            p = cursor.vestano_inventory.find_one({'productId': rec['productId']})
            if 'pack_products' in p.keys():
                for pp in p['pack_products']:
                    vinvent = cursor.vestano_inventory.find_one({'productId': pp['productId']})
                    cursor.vestano_inventory.update_many(
                        {'productId': pp['productId']},
                        {'$set':{
                        'count': vinvent['count'] - (rec['count']*pp['count'])
                        }
                        }
                        )
                    cursor.vestano_inventory.update_many(
                        {'productId': rec['productId']},
                        {'$set':{
                        'count': p['count'] - rec['count']
                        }
                        }
                        )
            
            else:
                cursor.vestano_inventory.update_many(
                    {'productId': rec['productId']},
                    {'$set':{
                    'count': p['count'] - rec['count']
                    }
                    }
                    )

def financial(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.orders.find()
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    for r in result:
        #filter just three status
        if (r['status'] in [11, 70, 71]) and (r['vendorName'] != u'سفارش موردی') :

            (sType, pType) = typeOfServicesToCode(r['serviceType'], r['payType'])

            #recalulate post delivery costs for returned orders
            if (r['status'] == 11) and (pType != 2):
                if 'for_accounting_recalculated_delivery_costs' not in r.keys():
                    weight = 0
                    for p in r['products']:
                        weight += p['weight'] * p['count']
                    deliveryPriceResult = GetDeliveryPrice(r['cityCode'], r['costs']['price'], weight, sType, 2)
                    for_accounting_delivery_costs = {
                    'PostDeliveryPrice': deliveryPriceResult['DeliveryPrice'],
                    'VatTax': deliveryPriceResult['VatTax']
                    }
                    cursor.orders.update_many(
                        {'orderId': r['orderId']},
                        {'$set':{'for_accounting_recalculated_delivery_costs': for_accounting_delivery_costs}})
                    r['costs']['PostDeliveryPrice'] = deliveryPriceResult['DeliveryPrice']
                    r['costs']['VatTax'] = deliveryPriceResult['VatTax']
                else:
                    r['costs']['PostDeliveryPrice'] = r['for_accounting_recalculated_delivery_costs']['PostDeliveryPrice']
                    r['costs']['VatTax'] = r['for_accounting_recalculated_delivery_costs']['VatTax']

            if (pType == 2) or (pType == 88):
                vendor_account = config.wage
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = 0 - (r['costs']['price'] - config.wage)
                post_account = r['costs']['price'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            vestano_account = config.wage - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

            t_vendor_account += vendor_account
            t_post_account += post_account
            t_vestano_account += vestano_account

            price += r['costs']['price']
            PostDeliveryPrice += r['costs']['PostDeliveryPrice']
            VatTax += r['costs']['VatTax']
            registerCost += r['costs']['registerCost']
            wage += r['costs']['wage']

            status = statusToString(r['status'])

            if 'credit_req_status' not in r.keys():
                r['credit_req_status'] = '-'
            if 'settlement_ref_number' not in r.keys():
                r['settlement_ref_number'] = ''

            protducts_list = []
            for p in r['products']:
                protducts_list.append(p['productName']+' - '+str(p['count']) + u' عدد ')

            record.append((r['orderId'], r['parcelCode'], r['costs']['price'],
            r['costs']['PostDeliveryPrice'], r['costs']['VatTax'], r['costs']['registerCost'],
            r['costs']['wage'], vendor_account, post_account, vestano_account , r['payType'],
            protducts_list, status, r['credit_req_status'], r['settlement_ref_number']))

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage,t_vendor_account ,t_post_account ,t_vestano_account)
    financial = {'record': record, 'totalCosts': totalCosts}

    return financial

def v_financial(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.orders.find()
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    for r in result:
        #filter just three status
        if (r['status'] in [11, 70, 71]) and (r['vendorName'] != u'سفارش موردی') :

            (sType, pType) = typeOfServicesToCode(r['serviceType'], r['payType'])

            #recalulate post delivery costs for returned orders
            if (r['status'] == 11) and (pType != 2):
                if 'for_accounting_recalculated_delivery_costs' not in r.keys():
                    weight = 0
                    for p in r['products']:
                        weight += p['weight'] * p['count']
                    deliveryPriceResult = GetDeliveryPrice(r['cityCode'], r['costs']['price'], weight, sType, 2)
                    for_accounting_delivery_costs = {
                    'PostDeliveryPrice': deliveryPriceResult['DeliveryPrice'],
                    'VatTax': deliveryPriceResult['VatTax']
                    }
                    cursor.orders.update_many(
                        {'orderId': r['orderId']},
                        {'$set':{'for_accounting_recalculated_delivery_costs': for_accounting_delivery_costs}})
                    r['costs']['PostDeliveryPrice'] = deliveryPriceResult['DeliveryPrice']
                    r['costs']['VatTax'] = deliveryPriceResult['VatTax']
                else:
                    r['costs']['PostDeliveryPrice'] = r['for_accounting_recalculated_delivery_costs']['PostDeliveryPrice']
                    r['costs']['VatTax'] = r['for_accounting_recalculated_delivery_costs']['VatTax']

            if (pType == 2) or (pType == 88):
                vendor_account = 0 - config.wage
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = r['costs']['price'] - config.wage
                post_account = r['costs']['price'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            vestano_account = config.wage - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

            t_vendor_account += vendor_account
            t_post_account += post_account
            t_vestano_account += vestano_account

            price += r['costs']['price']
            PostDeliveryPrice += r['costs']['PostDeliveryPrice']
            VatTax += r['costs']['VatTax']
            registerCost += r['costs']['registerCost']
            wage += r['costs']['wage']

            status = statusToString(r['status'])

            if 'credit_req_status' not in r.keys():
                r['credit_req_status'] = '-'
            if 'settlement_ref_number' not in r.keys():
                r['settlement_ref_number'] = ''

            protducts_list = []
            for p in r['products']:
                protducts_list.append(p['productName']+' - '+str(p['count']) + u' عدد ')

            record.append((r['orderId'], r['parcelCode'], r['costs']['price'],
            r['costs']['PostDeliveryPrice'], r['costs']['VatTax'], r['costs']['registerCost'],
            r['costs']['wage'], vendor_account, post_account, vestano_account , r['payType'],
            protducts_list, status, r['credit_req_status'], r['settlement_ref_number']))

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage,t_vendor_account ,t_post_account ,t_vestano_account)
    v_financial = {'record': record, 'totalCosts': totalCosts}

    return v_financial

def financial_vendor_credit(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.orders.find()
    record = []
    order_id_list = []
    credit_count = 0
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    post_account = 0
    vestano_account = 0
    for r in result:

        if 'credit_req_status' in r.keys():
            if (r['credit_req_status'] == u'در دست بررسی') or (r['credit_req_status'] == u'واریز شد'):
                continue
        else:
            r['credit_req_status'] = '-'
        #filter just three status
        if (r['status'] in [11, 71]) and (r['vendorName'] != u'سفارش موردی') :

            (sType, pType) = typeOfServicesToCode(r['serviceType'], r['payType'])

            #recalulate post delivery costs for returned orders
            if (r['status'] == 11) and (pType != 2):
                if 'for_accounting_recalculated_delivery_costs' not in r.keys():
                    weight = 0
                    for p in r['products']:
                        weight += p['weight'] * p['count']
                    deliveryPriceResult = GetDeliveryPrice(r['cityCode'], r['costs']['price'], weight, sType, 2)
                    for_accounting_delivery_costs = {
                    'PostDeliveryPrice': deliveryPriceResult['DeliveryPrice'],
                    'VatTax': deliveryPriceResult['VatTax']
                    }
                    cursor.orders.update_many(
                        {'orderId': r['orderId']},
                        {'$set':{'for_accounting_recalculated_delivery_costs': for_accounting_delivery_costs}})
                    r['costs']['PostDeliveryPrice'] = deliveryPriceResult['DeliveryPrice']
                    r['costs']['VatTax'] = deliveryPriceResult['VatTax']
                else:
                    r['costs']['PostDeliveryPrice'] = r['for_accounting_recalculated_delivery_costs']['PostDeliveryPrice']
                    r['costs']['VatTax'] = r['for_accounting_recalculated_delivery_costs']['VatTax']

            if (pType == 2) or (pType == 88):
                vendor_account = 0 - config.wage
                #post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = r['costs']['price'] - config.wage
                #post_account = r['costs']['price'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            #vestano_account = config.wage - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

            t_vendor_account += vendor_account
            #t_post_account += post_account
            #t_vestano_account += vestano_account

            price += r['costs']['price']
            PostDeliveryPrice += r['costs']['PostDeliveryPrice']
            VatTax += r['costs']['VatTax']
            registerCost += r['costs']['registerCost']
            wage += r['costs']['wage']

            status = statusToString(r['status'])

            protducts_list = []
            for p in r['products']:
                protducts_list.append(p['productName']+' - '+str(p['count']) + u' عدد ')

            record.append((r['orderId'], r['parcelCode'], r['costs']['price'],
            r['costs']['PostDeliveryPrice'], r['costs']['VatTax'], r['costs']['registerCost'],
            r['costs']['wage'], vendor_account, post_account, vestano_account , r['payType'],
            protducts_list, status, r['credit_req_status']))

            credit_count += 1
            order_id_list.append(int(r['orderId']))

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage, t_vendor_account , t_post_account, t_vestano_account)
    financial = {
    'record': record,
    'totalCosts': totalCosts,
    'credit_count': credit_count,
    'order_id_list': order_id_list
    }

    return financial

def req_credit_orders(cursor, orderId_list):
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    post_account = 0
    vestano_account = 0
    for Id in orderId_list:
        r = cursor.orders.find_one({'orderId':Id})
        (sType, pType) = typeOfServicesToCode(r['serviceType'], r['payType'])

        #recalulate post delivery costs for returned orders
        if (r['status'] == 11) and (pType != 2):
            if 'for_accounting_recalculated_delivery_costs' not in r.keys():
                weight = 0
                for p in r['products']:
                    weight += p['weight'] * p['count']
                deliveryPriceResult = GetDeliveryPrice(r['cityCode'], r['costs']['price'], weight, sType, 2)
                for_accounting_delivery_costs = {
                'PostDeliveryPrice': deliveryPriceResult['DeliveryPrice'],
                'VatTax': deliveryPriceResult['VatTax']
                }
                cursor.orders.update_many(
                    {'orderId': r['orderId']},
                    {'$set':{'for_accounting_recalculated_delivery_costs': for_accounting_delivery_costs}})
                r['costs']['PostDeliveryPrice'] = deliveryPriceResult['DeliveryPrice']
                r['costs']['VatTax'] = deliveryPriceResult['VatTax']
            else:
                r['costs']['PostDeliveryPrice'] = r['for_accounting_recalculated_delivery_costs']['PostDeliveryPrice']
                r['costs']['VatTax'] = r['for_accounting_recalculated_delivery_costs']['VatTax']

        if (pType == 2) or (pType == 88):
            vendor_account = 0 - config.wage
        else:
            vendor_account = r['costs']['price'] - config.wage

        t_vendor_account += vendor_account

        price += r['costs']['price']
        PostDeliveryPrice += r['costs']['PostDeliveryPrice']
        VatTax += r['costs']['VatTax']
        registerCost += r['costs']['registerCost']
        wage += r['costs']['wage']

        status = statusToString(r['status'])

        protducts_list = []
        for p in r['products']:
            protducts_list.append(p['productName']+' - '+str(p['count']) + u' عدد ')

        record.append((r['orderId'], r['parcelCode'], r['costs']['price'],
        r['costs']['PostDeliveryPrice'], r['costs']['VatTax'], r['costs']['registerCost'],
        r['costs']['wage'], vendor_account, post_account, vestano_account , r['payType'], protducts_list, status))

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage, t_vendor_account)
    financial = {
    'record': record,
    'totalCosts': totalCosts
    }
    return financial

def credit_requests_list(cursor):
    result = cursor.credit_requests.find()
    return result

def paid_list(cursor):
    result = cursor.credit_requests.find({'req_status': u'واریز شد'})
    return result

def accounting(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.orders.find()
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    for r in result:
        #filter just three status
        if (r['status'] in [11, 70, 71]) and (r['vendorName'] != u'سفارش موردی') :
            state_result = cursor.states.find_one({'Code': r['stateCode']})
            for rec in state_result['Cities']:
                if r['cityCode'] == rec['Code']:
                    city = rec['Name']
                    break

            (sType, pType) = typeOfServicesToCode(r['serviceType'], r['payType'])

            if pType == 2:
                vendor_account = config.wage
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = 0 - (r['costs']['price'] - config.wage)
                post_account = r['costs']['price'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            vestano_account = config.wage - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

            t_vendor_account += vendor_account
            t_post_account += post_account
            t_vestano_account += vestano_account

            price += r['costs']['price']
            PostDeliveryPrice += r['costs']['PostDeliveryPrice']
            VatTax += r['costs']['VatTax']
            registerCost += r['costs']['registerCost']
            wage += r['costs']['wage']

            status = statusToString(r['status'])

            protducts_list = []
            for p in r['products']:
                protducts_list.append(p['productName'])

            record.append((r['orderId'], r['parcelCode'], r['costs']['price'],
            r['costs']['PostDeliveryPrice'], r['costs']['VatTax'], r['costs']['registerCost'],
            r['costs']['wage'], vendor_account, post_account, vestano_account , r['payType'], protducts_list, status))

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage,t_vendor_account ,t_post_account ,t_vestano_account)
    acounting = {'record': record, 'totalCosts': totalCosts}

    return acounting


def details(cursor, orderId, code):
    city = ""
    price = 0
    count = 0
    weight = 0
    Weight = 0
    discount = 0
    if code == 'temp':
        r = cursor.temp_orders.find_one({'orderId': orderId})
    elif code == 'rts':
        r = cursor.ready_to_ship.find_one({'orderId': orderId})
    elif code == 'accounting':
        r = cursor.orders.find_one({'orderId': orderId})
    elif code == 'financial':
        r = cursor.orders.find_one({'orderId': orderId})
    elif code == 'v_financial':
        r = cursor.orders.find_one({'orderId': orderId})
    elif code == 'vendor_credit':
        r = cursor.orders.find_one({'orderId': orderId})
    elif code == 'req_credit':
        r = cursor.orders.find_one({'orderId': orderId})
    elif code == 'today':
        r = cursor.today_orders.find_one({'orderId': orderId})
    elif code == 'cnl':
        r = cursor.canceled_orders.find_one({'orderId': orderId})
    elif code == 'pnd':
        r = cursor.pending_orders.find_one({'orderId': orderId})
    elif code == 'grnt':
        r = cursor.guarantee_orders.find_one({'orderId': orderId})
    elif code == 'all':
        r = cursor.orders.find_one({'orderId': orderId})
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
        r['products'][i]['if_pack'] = False
        r['products'][i]['pack_products'] = []
        price = price + p['price']*p['count']
        Weight = Weight + p['weight']*p['count']
        count = count + p['count']
        discount = discount + p['percentDiscount']
        if r['vendorName'] == u'سفارش موردی':
            vinvent = cursor.case_inventory.find_one({'productId': p['productId']})
        else:
            vinvent = cursor.vestano_inventory.find_one({'productId': p['productId']})

        if vinvent:
            r['products'][i]['inventory_count'] = vinvent['count']
        
        
            #if order is a pack product: fetch the count of each pack's item from inventory
            if 'pack_products' in vinvent.keys():
                r['products'][i]['if_pack'] = True
                r['products'][i]['pack_products'] = vinvent['pack_products']
                for j in range(len(r['products'][i]['pack_products'])):
                    if r['vendorName'] == u'سفارش موردی':
                        pp_vinvent = cursor.case_inventory.find_one({'productId': r['products'][i]['pack_products'][j]['productId']})
                    else:
                        pp_vinvent = cursor.vestano_inventory.find_one({'productId': r['products'][i]['pack_products'][j]['productId']})
                    r['products'][i]['pack_products'][j]['invent_count'] = pp_vinvent['count']
                    r['products'][i]['pack_products'][j]['productName'] = pp_vinvent['productName']
            
            i += 1

    (sType, pType) = typeOfServicesToCode(r['serviceType'], r['payType'])

    parcelCode = r['parcelCode']

    if r['vendorName'] == u'سفارش موردی':
        case_ord_res = cursor.case_orders.find_one({'orderId': orderId})
        if weight < 10000:
            wage = config.to10
        elif 10000 <= weight < 15000:
            wage = config.to15
        elif 15000 <= weight < 20000:
            wage = config.to20
        elif 20000 <= weight < 25000:
            wage = config.to25
        elif 25000 <= weight < 30000:
            wage = config.to30
        elif weight >= 30000:
            wage = config.gthan30
        senderName = case_ord_res['senderFirstName'] + ' ' + case_ord_res['senderLastName']
        senderCellNumber = case_ord_res['senderCellNumber']
        senderPostalCode = case_ord_res['senderPostalCode']        
    else:
        wage = config.wage
        senderName = ''
        senderCellNumber = ''
        senderPostalCode = ''

    if 'costs' in r.keys():
        deliveryPrice = r['costs']['PostDeliveryPrice'] + r['costs']['VatTax']
        temp_wage = r['costs']['wage']
    else:
        if 'temp_delivery_costs' in r.keys():
            deliveryPrice = r['temp_delivery_costs']
            if 'temp_wage' in r.keys():
                temp_wage = r['temp_wage']
            else:
                temp_wage = wage
        else:
            deliveryPriceResult = GetDeliveryPrice(r['cityCode'], price, weight, sType, pType)
            deliveryPrice = deliveryPriceResult['DeliveryPrice'] + deliveryPriceResult['VatTax']
            if 'temp_wage' in r.keys():
                temp_wage = r['temp_wage']
            else:
                temp_wage = wage
            if code == 'temp':
                cursor.temp_orders.update_many(
                    {'orderId': r['orderId']},
                    {'$set':{'temp_delivery_costs': deliveryPrice, 'temp_wage': wage}})
            elif code == 'today':
                cursor.today_orders.update_many(
                    {'orderId': r['orderId']},
                    {'$set':{'temp_delivery_costs': deliveryPrice, 'temp_wage': wage}})
            elif code == 'grnt':
                cursor.guarantee_orders.update_many(
                    {'orderId': r['orderId']},
                    {'$set':{'temp_delivery_costs': deliveryPrice, 'temp_wage': wage}})
            elif code == 'cnl':
                cursor.canceled_orders.update_many(
                    {'orderId': r['orderId']},
                    {'$set':{'temp_delivery_costs': deliveryPrice, 'temp_wage': wage}})
            elif code == 'pnd':
                cursor.pending_orders.update_many(
                    {'orderId': r['orderId']},
                    {'$set':{'temp_delivery_costs': deliveryPrice, 'temp_wage': wage}})
        
    details = (r['orderId'], r['vendorName'], r['record_time']+' - '+r['record_date'],
        r['registerFirstName']+' '+r['registerLastName'], r['registerCellNumber'], r['registerPostalCode'],
        r['serviceType'], r['payType'], state_result['Name']+' - '+city+' - '+r['registerAddress'],
        r['products'],count, price, discount, orderId, status, temp_wage, parcelCode, deliveryPrice,
        senderName, senderCellNumber, senderPostalCode, Weight)

    return details

def inventory_details(cursor, status, productId):
    other = 0
    r_list = []
    product_result = []
    if int(status) == 80:
        if session['role'] == 'vendor_admin':
            product_result = cursor.temp_orders.find({'vendorName': session['vendor_name']})
        else:
            product_result = cursor.temp_orders.find()
    elif int(status) == 82:
        if session['role'] == 'vendor_admin':
            product_result = cursor.pending_orders.find({'vendorName': session['vendor_name']})
        else:
            product_result = cursor.pending_orders.find()
    elif int(status) in [2, 81, 7, 71, 11]:
        if session['role'] == 'vendor_admin':
            product_result = cursor.orders.find({'vendorName': session['vendor_name']})
        else:
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
        if session['role'] == 'vendor_admin':
            product_result = cursor.orders.find({'vendorName': session['vendor_name']})
        else:
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
    else:
        return None

    if payType==88:
        pType = u'ارسال رایگان'
    elif payType==1:
        pType = u'پرداخت در محل'
    elif payType==2:
        pType = u'پرداخت آنلاین'
    else:
        return None

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
    if statusCode==83:
        statusString = u'لغو شده'

    return statusString    

def states(cursor):
    result = cursor.states.find()
    states = []
    for r in result:
        states.append((r['Code'], r['Name'], r['Cities']))
    return states

def cities(cursor, code):
    result = cursor.states.find_one({'Code': code})
    ans = {'Code':[], 'Name':[], 'stateName':result['Name'], 'stateCode':code}
    for r in result['Cities']:
        ans['Code'].append(r['Code'])
        ans['Name'].append(r['Name'])
    return ans

def Products(cursor, product):
    result = cursor.vestano_inventory.find_one({'productId': product})
    if not result:
        result = cursor.case_inventory.find_one({'productId': product})
    ans = {
    'productName': result['productName'],
    'productId': product,
    'count': result['count'],
    'vendor': result['vendor'],
    'price': result['price'] - config.defaultWageForDefineStuff,
    'weight': result['weight'],
    'discount': result['percentDiscount']
    }
    return ans

def tickets_departements(departement):
    if departement == 'management':
        dep = u'مدیریت' 
    elif departement == 'orders':
        dep = u'سفارشات' 
    elif departement == 'inventory':
        dep = u'انبارداری' 
    elif departement == 'accounting':
        dep = u'حسابداری' 
    elif departement == 'technical':
        dep = u'فنی' 
    return dep

def tickets_access_departements(departement):
    if departement == u'مدیریت':
        access = 'adminTicket' 
    elif departement == u'سفارشات':
        access = 'ordersTicket' 
    elif departement == u'انبارداری':
        access = 'inventoryTicket' 
    elif departement == u'حسابداری':
        access = 'financialTicket' 
    elif departement == u'فنی':
        access = 'techTicket'
    return access

def tickets(cursor, role, session_username, access):
    if role == 'vendor_admin':
        result = cursor.tickets.find({'sender_username': session_username})
    else:
        if 'adminTicket' in access:
            result = cursor.tickets.find()
        elif 'ordersTicket' in access:
            result = cursor.tickets.find({'departement': u'orders'})
        elif 'inventoryTicket' in access:
            result = cursor.tickets.find({'departement': u'inventory'})
        elif 'financialTicket' in access:
            result = cursor.tickets.find({'departement': u'accounting'})
        elif 'techTicket' in access:
            result = cursor.tickets.find({'departement': u'technical'})
    tickets = []
    for rec in result:
        rec['departement'] = tickets_departements(rec['departement'])
        tickets.append(rec)
    return tickets

def sent_tickets(cursor, role, session_username, access):
    if 'adminTicket' in access:
        result = cursor.tickets.find({'sender_departement': u'مدیریت'})
    elif 'ordersTicket' in access:
        result = cursor.tickets.find({'sender_departement': 'سفارشات'})
    elif 'inventoryTicket' in access:
        result = cursor.tickets.find({'sender_departement': 'انبارداری'})
    elif 'financialTicket' in access:
        result = cursor.tickets.find({'sender_departement': 'حسابداری'})
    elif 'techTicket' in access:
        result = cursor.tickets.find({'sender_departement': 'فنی'})
    tickets = []
    for rec in result:
        rec['departement'] = tickets_departements(rec['departement'])
        tickets.append(rec)
    return tickets

def ticket_details(cursor, ticket_num):
    result = cursor.tickets.find_one({'number': ticket_num})
    result['departement'] = tickets_departements(result['departement'])
    return result

def transfer_req_type(req_type):
    if req_type == 'new':
        req = u'ایجاد کالای جدید' 
    elif req_type == 'inc':
        req = u'افزودن کالای موجود' 
    elif req_type == 'edit':
        req = u'ویرایش کالا' 
    elif req_type == 'release':
        req = u'خروج از انبار' 
    elif req_type == 'pack':
        req = u'ایجاد بسته' 
    return req

def transfer_req(cursor):
    result = cursor.inventory_transfer.find()
    transfer_list = []
    for r in result:
        if 'productId' in r.keys():
            r_result = cursor.vestano_inventory.find_one({'productId': r['productId']})
            if r_result:
                r['productName'] = r_result['productName']
            else:
                r['productName'] = ""
        r['request_type'] = transfer_req_type(r['request_type'])
        transfer_list.append(r)
    return transfer_list

def transfer_details(cursor, number):
    result = cursor.inventory_transfer.find_one({'number':number})
    result['transfer_req_type'] = transfer_req_type(result['request_type'])
    if 'productId' in result.keys():
        r_result = cursor.vestano_inventory.find_one({'productId': result['productId']})
        if result['request_type'] != 'edit':
            result['productName'] = r_result['productName']
            result['price'] = r_result['price']
            result['percentDiscount'] = r_result['percentDiscount']
            result['weight'] = r_result['weight']
            result['exist_count'] = r_result['count']
        else:
            result['exist_count'] = r_result['count']
    return result

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

    #initial states in database:
    #for state in states_list:
        #cursor.states.insert_one(state)
    return states_list

def GetStatus(cursor):
    client = Client(API_URI)
    #print(client)
    change_flag = 0

    status_records = cursor.status.find()
    for rec in status_records:
        if rec['status'] in [1, 11, 71]:
            cursor.status.remove({'parcelCode': rec['parcelCode']})

    status_records = cursor.status.find()
    for rec in status_records:
        orders_records = cursor.orders.find_one({'parcelCode': rec['parcelCode']})
        if not orders_records:
            continue

        status = client.service.GetStatus(username = username, password = password,
            parcelCode=rec['parcelCode'])

        if (orders_records['status'] == 81) and (status == 2):
            continue

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
            cursor.status.update_many(
                {'parcelCode': rec['parcelCode']},
                {'$set':{
                'status': status,
                'lastUpdate' : datetime.datetime.now()
                }
                }
                )
            cursor.today_orders.update_many(
                {'parcelCode': rec['parcelCode']},
                {'$set':{
                'status': status
                }
                }
                )
            cursor.ready_to_ship.update_many(
                {'parcelCode': rec['parcelCode']},
                {'$set':{
                'status': status
                }
                }
                )
            cursor.guarantee_orders.update_many(
                {'parcelCode': rec['parcelCode']},
                {'$set':{
                'status': status
                }
                }
                )
            change_flag = 1
            for i in range(len(orders_records['products'])):
                if orders_records['vendorName'] == u'سفارش موردی':
                    vinvent = cursor.case_inventory.find_one({'productId':orders_records['products'][i]['productId']})
                    if vinvent:
                        vinvent['status'][str(status)]+= orders_records['products'][i]['count']
                        vinvent['status'][str(prev_status)]-= orders_records['products'][i]['count']
                        cursor.case_inventory.update_many(
                            {'productId': vinvent['productId']},
                            {'$set':{'status': vinvent['status']}}
                            )
                else:
                    vinvent = cursor.vestano_inventory.find_one({'productId':orders_records['products'][i]['productId']})
                    if vinvent:
                        vinvent['status'][str(status)]+= orders_records['products'][i]['count']
                        vinvent['status'][str(prev_status)]-= orders_records['products'][i]['count']
                        cursor.vestano_inventory.update_many(
                            {'productId': vinvent['productId']},
                            {'$set':{'status': vinvent['status']}}
                            )
        
    return change_flag

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
    client.service.ReadyToShip(**param)

def GetStatus_test(orderId):
    client = Client(VESTANO_API, cache=None)
    username = 'jan'
    password = '123'
    return client.service.GetStatus(username, password, orderId)

def test_temp_order(temp_order):
    client = Client(VESTANO_API, cache=None)
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

def editStuff(productId, weight, price):
    client = Client(API_URI)
    price_result = client.service.EditStuffPrice(
        username = username,
        password = password,
        stuffId = int(productId),
        price = int(price)
        )
    weight_result = client.service.EditStuffWeight(
        username = username,
        password = password,
        stuffId = int(productId),
        weight = int(weight)
        )
    return (price_result, weight_result)

def GetDeliveryPrice(cityCode, price, weight, serviceType, payType):
    client = Client(API_URI)
    price = client.service.GetDeliveryPrice(
        username = username,
        password = password,
        cityCode = cityCode,
        price = price,
        weight = weight,
        serviceType = serviceType,
        payType = payType
        )
    ans = {
    'DeliveryPrice':price.PostDeliveryPrice,
    'VatTax':price.VatTax
    }
    return ans


def SoapClient(order):
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
    'ErrorCode': add_parcel_result.ErrorCode,
    'Description': add_parcel_result.Description
    }

    #print('add_parcel_result: ', parcel_code)

    return parcel_code

def init_status_inventory():
    status = {}
    status['0'] = 0
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
    status['83'] = 0
    for rec in cursor.vestano_inventory.find():
        cursor.vestano_inventory.update_many(
            {'productId': rec['productId']},
            {'$set':{
            'status': status
            }
            }
            )

def init_status_case_inventory():
    status = {}
    status['0'] = 0
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
    status['83'] = 0
    for rec in cursor.case_inventory.find():
        cursor.case_inventory.update_many(
            {'productId': rec['productId']},
            {'$set':{
            'status': status
            }
            }
            )

def add_empty_status():
    status = {}
    status['0'] = 0
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
    status['83'] = 0
    return status

def inventory_sumation(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.vestano_inventory.find({'vendor': session['vendor_name']})
    else:
        result = cursor.vestano_inventory.find()
    status_sum = add_empty_status()
    count_sum = 0
    for r in result:
        count_sum += r['count']
        for s in r['status'].keys():
            status_sum[s] += r['status'][s]
    other_status_sum = sum(status_sum.values())-status_sum['80']-status_sum['2']-status_sum['81']-status_sum['7']-status_sum['71']-status_sum['11']-status_sum['82']-status_sum['83']
    ans = {'count_sum': count_sum, 'status_sum': status_sum, 'other_status_sum': other_status_sum}
    return(ans)

def status83():
    for rec in cursor.case_inventory.find():
        rec['status']['83'] = 0
        cursor.case_inventory.update_many(
            {'productId': rec['productId']},
            {'$set':{
            'status': rec['status']
            }
            }
            )
    for rec in cursor.vestano_inventory.find():
        rec['status']['83'] = 0
        cursor.vestano_inventory.update_many(
            {'productId': rec['productId']},
            {'$set':{
            'status': rec['status']
            }
            }
            )

def write_excel(cursor):
    #filename = "E:/projects/VESTANO/Vestano/static/pdf/inventory.xls"
    filename = "/root/vestano/static/pdf/xls/inventory.xls"
    invent = inventory(cursor)
    excel_file = xlwt.Workbook()
    today = jdatetime.datetime.today().strftime('%Y-%m-%d')
    sheet = excel_file.add_sheet(today)
    style0 = xlwt.easyxf('font: name Times New Roman, bold on;'
        'pattern: pattern solid, fore_colour yellow;'
        'align: horiz center;')
    sheet.cols_right_to_left = 1
    sheet.write(0, 0, u'عنوان کالا', style0)
    sheet.write(0, 1, u'شناسه کالا', style0)
    sheet.write(0, 2, u'موجودی', style0)
    sheet.write(0, 3, u'صف پردازش', style0)
    sheet.write(0, 4, u'آماده ارسال', style0)
    sheet.write(0, 5, u'ارسال شده از وستانو', style0)
    sheet.write(0, 6, u'توزیع شده', style0)
    sheet.write(0, 7, u'تسویه شده', style0)
    sheet.write(0, 8, u'برگشتی', style0)
    sheet.write(0, 9, u'در انتظار کالا', style0)
    sheet.write(0, 10, u'سایر وضعیت ها', style0)
    for i in range(1, len(invent)+1):
        row = i
        for j in range(3):
            col = j
            ctype = 'string'
            value = invent[i-1][j]
            xf = 0
            sheet.write(row, col, value)
        q = 3
        for s in ['80', '2', '81', '7', '71', '11', '82']:
            col = q
            ctype = 'string'
            value = invent[i-1][5][s]
            xf = 0
            sheet.write(row, col, value)
            q = q + 1
        col = q
        ctype = 'string'
        value = invent[i-1][6]
        xf = 0
        sheet.write(row, col, value)
    excel_file.save(filename)

def calculate_wage(vendor, weight):
    if vendor == u'سفارش موردی':
        if weight < 10000:
            vestano_wage = config.to10
        elif 10000 <= weight < 15000:
            vestano_wage = config.to15
        elif 15000 <= weight < 20000:
            vestano_wage = config.to20
        elif 20000 <= weight < 25000:
            vestano_wage = config.to25
        elif 25000 <= weight < 30000:
            vestano_wage = config.to30
        elif weight >= 30000:
            vestano_wage = config.gthan30
    else:
        vestano_wage = config.wage
    return vestano_wage