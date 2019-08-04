#coding: utf-8
from flask import Flask, render_template, flash, redirect, url_for, session, request, jsonify
from flask import Response, logging, Markup, abort, after_this_request, make_response, send_file
#from flask_recaptcha import ReCaptcha
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from functools import wraps
from flask_spyne import Spyne
from cerberus import Validator
from spyne.protocol.soap import Soap11
from spyne.model.primitive import Unicode, Integer, String
from spyne.model.complex import Array, Iterable, ComplexModel
from werkzeug.utils import secure_filename
import requests
import random2
import uuid
import os
import subprocess
import sys
import jwt
import datetime
import jdatetime
import pdfkit
import copy
import json
import utils, config

#Config mongodb
cursor = utils.config_mongodb()

ATTACHED_FILE_FOLDER = '/root/vestano/static/attachments/'
#ATTACHED_FILE_FOLDER = 'E:/projects/VESTANO/Vestano/static/attachments/'

app = Flask(__name__)

app.secret_key = 'secret@vestano@password_hash@840'

app.config['ATTACHED_FILE_FOLDER'] = ATTACHED_FILE_FOLDER
#app.config.update({
    #'RECAPTCHA_ENABLED': True,
    #'RECAPTCHA_SITE_KEY': '6Lc-0asUAAAAAMBA5mQR2Svai9uFEtNJe5gvu8_z',
    #'RECAPTCHA_SECRET_KEY': '6Lc-0asUAAAAAG3ukYfT0Gwd4llqFCyYTmfcvRul'
    #})
#recaptcha = ReCaptcha(app=app)

spyne = Spyne(app)

name_schema = {
'name': {
    'type': 'string',
    'required': True,
    'regex': '^[ آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهءئی]+$'
}
}

number_schema = {
'number':{
    'type': 'string',
    'required': True,
    'regex': '^([0])[0-9]+$',
    'maxlength': 11
}
}

v = Validator()

#Create namespace
class Products(ComplexModel):
    __namespace__ = "products"
    productId = String
    count = Integer
    price = Integer
    percentDiscount = Integer

class Codes(ComplexModel):
    __namespace__ = "codes"
    Name = Unicode
    Code = Integer

class SomeSoapService(spyne.Service):
    __service_url_path__ = '/soap/VestanoWebService'
    __in_protocol__ = Soap11(validator='lxml')
    __out_protocol__ = Soap11()

    @spyne.srpc(String, String, Unicode, Unicode, Unicode, String, Integer, Integer, Unicode, String,
        Array(Products), Integer, Integer, String, String, String, _returns=String)
    def NewOrder(username, password, vendorName, registerFirstName, registerLastName, registerCellNumber,
        stateCode, cityCode, registerAddress, registerPostalCode, products, serviceType, payType, guaranteeProduct,
        orderDate, orderTime):
        if not username:
            print('Missed Username Field!')
            return 4
        if not password:
            print('Missed Password Field!')
            return 3
        user_result = cursor.api_users.find_one({"username": username})
        if user_result:
            if sha256_crypt.verify(password, user_result['password']):
                if not serviceType:
                    return 0
                if not payType:
                    return 0
                if not vendorName:
                    return 0
                if not registerFirstName:
                    return 0
                if not registerLastName:
                    return 0
                if not registerCellNumber:
                    return 0
                if not stateCode:
                    return 0
                if not cityCode:
                    return 0
                if not registerAddress:
                    return 0
                if not registerPostalCode:
                    registerPostalCode = ""
                if not orderDate:
                    orderDate = ""
                if not orderTime:
                    orderTime = ""
                p_list = []
                price = 0
                count = 0
                weight = 0
                discount = 0
                for i in range(len(products)):
                    p_dict = {}
                    #print(vendorName)
                    if vendorName == u'سفارش موردی':
                        p_details = cursor.case_inventory.find_one({'productId': products[i].productId})
                    else:
                        p_details = cursor.vestano_inventory.find_one({'productId': products[i].productId})
                    #print('p_details: ', p_details)
                    if not p_details:
                        print('Error in enterance data!')
                        return 0
                    p_dict['productId'] = products[i].productId
                    p_dict['productName'] = p_details['productName']
                    p_dict['count'] = products[i].count
                    p_dict['price'] = products[i].price
                    p_dict['weight'] = p_details['weight']
                    p_dict['percentDiscount'] = products[i].percentDiscount
                    p_dict['description'] = p_details['description']
                    price = price + products[i].price*products[i].count
                    count = count + products[i].count
                    weight = weight + p_details['weight']
                    discount = discount + products[i].percentDiscount

                    p_list.append(p_dict)

                if not utils.typeOfServicesToString(serviceType, payType):
                    return 0

                (sType, pType) = utils.typeOfServicesToString(serviceType, payType)

                order_id = str(random2.randint(1000000, 9999999))

                input_data = {
                'vendorName' : vendorName,
                'orderId' : order_id,
                'registerFirstName' : registerFirstName,
                'registerLastName' : registerLastName,
                'registerCellNumber' : registerCellNumber,
                'stateCode' : stateCode,
                'cityCode' : cityCode,
                'registerAddress' : registerAddress,
                'registerPostalCode' : registerPostalCode,
                'products' : p_list,
                'serviceType' : sType,
                'payType' : pType,
                'grntProduct' : guaranteeProduct,
                'orderDate': orderDate,
                'orderTime': orderTime,
                'record_date': jdatetime.datetime.now().strftime('%d / %m / %Y'),
                'record_time': jdatetime.datetime.now().strftime('%M : %H'),
                'parcelCode': '-',
                'datetime': jdatetime.datetime.today().strftime('%Y/%m/%d'),
                'status' : 80
                }

                if order_id :
                    cursor.temp_orders.insert_one(input_data)
                    for i in range(len(input_data['products'])):
                        if vendorName == u'سفارش موردی':
                            vinvent = cursor.case_inventory.find_one({'productId':input_data['products'][i]['productId']})
                        else:
                            vinvent = cursor.vestano_inventory.find_one({'productId':input_data['products'][i]['productId']})
                        vinvent['status']['80']+= input_data['products'][i]['count']
                        cursor.vestano_inventory.update_many(
                            {'productId': vinvent['productId']},
                            {'$set':{'status': vinvent['status']}}
                            )
                    cursor.today_orders.insert_one(input_data)
                    cursor.all_records.insert_one(input_data)
                    if guaranteeProduct:
                        cursor.guarantee_orders.insert_one(input_data)
                    return order_id
                else:
                    print('Error in enterance data!')
                    return 0
            else:
                print('The Password Does Not Match!')
                return 1
        else:
            print('Not Signed up Username!')
            return 2

    @spyne.srpc(String, String, _returns=Array(Codes))
    def GetStates(username, password):
        user_result = cursor.api_users.find_one({"username": username})
        if user_result:
            if sha256_crypt.verify(password, user_result['password']):
                states_list = []
                state_result = cursor.states.find()
                for rec in state_result:
                    states_list.append({'Name': rec['Name'], 'Code': rec['Code']})
                return states_list

    @spyne.srpc(String, String, Integer, _returns=Array(Codes))
    def GetCities(username, password, stateCode):
        user_result = cursor.api_users.find_one({"username": username})
        if user_result:
            if sha256_crypt.verify(password, user_result['password']):
                cities_list = []
                city_result = cursor.states.find_one({'Code': stateCode})
                for rec in city_result['Cities']:
                    cities_list.append({'Name': rec['Name'], 'Code': rec['Code']})
                return cities_list

    @spyne.srpc(String, String, String, _returns=Integer)
    def GetStatus(username, password, orderId):
        user_result = cursor.api_users.find_one({"username": username})
        if not username:
            return 104
        if not password:
            return 103
        if user_result:
            if sha256_crypt.verify(password, user_result['password']):
                if not orderId:
                    return 105
                result = cursor.orders.find_one({'orderId': orderId})
                if not result:
                    result = cursor.temp_orders.find_one({'orderId': orderId})
                    if not result:
                        result = cursor.canceled_orders.find_one({'orderId': orderId})
                        if not result:
                            return 106
                        return 83
                    return result['status']
                return result['status']
            else:
                return 101
        else:
            return 102

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'loged_in' not in session:
            flash('Please Sign in First!', 'danger')
            return redirect(url_for('logout'))

        if 'access-token' in request.headers['Cookie']:
            Token = request.headers['Cookie'].split(' ')
            token = Token[0][13:-1]

        if not token:
            flash('Token is missing!', 'danger')
            return redirect(request.referrer)

        try:
            data = jwt.decode(token, app.secret_key)
            utils.today_orders(cursor)
            session['temp_orders'] = cursor.temp_orders.estimated_document_count()
            session['canceled_orders'] = cursor.canceled_orders.estimated_document_count()
            session['today_orders'] = cursor.today_orders.estimated_document_count()
            session['pending_orders'] = cursor.pending_orders.estimated_document_count()
            session['guarantee_orders'] = cursor.guarantee_orders.estimated_document_count()
            session['ready_to_ship'] = cursor.ready_to_ship.estimated_document_count()
            session['all_orders'] = cursor.orders.estimated_document_count()
            if 'username' in session:
                if session['role'] == 'vendor_admin':
                    session['unread_tickets'] = cursor.tickets.find({'read': False}).count()
                    session['unread_inv_transfers'] = cursor.inventory_transfer.find({'read': False}).count()
                else:
                    session['unread_tickets'] = cursor.tickets.find({'sender_reply': True}).count()
                    not_processed = cursor.inventory_transfer.find({'req_status': u'بررسی نشده'}).count()
                    edited = cursor.inventory_transfer.find({'req_status': u'ویرایش شده'}).count()
                    session['unread_inv_transfers'] = not_processed + edited
        except:
            return redirect(url_for('token_logout'))            

        result = cursor.users.find_one({"user_id": data['user_id']})
        if result:
            if 'username' not in session:
                username = result['username']
                session['username'] = username
                session['message'] = result['name']
                session['role'] = result['role']
                session['access'] = result['access']
                session['jdatetime'] = jdatetime.datetime.today().strftime('%d / %m / %Y')
                session['temp_orders'] = cursor.temp_orders.estimated_document_count()
                session['canceled_orders'] = cursor.canceled_orders.estimated_document_count()
                session['guarantee_orders'] = cursor.guarantee_orders.estimated_document_count()
                session['today_orders'] = cursor.today_orders.estimated_document_count()
                if session['role'] == 'vendor_admin':
                    session['unread_tickets'] = cursor.tickets.find({'read': False}).count()
                    session['unread_inv_transfers'] = cursor.inventory_transfer.find({'read': False}).count()
                else:
                    session['unread_tickets'] = cursor.tickets.find({'sender_reply': True}).count()
                    not_processed = cursor.inventory_transfer.find({'req_status': u'بررسی نشده'}).count()
                    edited = cursor.inventory_transfer.find({'req_status': u'ویرایش شده'}).count()
                    session['unread_inv_transfers'] = not_processed + edited

                flash(result['name'] + u' عزیز خوش آمدید', 'success-login')
        
        else:
            flash('Token is not valid!', 'danger')
            return redirect(request.referrer)

        return f(*args, **kwargs)
    return decorated

@app.route('/badrequest400')
def bad_request():
    return abort(403)
   
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))

    @after_this_request
    def add_header(response):
        response.headers['Set-Cookie'] = '%s=%s'%('access-token',token)
        response.headers.add('X-Access-Token', token)
        return response

    token = None
    session['temp_orders'] = cursor.temp_orders.estimated_document_count()
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        result = cursor.users.find_one({"username": username})

        if result:
            if sha256_crypt.verify(password, result['password']):

                #if recaptcha.verify():
                
                #r = requests.post('https://www.google.com/recaptcha/api/siteverify', 
                    #data = {
                    #'secret' : '6Lca0qsUAAAAAJP-OpE0-WLpaxV09r4VzPvA3ycd',
                    #'response' : request.form['g-recaptcha-response']
                    #})

                #google_response = json.loads(r.text)
                #print('JSON: ', google_response)

                #if google_response['success']:
                    #print('SUCCESS')

                session['loged_in'] = True
                TOKEN = jwt.encode({'user_id':result['user_id'],
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60)},
                    app.secret_key)
                token = TOKEN.decode('UTF-8')
                session['role'] = result['role']
                if (session['role'] == 'office') or (session['role'] == 'admin'):
                    return redirect(url_for('temp_orders'))
                elif (session['role'] == 'vendor_admin'):
                    return redirect(url_for('today_orders'))
            #else:
                #flash(u'معتبر نیست!', 'danger')
            else:
                flash(u'کلمه عبور مطابقت ندارد', 'danger')
        else:
            flash(u'نام کاربری ثبت نشده است. لطفا  ابتدا ثبت نام کنید', 'error')

    return render_template('login.html')

@app.route('/', methods=['GET'])
def home():

    return render_template('home.html')

@app.route('/user-pannel/orderList', methods=['GET'])
@token_required
def temp_orders():
    if ('processList' or 'caseProcessList') not in session['access']:
        flash(u'شما مجوز لازم برای ورود به این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    session['temp_orders'] = cursor.temp_orders.estimated_document_count()
    session['canceled_orders'] = cursor.canceled_orders.estimated_document_count()
    session['today_orders'] = cursor.today_orders.estimated_document_count()
    session['guarantee_orders'] = cursor.guarantee_orders.estimated_document_count()
    session['ready_to_ship'] = cursor.ready_to_ship.estimated_document_count()
    session['all_orders'] = cursor.orders.estimated_document_count()

    return render_template('user_pannel.html',
        item='orderList',
        inventory = utils.inventory(cursor),
        temp_orders = utils.temp_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/confirm-order/<code>', methods=['GET'])
@token_required
def confirm_orders(code):
    if ('processList' or 'caseProcessList') not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    result = cursor.temp_orders.find_one({"orderId": code})
    if result:
        (sType, pType) = utils.typeOfServicesToCode(result['serviceType'], result['payType'])
        new_rec = copy.deepcopy(result)
        price = 0
        count = 0
        weight = 0
        discount = 0
        old_productId = []
        index = []
        if result['products'][0]['count'] > 1:
            new_list = copy.deepcopy(result['products'][0])
            new_count = new_list['count'] - 1
            result['products'][0]['count'] = 1
            result['products'].append(new_list)
            result['products'][-1]['count'] = new_count

        for i in range(len(result['products'])):
            if result['vendorName'] == u'سفارش موردی':
                inv = cursor.case_inventory.find_one({'productId':result['products'][i]['productId']})
            else:
                inv = cursor.vestano_inventory.find_one({'productId':result['products'][i]['productId']})
                #check if product price + vestano post wage is equal to inventory price or not?
                #if not a new product should be define.
                if ((result['products'][i]['price']+config.defaultWageForDefineStuff) != inv['price']) or (result['products'][i]['weight'] != inv['weight']) or (len(result['products'])>1):
                    record = {}
                    record['productName'] = inv['productName']
                    if i > 0:
                        record['price'] = result['products'][i]['price']
                    else:
                        #if result['products'][i]['count'] > 1:
                        record['price'] = result['products'][i]['price'] + config.defaultWageForDefineStuff
                    record['weight'] = result['products'][i]['weight']
                    record['count'] = result['products'][i]['count']
                    record['percentDiscount'] = result['products'][i]['percentDiscount']
                    record['description'] = inv['percentDiscount']
                    old_productId.append(result['products'][i]['productId'])
                    index.append(i)
                    new_productId = str(utils.AddStuff(record))
                    result['products'][i]['productId'] = new_productId
                else:
                    old_productId.append("")
                    index.append("")

            if (inv['count'] - result['products'][i]['count']) < 0:
                flash(u'موجودی انبار کافی نیست!', 'error')
                return redirect(request.referrer)
            price = price + result['products'][i]['price']*result['products'][i]['count']
            count = count + result['products'][i]['count']
            weight = weight + result['products'][i]['weight']
            discount = discount + result['products'][i]['percentDiscount']

        order = {
        'cityCode': result['cityCode'],
        'price': price,
        'weight': weight,
        'count': count,
        'serviceType': sType,
        'payType': pType,
        'description': '',
        'percentDiscount': discount,
        'firstName': result['registerFirstName'],
        'lastName': result['registerLastName'],
        'address': result['registerAddress'],
        'phoneNumber': '',
        'cellNumber': result['registerCellNumber'],
        'postalCode': result['registerPostalCode'],
        'products': result['products']
        }

        try:
            soap_result = utils.SoapClient(order)
            #print('errorcode: ', soap_result['ErrorCode'])
            #soap_result = {'ErrorCode' :0, 'ParcelCode': '21868000011931436408', 'PostDeliveryPrice':50000, 'VatTax':9000}
            if soap_result['ErrorCode'] == -10:
                flash(u'پاسخی از گیت وی دریافت نشد!', 'error')
                return redirect(request.referrer)

            if soap_result['ErrorCode'] == -6:
                postal_code_db = cursor.postal_codes.find_one({'Code': result['stateCode']})
                print("postal_code_db['Code']: ", postal_code_db['Code'])
                postalCode_flag = 1
                for i in range (len(postal_code_db['postalCodes'])):
                    if result['cityCode'] == postal_code_db['postalCodes'][i]['Code']:
                        order['postalCode'] = postal_code_db['postalCodes'][i]['postalCode']
                        new_rec['registerPostalCode'] = postal_code_db['postalCodes'][i]['postalCode']
                        postalCode_flag = 0
                        break
                if postalCode_flag:
                    order['postalCode'] = postal_code_db['refPostalCode']
                    new_rec['registerPostalCode'] = postal_code_db['refPostalCode']

                soap_result = utils.SoapClient(order)

                if soap_result['ErrorCode'] == -10:
                    flash(u'پاسخی از گیت وی دریافت نشد!', 'error')
                    return redirect(request.referrer)


            
            if not soap_result['ErrorCode']:

                new_rec['record_datetime'] = jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')
                new_rec['parcelCode'] = soap_result['ParcelCode']
                new_rec['username'] = session['username']

                #utils.ReadyToShip(soap_result['ParcelCode'])
                #new_rec['status'] = utils.GetStatus_one(cursor, soap_result['ParcelCode'])
                new_rec['status'] = 0
                new_rec['status_updated'] = False

                costs = {
                'price': price,
                'PostDeliveryPrice': soap_result['PostDeliveryPrice'],
                'VatTax': soap_result['VatTax'],
                'registerCost': config.registerCost,
                'wage': config.wage
                }

                new_rec['costs'] = costs

                cursor.orders.insert_one(new_rec)
                cursor.ready_to_ship.insert_one(new_rec)
                new_rec['last update'] = datetime.datetime.now()
                cursor.status.insert_one(new_rec)
                cursor.temp_orders.remove({'orderId': code})
                cursor.today_orders.remove({'orderId': code})
                cursor.today_orders.insert_one(new_rec)
                if 'grntProduct' in new_rec.keys():
                    if new_rec['grntProduct']:
                        cursor.guarantee_orders.remove({'orderId': code})
                        cursor.guarantee_orders.insert_one(new_rec)

                #update status in vestano_inventory
                for i in range(len(new_rec['products'])):
                    if new_rec['vendorName'] == u'سفارش موردی':
                        vinvent = cursor.case_inventory.find_one({'productId':new_rec['products'][i]['productId']})
                        vinvent['status'][str(new_rec['status'])]+= new_rec['products'][i]['count']
                        vinvent['status']['80']-= new_rec['products'][i]['count']
                        cursor.case_inventory.update_many(
                            {'productId': vinvent['productId']},
                            {'$set':{'status': vinvent['status']}}
                            )
                    else:
                        vinvent = cursor.vestano_inventory.find_one({'productId':new_rec['products'][i]['productId']})
                        vinvent['status'][str(new_rec['status'])]+= new_rec['products'][i]['count']
                        vinvent['status']['80']-= new_rec['products'][i]['count']
                        cursor.vestano_inventory.update_many(
                            {'productId': vinvent['productId']},
                            {'$set':{'status': vinvent['status']}}
                            )

                if new_rec['vendorName'] == u'سفارش موردی':
                    case_result = cursor.case_orders.find_one({'orderId': new_rec['orderId']})
                    state_result = cursor.states.find_one({'Code': new_rec['stateCode']})
                    for c in state_result['Cities']:
                        if c['Code'] == new_rec['cityCode']:
                            city = c['Name']
                            break

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

                    pdfkit.from_string(render_template('includes/_caseOrderPdf.html',
                        datetime = jdatetime.datetime.now().strftime('%H:%M %Y/%m/%d'),
                        orderId = new_rec['orderId'],
                        parcelCode = new_rec['parcelCode'],
                        sender = case_result['senderFirstName']+' '+case_result['senderLastName'],
                        s_cellNumber = case_result['senderCellNumber'],
                        s_address = case_result['senderAddress'],
                        s_postalCode = case_result['senderPostalCode'],
                        receiver = case_result['receiverFirstName']+' '+case_result['receiverLastName'],
                        cellNumber = case_result['receiverCellNumber'],
                        destination = state_result['Name']+' / '+city+' / '+case_result['registerAddress'],
                        postalCode = new_rec['registerPostalCode'],
                        weight = weight,
                        sType = order['serviceType'],
                        serviceType = new_rec['serviceType'],
                        payType = new_rec['payType'],
                        packing = case_result['packing'],
                        carton = case_result['carton'],
                        gathering = case_result['gathering'],
                        without_ck = case_result['without_ck'],
                        deliveryPrice = soap_result['PostDeliveryPrice'] + vestano_wage,
                        VatTax = soap_result['VatTax']
                        ), 'static/pdf/caseOrders/orderId_'+new_rec['orderId']+'.pdf')

                utils.removeFromInventory(cursor, new_rec['orderId'])

                flash(u'سفارش تایید و آماده ارسال شد!', 'success')
                return redirect(request.referrer)
            else:
                #print('error code: ', soap_result['ErrorCode'])
                flash(soap_result['Description'], 'error')
                return redirect(request.referrer)

        except:
            flash(u'پاسخی از گیت وی دریافت نشد!', 'error')
            return redirect(request.referrer)
    else:
        flash(u'خطایی رخ داده است! (شناسه سفارش)', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='orderList')

@app.route('/user-pannel/ready-to-ship', methods=['GET'])
@token_required
def readyToShip_orders():
    if 'rtsOrders' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='readyToShip',
        inventory = utils.inventory(cursor),
        readyToShip_orders = utils.readyToShip_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/today-orders', methods=['GET'])
@token_required
def today_orders():
    if 'todayOrders' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='todayOrders',
        inventory = utils.inventory(cursor),
        today_orders = utils.today_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/guarantee-orders', methods=['GET'])
@token_required
def guarantee_orders():
    if 'grntOrders' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='grntOrders',
        inventory = utils.inventory(cursor),
        guarantee_orders = utils.guarantee_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/pending-orders', methods=['GET'])
@token_required
def pending_orders():
    if 'pndOrders' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='pendingOrders',
        inventory = utils.inventory(cursor),
        pending_orders = utils.pending_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/all-orders', methods=['GET'])
@token_required
def all_orders():
    if 'allOrders' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='allOrders',
        inventory = utils.inventory(cursor),
        all_orders = utils.all_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/finish-process/<orderId>', methods=['GET'])
@token_required
def finish_process(orderId):
    if ('processList' or 'caseProcessList') not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    new_rec = cursor.ready_to_ship.find_one({'orderId': orderId})
    this_status = utils.GetStatus_one(cursor, new_rec['parcelCode'])
    if this_status != 2:
        cursor.ready_to_ship.remove({'orderId': orderId})
        flash(u'فرآیند سفارش با موفقیت به پایان رسید!', 'success')
        return redirect(request.referrer)
    cursor.orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 81}}
        )
    cursor.status.update_many(
        {'orderId': orderId},
        {'$set':{'status': 81}}
        )
    cursor.today_orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 81}}
        )
    cursor.guarantee_orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 81}}
        )
    for i in range(len(new_rec['products'])):
        if new_rec['vendorName'] == u'سفارش موردی':
            vinvent = cursor.case_inventory.find_one({'productId':new_rec['products'][i]['productId']})
            vinvent['status'][str(new_rec['status'])] -= new_rec['products'][i]['count']
            vinvent['status']['81'] += new_rec['products'][i]['count']
            cursor.case_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
        else:
            vinvent = cursor.vestano_inventory.find_one({'productId':new_rec['products'][i]['productId']})
            vinvent['status'][str(new_rec['status'])] -= new_rec['products'][i]['count']
            vinvent['status']['81'] += new_rec['products'][i]['count']
            cursor.vestano_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
    cursor.ready_to_ship.remove({'orderId': orderId})
    flash(u'فرآیند سفارش با موفقیت به پایان رسید!', 'success')
    return redirect(request.referrer)

@app.route('/user-pannel/canceled-orders', methods=['GET'])
@token_required
def canceled_orders():
    if 'cnlOrders' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='cnlOrders',
        inventory = utils.inventory(cursor),
        canceled_orders = utils.canceled_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/cancel-order/<orderId>', methods=['GET'])
@token_required
def cancel_orders(orderId):
    if ('processList' or 'caseProcessList') not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    rec = cursor.temp_orders.find_one({'orderId': orderId})
    cursor.today_orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 83}}
        )
    cursor.guarantee_orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 83}}
        )
    cursor.canceled_orders.insert_one(rec)
    cursor.temp_orders.remove({'orderId': orderId})
    flash(u'سفارش مورد نظر لغو شد!', 'danger')
    for i in range(len(rec['products'])):
        if rec['vendorName'] == u'سفارش موردی':
            if vinvent:
                vinvent = cursor.case_inventory.find_one({'productId':rec['products'][i]['productId']})
                vinvent['status']['80']-= rec['products'][i]['count']
                vinvent['status']['83']+= rec['products'][i]['count']
                cursor.case_inventory.update_many(
                    {'productId': vinvent['productId']},
                    {'$set':{'status': vinvent['status']}}
                    )
        else:
            vinvent = cursor.vestano_inventory.find_one({'productId':rec['products'][i]['productId']})
            if vinvent:
                vinvent['status']['80']-= rec['products'][i]['count']
                vinvent['status']['83']+= rec['products'][i]['count']
                cursor.vestano_inventory.update_many(
                    {'productId': vinvent['productId']},
                    {'$set':{'status': vinvent['status']}}
                    )
    return redirect(request.referrer)

@app.route('/pending-order/<orderId>', methods=['GET'])
@token_required
def pending_order(orderId):
    if ('processList' or 'caseProcessList') not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    rec = cursor.temp_orders.find_one({'orderId': orderId})
    rec['status'] = 82
    cursor.today_orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 82}}
        )
    cursor.guarantee_orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 82}}
        )
    cursor.pending_orders.insert_one(rec)
    for i in range(len(rec['products'])):
        if rec['vendorName'] == u'سفارش موردی':
            vinvent = cursor.case_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['80'] -= rec['products'][i]['count']
            vinvent['status']['82'] += rec['products'][i]['count']
            cursor.case_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
        else:
            vinvent = cursor.vestano_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['80'] -= rec['products'][i]['count']
            vinvent['status']['82'] += rec['products'][i]['count']
            cursor.vestano_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
    cursor.temp_orders.remove({'orderId': orderId})
    flash(u'سفارش در انتظار کالا قرار گرفت.', 'danger')
    return redirect(request.referrer)

@app.route('/delete-order/<orderId>', methods=['GET'])
@token_required
def delete_order(orderId):
    if ('processList' or 'caseProcessList') not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    rec = cursor.canceled_orders.find_one({'orderId': orderId})
    for i in range(len(rec['products'])):
        if rec['vendorName'] == u'سفارش موردی':
            vinvent = cursor.case_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['83'] -= rec['products'][i]['count']
            cursor.case_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
        else:
            vinvent = cursor.vestano_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['83'] -= rec['products'][i]['count']
            cursor.vestano_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
    cursor.canceled_orders.remove({'orderId': orderId})
    cursor.today_orders.remove({'orderId': orderId})
    cursor.guarantee_orders.remove({'orderId': orderId})
    cursor.deleted_orders.insert_one(rec)
    flash(u'سفارش حذف شد!', 'danger')
    return redirect(request.referrer)

@app.route('/return-order/<orderId>', methods=['GET'])
@token_required
def return_order(orderId):
    if ('processList' or 'caseProcessList') not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    rec = cursor.pending_orders.find_one({'orderId': orderId})
    cursor.today_orders.remove({'orderId': orderId})
    cursor.guarantee_orders.remove({'orderId': orderId})
    rec['status'] = 80
    rec['record_date'] = jdatetime.datetime.now().strftime('%d / %m / %Y')
    rec['record_time'] = jdatetime.datetime.now().strftime('%M : %H')
    
    cursor.temp_orders.insert_one(rec)
    for i in range(len(rec['products'])):
        if rec['vendorName'] == u'سفارش موردی':
            vinvent = cursor.case_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['82'] -= rec['products'][i]['count']
            vinvent['status']['80'] += rec['products'][i]['count']
            cursor.case_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
        else:
            vinvent = cursor.vestano_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['82'] -= rec['products'][i]['count']
            vinvent['status']['80'] += rec['products'][i]['count']
            cursor.vestano_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
    cursor.pending_orders.remove({'orderId': orderId})
    flash(u'سفارش به صف پردازش برگشت!', 'success')
    return redirect(request.referrer)

@app.route('/edit-order/<orderId>', methods=['GET', 'POST'])
@token_required
def edit_orders(orderId):
    if ('Ordering' or 'caseOrdering') not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    edit_result = cursor.canceled_orders.find_one({'orderId': orderId})
    state_result = cursor.states.find_one({'Code': edit_result['stateCode']})
    stateName = state_result['Name']
    for rec in state_result['Cities']:
        if edit_result['cityCode'] == rec['Code']:
            cityName = rec['Name']
            break

    (serviceType, payType) = utils.typeOfServicesToCode(edit_result['serviceType'], edit_result['payType'])

    if request.method == 'POST':
        temp_order_products = []
        if edit_result['vendorName'] == u'سفارش موردی':
            for i in range (1, 100):
                if request.form.get('product_'+str(i)):
                    Edit_result = utils.editStuff(
                            request.form.get('product_'+str(i)),
                            int(request.form.get('weight_'+str(i))),
                            int(request.form.get('price_'+str(i)))
                            )
                    cursor.case_inventory.update_many(
                        {'productId': request.form.get('product_'+str(i))},
                        {'$set':{
                        'price': int(request.form.get('price_'+str(i))),
                        'weight': int(request.form.get('weight_'+str(i))),
                        }
                        }
                        )
                    temp_order_product = {}
                    temp_order_product['productId'] = request.form.get('product_'+str(i))
                    temp_order_product['count'] = int(request.form.get('count_'+str(i)))
                    temp_order_product['price'] = int(request.form.get('price_'+str(i)))
                    temp_order_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))

                    vinvent = cursor.case_inventory.find_one({'productId':request.form.get('product_'+str(i))})
                    vinvent['status']['83'] -= int(request.form.get('count_'+str(i)))
                    cursor.case_inventory.update_many(
                        {'productId': vinvent['productId']},
                        {'$set':{'status': vinvent['status']}}
                        )

                    temp_order_products.append(temp_order_product)
        else:
            for i in range (1, 100):
                if request.form.get('product_'+str(i)):
                    temp_order_product = {}
                    temp_order_product['productId'] = request.form.get('product_'+str(i))
                    temp_order_product['count'] = int(request.form.get('count_'+str(i)))
                    temp_order_product['price'] = int(request.form.get('price_'+str(i)))
                    temp_order_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))

                    vinvent = cursor.vestano_inventory.find_one({'productId':request.form.get('product_'+str(i))})
                    vinvent['status']['83'] -= int(request.form.get('count_'+str(i)))
                    cursor.vestano_inventory.update_many(
                        {'productId': vinvent['productId']},
                        {'$set':{'status': vinvent['status']}}
                        )

                    temp_order_products.append(temp_order_product)

        if len(request.form.getlist('free')):
            (sType, pType) = utils.typeOfServicesToString(int(request.form.get('serviceType')), 88)
            pTypeCode = 88
        else:
            (sType, pType) = utils.typeOfServicesToString(int(request.form.get('serviceType')),
                int(request.form.get('payType')))
            pTypeCode = int(request.form.get('payType'))

        if edit_result['vendorName'] == u'سفارش موردی':
            temp_order = {
            'vendorName' : u'سفارش موردی',
            'registerFirstName' : request.form.get('r_first_name'),
            'registerLastName' : request.form.get('r_last_name'),
            'registerCellNumber' : request.form.get('r_cell_number'),
            'stateCode' : int(request.form.get('stateCode')),
            'cityCode' : int(request.form.get('cityCode')),
            'registerAddress' : request.form.get('address'),
            'registerPostalCode' : request.form.get('postal_code'),
            'products' : temp_order_products,
            'serviceType' : int(request.form.get('serviceType')),
            'payType' : pTypeCode,
            'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
            'orderTime': jdatetime.datetime.now().strftime('%M : %H')
            }

            new_orderId = utils.test_temp_order(temp_order)
            flash(u'ثبت شد!', 'success')

            cursor.case_orders.update_many(
                {'orderId': orderId},
                {'$set':{
                'vendorName' : u'سفارش موردی',
                'senderFirstName' : request.form.get('s_first_name'),
                'senderLastName' : request.form.get('s_last_name'),
                'senderCellNumber' : request.form.get('s_cell_number'),
                'senderAddress' : request.form.get('s_address'),
                'senderPostalCode' : request.form.get('s_postal_code'),
                'receiverFirstName' : request.form.get('r_first_name'),
                'receiverLastName' : request.form.get('r_last_name'),
                'receiverCellNumber' : request.form.get('r_cell_number'),
                'stateCode' : int(request.form.get('stateCode')),
                'cityCode' : int(request.form.get('cityCode')),
                'registerAddress' : request.form.get('address'),
                'registerPostalCode' : request.form.get('postal_code'),
                'products' : temp_order_products,
                'serviceType' : int(request.form.get('serviceType')),
                'payType' : pTypeCode,
                'username' : session['username'],
                'packing': int(request.form.get('packing')),
                'carton': int(request.form.get('carton')),
                'gathering': int(request.form.get('gathering')),
                'orderId' : new_orderId,
                'without_ck': request.form.getlist('without_ck'),
                'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
                'orderTime': jdatetime.datetime.now().strftime('%M : %H')
                }
                }
                )

        else:
            if request.form.getlist('grnt'):
                grnt = request.form.getlist('grnt')[0]
            else:
                grnt = ''

            temp_order = {
            'vendorName' : u'روژیاپ',
            'registerFirstName' : request.form.get('first_name'),
            'registerLastName' : request.form.get('last_name'),
            'registerCellNumber' : request.form.get('cell_number'),
            'stateCode' : int(request.form.get('stateCode')),
            'cityCode' : int(request.form.get('cityCode')),
            'registerAddress' : request.form.get('address'),
            'registerPostalCode' : request.form.get('postal_code'),
            'guaranteeProduct' : grnt,
            'products' : temp_order_products,
            'serviceType' : int(request.form.get('serviceType')),
            'payType' : pTypeCode,
            'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
            'orderTime': jdatetime.datetime.now().strftime('%M : %H')
            }
            print(utils.test_temp_order(temp_order))
            flash(u'ثبت شد!', 'success')

        

        cursor.canceled_orders.remove({'orderId': orderId})
        cursor.today_orders.remove({'orderId': orderId})
        cursor.guarantee_orders.remove({'orderId': orderId})
        #return redirect(request.referrer)


    if edit_result['vendorName'] == u'سفارش موردی':
        case_data = cursor.case_orders.find_one({'orderId': orderId})
        return render_template('includes/_editCaseOrders.html',
            inventory = utils.case_inventory(cursor),
            states = utils.states(cursor),
            data = edit_result,
            case_data = case_data,
            stateName = stateName,
            cityName = cityName,
            sType=serviceType,
            pType=payType
            )
    else:
        return render_template('includes/_editOrder.html',
            inventory = utils.inventory(cursor),
            states = utils.states(cursor),
            data = edit_result,
            stateName = stateName,
            cityName = cityName,
            sType=serviceType,
            pType=payType
            )

@app.route('/user-pannel/<item>', methods=['GET', 'POST'])
@token_required
def ordering(item):
    if 'Ordering' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    if 'username' in session:
        ordered_products = []
        username = session['username']
        if item == 'ordering':
            if request.method == 'POST':
                temp_order_products = []
                for i in range (1, 100):
                    if request.form.get('product_'+str(i)):
                        temp_order_product = {}
                        temp_order_product['productId'] = request.form.get('product_'+str(i))
                        temp_order_product['count'] = int(request.form.get('count_'+str(i)))
                        temp_order_product['price'] = int(request.form.get('price_'+str(i)))
                        temp_order_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))

                        temp_order_products.append(temp_order_product)

                if len(request.form.getlist('free')):
                    (sType, pType) = utils.typeOfServicesToString(int(request.form.get('serviceType')), 88)
                    pTypeCode = 88
                else:
                    (sType, pType) = utils.typeOfServicesToString(int(request.form.get('serviceType')),
                        int(request.form.get('payType')))
                    pTypeCode = int(request.form.get('payType'))

                if request.form.getlist('grnt'):
                    grnt = request.form.getlist('grnt')[0]
                else:
                    grnt = ''

                temp_order = {
                'vendorName' : u'روژیاپ',
                'registerFirstName' : request.form.get('first_name'),
                'registerLastName' : request.form.get('last_name'),
                'registerCellNumber' : request.form.get('cell_number'),
                'stateCode' : int(request.form.get('stateCode')),
                'cityCode' : int(request.form.get('cityCode')),
                'registerAddress' : request.form.get('address'),
                'registerPostalCode' : request.form.get('postal_code'),
                'guaranteeProduct' : grnt,
                'products' : temp_order_products,
                'serviceType' : int(request.form.get('serviceType')),
                'payType' : pTypeCode,
                'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
                'orderTime': jdatetime.datetime.now().strftime('%M : %H')
                }

                flash(u'ثبت شد!', 'success')

                print(utils.test_temp_order(temp_order))

                return redirect(url_for('ordering', item='ordering'))
    else:
        flash(u'لطفا ابتدا وارد شوید', 'error')
        return redirect(request.referrer)
    return render_template('user_pannel.html',
        item=item,
        inventory = utils.inventory(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/case-orders', methods=['GET', 'POST'])
@token_required
def case_orders():
    if 'caseOrdering' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    if 'username' in session:
        ordered_products = []
        username = session['username']
        if request.method == 'POST':

            temp_order_products = []
            for i in range (1, 100):
                if request.form.get('product_'+str(i)):
                    edit_result = utils.editStuff(
                        request.form.get('product_'+str(i)),
                        int(request.form.get('weight_'+str(i))),
                        int(request.form.get('price_'+str(i)))
                        )
                    cursor.case_inventory.update_many(
                        {'productId': request.form.get('product_'+str(i))},
                        {'$set':{
                        'price': int(request.form.get('price_'+str(i))),
                        'weight': int(request.form.get('weight_'+str(i))),
                        }
                        }
                        )
                    temp_order_product = {}
                    temp_order_product['productId'] = request.form.get('product_'+str(i))
                    temp_order_product['count'] = int(request.form.get('count_'+str(i)))
                    temp_order_product['price'] = int(request.form.get('price_'+str(i)))
                    temp_order_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))

                    temp_order_products.append(temp_order_product)

            if len(request.form.getlist('free')):
                (sType, pType) = utils.typeOfServicesToString(int(request.form.get('serviceType')), 88)
                pTypeCode = 88
            else:
                (sType, pType) = utils.typeOfServicesToString(int(request.form.get('serviceType')),
                    int(request.form.get('payType')))
                pTypeCode = int(request.form.get('payType'))

            temp_order = {
            'vendorName' : u'سفارش موردی',
            'registerFirstName' : request.form.get('r_first_name'),
            'registerLastName' : request.form.get('r_last_name'),
            'registerCellNumber' : request.form.get('r_cell_number'),
            'stateCode' : int(request.form.get('stateCode')),
            'cityCode' : int(request.form.get('cityCode')),
            'registerAddress' : request.form.get('address'),
            'registerPostalCode' : request.form.get('postal_code'),
            'products' : temp_order_products,
            'serviceType' : int(request.form.get('serviceType')),
            'payType' : pTypeCode,
            'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
            'orderTime': jdatetime.datetime.now().strftime('%M : %H')
            }

            orderId = utils.test_temp_order(temp_order)

            case_order = {
            'vendorName' : u'سفارش موردی',
            'senderFirstName' : request.form.get('s_first_name'),
            'senderLastName' : request.form.get('s_last_name'),
            'senderCellNumber' : request.form.get('s_cell_number'),
            'senderAddress' : request.form.get('s_address'),
            'senderPostalCode' : request.form.get('s_postal_code'),
            'receiverFirstName' : request.form.get('r_first_name'),
            'receiverLastName' : request.form.get('r_last_name'),
            'receiverCellNumber' : request.form.get('r_cell_number'),
            'stateCode' : int(request.form.get('stateCode')),
            'cityCode' : int(request.form.get('cityCode')),
            'registerAddress' : request.form.get('address'),
            'registerPostalCode' : request.form.get('postal_code'),
            'products' : temp_order_products,
            'serviceType' : int(request.form.get('serviceType')),
            'payType' : pTypeCode,
            'username' : session['username'],
            'packing': int(request.form.get('packing')),
            'carton': int(request.form.get('carton')),
            'gathering': int(request.form.get('gathering')),
            'orderId' : orderId,
            'without_ck': request.form.getlist('without_ck'),
            'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
            'orderTime': jdatetime.datetime.now().strftime('%M : %H')
            }

            cursor.case_orders.insert_one(case_order)

            flash(u'ثبت شد!', 'success')

            return redirect(url_for('case_orders'))
    else:
        flash(u'لطفا ابتدا وارد شوید', 'error')
        return redirect(request.referrer)
    return render_template('user_pannel.html',
        item='case-orders',
        inventory = utils.case_inventory(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/inventory-management/<sub_item>', methods=['GET', 'POST'])
@token_required
def inventory_management(sub_item):
    productId_result = ""
    if request.method == 'POST':
        if sub_item == 'case':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productName'] = request.form.get('productName')
            record['price'] = int(request.form.get('price'))
            record['weight'] = int(request.form.get('weight'))
            record['count'] = int(request.form.get('count'))
            if request.form.get('percentDiscount'):
                record['percentDiscount'] = int(request.form.get('percentDiscount'))
            else:
                record['percentDiscount'] = 0
            record['description'] = request.form.get('description')
            record['vendor'] = request.form.get('vendor')
            record['productId'] = str(utils.AddStuff(record))
            record['status'] = utils.add_empty_status()
            record['record'] = []
            first_add = {
            'action': 'add',
            'datetime' : record['datetime'],
            'count': int(request.form.get('count')),
            'exist_count': int(request.form.get('count')),
            'person': session['username']
            }
            record['record'].append(first_add)

            cursor.case_inventory.insert_one(record)
            flash(u'محصول جدید ثبت شد. شناسه کالا: ' + str(record['productId']), 'success')

        elif sub_item == 'cEdit':
            cursor.case_inventory.update_many(
                {'productId': request.form.get('product')},
                {'$set':{
                'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'productName': request.form.get('productName'),
                'price': int(request.form.get('price')),
                'percentDiscount': int(request.form.get('percentDiscount')),
                'weight': int(request.form.get('weight')),
                'count': int(request.form.get('exist_count')),
                'vendor': u'سفارش موردی'
                }
                }
                )
            edit_result = utils.editStuff(
                request.form.get('product'),
                int(request.form.get('weight')),
                int(request.form.get('price'))
                )
            flash(u'ثبت شد!', 'success')

        elif sub_item == 'new':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productName'] = request.form.get('productName')
            record['price'] = int(request.form.get('price')) + config.defaultWageForDefineStuff
            record['weight'] = int(request.form.get('weight'))
            record['count'] = int(request.form.get('count'))
            if request.form.get('percentDiscount'):
                record['percentDiscount'] = int(request.form.get('percentDiscount'))
            else:
                record['percentDiscount'] = 0
            record['description'] = request.form.get('description')
            record['vendor'] = request.form.get('vendor')
            record['productId'] = str(utils.AddStuff(record))
            record['status'] = utils.add_empty_status()
            record['record'] = []
            first_add = {
            'action': 'add',
            'datetime' : record['datetime'],
            'count': int(request.form.get('count')),
            'exist_count': int(request.form.get('count')),
            'person': session['username']
            }
            record['record'].append(first_add)

            cursor.vestano_inventory.insert_one(record)
            flash(u'محصول جدید ثبت شد. شناسه کالا: ' + str(record['productId']), 'success')

        elif sub_item == 'inc':
            result = cursor.vestano_inventory.find_one({'productId': request.form.get('product')})
            if request.form.getlist('returned'):
                add = {
                'action': 'returned',
                'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'count': int(request.form.get('count')),
                'exist_count': result['count'] + int(request.form.get('count')),
                'person': session['username']
                }
            else:
                add = {
                'action': 'add',
                'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'count': int(request.form.get('count')),
                'exist_count': result['count'] + int(request.form.get('count')),
                'person': session['username']
                }
            result['record'].append(add)
            cursor.vestano_inventory.update_many(
                {'productId': request.form.get('product')},
                {'$set':{
                'datetime': add['datetime'],
                'count': result['count'] + int(request.form.get('count')),
                'record': result['record']
                }
                }
                )
            flash(u'ثبت شد!', 'success')

        elif sub_item == 'edit':
            cursor.vestano_inventory.update_many(
                {'productId': request.form.get('product')},
                {'$set':{
                'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'productName': request.form.get('productName'),
                'price': int(request.form.get('price')) + config.defaultWageForDefineStuff,
                'percentDiscount': int(request.form.get('percentDiscount')),
                'weight': int(request.form.get('weight')),
                'vendor': request.form.get('vendor')
                }
                }
                )
            edit_result = utils.editStuff(
                request.form.get('product'),
                int(request.form.get('weight')),
                int(request.form.get('price')) + config.defaultWageForDefineStuff
                )
            flash(u'ثبت شد!', 'success')

        elif sub_item == 'pack':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productName'] = request.form.get('packName')
            record['price'] = int(request.form.get('price')) + config.defaultWageForDefineStuff
            #record['weight'] = int(request.form.get('weight'))
            record['count'] = int(request.form.get('count'))
            record['weight'] = int(request.form.get('weight'))
            if request.form.get('percentDiscount'):
                record['percentDiscount'] = int(request.form.get('percentDiscount'))
            else:
                record['percentDiscount'] = 0
            record['description'] = request.form.get('description')
            record['vendor'] = request.form.get('vendor')

            pack_products = []
            weight = 0
            for i in range (1, 100):
                if request.form.get('product_'+str(i)):
                    ppr = cursor.vestano_inventory.find_one({'productId':request.form.get('product_'+str(i))})
                    pack_product = {}
                    pack_product['productId'] = request.form.get('product_'+str(i))
                    pack_product['productName'] = ppr['productName']
                    pack_product['count'] = int(request.form.get('count_'+str(i)))
                    pack_product['weight'] = int(request.form.get('weight_'+str(i)))
                    pack_product['price'] = int(request.form.get('price_'+str(i)))
                    pack_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))
                    weight += int(request.form.get('weight_'+str(i)))
                    pack_products.append(pack_product)

            record['record'] = []
            first_add = {
            'action': 'add',
            'datetime' : record['datetime'],
            'count': int(request.form.get('count')),
            'exist_count': int(request.form.get('count')),
            'person': session['username']
            }
            record['record'].append(first_add)

            record['pack_products'] = pack_products
            record['productId'] = str(utils.AddStuff(record))
            record['status'] = utils.add_empty_status()
            cursor.vestano_inventory.insert_one(record)
            flash(u'بسته جدید ایجاد شد. شناسه کالا: ' + str(record['productId']), 'success')

        elif sub_item == 'release':
            result = cursor.vestano_inventory.find_one({'productId': request.form.get('product')})
            dec = {
            'action': 'release',
            'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
            'count': int(request.form.get('count')),
            'exist_count': result['count'] - int(request.form.get('count')),
            'person': session['username']
            }
            result['record'].append(dec)
            if int(request.form.get('count')) > result['count']:
                flash(u'تعداد مرجوعی از موجودی انبار بیشتر است!', 'danger')
                return redirect(request.referrer)
            cursor.vestano_inventory.update_many(
                {'productId': request.form.get('product')},
                {'$set':{
                'datetime': dec['datetime'],
                'count': result['count'] - int(request.form.get('count')),
                'record': result['record']
                }
                }
                )
            flash(u'ثبت شد!', 'success')

    return render_template('user_pannel.html',
        item='inventManagement',
        inventory = utils.inventory(cursor),
        for_edit_case_inventory = utils.for_edit_case_inventory(cursor),
        sub_item=sub_item,
        productId_result=productId_result
        )

@app.route('/user-pannel/inventory-transfer/<sub_item>', methods=['GET', 'POST'])
@token_required
def inventory_transfer(sub_item):
    if request.method == 'POST':
        if sub_item == 'newT':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productName'] = request.form.get('productName')
            record['price'] = int(request.form.get('price'))
            record['weight'] = int(request.form.get('weight'))
            record['count'] = int(request.form.get('count'))
            if request.form.get('percentDiscount'):
                record['percentDiscount'] = int(request.form.get('percentDiscount'))
            else:
                record['percentDiscount'] = 0
            record['description'] = request.form.get('description')
            record['vendor'] = request.form.get('vendor')
            record['shipment'] = request.form.get('shipment')
            record['shipment_date'] = request.form.get('shipment_date')
            record['username'] = session['username']
            record['request_type'] = 'new'
            record['req_status'] = u'بررسی نشده'
            record['number'] = 'VES-I-' + str(random2.randint(10000000, 99999999))
            record['read'] = False

            cursor.inventory_transfer.insert_one(record)
            flash(u'نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+record['number'], 'success')

        elif sub_item == 'incT':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            incT_res = cursor.vestano_inventory.find_one({'productId': request.form.get('product')})
            record['productId'] = request.form.get('product')
            record['count'] = int(request.form.get('count'))
            record['returned'] = request.form.getlist('returned')
            record['vendor'] = incT_res['vendor']
            record['shipment'] = request.form.get('shipment')
            record['shipment_date'] = request.form.get('shipment_date')
            record['username'] = session['username']
            record['request_type'] = 'inc'
            record['req_status'] = u'بررسی نشده'
            record['number'] = 'VES-I-' + str(random2.randint(10000000, 99999999))
            record['read'] = False

            cursor.inventory_transfer.insert_one(record)
            flash(u'نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+record['number'], 'success')

        elif sub_item == 'editT':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productId'] = request.form.get('product')
            record['productName'] = request.form.get('productName')
            record['price'] = int(request.form.get('price'))
            record['percentDiscount'] = int(request.form.get('percentDiscount'))
            record['weight'] = int(request.form.get('weight'))
            record['vendor'] = request.form.get('vendor')
            record['username'] = session['username']
            record['request_type'] = 'edit'
            record['req_status'] = u'بررسی نشده'
            record['number'] = 'VES-I-' + str(random2.randint(10000000, 99999999))
            record['read'] = False

            cursor.inventory_transfer.insert_one(record)
            flash(u'نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+record['number'], 'success')

        elif sub_item == 'packT':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productName'] = request.form.get('packName')
            record['price'] = int(request.form.get('price'))
            #record['weight'] = int(request.form.get('weight'))
            record['count'] = int(request.form.get('count'))
            record['weight'] = int(request.form.get('weight'))
            if request.form.get('percentDiscount'):
                record['percentDiscount'] = int(request.form.get('percentDiscount'))
            else:
                record['percentDiscount'] = 0
            record['description'] = request.form.get('description')
            record['vendor'] = request.form.get('vendor')

            pack_products = []
            weight = 0
            for i in range (1, 100):
                if request.form.get('product_'+str(i)):
                    ppr = cursor.vestano_inventory.find_one({'productId':request.form.get('product_'+str(i))})
                    pack_product = {}
                    pack_product['productId'] = request.form.get('product_'+str(i))
                    pack_product['productName'] = ppr['productName']
                    pack_product['count'] = int(request.form.get('count_'+str(i)))
                    pack_product['weight'] = int(request.form.get('weight_'+str(i)))
                    pack_product['price'] = int(request.form.get('price_'+str(i)))
                    pack_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))
                    weight += int(request.form.get('weight_'+str(i)))
                    pack_products.append(pack_product)

            record['pack_products'] = pack_products
            record['shipment'] = request.form.get('shipment')
            record['shipment_date'] = request.form.get('shipment_date')
            record['username'] = session['username']
            record['request_type'] = 'pack'
            record['req_status'] = u'بررسی نشده'
            record['number'] = 'VES-I-' + str(random2.randint(10000000, 99999999))
            record['read'] = False

            cursor.inventory_transfer.insert_one(record)
            flash(u'نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+record['number'], 'success')

        elif sub_item == 'releaseT':
            releaseT_res = cursor.vestano_inventory.find_one({'productId': request.form.get('product')})
            if int(request.form.get('count')) > releaseT_res['count']:
                flash(u'تعداد مرجوعی از موجودی انبار بیشتر است!', 'danger')
                return redirect(request.referrer)

            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productId'] = request.form.get('product')
            record['count'] = int(request.form.get('count'))
            record['vendor'] = releaseT_res['vendor']
            record['shipment'] = request.form.get('shipment')
            record['shipment_date'] = request.form.get('shipment_date')
            record['username'] = session['username']
            record['request_type'] = 'release'
            record['req_status'] = u'بررسی نشده'
            record['number'] = 'VES-I-' + str(random2.randint(10000000, 99999999))
            record['read'] = False

            cursor.inventory_transfer.insert_one(record)
            flash(u'نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+record['number'], 'success')

        elif sub_item == 'listT':
            pass

    return render_template('user_pannel.html',
        item='inventTransfer',
        inventory = utils.inventory(cursor),
        transfer_req = utils.transfer_req(cursor),
        sub_item=sub_item
        )

@app.route('/user-pannel/inventory-transfer-details/<number>', methods=['GET', 'POST'])
@token_required
def inventory_transfer_details(number):
    if session['role'] == 'vendor_admin':
        cursor.inventory_transfer.update_many(
            {'number': number},
            {'$set':{'read': True}})

    result = cursor.inventory_transfer.find_one({'number':number})
    sub_item = result['request_type']
    if request.method == 'POST':
        if result['req_status'] == u'تایید شد':
            flash(u'امکان ویرایش حواله پس از تایید آن وجود ندارد!', 'danger')
            return redirect(request.referrer)

        if sub_item == 'new':
            cursor.inventory_transfer.update_many(
                {'number': number},
                {'$set':{
                'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'productName': request.form.get('productName'),
                'price': int(request.form.get('price')),
                'weight': int(request.form.get('weight')),
                'count': int(request.form.get('count')),
                'percentDiscount': int(request.form.get('percentDiscount')),
                'description': request.form.get('description'),
                'vendor': request.form.get('vendor'),
                'shipment': request.form.get('shipment'),
                'shipment_date': request.form.get('shipment_date'),
                'req_status': u'ویرایش شده',
                'refuse_reason': '',
                'read': False
                }
                }
                )
            flash(u'ویرایش انجام شد. نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+number, 'success')

        elif sub_item == 'inc':
            cursor.inventory_transfer.update_many(
                {'number': number},
                {'$set':{
                'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'count': int(request.form.get('count')),
                'returned': request.form.getlist('returned'),
                'shipment': request.form.get('shipment'),
                'shipment_date': request.form.get('shipment_date'),
                'req_status': u'ویرایش شده',
                'refuse_reason': '',
                'read': False
                }
                }
                )
            flash(u'ویرایش انجام شد. نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+number, 'success')

        elif sub_item == 'edit':
            cursor.inventory_transfer.update_many(
                {'number': number},
                {'$set':{
                'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'productName': request.form.get('productName'),
                'price': int(request.form.get('price')),
                'weight': int(request.form.get('weight')),
                'percentDiscount': int(request.form.get('percentDiscount')),
                'vendor': request.form.get('vendor'),
                'req_status': u'ویرایش شده',
                'refuse_reason': '',
                'read': False
                }
                }
                )
            flash(u'ویرایش انجام شد. نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+number, 'success')

        elif sub_item == 'pack':
            pack_products = []
            weight = 0
            for i in range (1, 100):
                if request.form.get('product_'+str(i)):
                    ppr = cursor.vestano_inventory.find_one({'productId':request.form.get('product_'+str(i))})
                    pack_product = {}
                    pack_product['productId'] = request.form.get('product_'+str(i))
                    pack_product['productName'] = ppr['productName']
                    pack_product['count'] = int(request.form.get('count_'+str(i)))
                    pack_product['weight'] = int(request.form.get('weight_'+str(i)))
                    pack_product['price'] = int(request.form.get('price_'+str(i)))
                    pack_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))
                    weight += int(request.form.get('weight_'+str(i)))
                    pack_products.append(pack_product)

            cursor.inventory_transfer.update_many(
                {'number': number},
                {'$set':{
                'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'productName': request.form.get('productName'),
                'price': int(request.form.get('price')),
                'weight': int(request.form.get('weight')),
                'count': int(request.form.get('count')),
                'percentDiscount': int(request.form.get('percentDiscount')),
                'description': request.form.get('description'),
                'pack_products': pack_products,
                'vendor': request.form.get('vendor'),
                'shipment': request.form.get('shipment'),
                'shipment_date': request.form.get('shipment_date'),
                'req_status': u'ویرایش شده',
                'refuse_reason': '',
                'read': False
                }
                }
                )
            flash(u'ویرایش انجام شد. نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+number, 'success')

        elif sub_item == 'release':
            cursor.inventory_transfer.update_many(
                {'number': number},
                {'$set':{
                'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'count': int(request.form.get('count')),
                'shipment': request.form.get('shipment'),
                'shipment_date': request.form.get('shipment_date'),
                'req_status': u'ویرایش شده',
                'refuse_reason': '',
                'read': False
                }
                }
                )
            flash(u'ویرایش انجام شد. نتیجه درخواست شما پس از بررسی اعلام خواهد شد! شماره حواله: '+number, 'success')

    return render_template('user_pannel.html',
        item='inventoryTransferDetails',
        inventory = utils.inventory(cursor),
        transfer_details = utils.transfer_details(cursor, number),
        sub_item=sub_item,
        number = number
        )

@app.route('/inventory-transfer-accept/<number>', methods=['GET', 'POST'])
@token_required
def inventory_transfer_accept(number):
    result = cursor.inventory_transfer.find_one({'number':number})
    if result['req_status'] == u'تایید شد':
            flash(u'درخواست قبلا تایید شده است!', 'success')
            return redirect(request.referrer)
    if result['req_status'] == u'رد درخواست':
            flash(u'درخواست قبلا رد شده است!', 'danger')
            return redirect(request.referrer)
    if result['request_type'] == 'new':
        record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
        record['productName'] = result['productName']
        record['price'] = result['price'] + config.defaultWageForDefineStuff
        record['weight'] = result['weight']
        record['count'] = result['count']
        record['percentDiscount'] = result['percentDiscount']
        record['description'] = result['percentDiscount']
        record['vendor'] = result['vendor']
        record['productId'] = str(utils.AddStuff(record))
        record['status'] = utils.add_empty_status()
        record['record'] = []
        first_add = {
        'action': 'add',
        'datetime' : record['datetime'],
        'count': result['count'],
        'exist_count': result['count'],
        'person': u'حواله '+number
        }
        record['record'].append(first_add)

        cursor.vestano_inventory.insert_one(record)
        cursor.inventory_transfer.update_many(
            {'number': number},
            {'$set':{'productId': record['productId']}})
        flash(u'محصول جدید ثبت شد. شناسه کالا: ' + str(record['productId']), 'success')

    elif result['request_type'] == 'inc':
        vest_res = cursor.vestano_inventory.find_one({'productId': result['productId']})
        print(vest_res['count'])
        if result['returned']:
            add = {
            'action': 'returned',
            'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
            'count': result['count'],
            'exist_count': vest_res['count'] + result['count'],
            'person': u'حواله '+number
            }
        else:
            add = {
            'action': 'add',
            'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
            'count': result['count'],
            'exist_count': vest_res['count'] + result['count'],
            'person': u'حواله '+number
            }
        vest_res['record'].append(add)
        cursor.vestano_inventory.update_many(
            {'productId': result['productId']},
            {'$set':{
            'datetime': add['datetime'],
            'count': vest_res['count'] + result['count'],
            'record': vest_res['record']
            }
            }
            )
        flash(u'درخواست با موفقیت ثبت شد!', 'success')

    elif result['request_type'] == 'edit':
        cursor.vestano_inventory.update_many(
            {'productId': result['productId']},
            {'$set':{
            'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
            'productName': result['productName'],
            'price': result['price'] + config.defaultWageForDefineStuff,
            'percentDiscount': result['percentDiscount'],
            'weight': result['weight'],
            'vendor': result['vendor']
            }
            }
            )
        edit_result = utils.editStuff(
            result['productId'],
            result['weight'],
            result['price'] + config.defaultWageForDefineStuff
            )
        flash(u'درخواست با موفقیت ثبت شد!', 'success')

    elif result['request_type'] == 'pack':
        record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
        record['productName'] = result['productName']
        record['price'] = result['price'] + config.defaultWageForDefineStuff
        #record['weight'] = int(request.form.get('weight'))
        record['count'] = result['count']
        record['percentDiscount'] = result['percentDiscount']
        record['description'] = result['description']
        record['vendor'] = result['vendor']

        pack_products = []
        weight = 0
        for i in range(len(result['pack_products'])):
            ppr = cursor.vestano_inventory.find_one({'productId':result['pack_products'][i]['productId']})
            pack_product = {}
            pack_product['productId'] = result['pack_products'][i]['productId']
            pack_product['productName'] = ppr['productName']
            pack_product['count'] = result['pack_products'][i]['count']
            pack_product['weight'] = result['pack_products'][i]['weight']
            pack_product['price'] = result['pack_products'][i]['price']
            pack_product['percentDiscount'] = result['pack_products'][i]['percentDiscount']
            weight += result['pack_products'][i]['weight']
            pack_products.append(pack_product)

        record['record'] = []
        first_add = {
        'action': 'add',
        'datetime' : record['datetime'],
        'count': result['count'],
        'exist_count': result['count'],
        'person': u'حواله '+number
        }
        record['record'].append(first_add)

        record['pack_products'] = pack_products
        record['weight'] = weight
        record['productId'] = str(utils.AddStuff(record))
        record['status'] = utils.add_empty_status()
        cursor.vestano_inventory.insert_one(record)
        cursor.inventory_transfer.update_many(
            {'number': number},
            {'$set':{'productId': record['productId']}})
        flash(u'بسته جدید ایجاد شد. شناسه کالا: ' + str(record['productId']), 'success')

    elif result['request_type'] == 'release':
        ves_res = cursor.vestano_inventory.find_one({'productId': result['productId']})
        dec = {
        'action': 'release',
        'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
        'count': result['count'],
        'exist_count': ves_res['count'] - result['count'],
        'person': u'حواله '+number
        }
        print(dec)
        ves_res['record'].append(dec)
        if result['count'] > ves_res['count']:
            flash(u'تعداد مرجوعی از موجودی انبار بیشتر است!', 'danger')
            return redirect(request.referrer)
        cursor.vestano_inventory.update_many(
            {'productId': result['productId']},
            {'$set':{
            'datetime': dec['datetime'],
            'count': ves_res['count'] - result['count'],
            'record': ves_res['record']
            }
            }
            )
        flash(u'درخواست با موفقیت ثبت شد!', 'success')

    cursor.inventory_transfer.update_many(
        {'number': number},
        {'$set':{
        'req_status': u'تایید شد',
        'read': False
        }
        }
        )
    return redirect(request.referrer)

@app.route('/inventory-transfer-refuse/<number>', methods=['GET', 'POST'])
@token_required
def inventory_transfer_refuse(number):
    result = cursor.inventory_transfer.find_one({'number':number})
    if result['req_status'] == u'تایید شد':
        flash(u'خطا! این درخواست قبلا تایید شده است!', 'danger')
        return redirect(request.referrer)
    if result['read']:
        flash(u'رد درخواست قبلا به اطلاع فروشگاه رسیده است!', 'danger')
        return redirect(request.referrer)
    cursor.inventory_transfer.update_many(
        {'number': number},
        {'$set':{
        'refuse_reason': request.args.get('refuse_reason'),
        'req_status': u'رد درخواست',
        'read': False
        }
        }
        )
    flash(u'رد درخواست اعمال شد!', 'success')
    return redirect(request.referrer)


@app.route('/user-pannel/inventory', methods=['GET', 'POST'])
@token_required
def inventory():
    if 'inventory' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item="inventory",
        inventory = utils.inventory(cursor),
        states = utils.states(cursor),
        sum = utils.inventory_sumation(cursor)
        )

@app.route('/delete-stuff/<productId>', methods=['GET'])
@token_required
def delete_from_inventory(productId):
    result = cursor.vestano_inventory.find_one({'productId': productId})
    if result:
        cursor.vestano_inventory.remove({'productId': productId})
        flash(u'کالای مورد نظر از موجودی انبار حذف شد!', 'success')
    else:
        result = cursor.case_inventory.find_one({'productId': productId})
        if result:
            cursor.case_inventory.remove({'productId': productId})
            flash(u'کالای مورد نظر از موجودی انبار سفارشات موردی حذف شد!', 'success')

    return redirect(request.referrer)

@app.route('/user-pannel/financial/<sub_item>', methods=['GET'])
@token_required
def financial(sub_item):
    if 'financialRep' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item = "financial",
        sub_item = sub_item,
        financial = utils.financial(cursor),
        v_financial = utils.v_financial(cursor),
        vendor_credit = utils.financial_vendor_credit(cursor),
        requests_list = utils.credit_requests_list(cursor),
        paid_list = utils.paid_list(cursor)
        )

@app.route('/req-credit/<price>/<orderId_list>', methods=['GET', 'POST'])
@token_required
def request_credit(price, orderId_list):
    if 'financialRep' not in session['access']:
        flash(u'شما مجوز لازم برای استفاده از این صفحه را ندارید!', 'error')
        return redirect(request.referrer)

    orderId_list = orderId_list[1:-1].split(', ')

    if request.method == 'POST':
        record = {'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
        record['credit_price'] = request.form.get('credit_price')
        record['account_number'] = request.form.get('account_number')
        record['account_holder'] = request.form.get('account_holder')
        record['number'] = 'VES-F-' + str(random2.randint(10000000, 99999999))
        #record['vendor'] = session['vendor']
        record['vendor'] = 'روژیاپ'
        record['read'] = False
        record['orderId_list'] = orderId_list
        record['username'] = session['username']
        record['ref_number'] = '-'
        record['req_status'] = u'در دست بررسی'

        cursor.credit_requests.insert_one(record)
        for orderId in orderId_list:
            cursor.orders.update_many(
                {"orderId": orderId},
                {'$set': {'credit_req_status': record['req_status']}})
        flash(u'درخواست واریز وجه با موفقیت ثبت شد. شماره ارجاع: '+record['number'], 'success')

    return render_template('includes/_requestCredit.html',
        price = price,
        orderId_list = orderId_list,
        orders = utils.req_credit_orders(cursor, orderId_list)
        )

@app.route('/financial-settlement/<number>', methods=['GET', 'POST'])
@token_required
def financial_settlement(number):
    result = cursor.credit_requests.find_one({'number':number})
    data = {
    'credit_price': result['credit_price'],
    'orders_count': len(result['orderId_list']),
    'account_number': result['account_number'],
    'account_holder': result['account_holder'],
    'ref_number': result['ref_number'],
    'req_status': result['req_status'],
    }
    if session['role'] != 'vendor_admin':
        if request.method == 'POST':
            cursor.credit_requests.update_many(
                {"number": number},
                {'$set': {'req_status': u'واریز شد',
                'ref_number': request.form.get('ref_number'),
                'paid_datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                'read': False}})

            for orderId in result['orderId_list']:
                cursor.orders.update_many(
                    {"orderId": orderId},
                    {'$set': {'credit_req_status': u'واریز شد',
                    'settlement_ref_number': request.form.get('ref_number')}})
            flash(u'واریز وجه ثبت شد.', 'success')
    else:
        cursor.credit_requests.update_many(
            {"number": number},
            {'$set': {'read': True}})

    return render_template('includes/_financialSettlement.html',
        data = data,
        orders = utils.req_credit_orders(cursor, result['orderId_list'])
        )

@app.route('/user-pannel/accounting', methods=['GET'])
@token_required
def accounting():
    return render_template('user_pannel.html',
        item="accounting",
        accounting = utils.accounting(cursor)
        )

@app.route('/user-pannel/tickets', methods=['GET'])
@token_required
def tickets():

    return render_template('user_pannel.html',
        item="tickets",
        tickets = utils.tickets(cursor, session['role'], session['username'])
        )

@app.route('/user-pannel/new-ticket', methods=['GET', 'POST'])
@token_required
def new_ticket():
    if request.method == 'POST':
        record = {'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
        record['departement'] = request.form.get('ticket-departement')
        record['title'] = request.form.get('ticket-title')
        record['sender_name'] = request.form.get('ticket-sender-name')
        record['sender_phone'] = request.form.get('ticket-sender-phone')
        record['text'] = request.form.get('ticket-text').split("\n")
        record['number'] = 'VES-T-' + str(random2.randint(10000000, 99999999))
        record['ref_ticket'] = ''
        record['sender_username'] = session['username']
        record['vendor'] = ''
        record['reply'] = {'sender':[], 'text':[], 'datetime':[]}
        record['read'] = False
        record['support_reply'] = False
        record['sender_reply'] = True

        file = request.files['ticket-attachment']
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['ATTACHED_FILE_FOLDER'], filename))
            file_type  = filename.rsplit('.', 1)[1].lower()
            directory = app.config['ATTACHED_FILE_FOLDER']
            if not os.path.exists(directory):
                os.makedirs(directory)
            os.rename(directory + filename,
                directory + record['number'] +'.'+ file_type)

            record['attch_path'] = directory + record['number'] +'.'+ file_type
        else:
            record['attch_path'] = ''

        flash(u'تیکت با موفقیت ارسال شد. شماره ارجاع: '+record['number'], 'success')

        cursor.tickets.insert_one(record)


    return render_template('user_pannel.html',
        item="newTicket"
        )

@app.route('/user-pannel/show-ticket/<ticket_num>', methods=['GET', 'POST'])
@token_required
def show_ticket(ticket_num):
    result = cursor.tickets.find_one({'number':ticket_num})
    if session['role'] == 'vendor_admin':
        cursor.tickets.update_many(
            {"number": ticket_num},
            {'$set': {'read': True}})

    if request.method == 'POST':
        if not request.form.get('ticket-reply'):
            flash(u'فیلد پاسخ خالی است!', 'danger')
            return redirect(request.referrer)

        if session['role'] == 'vendor_admin':
            user_result = cursor.users.find_one({'username':session['username']})
            result['reply']['sender'].append({'name': user_result['name'], 'username': session['username']})
            support_reply = False
            sender_reply = True
            read = True
        else:
            result['reply']['sender'].append({'name': u'پشتیبانی', 'username': session['username']})
            support_reply = True
            sender_reply = False
            read = False

        result['reply']['text'].append(request.form.get('ticket-reply').split("\n"))
        result['reply']['datetime'].append(jdatetime.datetime.now().strftime('%Y/%m/%d - %H:%M'))
        cursor.tickets.update_many(
        {"number": ticket_num},
        {'$set': {
        'reply': result['reply'],
        'read': read,
        'support_reply': support_reply,
        'sender_reply': sender_reply
        }})
        flash(u'پاسخ تیکت با موفقیت ارسال شد.', 'success')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item = "showTicket",
        ticket_num = ticket_num,
        ticket_details = utils.ticket_details(cursor, ticket_num)
        )

@app.route('/about')
def about():

    return render_template('about.html')

@app.route('/register', methods=['GET', 'POST'])
@token_required
def register():
    if (session['role'] == 'admin') or (session['role'] == 'vendor_admin'):
        if request.method == 'POST':
            users = {'created_date': datetime.datetime.now()}
            users['name'] = request.form.get('name')
            users['email'] = request.form.get('email')
            users['phone'] = request.form.get('phone')
            users['username'] = request.form.get('username')
            new_password = request.form.get('password')
            confirm = request.form.get('confirm')
            users['password'] = sha256_crypt.hash(str(request.form.get('password')))

            if len(request.form.getlist('api_user')):
                users['role'] = 'api'
                users['acces'] = []
                result = cursor.api_users.find_one({"username": users['username']})
                if result:
                    flash(u'نام کاربری تکراری است. لطفا نام کاربری دیگری انتخاب کنید', 'danger')
                else:
                    if new_password == confirm:
                        users['user_id'] = str(uuid.uuid4())
                        cursor.api_users.insert_one(users)
                        flash(u'ثبت نام با موفقیت انجام شد!', 'success')
                    else:
                        flash(u'کلمه عبور مطابقت ندارد', 'error')
            else:
                users['role'] = request.form.get('role')
                users['access'] = request.form.getlist('access')
                result = cursor.users.find_one({"username": users['username']})
                if result:
                    flash(u'نام کاربری تکراری است. لطفا نام کاربری دیگری انتخاب کنید', 'danger')
                else:
                    if new_password == confirm:
                        users['user_id'] = str(uuid.uuid4())
                        cursor.users.insert_one(users)
                        flash(u'ثبت نام با موفقیت انجام شد!', 'success')
                    else:
                        flash(u'کلمه عبور مطابقت ندارد', 'error')
    else:
        flash(u'دسترسی لازم را ندارید!', 'danger')

    return render_template('register.html')

@app.route('/change-password', methods=['GET', 'POST'])
@token_required
def change_password():
    if 'username' not in session:
        flash(u'دسترسی لازم را ندارید!', 'danger')
        return redirect(request.referrer)

    if request.method == 'POST':
        current_pass = request.form.get('current_pass')
        new_pass = request.form.get('password')
        confirm = request.form.get('confirm')
        
        result = cursor.users.find_one({"username": session['username']})

        if sha256_crypt.verify(current_pass, result['password']):
            if new_pass == confirm:
                new_pass = sha256_crypt.hash(str(new_pass))
                cursor.users.update_many(
                        {"username": session['username']},
                        {'$set': {'password': new_pass}}
                        )
                flash(u'کلمه عبور با موفقیت تغییر یافت. لطفا مجددا وارد شوید.', 'success-login')
                return redirect(url_for('logout'))
            else:
                flash(u"کلمه عبور مطابقت ندارد! لطفا مجددا وارد کنید.", 'danger')
                return redirect(url_for('change_password'))
        else:
            flash('Current Password Not Matched!', 'danger')
    return render_template('includes/_changePassword.html')

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    session.pop('message', None)
    session.pop('temp_orders', None)
    session.pop('canceled_orders', None)
    session.pop('today_orders', None)
    session.pop('all_orders', None)
    session.pop('guarantee_orders', None)
    session.pop('role', None)
    session.pop('access', None)
    session.pop('jdatetime', None)
    session.pop('unread_tickets', None)
    session.pop('unread_inv_transfers', None)
    return redirect(url_for('home'))

@app.route('/token-logout')
def token_logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    session.pop('message', None)
    session.pop('temp_orders', None)
    session.pop('canceled_orders', None)
    session.pop('today_orders', None)
    session.pop('all_orders', None)
    session.pop('guarantee_orders', None)
    session.pop('role', None)
    session.pop('access', None)
    session.pop('jdatetime', None)
    session.pop('unread_tickets', None)
    session.pop('unread_inv_transfers', None)
    return redirect(url_for('login'))

@app.route('/ajax', methods=['GET'])
def ajax():
    if 'username' in session:
        data = request.args.get('code')
        if len(data) < 3:
            result = utils.cities(cursor, int(data))
        else:
            result = utils.Products(cursor, data)

    else:
        flash(u'لطفا ابتدا وارد شوید', 'error')
        return redirect(request.referrer)
        
    return jsonify(result)

@app.route('/price-ajax', methods=['GET'])
def price_ajax():
    if 'username' in session:
        weight = int(request.args.get('weight'))
        price = int(request.args.get('price'))
        city = int(request.args.get('city'))
        pType = int(request.args.get('pType'))
        print(weight, price, city, pType)
        sefareshi = utils.GetDeliveryPrice(city, price, weight, 2, pType)
        pishtaz = utils.GetDeliveryPrice(city, price, weight, 1, pType)
        result = {
        'sefareshi': sefareshi['DeliveryPrice'] + sefareshi['VatTax'],
        'pishtaz': pishtaz['DeliveryPrice'] + pishtaz['VatTax']
        }
        print(result)
    else:
        flash(u'لطفا ابتدا وارد شوید', 'error')
        return redirect(request.referrer)
        
    return jsonify(result)

@app.route('/validator-ajax', methods=['GET'])
def validator_ajax():
    if 'username' in session:
        Type = request.args.get('type')
        Data = request.args.get('data')

        if Type == 'name':
            data = {
            'name' : Data.encode('utf-8').decode('unicode-escape')
            }
            if v.validate(data, name_schema):
                return jsonify({'result': True})
            else:
                #flash(u'خطا !\nنام و نام خانوادگی باید فقط شامل حروف فارسی باشند!', 'danger')
                return jsonify({'result': False})
        elif Type == 'number':
            data = {
            'number' : Data
            }
            if v.validate(data, number_schema):
                return jsonify({'result': True})
            else:
                return jsonify({'result': False})

@app.route('/case-ajax', methods=['GET'])
def case_ajax():
    if 'username' in session:
        productId = request.args.get('code')
        result = cursor.case_inventory.find_one({'productId': productId})
        ans = {
        'productName': result['productName'],
        'productId': productId,
        'count': result['count'],
        'vendor': result['vendor'],
        'price': result['price'],
        'weight': result['weight'],
        'discount': result['percentDiscount']
        }

    else:
        flash(u'لطفا ابتدا وارد شوید', 'error')
        return redirect(request.referrer)
        
    return jsonify(ans)

@app.route('/shipmentTrack-ajax', methods=['GET'])
def shipmentTrack_ajax():
    track_id = str(request.args.get('track_id'))
    orderId = track_id
    trackId = u'شماره پیگیری: ' + track_id
    success = 1
    result = cursor.orders.find_one({'orderId':track_id})
    if not result:
        result = cursor.orders.find_one({'parcelCode':track_id})
        if not result:
            success = 0
            return jsonify({'success':success})
        trackId = u'بارکد: ' + track_id
        orderId = result['orderId']

    if result['vendorName'] == u'سفارش موردی':
        r = cursor.case_orders.find_one({'orderId': orderId})
        senderName = r['senderFirstName'] +' '+ r['senderLastName']
    else:
        senderName = u'سامانه پستی وستانو'

    state_result = cursor.states.find_one({'Code': result['stateCode']})
    for rec in state_result['Cities']:
        if result['cityCode'] == rec['Code']:
            state = state_result['Name']
            city = rec['Name']
            break

    pNameList = []
    weight_sum = 0
    for i in range(len(result['products'])):
        pNameList.append(result['products'][i]['productName'] +' - '+str(result['products'][i]['count']) + u' عدد ')
        weight_sum += result['products'][i]['weight'] * result['products'][i]['count']

    ans = {
    'success': success,
    'senderName': senderName,
    'senderAdd': u'استان کرمانشاه - شهر کرمانشاه',
    'trackId': trackId,
    'receiverName': result['registerFirstName'] + ' ' + result['registerLastName'],
    'receiverAdd': u'استان '+ state + u' - شهر ' + city,
    'receiverCellNumber': result['registerCellNumber'],
    'receiverPostalCode': result['registerPostalCode'],
    'datetime': result['record_date'] + ' - ' + result['record_time'],
    'products': ('<br />'.join(pNameList)),
    'weight': str(weight_sum) + ' ' + u'گرم',
    'serviceType': result['serviceType'],
    'status': utils.statusToString(result['status']),
    'parcelCode': result['parcelCode']
    }
    return jsonify(ans)

@app.route('/fetch-stuff', methods=['GET'])
def fetch_stuff():
    if 'username' in session:
        product_id = request.args.get('code')
        print(product_id)
        result = cursor.vestano_inventory.find_one({'productId': product_id})
        if not result:
            flash(u'شناسه کالا در انبار ثبت نشده است!', 'error')
            return False
        else:
            del result["_id"]
            print(result)
    else:
        flash(u'لطفا ابتدا وارد شوید', 'error')
        return False
        
    return jsonify(result)

@app.route('/orders-details/<orderId>/<code>', methods=['GET', 'POST'])
@token_required
def order_details(orderId, code):

    return render_template('includes/_orderDetails.html',
        code = code,
        details = utils.details(cursor, orderId, code)
        )

@app.route('/inventory-details/<status>/<productId>', methods=['GET', 'POST'])
@token_required
def inventory_details(status, productId):
    r = cursor.vestano_inventory.find_one({'productId': productId})
    productName = r['productName']

    return render_template('includes/_inventoryDetails.html',
        details = utils.inventory_details(cursor, status, productId),
        productName = productName
        )

@app.route('/inventory-enterance-details/<productId>', methods=['GET', 'POST'])
@token_required
def enterance_details(productId):
    product = cursor.vestano_inventory.find_one({'productId': productId})

    return render_template('includes/_enteranceDetails.html',
        details = product['record'],
        productName = product['productName'],
        productId = productId
        )

@app.route('/update-status', methods=['GET'])
@token_required
def update_status():
    update = utils.GetStatus(cursor)
    if update:
        flash(u"تغییرات بروزرسانی شد.", 'success')
    else:
        flash(u"تغییری مشاهده نشد.", 'success')
    return redirect(request.referrer)

@app.route('/show-pdf/<orderId>', methods=['GET'])
@token_required
def show_pdf(orderId):
    filename = '/root/vestano/static/pdf/caseOrders/orderId_'+orderId+'.pdf'
    
    return send_file(filename, as_attachment=True)

@app.route('/export-excel', methods=['GET'])
@token_required
def export_excel():
    utils.write_excel(cursor)
    filename = '/root/vestano/static/pdf/xls/inventory.xls'
    
    return send_file(filename, as_attachment=True)

@app.route('/api-guide', methods=['GET'])
def api_guide():
    filename = '/root/vestano/static/pdf/apiGuide/api_guide.pdf'
    
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug = True)