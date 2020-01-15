#coding: utf-8
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging, jsonify
from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from operator import itemgetter
import string
import requests
import re
import json
import collections
import xlrd
import random2
import xlwt
import datetime
import jdatetime
import config


MONGO_HOST = "localhost"
MONGO_PORT = 27017
DB_NAME = 'vestano'
API_URI = 'http://svc.ebazaar-post.ir/EShopService.svc?WSDL'
VESTANO_API = 'http://vestanops.com/soap/VestanoWebService?wsdl'
#VESTANO_API = 'http://localhost:5000/soap/VestanoWebService?wsdl'
username = 'vestano3247'
password = 'Vestano3247'
postAvval_username = 'vesta'
postAvval_password = 'w8cv9e1n'
REC_IN_EACH_PAGE = 100
NUM_OF_SHOWN_PAGE = 10


#Bearer Token Auth for requests.post
class BearerAuth(requests.auth.AuthBase):
    token = None
    def __init__(self, token):
        self.token = token
    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r

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

def caseTemp_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.caseTemp_orders.find({'vendorName': session['vendor_name']})
    elif session['role'] == 'admin':
        result = cursor.caseTemp_orders.find()
    else:
        result = cursor.caseTemp_orders.find({'init_username': session['username']})
    temp = []
    for r in result:
        postAvvalOrder = False
        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            status = statusToString(r['status'])
        case_result = cursor.case_orders.find_one({'orderId': r['orderId']})
        if case_result:
            sender_name = case_result['senderFirstName']+' '+case_result['senderLastName']
        else:
            sender_name = '-'
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        temp.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, sender_name, postAvvalOrder))
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
        postAvvalOrder = False
        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            status = statusToString(r['status'])
        #write sender name instead of vendor name in case of case orders:
        if r['vendorName'] == u'سفارش موردی':
            case_ord_res = cursor.case_orders.find_one({'orderId': r['orderId']})
            vendorName = case_ord_res['senderFirstName'] + ' ' + case_ord_res['senderLastName']
        else:
            vendorName = r['vendorName']
            
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        today.append((r['orderId'], vendorName, r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, postAvvalOrder))
    return today

def canceled_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.canceled_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.canceled_orders.find()
    cnl = []
    
    for r in result:
        postAvvalOrder = False
        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            status = statusToString(r['status'])
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        cnl.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, postAvvalOrder))
    return cnl

def readyToShip_orders(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.ready_to_ship.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.ready_to_ship.find()
    rts = []
    
    for r in result:
        postAvvalOrder = False
        if 'postAvvalFlag' in r.keys():
            print(r['orderId'])
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            status = statusToString(r['status'])
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        rts.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, postAvvalOrder))
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
    if session['role'] == 'vendor_admin':
        result = cursor.pending_orders.find({'vendorName': session['vendor_name']})
    else:
        result = cursor.pending_orders.find()
    #remove 7 days before orders
    d = jdatetime.datetime.today() - jdatetime.timedelta(days=7)
    seven_days_before = d.strftime('%Y/%m/%d')
    for r in result:
        if r['datetime'] < seven_days_before:
            #for i in range(len(r['products'])):
                #vinvent = cursor.vestano_inventory.find_one({'productId':r['products'][i]['productId']})
                #vinvent['status']['82'] -= r['products'][i]['count']
                #if '84' in vinvent['status'].keys():
                    #vinvent['status']['84'] += r['products'][i]['count']
                #else:
                    #vinvent['status']['84'] = r['products'][i]['count']
                #cursor.vestano_inventory.update_many(
                    #{'productId': vinvent['productId']},
                    #{'$set':{'status': vinvent['status']}}
                    #)
            cursor.pending_orders.update_many(
                {'orderId': r['orderId']},
                {'$set':{'status': 84}}
                )
            cursor.today_orders.update_many(
                {'orderId': r['orderId']},
                {'$set':{'status': 84}}
                )
            cursor.guarantee_orders.update_many(
                {'orderId': r['orderId']},
                {'$set':{'status': 84}}
                )
            #cursor.pending_orders.remove({'orderId': r['orderId']})
            #cursor.delFmPendings.insert_one(r)
            #cursor.deleted_orders.insert_one(r)

    if session['role'] == 'vendor_admin':
        result = cursor.pending_orders.find({'vendorName': session['vendor_name'], 'status':82})
        result2 = cursor.pending_orders.find({'vendorName': session['vendor_name'], 'status':84})
    else:
        result = cursor.pending_orders.find({'status':82})
        result2 = cursor.pending_orders.find({'status':84})
    pnd = []
    for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        pnd.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    for r in result2:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        state_result = cursor.states.find_one({'Code': r['stateCode']})
        pnd.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            statusToString(r['status']), pNameList))
    return pnd

#def all_orders(cursor):
def all_orders(cursor, page):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({'vendorName': session['vendor_name']}).sort("_id", -1)
        L = cursor.orders.find({'vendorName': session['vendor_name']}).count()
    else:
        result = cursor.orders.find().sort("_id", -1)
        L = cursor.orders.find().count()
    all_list = []
    #new(
    res = []
    if L > (REC_IN_EACH_PAGE*page):
        for i in range((REC_IN_EACH_PAGE*(page-1)), (REC_IN_EACH_PAGE*page)):
            res.append(result[i])
    else:
        for i in range((REC_IN_EACH_PAGE*(page-1)), L):
            res.append(result[i])
    
    for r in res:
        postAvvalOrder = False
        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            status = statusToString(r['status'])
    #)
    #for r in result:
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        all_list.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, postAvvalOrder))
    #return (all_list)
    return (all_list, L)

def case_all_orders(cursor):
    result = cursor.orders.find({'vendorName': 'سفارش موردی'})
    all_list = []
    
    for r in result:
        postAvvalOrder = False
        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            status = statusToString(r['status'])
        case_result = cursor.case_orders.find_one({'orderId': r['orderId']})
        if case_result:
            sender_name = case_result['senderFirstName']+' '+case_result['senderLastName']
        else:
            sender_name = '-'
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        all_list.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, sender_name, postAvvalOrder))
    return all_list

def vendors_all_orders(cursor):
    result = cursor.orders.find({'vendorName': {'$ne': 'سفارش موردی'}})
    all_list = []

    for r in result:
        postAvvalOrder = False
        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            status = statusToString(r['status'])
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        all_list.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, postAvvalOrder))
    return all_list

def search_result(cursor, result):
    all_list = []
    
    for r in result:
        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            postAvvalOrder = False
            status = statusToString(r['status'])
        case_result = cursor.case_orders.find_one({'orderId': r['orderId']})
        if case_result:
            sender_name = case_result['senderFirstName']+' '+case_result['senderLastName']
        else:
            sender_name = '-'
        pNameList = []
        for i in range(len(r['products'])):
            pNameList.append(r['products'][i]['productName'] +' - '+str(r['products'][i]['count']) + u' عدد ')
        if postAvvalOrder:
            state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        else:
            state_result = cursor.states.find_one({'Code': r['stateCode']})
        all_list.append((r['orderId'], r['vendorName'], r['registerFirstName']+' '+r['registerLastName'],
            state_result['Name'],r['record_date'],r['record_time'], r['payType'], r['registerCellNumber'],
            status, pNameList, sender_name, postAvvalOrder))
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

#function for export full excel file from accounting page
def financial_full(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({
            'datetime': {'$gte': '1398/06/05'},
            'vendorName': session['vendor_name']
            })
    else:
        result = cursor.orders.find({
            'datetime': {'$gte': '1398/06/05'}
            })

    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    constant_wage_flag = False
    
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

            api_users_result = cursor.api_users.find_one({'vendor_name':r['vendorName']})
            if 'if_constant_wage' in api_users_result.keys():
                if len(api_users_result['if_constant_wage']):
                    constant_wage_flag = True
                    returned_account = int(api_users_result['constant_wage']['returned'])

            if (pType == 2) or (r['status'] == 11):
                vendor_account = r['costs']['wage']
                if r['status'] == 11:
                    if constant_wage_flag:
                        vendor_account = returned_account
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            elif pType == 88:
                vendor_account = 0 - (r['costs']['price'])
                post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = 0 - (r['costs']['price'])
                post_account = (r['costs']['price']+r['costs']['wage'])

            if pType == 1:
                vestano_account = r['costs']['wage']
            else:
                vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

            t_vendor_account += vendor_account
            t_post_account += post_account
            t_vestano_account += vestano_account

            price += r['costs']['price']
            PostDeliveryPrice += r['costs']['PostDeliveryPrice']
            VatTax += r['costs']['VatTax']
            registerCost += r['costs']['registerCost']
            wage += r['costs']['wage']

            if 'postAvvalFlag' in r.keys():
                postAvvalOrder = True
                status = postAvvalStatusToString(r['status'])
            else:
                postAvvalOrder = False
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

#case-function for calculate full sum of total costs
def case_financial_full(cursor):
    result = cursor.orders.find({
        'vendorName': 'سفارش موردی'
        })

    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_post_account = 0
    t_vestano_account = 0
    
    for r in result:
        #filter just three status
        if (r['status'] in [11, 70, 71]) and ('postAvvalFlag' not in r.keys()):
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

            if (pType == 2) or (r['status'] == 11):
                #vendor_account = r['costs']['wage']
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            elif pType == 88:
                #vendor_account = 0 - (r['costs']['price'])
                post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                #vendor_account = 0 - (r['costs']['price'])
                post_account = (r['costs']['price']+r['costs']['wage'])

            if pType == 1:
                vestano_account = r['costs']['wage']
            else:
                vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

            #t_vendor_account += vendor_account
            t_post_account += post_account
            t_vestano_account += vestano_account

            price += r['costs']['price']
            PostDeliveryPrice += r['costs']['PostDeliveryPrice']
            VatTax += r['costs']['VatTax']
            registerCost += r['costs']['registerCost']
            wage += r['costs']['wage']

            if 'postAvvalFlag' in r.keys():
                postAvvalOrder = True
                status = postAvvalStatusToString(r['status'])
            else:
                postAvvalOrder = False
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
            r['costs']['wage'], 0, post_account, vestano_account , r['payType'],
            protducts_list, status, r['credit_req_status'], r['settlement_ref_number']))

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage, 0, t_post_account, t_vestano_account)
    case_financial = {'record': record, 'totalCosts': totalCosts}

    return case_financial

#def financial(cursor):
def financial(cursor, page):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({
            'datetime': {'$gte': '1398/06/05'},
            'vendorName': session['vendor_name']
            }).sort("_id", -1)
    else:
        result = cursor.orders.find({
            'datetime': {'$gte': '1398/06/05'}
            }).sort("_id", -1)

    filtered_res = []
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    constant_wage_flag = False
    
    #filter just three status
    for r in result:
        if (r['status'] in [11, 70, 71]) and (r['vendorName'] != u'سفارش موردی') :
            filtered_res.append(r)

    L = len(filtered_res)
    res = []
    if L > (REC_IN_EACH_PAGE*page):
        for i in range((REC_IN_EACH_PAGE*(page-1)), (REC_IN_EACH_PAGE*page)):
            res.append(filtered_res[i])
    else:
        for i in range((REC_IN_EACH_PAGE*(page-1)), L):
            res.append(filtered_res[i])
    
    for r in res:
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

        api_users_result = cursor.api_users.find_one({'vendor_name':r['vendorName']})
        if 'if_constant_wage' in api_users_result.keys():
            if len(api_users_result['if_constant_wage']):
                constant_wage_flag = True
                returned_account = int(api_users_result['constant_wage']['returned'])

        if (pType == 2) or (r['status'] == 11):
            vendor_account = r['costs']['wage']
            if r['status'] == 11:
                if constant_wage_flag:
                    vendor_account = returned_account
            post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
        elif pType == 88:
            vendor_account = 0 - (r['costs']['price'])
            post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
        else:
            vendor_account = 0 - (r['costs']['price'])
            post_account = (r['costs']['price']+r['costs']['wage'])

        if pType == 1:
            vestano_account = r['costs']['wage']
        else:
            vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

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

    return (financial, L)

def case_financial(cursor, page):
    result = cursor.orders.find({
        'vendorName': 'سفارش موردی'
        }).sort("_id", -1)

    filtered_res = []
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_post_account = 0
    t_vestano_account = 0
    
    #filter just three status
    for r in result:
        if (r['status'] in [11, 70, 71]) and ('postAvvalFlag' not in r.keys()) :
            filtered_res.append(r)

    L = len(filtered_res)
    res = []
    if L > (REC_IN_EACH_PAGE*page):
        for i in range((REC_IN_EACH_PAGE*(page-1)), (REC_IN_EACH_PAGE*page)):
            res.append(filtered_res[i])
    else:
        for i in range((REC_IN_EACH_PAGE*(page-1)), L):
            res.append(filtered_res[i])
    
    for r in res:
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

        if (pType == 2) or (r['status'] == 11):
            #vendor_account = r['costs']['wage']
            post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
        elif pType == 88:
            #vendor_account = 0 - (r['costs']['price'])
            post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
        else:
            #vendor_account = 0 - (r['costs']['price'])
            post_account = (r['costs']['price']+r['costs']['wage'])

        if pType == 1:
            vestano_account = r['costs']['wage']
        else:
            vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

        #t_vendor_account += vendor_account
        t_post_account += post_account
        t_vestano_account += vestano_account

        price += r['costs']['price']
        PostDeliveryPrice += r['costs']['PostDeliveryPrice']
        VatTax += r['costs']['VatTax']
        registerCost += r['costs']['registerCost']
        wage += r['costs']['wage']

        if 'postAvvalFlag' in r.keys():
            postAvvalOrder = True
            status = postAvvalStatusToString(r['status'])
        else:
            postAvvalOrder = False
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
        r['costs']['wage'], 0, post_account, vestano_account , r['payType'],
        protducts_list, status, r['credit_req_status'], r['settlement_ref_number']))

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage, 0, t_post_account, t_vestano_account)
    case_financial = {'record': record, 'totalCosts': totalCosts}

    return (case_financial, L)

def v_financial(cursor):
#def v_financial(cursor, page):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({
            'datetime': {'$gte': '1398/06/05'},
            'vendorName': session['vendor_name']
            })
    else:
        result = cursor.orders.find({
            'datetime': {'$gte': '1398/06/05'}
            })
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    constant_wage_flag = False

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

            api_users_result = cursor.api_users.find_one({'vendor_name':r['vendorName']})
            if 'if_constant_wage' in api_users_result.keys():
                if len(api_users_result['if_constant_wage']):
                    constant_wage_flag = True
                    returned_account = int(api_users_result['constant_wage']['returned'])

            if (pType == 2) or (r['status'] == 11):
                vendor_account = 0 - r['costs']['wage']
                if r['status'] == 11:
                    if constant_wage_flag:
                        vendor_account =0 - returned_account
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            elif pType == 88:
                vendor_account = r['costs']['price']
                post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = r['costs']['price']
                post_account = (r['costs']['price']+r['costs']['wage'])

            if pType == 1:
                vestano_account = r['costs']['wage']
            else:
                vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

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

def search_financial(cursor, result):
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    constant_wage_flag = False
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

            api_users_result = cursor.api_users.find_one({'vendor_name':r['vendorName']})
            if 'if_constant_wage' in api_users_result.keys():
                if len(api_users_result['if_constant_wage']):
                    constant_wage_flag = True
                    returned_account = int(api_users_result['constant_wage']['returned'])

            if (pType == 2) or (r['status'] == 11):
                vendor_account = r['costs']['wage']
                if r['status'] == 11:
                    if constant_wage_flag:
                        vendor_account = returned_account
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            elif pType == 88:
                vendor_account = 0 - (r['costs']['price'])
                post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = 0 - (r['costs']['price'])
                post_account = (r['costs']['price']+r['costs']['wage'])

            if pType == 1:
                vestano_account = r['costs']['wage']
            else:
                vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

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
    s_financial = {'record': record, 'totalCosts': totalCosts}

    return s_financial

def search_v_financial(cursor, result):
    record = []
    price = 0
    PostDeliveryPrice = 0
    VatTax = 0
    registerCost = 0
    wage = 0
    t_vendor_account = 0
    t_post_account = 0
    t_vestano_account = 0
    constant_wage_flag = False
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

            api_users_result = cursor.api_users.find_one({'vendor_name':r['vendorName']})
            if 'if_constant_wage' in api_users_result.keys():
                if len(api_users_result['if_constant_wage']):
                    constant_wage_flag = True
                    returned_account = int(api_users_result['constant_wage']['returned'])

            if (pType == 2) or (r['status'] == 11):
                vendor_account = 0 - r['costs']['wage']
                if r['status'] == 11:
                    if constant_wage_flag:
                        vendor_account =0 - returned_account
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            elif pType == 88:
                vendor_account = r['costs']['price']
                post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = r['costs']['price']
                post_account = (r['costs']['price']+r['costs']['wage'])

            if pType == 1:
                vestano_account = r['costs']['wage']
            else:
                vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

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
    s_v_financial = {'record': record, 'totalCosts': totalCosts}

    return s_v_financial

def financial_vendor_credit(cursor, vendorName):
    if session['role'] == 'vendor_admin':
        result = cursor.orders.find({
            'datetime': {'$gte': '1398/06/05'},
            'vendorName': session['vendor_name']
            })
    else:
        if vendorName:
            result = cursor.orders.find({
                'datetime': {'$gte': '1398/06/05'},
                'vendorName': vendorName
                })
        else:
            result = cursor.orders.find({
                'datetime': {'$gte': '1398/06/05'}
                })
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
    constant_wage_flag = False
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

            api_users_result = cursor.api_users.find_one({'vendor_name':r['vendorName']})
            if 'if_constant_wage' in api_users_result.keys():
                if len(api_users_result['if_constant_wage']):
                    constant_wage_flag = True
                    returned_account = int(api_users_result['constant_wage']['returned'])

            if (pType == 2) or (r['status'] == 11):
                vendor_account = 0 - r['costs']['wage']
                if r['status'] == 11:
                    if constant_wage_flag:
                        vendor_account =0 - returned_account
                #post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            elif pType == 88:
                vendor_account = r['costs']['price']
                #post_account = (r['costs']['price']+r['costs']['wage']) - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = r['costs']['price']
                #post_account = (r['costs']['price']+r['costs']['wage'])
            #vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

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
            order_id_list.append(r['orderId'])

    credit_request_query = {
    'datetime': jdatetime.datetime.today().strftime('%Y/%m/%d'),
    'jdatetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
    'unique_id': str(random2.randint(10000000, 99999999)),
    'order_id_list': order_id_list,
    'username': session['username'],
    'total_price': t_vendor_account
    }
    cursor.credit_request_query.insert_one(credit_request_query)

    totalCosts = (price, PostDeliveryPrice, VatTax, registerCost, wage, t_vendor_account , t_post_account, t_vestano_account)
    financial = {
    'record': record,
    'totalCosts': totalCosts,
    'credit_count': credit_count,
    'order_id_list': order_id_list,
    'unique_id': credit_request_query['unique_id']
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
    constant_wage_flag = False
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

        api_users_result = cursor.api_users.find_one({'vendor_name':r['vendorName']})
        if 'if_constant_wage' in api_users_result.keys():
            if len(api_users_result['if_constant_wage']):
                constant_wage_flag = True
                returned_account = int(api_users_result['constant_wage']['returned'])

        if (pType == 2) or (r['status'] == 11):
            vendor_account = 0 - r['costs']['wage']
            if r['status'] == 11:
                if constant_wage_flag:
                    vendor_account = 0 - returned_account
        elif pType == 88:
            vendor_account = r['costs']['price']
        else:
            vendor_account = r['costs']['price']

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
    if session['role'] == 'vendor_admin':
        result = cursor.credit_requests.find({'vendor': session['vendor_name']})
    else:
        result = cursor.credit_requests.find()
    credit_requests_list = []
    for r in result:
        credit_requests_list.append(r)
    return credit_requests_list

def paid_list(cursor):
    if session['role'] == 'vendor_admin':
        result = cursor.credit_requests.find({
            'req_status': u'واریز شد',
            'vendor': session['vendor_name']
            })
    else:
        result = cursor.credit_requests.find({'req_status': u'واریز شد'})
    paid_list = []
    for r in result:
        paid_list.append(r)
    return paid_list

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
                vendor_account = r['costs']['wage']
                post_account = 0 - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            else:
                vendor_account = 0 - (r['costs']['price'] - r['costs']['wage'])
                post_account = r['costs']['price'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])
            
            if pType == 1:
                vestano_account = r['costs']['wage']
            else:
                vestano_account = r['costs']['wage'] - (r['costs']['PostDeliveryPrice']+r['costs']['VatTax']+r['costs']['registerCost'])

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
    Weight = 0
    discount = 0
    postAvvalOrder = False
    if code == 'temp':
        r = cursor.temp_orders.find_one({'orderId': orderId})
    elif code == 'caseTemp':
        r = cursor.caseTemp_orders.find_one({'orderId': orderId})
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
    elif code == 'search':
        if cursor.orders.find_one({'orderId': orderId}):
            r = cursor.orders.find_one({'orderId': orderId})
        elif cursor.temp_orders.find_one({'orderId': orderId}):
            r = cursor.temp_orders.find_one({'orderId': orderId})
        elif cursor.caseTemp_orders.find_one({'orderId': orderId}):
            r = cursor.caseTemp_orders.find_one({'orderId': orderId})
        elif cursor.pending_orders.find_one({'orderId': orderId}):
            r = cursor.pending_orders.find_one({'orderId': orderId})
        elif cursor.canceled_orders.find_one({'orderId': orderId}):
            r = cursor.canceled_orders.find_one({'orderId': orderId})
    if not r:
        return None

    if 'postAvvalFlag' in r.keys():
        state_result = cursor.postAvvalStates.find_one({'Code': r['stateCode']})
        postAvvalOrder = True
    else:
        state_result = cursor.states.find_one({'Code': r['stateCode']})

    #sabte code varizi (payInCode)
    payInCode = r['payInCode'] if 'payInCode' in r.keys() else "-"

    #e'lane vaziate darkhaste vajh
    if 'credit_req_status' in r.keys():
        ifCreditPaid = True if r['credit_req_status'] == u'واریز شد' else False
        settlement_ref_num = r['settlement_ref_number'] if 'settlement_ref_number' in r.keys() else ""
    else:
        ifCreditPaid = False
        settlement_ref_num = ''

    for rec in state_result['Cities']:
        if r['cityCode'] == rec['Code']:
            city = rec['Name']
            break

    if postAvvalOrder:
        print(r['status'])
        status = postAvvalStatusToString(r['status'])
    else:
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

    if 'registerPhoneNumber' not in r.keys():
        r['registerPhoneNumber'] = '-'

    if 'username' not in r.keys():
        r['username'] = '-'
    if 'init_username' not in r.keys():
        r['init_username'] = '-'

    if r['vendorName'] == u'سفارش موردی':
        case_ord_res = cursor.case_orders.find_one({'orderId': orderId})
        if 'wage' not in case_ord_res.keys():
            if 'rad' in case_ord_res.keys():
                if len(case_ord_res['rad']):
                    service = 'rad'
                elif len(case_ord_res['cgd']):
                    service = 'cgd'
                else:
                    service = servicesForWageCalculation(pType)
            else:
                service = servicesForWageCalculation(pType)
            wage = calculateWage(cursor, r['vendorName'], Weight, service)
            #wage = calculate_wage(r['vendorName'], Weight)
        else:
            wage = case_ord_res['wage']
        packing = case_ord_res['packing']
        carton = case_ord_res['carton']
        gathering = case_ord_res['gathering']
        senderName = case_ord_res['senderFirstName'] + ' ' + case_ord_res['senderLastName']
        senderCellNumber = case_ord_res['senderCellNumber']
        senderPostalCode = case_ord_res['senderPostalCode']
        if 'senderPhoneNumber' in case_ord_res.keys():
            senderPhoneNumber = case_ord_res['senderPhoneNumber']
        else:
            senderPhoneNumber = '-'
        grnt = None
        if 'rad' in case_ord_res.keys():
            if len(case_ord_res['rad']):
                rad = True
            else:
                rad = False
            if len(case_ord_res['cgd']):
                cgd = True
            else:
                cgd = False
        else:
            rad = None
            cgd = None

        #add wages to product price in cod orders for calculate deliveryPrice
        if (not postAvvalOrder) and (not rad) and (not cgd) and (pType == 1):
            s = wage + packing + carton + gathering
            price_total = price + s
        else:
            price_total = price
    else:
        service = servicesForWageCalculation(pType)
        wage = calculateWage(cursor, r['vendorName'], Weight, service)
        #wage = config.wage
        packing = 0
        carton = 0
        gathering = 0
        senderName = ''
        senderCellNumber = ''
        senderPostalCode = ''
        senderPhoneNumber = ''
        if 'grntProduct' in r.keys():
            grnt = r['grntProduct']
        else:
            grnt = None
        rad = None
        cgd = None

        price_total = price

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
            if postAvvalOrder:
                deliveryPrice = 0
            else:
                deliveryPriceResult = GetDeliveryPrice(r['cityCode'], price_total, Weight, sType, pType)
                deliveryPrice = deliveryPriceResult['DeliveryPrice'] + deliveryPriceResult['VatTax']
            if 'temp_wage' in r.keys():
                temp_wage = r['temp_wage']
            else:
                temp_wage = wage
            if code == 'temp':
                cursor.temp_orders.update_many(
                    {'orderId': r['orderId']},
                    {'$set':{'temp_delivery_costs': deliveryPrice, 'temp_wage': wage}})
            elif code == 'caseTemp':
                cursor.caseTemp_orders.update_many(
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
        senderName, senderCellNumber, senderPostalCode, Weight, packing, carton, gathering, rad,
        cgd, grnt, r['registerPhoneNumber'], r['username'], r['init_username'], senderPhoneNumber,
        postAvvalOrder, price_total, payInCode, ifCreditPaid, settlement_ref_num)

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
    if (serviceType == u'پست پیشتاز') or (serviceType == u'سرویس استاندارد'):
        sType = 1
    elif (serviceType == u'پست سفارشی') or (serviceType == u'سرویس اکسپرس'):
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

def postAvvalTypeOfServicesToString(serviceType, payType):
    if serviceType==1:
        sType = u'سرویس استاندارد'
    elif serviceType==2:
        sType = u'سرویس اکسپرس'
    elif serviceType==3:
        sType = u'سرویس خارجه'
    else:
        return None

    if payType==1:
        pType = u'پرداخت در محل'
    elif payType==2:
        pType = u'پرداخت آنلاین'
    else:
        return None

    return (sType, pType)

def servicesForWageCalculation(pType):
    if pType == 10:
        service = 'rad'
    elif pType == 20:
        service = 'cgd'
    elif (pType == 1) or (pType == 88):
        service = 'cod'
    elif pType == 2:
        service = 'online'

    return service

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
    if statusCode==84:
        statusString = u'حذف از در انتظار کالا'

    return statusString

def statusToStringForCaseOrders(statusCode):
    if statusCode in [0, 2, 5]:
        statusString = u'ارسال شده'
    elif statusCode in [10, 11]:
        statusString = u'برگشتی'
    elif statusCode in [7, 70, 71]:
        statusString = u'تحویل داده شده'
    elif statusCode == 9:
        statusString = u'توقیفی'
    elif statusCode == 8:
        statusString = u'باجه معطله'
    elif statusCode == 80:
        statusString = u'در صف پردازش'
    else:
        statusString = u'لطفا با وستانو تماس بگیرید'

    return statusString

def RolesToFarsi(role):
    if role == 'admin':
        roleFarsi = u'مدیر'
    if role == 'office':
        roleFarsi = u'دفتر'
    if role == 'vendor_admin':
        roleFarsi = u'مدیر فروشگاه'
    if role == 'support':
        roleFarsi = u'پشتیبانی'
    if role == 'api':
        roleFarsi = u'وب سرویس'
    return roleFarsi

def accessToFarsi(access):
    if access == 'caseOrdering':
        accessFarsi = u'ثبت سفارش موردی'
    if access == 'postAvvalOrdering':
        accessFarsi = u'ثبت سفارش پست اول'
    if access == 'Ordering':
        accessFarsi = u'ثبت سفارش'
    if access == 'caseProcessList':
        accessFarsi = u'صف پردازش (موردی)'
    if access == 'processList':
        accessFarsi = u'صف پردازش (فروشگاه)'
    if access == 'todayOrders':
        accessFarsi = u'سفارشات امروز'
    if access == 'cnlOrders':
        accessFarsi = u'سفارشات لغو شده'
    if access == 'rtsOrders':
        accessFarsi = u'سفارشات آماده ارسال'
    if access == 'pndOrders':
        accessFarsi = u'سفارشات در انتظار کالا'
    if access == 'grntOrders':
        accessFarsi = u'سفارشات گارانتی'
    if access == 'allOrders':
        accessFarsi = u'مشاهده همه سفارشات'
    if access == 'caseNewStuff':
        accessFarsi = u'افزودن کالای موردی'
    if access == 'caseEditStuff':
        accessFarsi = u'ویرایش کالای موردی'
    if access == 'newStuff':
        accessFarsi = u'افزودن کالای جدید'
    if access == 'incStuff':
        accessFarsi = u'افزودن کالای موجود'
    if access == 'editStuff':
        accessFarsi = u'ویرایش کالا'
    if access == 'newPack':
        accessFarsi = u'ایجاد بسته'
    if access == 'releaseStuff':
        accessFarsi = u'خروج از انبار'
    if access == 'searchStuff':
        accessFarsi = u'جستجو در انبار'
    if access == 'inventory':
        accessFarsi = u'انبارداری'
    if access == 'financialRep':
        accessFarsi = u'صفحه مالی'
    if access == 'accounting':
        accessFarsi = u'حسابداری'
    if access == 'vendorCredit':
        accessFarsi = u'بستانکاری فروشگاه'
    if access == 'creditList':
        accessFarsi = u'لیست درخواست های واریز وجه'
    if access == 'paidList':
        accessFarsi = u'مبالغ واریزی'
    if access == 'searchPage':
        accessFarsi = u'صفحه جستجو'
    if access == 'vendorTicket':
        accessFarsi = u'تیکت فروشگاه'
    if access == 'adminTicket':
        accessFarsi = u'تیکت مدیریت'
    if access == 'ordersTicket':
        accessFarsi = u'تیکت سفارشات'
    if access == 'inventoryTicket':
        accessFarsi = u'تیکت انبارداری'
    if access == 'financialTicket':
        accessFarsi = u'تیکت حسابداری'
    if access == 'techTicket':
        accessFarsi = u'تیکت فنی'
    if access == 'incCredit':
        accessFarsi = u'افزایش اعتبار '
    if access == 'requestForStuff':
        accessFarsi = u'درخواست حواله و خروج از انبار'
    if access == 'dashboard':
        accessFarsi = u'داشبورد'
    if access == 'defineUser':
        accessFarsi = u'ایجاد کاربری'
    if access == 'wageManagement':
        accessFarsi = u'مدیریت کارمزدها'
    if access == 'inventManagement':
        accessFarsi = u'مدیریت انبار'
    if access == 'caseAllOrders':
        accessFarsi = u'همه سفارشات موردی'
    if access == 'vendorsAllOrders':
        accessFarsi = u'همه سفارشات فروشگاهی'
    if access == 'searchInCases':
        accessFarsi = u'جستجو - سفارشات موردی'
    if access == 'searchInVendors':
        accessFarsi = u'جستجو - سفارشات فروشگاهی'
    if access == 'searchInAccounting':
        accessFarsi = u'جستجو - حسابداری'

    return accessFarsi

def states(cursor):
    result = cursor.states.find()
    states = []
    for r in result:
        states.append((r['Code'], r['Name'], r['Cities']))
    return states

def postAvvalStates(cursor):
    result = cursor.postAvvalStates.find()
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

def postAvvalCities(cursor, code):
    result = cursor.postAvvalStates.find_one({'Code': code})
    ans = {'Code':[], 'Name':[], 'stateName':result['Name'], 'stateCode':code}
    for r in result['Cities']:
        ans['Code'].append(r['Code'])
        ans['Name'].append(r['Name'])
    return ans

def Products(cursor, product):
    result = cursor.vestano_inventory.find_one({'productId': product})
    if not result:
        result = cursor.case_inventory.find_one({'productId': product})
    if 'pack_products' not in result.keys():
        result['pack_products'] = []

    defaultWageForDefineStuff = defaultWage(cursor, result['vendor'])
    ans = {
    'productName': result['productName'],
    'productId': product,
    'count': result['count'],
    'vendor': result['vendor'],
    'price': result['price'] - defaultWageForDefineStuff,
    'weight': result['weight'],
    'discount': result['percentDiscount'],
    'pack_products': result['pack_products']
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
    if session['role'] == 'vendor_admin':
        result = cursor.inventory_transfer.find({'vendor': session['vendor_name']})
    else:
        result = cursor.inventory_transfer.find()
    transfer_list = []
    for r in result:
        r['request_type'] = transfer_req_type(r['request_type'])
        transfer_list.append(r)
    return transfer_list

def transfer_details(cursor, number):
    result = cursor.inventory_transfer.find_one({'number':number})
    result['transfer_req_type'] = transfer_req_type(result['request_type'])
    if 'productId' in result.keys():
        r_result = cursor.vestano_inventory.find_one({'productId': result['productId']})
        if r_result:
            result['exist_count'] = r_result['count']
        #if result['request_type'] != 'edit':
            #result['productName'] = r_result['productName']
            #result['price'] = r_result['price']
            #result['percentDiscount'] = r_result['percentDiscount']
            #result['weight'] = r_result['weight']
            #result['exist_count'] = r_result['count']
        #else:
            #result['exist_count'] = r_result['count']
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

def GetStatus(cursor, s):
    client = Client(API_URI)
    #print(client)
    change_flag = 0

    status_records = cursor.status.find()
    for rec in status_records:
        if rec['status'] in [1, 11, 71]:
            cursor.status.remove({'parcelCode': rec['parcelCode']})

    status_records = cursor.status.find()
    for rec in status_records:

        if 'postAvvalFlag' in rec.keys():
            continue
        if s == '0':
            if rec['status'] != 0:
                continue
        elif s == '2':
            if rec['status'] != 2:
                continue
        elif s == '5':
            if rec['status'] != 5:
                continue
        elif s == '7':
            if rec['status'] != 7:
                continue
        elif s == '70':
            if rec['status'] != 70:
                continue
        else:
            if rec['status'] not in [3, 4, 6, 8, 9, 10, 81]:
                continue

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
            if status == 7:
                cursor.orders.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{'status7Update': jdatetime.datetime.today().strftime('%Y/%m/%d')}}
                    )
                cursor.status.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{'status7Update': jdatetime.datetime.today().strftime('%Y/%m/%d')}}
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

def write_excel_financial(cursor, role):
    #filename = "E:/projects/VESTANO/Vestano/static/pdf/financial.xls"
    filename = "/root/vestano/static/pdf/xls/financial.xls"
    f = financial_full(cursor)
    finan = f['record']
    excel_file = xlwt.Workbook()
    today = jdatetime.datetime.today().strftime('%Y-%m-%d')
    sheet = excel_file.add_sheet(today)
    style0 = xlwt.easyxf('font: name Times New Roman, bold on;'
        'pattern: pattern solid, fore_colour yellow;'
        'align: horiz center;')
    if role == 'vendor_admin':
        sheet.cols_right_to_left = 1
        sheet.write(0, 0, u'شناسه سفارش', style0)
        sheet.write(0, 1, u'کد رهگیری', style0)
        sheet.write(0, 2, u'مبلغ تمام شده کالا', style0)
        sheet.write(0, 3, u'کارمزد', style0)
        sheet.write(0, 4, u'بستانکار | بدهکار فروشگاه', style0)
        sheet.write(0, 5, u'وضعیت درخواست وجه', style0)
        sheet.write(0, 6, u'وضعیت مرسوله', style0)
        sheet.write(0, 7, u'نوع پرداخت', style0)
        for i in range(1, len(finan)+1):
            row = i
            for j in range(3):
                col = j
                ctype = 'string'
                value = finan[i-1][j]
                xf = 0
                sheet.write(row, col, value)
            col = 3
            ctype = 'string'
            value = finan[i-1][6]
            xf = 0
            sheet.write(row, col, value)
            col = 4
            ctype = 'string'
            value = (0 - finan[i-1][7])
            xf = 0
            sheet.write(row, col, value)
            col = 5
            ctype = 'string'
            value = finan[i-1][13]
            xf = 0
            sheet.write(row, col, value)
            col = 6
            ctype = 'string'
            value = finan[i-1][12]
            xf = 0
            sheet.write(row, col, value)
            col = 7
            ctype = 'string'
            value = finan[i-1][10]
            xf = 0
            sheet.write(row, col, value)
    else:
        sheet.cols_right_to_left = 1
        sheet.write(0, 0, u'شناسه سفارش', style0)
        sheet.write(0, 1, u'کد رهگیری', style0)
        sheet.write(0, 2, u'مبلغ تمام شده کالا', style0)
        sheet.write(0, 3, u'هزینه ارسال', style0)
        sheet.write(0, 4, u'ارزش افزوده', style0)
        sheet.write(0, 5, u'حق ثبت', style0)
        sheet.write(0, 6, u'کارمزد', style0)
        sheet.write(0, 7, u'بستانکار | بدهکار فروشگاه', style0)
        sheet.write(0, 8, u'بستانکار | بدهکار پست', style0)
        sheet.write(0, 9, u'بستانکار | بدهکار وستانو', style0)
        sheet.write(0, 10, u'وضعیت درخواست وجه', style0)
        sheet.write(0, 11, u'وضعیت مرسوله', style0)
        sheet.write(0, 12, u'نوع پرداخت', style0)
        for i in range(1, len(finan)+1):
            row = i
            for j in range(10):
                col = j
                ctype = 'string'
                value = finan[i-1][j]
                xf = 0
                sheet.write(row, col, value)
            col = 10
            ctype = 'string'
            value = finan[i-1][13]
            xf = 0
            sheet.write(row, col, value)
            col = 11
            ctype = 'string'
            value = finan[i-1][12]
            xf = 0
            sheet.write(row, col, value)
            col = 12
            ctype = 'string'
            value = finan[i-1][10]
            xf = 0
            sheet.write(row, col, value)
    excel_file.save(filename)

def lias_write_excel(cursor, result):
    #filename = "E:/projects/VESTANO/Vestano/static/pdf/lias.xls"
    filename = "/root/vestano/static/pdf/xls/lias.xls"
    excel_file = xlwt.Workbook()
    today = jdatetime.datetime.today().strftime('%Y-%m-%d')
    sheet = excel_file.add_sheet(today)
    style0 = xlwt.easyxf('font: name Times New Roman, bold on;'
        'pattern: pattern solid, fore_colour yellow;'
        'align: horiz center;')
    sheet.cols_right_to_left = 1
    sheet.write(0, 0, u'ردیف', style0)
    sheet.write(0, 1, u'بارکد پستی', style0)
    sheet.write(0, 2, u'مقصد', style0)
    sheet.write(0, 3, u'وزن', style0)
    sheet.write(0, 4, u'فرستنده', style0)
    sheet.write(0, 5, u'گیرنده', style0)
    sheet.write(0, 6, u'هزینه پستی', style0)
    sheet.write(0, 7, u'تاریخ', style0)
    for i in range(len(result)):
        state_result = cursor.states.find_one({'Code': result[i]['stateCode']})
        weight = 0
        for j in range(len(result[i]['products'])):
            weight += (result[i]['products'][j]['weight'] * result[i]['products'][j]['count'])
        ctype = 'string'
        xf = 0
        sheet.write(i+1, 0, i+1)
        sheet.write(i+1, 1, result[i]['parcelCode'])
        sheet.write(i+1, 2, state_result['Name'])
        sheet.write(i+1, 3, weight)
        sheet.write(i+1, 4, u'سامانه پستی وستانو')
        sheet.write(i+1, 5, result[i]['registerFirstName']+' '+result[i]['registerLastName'])
        sheet.write(i+1, 6, result[i]['costs']['PostDeliveryPrice']+result[i]['costs']['VatTax'])
        sheet.write(i+1, 7, result[i]['datetime'])
    excel_file.save(filename)

def sellsProducts_write_excel(cursor, result):
    #filename = "E:/projects/VESTANO/Vestano/static/pdf/sellsProducts.xls"
    filename = "/root/vestano/static/pdf/xls/sellsProducts.xls"
    excel_file = xlwt.Workbook()
    today = jdatetime.datetime.today().strftime('%Y-%m-%d')
    sheet = excel_file.add_sheet(today)
    style0 = xlwt.easyxf('font: name Times New Roman, bold on;'
        'pattern: pattern solid, fore_colour yellow;'
        'align: horiz center;')
    style1 = xlwt.easyxf('font: name Times New Roman, bold on;'
        'pattern: pattern solid, fore_colour white;'
        'align: horiz center;')
    sheet.cols_right_to_left = 1
    sheet.write(0, 0, u'ردیف', style0)
    sheet.write(0, 1, u'شناسه محصول', style0)
    sheet.write(0, 2, u'نام محصول', style0)
    sheet.write(0, 3, u'تعداد', style0)
    vendor_inventory = cursor.vestano_inventory.find({'vendor': session['vendor_name']})
    products = {}
    #for res in vendor_inventory:
    #count = 0
    for orderId in result:
        r = cursor.orders.find_one({'orderId': orderId})
        for j in range(len(r['products'])):
            if r['products'][j]['productId'] in products.keys():
                products[r['products'][j]['productId']][0] += r['products'][j]['count']
            else:
                products[r['products'][j]['productId']] = []
                products[r['products'][j]['productId']].append(r['products'][j]['count'])
                products[r['products'][j]['productId']].append(r['products'][j]['productName'])
    #print(products)
    #products.append((res['productId'], res['productName'], count))
    for i in range(len(products.keys())):
        ctype = 'string'
        xf = 0#
        sheet.write(i+1, 0, i+1, style1)
        sheet.write(i+1, 1, products.keys()[i], style1)
        sheet.write(i+1, 2, products[products.keys()[i]][1], style1)
        sheet.write(i+1, 3, products[products.keys()[i]][0], style1)
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

def calculateWage(cursor, vendor, weight, service):
    constant_wage = False
    number = cursor.wage_setting.estimated_document_count()
    wage_result = cursor.wage_setting.find_one({'number':number})
    vendor_wage_status = cursor.api_users.find_one({'vendor_name':vendor})
    if vendor_wage_status:
        if 'if_constant_wage' in vendor_wage_status.keys():
            if len(vendor_wage_status['if_constant_wage']):
                constant_wage = True
        if 'if_variable_wage' in vendor_wage_status.keys():
            if len(vendor_wage_status['if_variable_wage']):
                wage_result = vendor_wage_status['variable_wage']

    if (vendor == u'سفارش موردی') or (not constant_wage):
        if weight < 10000:
            if service == 'online':
                vestano_wage = wage_result['online']['LT10']
            elif service == 'cod':
                vestano_wage = wage_result['cod']['LT10']
            elif service == 'cgd':
                vestano_wage = wage_result['cgd']['LT10']
            elif service == 'rad':
                vestano_wage = wage_result['rad']['LT10']
        elif 10000 <= weight < 15000:
            if service == 'online':
                vestano_wage = wage_result['online']['10-15']
            elif service == 'cod':
                vestano_wage = wage_result['cod']['10-15']
            elif service == 'cgd':
                vestano_wage = wage_result['cgd']['10-15']
            elif service == 'rad':
                vestano_wage = wage_result['rad']['10-15']            
        elif 15000 <= weight < 20000:
            if service == 'online':
                vestano_wage = wage_result['online']['15-20']
            elif service == 'cod':
                vestano_wage = wage_result['cod']['15-20']
            elif service == 'cgd':
                vestano_wage = wage_result['cgd']['15-20']
            elif service == 'rad':
                vestano_wage = wage_result['rad']['15-20']
        elif 20000 <= weight < 25000:
            if service == 'online':
                vestano_wage = wage_result['online']['20-25']
            elif service == 'cod':
                vestano_wage = wage_result['cod']['20-25']
            elif service == 'cgd':
                vestano_wage = wage_result['cgd']['20-25']
            elif service == 'rad':
                vestano_wage = wage_result['rad']['20-25']
        elif 25000 <= weight < 30000:
            vestano_wage = wage_result['online']['25-30']
        elif weight >= 30000:
            if service == 'online':
                vestano_wage = wage_result['online']['GT30']
            elif service == 'cod':
                vestano_wage = wage_result['cod']['GT30']
            elif service == 'cgd':
                vestano_wage = wage_result['cgd']['GT30']
            elif service == 'rad':
                vestano_wage = wage_result['rad']['GT30']
    else:
        vestano_wage = vendor_wage_status['constant_wage']['distributive']

    return int(vestano_wage)

def case_query_result(cursor, rec, query_list_1, query_list_2):
    if len(query_list_1):
        query_1 = {
                'datetime': {'$gte': rec['date_from'], '$lte': rec['date_to']},
                'vendorName': 'سفارش موردی',
                '$and': query_list_1
                }
    else:
        query_1 = {
                'datetime': {'$gte': rec['date_from'], '$lte': rec['date_to']},
                'vendorName': 'سفارش موردی'
                }
    if len(query_list_2):
        query_2 = {'$and': query_list_2}
    else:
        query_2 = {}
    res_1 = cursor.orders.find(query_1)
    res_2 = cursor.caseTemp_orders.find(query_1)
    res_3 = cursor.canceled_orders.find(query_1)
    res_all = []
    result_1 = []
    for r in res_1:
        res_all.append([r, r['datetime']])
    for r in res_2:
        res_all.append([r, r['datetime']])
    for r in res_3:
        res_all.append([r, r['datetime']])
    res_all = sorted(res_all, key=itemgetter(1))
    for r in res_all:
        result_1.append(r[0])

    result_2 = cursor.case_orders.find(query_2)
    result = []
    result_2_list = []
    if rec['s_name'] and rec['r_name']:
        for r in result_2:
            if (rec['s_name'] in (r['senderFirstName']+' '+r['senderLastName'])) and (rec['r_name'] in (r['receiverFirstName']+' '+r['receiverLastName'])):
                result_2_list.append(r)
    elif rec['s_name']:
        for r in result_2:
            if (rec['s_name'] in (r['senderFirstName']+' '+r['senderLastName'])):
                result_2_list.append(r)
    elif rec['r_name']:
        for r in result_2:
            if (rec['r_name'] in (r['receiverFirstName']+' '+r['receiverLastName'])):
                result_2_list.append(r)
    else:
        for r in result_2:
            result_2_list.append(r)
    for r1 in result_1:
        for r2 in result_2_list:
            if r1['orderId'] == r2['orderId']:
                result.append(r1)
    return result

def query_result(cursor, rec, query_list):
    if len(query_list):
        query = {
        'datetime': {'$gte': rec['date_from'], '$lte': rec['date_to']},
        'vendorName': {'$ne': 'سفارش موردی'},
        '$and': query_list
        }
    else:
        query = {
        'datetime': {'$gte': rec['date_from'], '$lte': rec['date_to']},
        'vendorName': {'$ne': 'سفارش موردی'}
        }
    
    result = []
    #not for accounting search result
    if 'serviceType' in rec.keys():
        if rec['status']:
            if rec['status'] == '80':
                res = cursor.temp_orders.find(query)
            elif rec['status'] in ['82', '84']:
                res = cursor.pending_orders.find(query)
            elif rec['status'] == '83':
                res = cursor.canceled_orders.find(query)
            else:
                res = cursor.orders.find(query)

            if rec['register_name']:
                for r in res:
                    if rec['register_name'] in (r['registerFirstName']+' '+r['registerLastName']):
                        result.append(r)
            else:
                for r in res:
                    result.append(r)
        
        else:
            result_all = []
            res = []
            result1 = cursor.orders.find(query)
            result2 = cursor.temp_orders.find(query)
            result3 = cursor.pending_orders.find(query)
            result4 = cursor.canceled_orders.find(query)
            for r in result1:
                result_all.append([r, r['datetime']])
            for r in result2:
                result_all.append([r, r['datetime']])
            for r in result3:
                result_all.append([r, r['datetime']])
            for r in result4:
                result_all.append([r, r['datetime']])
            result_all = sorted(result_all, key=itemgetter(1))
            for r in result_all:
                res.append(r[0])
            if rec['register_name']:
                for r in res:
                    if rec['register_name'] in (r['registerFirstName']+' '+r['registerLastName']):
                        result.append(r)
            else:
                result = res
    else:
        res = cursor.orders.find(query)
        for r in res:
            if r['status'] in [11, 70, 71]:
                result.append(r)
    return result

def case_search(cursor, rec):
    query_list_1 = []
    query_list_2 = []
    for key, value in rec.items():
        if (value) and (key not in ['date_from', 'date_to', 's_name', 'r_name', 'rad', 'cgd']):
            if key in ['stateCode', 'cityCode', 'status']:
                query_list_1.append({key: int(value)})
            elif key == 'productId':
                query_list_1.append({'products.productId': value})
            else:
                if (value != 'rad') and (value != 'cgd'):
                    query_list_1.append({key: value})
        if (value) and (key in ['rad', 'cgd']):
            query_list_2.append({key: value})
    result = case_query_result(cursor, rec, query_list_1, query_list_2)
    return result

def vendor_search(cursor, rec):
    query_list = []
    for key, value in rec.items():
        if (value) and (key not in ['date_from', 'date_to', 'register_name']):
            if key in ['stateCode', 'cityCode', 'status']:
                query_list.append({key: int(value)})
            elif key == 'productId':
                query_list.append({'products.productId': value})
            else:
                query_list.append({key: value})
    result = query_result(cursor, rec, query_list)
    return result

def accounting_search(cursor, rec):
    query_list = []
    for key, value in rec.items():
        if (value) and (key not in ['date_from', 'date_to']):
            if key in ['status']:
                query_list.append({key: int(value)})
            elif key == 'productId':
                query_list.append({'products.productId': value})
            else:
                query_list.append({key: value})
    result = query_result(cursor, rec, query_list)
    return result

def lias_search(cursor, rec, prev_lias):
    query = {
    'datetime': {'$gte': rec['date_from'], '$lte': rec['date_to']}
    }

    result = []
    res = cursor.orders.find(query)
    for r in res:
        if (r['orderId'] in prev_lias) or (r['status'] == 1) or (r['status'] == 3):
            continue

        if r['status'] in [0, 2]:
            status = GetStatus_one(cursor, r['parcelCode'])
            if status not in [0, 1, 3]:
                result.append(r)
                prev_status = r['status']
                cursor.orders.update_many(
                    {'parcelCode': r['parcelCode']},
                    {'$set':{
                    'status': status,
                    'lastUpdate' : datetime.datetime.now(),
                    'status_updated' : True
                    }
                    }
                    )
                cursor.status.update_many(
                    {'parcelCode': r['parcelCode']},
                    {'$set':{
                    'status': status,
                    'lastUpdate' : datetime.datetime.now(),
                    'status_updated' : True
                    }
                    }
                    )
                cursor.today_orders.update_many(
                    {'parcelCode': r['parcelCode']},
                    {'$set':{
                    'status': status
                    }
                    }
                    )
                cursor.ready_to_ship.update_many(
                    {'parcelCode': r['parcelCode']},
                    {'$set':{
                    'status': status
                    }
                    }
                    )
                cursor.guarantee_orders.update_many(
                    {'parcelCode': r['parcelCode']},
                    {'$set':{
                    'status': status
                    }
                    }
                    )
                for i in range(len(r['products'])):
                    if r['vendorName'] == u'سفارش موردی':
                        vinvent = cursor.case_inventory.find_one({'productId':r['products'][i]['productId']})
                        if vinvent:
                            vinvent['status'][str(status)]+= r['products'][i]['count']
                            vinvent['status'][str(prev_status)]-= r['products'][i]['count']
                            cursor.case_inventory.update_many(
                                {'productId': vinvent['productId']},
                                {'$set':{'status': vinvent['status']}}
                                )
                    else:
                        vinvent = cursor.vestano_inventory.find_one({'productId':r['products'][i]['productId']})
                        if vinvent:
                            vinvent['status'][str(status)]+= r['products'][i]['count']
                            vinvent['status'][str(prev_status)]-= r['products'][i]['count']
                            cursor.vestano_inventory.update_many(
                                {'productId': vinvent['productId']},
                                {'$set':{'status': vinvent['status']}}
                                )
        else:
            result.append(r)
    return result

def defaultWage(cursor, vendor_name):
    defaultWage = 0
    api_users_result = cursor.api_users.find_one({'vendor_name': vendor_name})
    if 'if_constant_wage' in api_users_result.keys():
        if len(api_users_result['if_constant_wage']):
            defaultWage = api_users_result['constant_wage']['distributive']
    return defaultWage

def postAvval_token_generator():
    data = {
    'username': postAvval_username,
    'password': postAvval_password,
    'client_id': 'ps.m.client',
    'scope': 'parcel_storage profile openid offline_access',
    'grant_type': 'password'
    }
    test_url = 'https://ttk.titec.ir/connect/token'
    url = 'https://tidp.titec.ir/connect/token'
    response = requests.post(test_url, data=data)
    return response.json()['access_token']

def postAvval_preCode(data, token):
    data = json.dumps(data)
    test_url = 'https://fpt.titec.ir/api/v1/parcel/getprecode'
    url = 'https://tcapi.titec.ir/api/v1/parcel/getprecode'
    bearer_token = "Bearer {}".format(token)
    header = {
    "authorization": bearer_token,
    "Content-Type": "application/json",
    "User-Agent": "PostmanRuntime/7.21.0",
    }
    response = requests.post(test_url, data=data, headers=header)
    print(response.status_code)
    #print(type(response.status_code))
    print(response.json())
    if response.status_code not in [201, 200]:
        result = False
    else:
        result = {
        'preCode': response.json()['preCode'],
        'createDatePersian': response.json()['createDatePersian']
        }
    return result

def postAvval_acceptparcel(data, token):
    data = json.dumps(data)
    test_url = "https://fpt.titec.ir/api/v1/parcel/acceptparcel"
    url = 'https://tcapi.titec.ir/api/v1/parcel/acceptparcel'
    bearer_token = "Bearer {}".format(token)
    header = {
    "authorization": bearer_token,
    "Content-Type": "application/json",
    "User-Agent": "PostmanRuntime/7.21.0",
    }
    response = requests.post(test_url, data=data, headers=header)
    if response.status_code not in [201, 200]:
        result = False
    else:
        result = {
        'parcelCode': response.json()['code'],
        'createDatePersian': response.json()['createDatePersian']
        }
    return result

def postAvval_provinces(token):
    test_url = 'https://gst.titec.ir/api/v1/general/getprovinces'
    url = 'https://tgsapi.titec.ir/api/v1/general/getprovinces'
    bearer_token = "Bearer {}".format(token)
    header = {
    "Authorization": bearer_token,
    "Content-Type": "application/json",
    }
    response = requests.get(test_url, headers=header)
    return response.json()

def postAvval_cities(token, p_id):
    test_url = 'https://gst.titec.ir/api/v1/general/getcitiesbyprovinceId/'+p_id
    url = 'https://tgsapi.titec.ir/api/v1/general/getcitiesbyprovinceId/'+p_id
    bearer_token = "Bearer {}".format(token)
    header = {
    "Authorization": bearer_token,
    "Content-Type": "application/json",
    }
    response = requests.get(test_url, headers=header)
    #print(response.status_code)
    #print(response.json())
    return response.json()

def postAvval_change_status(data, token):
    data = json.dumps(data)
    test_url = "https://fpt.titec.ir/api/v1/parcel/changestatus"
    url = 'https://tcapi.titec.ir/api/v1/parcel/changestatus'
    bearer_token = "Bearer {}".format(token)
    header = {
    "authorization": bearer_token,
    "Content-Type": "application/json",
    "User-Agent": "PostmanRuntime/7.21.0",
    }
    response = requests.post(test_url, data=data, headers=header)
    print(response.status_code)
    #print(type(response.status_code))
    print(response.json())
    if response.status_code not in [201, 200]:
        result = False
    else:
        result = response.json()
    return result

#set the "postAvvalStates" collection in database
def creat_postAvvalStates_collection():
    token = postAvval_token_generator()
    postAvvalStates = cursor.postAvvalStates.find_one({'Code': 1})
    if postAvvalStates:
        if 'Cities' not in postAvvalStates.keys():
            postAvvalStates = cursor.postAvvalStates.find()
            for r in postAvvalStates:
                response = postAvval_cities(token, str(r['Code']))
                cities = []
                for c in response:
                    d = {
                    'Code': c['id'],
                    'Name':c['name']
                    }
                    cities.append(d)
                cursor.postAvvalStates.update_many(
                    {'Code': r['Code']},
                    {'$set':{'Cities': cities}}
                    )
    else:
        response = postAvval_provinces(token)
        for r in response:
            cursor.postAvvalStates.insert_one({'Code': r['id'], 'Name': r['name']})

def dimension(value):
    if value == "0":
        dimension = {"length": "15", "width": "10", "height": "8"}
    elif value == "1":
        dimension = {"length": "20", "width": "14", "height": "10"}
    elif value == "2":
        dimension = {"length": "24", "width": "17", "height": "12"}
    elif value == "3":
        dimension = {"length": "28", "width": "20", "height": "14"}
    elif value == "4":
        dimension = {"length": "30", "width": "22", "height": "15"}
    elif value == "5":
        dimension = {"length": "35", "width": "25", "height": "18"}
    elif value == "6":
        dimension = {"length": "40", "width": "27", "height": "20"}
    elif value == "7":
        dimension = {"length": "45", "width": "35", "height": "22"}
    elif value == "8":
        dimension = {"length": "60", "width": "45", "height": "30"}
    return dimension

def dimensionToValue(dimension):
    if dimension == {"length": "15", "width": "10", "height": "8"}:
        value = (u'سایز نیم', "0")
    elif dimension == {"length": "20", "width": "14", "height": "10"}:
        value = (u'سایز 1', "1")
    elif dimension == {"length": "24", "width": "17", "height": "12"}:
        value = (u'سایز 2', "2")
    elif dimension == {"length": "28", "width": "20", "height": "14"}:
        value = (u'سایز 3', "3")
    elif dimension == {"length": "30", "width": "22", "height": "15"}:
        value = (u'سایز 4', "4")
    elif dimension == {"length": "35", "width": "25", "height": "18"}:
        value = (u'سایز 5', "5")
    elif dimension == {"length": "40", "width": "27", "height": "20"}:
        value = (u'سایز 6', "6")
    elif dimension == {"length": "45", "width": "35", "height": "22"}:
        value = (u'سایز 7', "7")
    elif dimension == {"length": "60", "width": "45", "height": "30"}:
        value = (u'سایز بزرگ', "8")
    return value

def convertPostAvvalCities(cityCode):
    states_result = cursor.postAvvalStates.find()
    flag = 0
    for r in states_result:
        for c in r['Cities']:
            if int(cityCode) == c['Code']:
                flag = 1
                (state, city) = (r['Name'], c['Name'])
                break
    if flag:
        State = cursor.states.find_one({'Name': state})
        if State:
            for r in State['Cities']:
                if r['Name'] == city:
                    return (State['Code'], r['Code'])
    return None

def postAvvalStatusToString(statusCode):
    statusCode = int(statusCode)
    if statusCode==1:
        statusString = u'ثبت سفارش'
    if statusCode==2:
        statusString = u'قبول'
    if statusCode==3:
        statusString = u'دریافت از محل فرستنده'
    if statusCode==4:
        statusString = u'دریافت از شعبه مبدا'
    if statusCode==5:
        statusString = u'دریافت از هاب مبدا'
    if statusCode==6:
        statusString = u'در مسیر شهر مقصد'
    if statusCode==7:
        statusString = u'دریافت در شعبه مقصد'
    if statusCode==8:
        statusString = u'دریافت در هاب مقصد'
    if statusCode==9:
        statusString = u'در مسیر توزیع'
    if statusCode==10:
        statusString = u'در مسیر هاب'
    if statusCode==11:
        statusString = u'در هاب'
    if statusCode==12:
        statusString = u'امتناع از تحویل گرفتن'
    if statusCode==13:
        statusString = u'عدم حضور در نشانی'
    if statusCode==14:
        statusString = u'نشانی صحیح نمی باشد'
    if statusCode==15:
        statusString = u'عودت (لطفا تا چهار روز با شعبه فرستنده تماس بگیرید)'
    if statusCode==16:
        statusString = u'مفقودی (با دفتر مرکزی تماس بگیرید)'
    if statusCode==17:
        statusString = u'پرونده خسارتی (با دفتر مرکزی تماس بگیرید)'
    if statusCode==18:
        statusString = u'تحویل مرسوله'
    if statusCode==19:
        statusString = u'تحویل عودتی به فرستنده'
    if statusCode==20:
        statusString = u'رسيدگی و جبران خسارت شد'
    if statusCode==80:
        statusString = u'در صف پردازش'
    if statusCode==81:
        statusString = u'ارسال شده از وستانو'
    if statusCode==82:
        statusString = u'در انتظار کالا'
    if statusCode==83:
        statusString = u'لغو شده'
    if statusCode==84:
        statusString = u'حذف از در انتظار کالا'
    if statusCode==101:
        statusString = u'عدم قبول'
    if statusCode==102:
        statusString = u'عدم تایيد'

    return statusString

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['xlsx', 'xls']

def update_settlement_status(src):
    if_change = False
    file = exel(src)
    for i in range(1, file.nrows):
        rec = cursor.orders.find_one({'parcelCode': str(file.cell(i, 1).value)})
        if rec:
            if str(file.cell(i, 5).value) in ['1', '4']:
                if_change = True
                cursor.orders.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 71,
                    'payInCode' : str(file.cell(i, 4).value),
                    'lastUpdate' : datetime.datetime.now(),
                    'status_updated' : True
                    }
                    }
                    )
                cursor.today_orders.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 71,
                    'payInCode' : str(file.cell(i, 4).value)
                    }
                    }
                    )
                cursor.ready_to_ship.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 71,
                    'payInCode' : str(file.cell(i, 4).value)
                    }
                    }
                    )
                cursor.guarantee_orders.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 71,
                    'payInCode' : str(file.cell(i, 4).value)
                    }
                    }
                    )
                cursor.status.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 71,
                    'lastUpdate' : datetime.datetime.now()
                    }
                    }
                    )
            elif str(file.cell(i, 5).value) == '2':
                if_change = True
                cursor.orders.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 11,
                    'payInCode' : str(file.cell(i, 4).value),
                    'lastUpdate' : datetime.datetime.now(),
                    'status_updated' : True
                    }
                    }
                    )
                cursor.today_orders.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 11,
                    'payInCode' : str(file.cell(i, 4).value)
                    }
                    }
                    )
                cursor.ready_to_ship.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 11,
                    'payInCode' : str(file.cell(i, 4).value)
                    }
                    }
                    )
                cursor.guarantee_orders.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 11,
                    'payInCode' : str(file.cell(i, 4).value)
                    }
                    }
                    )
                cursor.status.update_many(
                    {'parcelCode': rec['parcelCode']},
                    {'$set':{
                    'status': 11,
                    'lastUpdate' : datetime.datetime.now()
                    }
                    }
                    )
    return if_change