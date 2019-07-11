#coding: utf-8
from flask import Flask, render_template, flash, redirect, url_for, session, request, jsonify
from flask import Response, logging, Markup, abort, after_this_request, make_response
#from flask_recaptcha import ReCaptcha
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from functools import wraps
from flask_spyne import Spyne
from cerberus import Validator
from spyne.protocol.soap import Soap11
from spyne.model.primitive import Unicode, Integer, String
from spyne.model.complex import Array, Iterable, ComplexModel
import requests
import random2
import uuid
import os
import jwt
import datetime
import jdatetime
import pdfkit
import json
import utils, config

#Config mongodb
cursor = utils.config_mongodb()

app = Flask(__name__)

app.secret_key = 'secret@vestano@password_hash@840'
#app.config.update({
    #'RECAPTCHA_ENABLED': True,
    #'RECAPTCHA_SITE_KEY': '6Lc-0asUAAAAAMBA5mQR2Svai9uFEtNJe5gvu8_z',
    #'RECAPTCHA_SECRET_KEY': '6Lc-0asUAAAAAG3ukYfT0Gwd4llqFCyYTmfcvRul'
    #})
#recaptcha = ReCaptcha(app=app)

spyne = Spyne(app)

schema = {
'firstName': {
    'type': 'string',
    'required': True,
    'regex': '^[ آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]+$'
},
'lastName': {
    'type': 'string',
    'required': True,
    'regex': '^[ آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]+$'
},
'cellNumber':{
    'type': 'string',
    'required': True,
    'regex': '^[0-9]+$',
    'maxlength': 11,
    'minlength': 11
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
        Array(Products), Integer, Integer, String, String, _returns=String)
    def NewOrder(username, password, vendorName, registerFirstName, registerLastName, registerCellNumber,
        stateCode, cityCode, registerAddress, registerPostalCode, products, serviceType, payType, orderDate, orderTime):
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
                'record_date': orderDate,
                'record_time': orderTime,
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
            session['temp_orders'] = cursor.temp_orders.estimated_document_count()
            session['canceled_orders'] = cursor.canceled_orders.estimated_document_count()
            session['today_orders'] = utils.today_orders(cursor)['count']
            session['ready_to_ship'] = cursor.ready_to_ship.estimated_document_count()
            session['all_orders'] = cursor.orders.estimated_document_count()
        except:
            return redirect(url_for('logout'))            

        result = cursor.users.find_one({"user_id": data['user_id']})
        if result:
            if 'username' not in session:
                username = result['username']
                session['username'] = username
                session['message'] = result['name']
                session['role'] = result['role']
                session['jdatetime'] = jdatetime.datetime.today().strftime('%d / %m / %Y')
                session['temp_orders'] = cursor.temp_orders.estimated_document_count()
                session['canceled_orders'] = cursor.canceled_orders.estimated_document_count()
                session['today_orders'] = cursor.today_orders.estimated_document_count()
                flash(result['name'] + u' عزیز خوش آمدید', 'success-login')
        
        else:
            flash('Token is not valid!', 'danger')
            return redirect(request.referrer)

        return f(*args, **kwargs)
    return decorated

@app.route('/badrequest400')
def bad_request():
    return abort(403)
   
@app.route('/', methods=['GET', 'POST'])
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
                return redirect(url_for('temp_orders'))
            #else:
                #flash(u'معتبر نیست!', 'danger')
            else:
                flash(u'کلمه عبور مطابقت ندارد', 'danger')
        else:
            flash(u'نام کاربری ثبت نشده است. لطفا  ابتدا ثبت نام کنید', 'error')

    return render_template('login.html')

@app.route('/home', methods=['GET'])
@token_required
def home():
    return render_template('home.html')

@app.route('/user-pannel/orderList', methods=['GET'])
@token_required
def temp_orders():
    session['temp_orders'] = cursor.temp_orders.estimated_document_count()
    session['canceled_orders'] = cursor.canceled_orders.estimated_document_count()
    session['today_orders'] = utils.today_orders(cursor)['count']
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
    result = cursor.temp_orders.find_one({"orderId": code})
    if result:
        (sType, pType) = utils.typeOfServicesToCode(result['serviceType'], result['payType'])
        new_rec = result
        price = 0
        count = 0
        weight = 0
        discount = 0
        for i in range(len(result['products'])):
            if result['vendorName'] == u'سفارش موردی':
                inv = cursor.case_inventory.find_one({'productId':result['products'][i]['productId']})
            else:
                inv = cursor.vestano_inventory.find_one({'productId':result['products'][i]['productId']})

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
        #soap_result = utils.SoapClient(order)
        #print('errorcode: ', soap_result['ErrorCode'])
        soap_result = {'ErrorCode' :0, 'ParcelCode': '21868000011931436408', 'PostDeliveryPrice':50000, 'VatTax':9000}
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


        
        if not soap_result['ErrorCode']:

            new_rec['record_datetime'] = jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')
            new_rec['parcelCode'] = soap_result['ParcelCode']
            new_rec['username'] = session['username']

            #utils.ReadyToShip(soap_result['ParcelCode'])
            new_rec['status'] = utils.GetStatus_one(cursor, soap_result['ParcelCode'])
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

                #WKHTMLTOPDF_PATH = '/usr/local/bin/wkhtmltopdf'
                #configure = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

                pdfkit.from_string(render_template('includes/_caseOrderPdf.html',
                    datetime = jdatetime.datetime.now().strftime('%H:%M %Y/%m/%d'),
                    orderId = new_rec['orderId'],
                    parcelCode = new_rec['parcelCode'],
                    sender = case_result['senderFirstName']+' '+case_result['senderLastName'],
                    receiver = case_result['receiverFirstName']+' '+case_result['receiverLastName'],
                    cellNumber = case_result['receiverCellNumber'],
                    destination = state_result['Name']+' / '+city+' / '+case_result['registerAddress'],
                    postalCode = new_rec['registerPostalCode'],
                    weight = weight,
                    sType = order['serviceType'],
                    packing = case_result['packing'],
                    carton = case_result['carton'],
                    gathering = case_result['gathering'],
                    without_ck = case_result['without_ck'],
                    deliveryPrice = soap_result['PostDeliveryPrice'] + vestano_wage + config.registerCost,
                    VatTax = soap_result['VatTax']
                    ), 'static/pdf/caseOrders/orderId_'+new_rec['orderId']+'.pdf')
                #os.startfile('E:/projects/VESTANO/Vestano/static/pdf/caseOrders/orderId_ '+new_rec['orderId']+'.pdf')

            utils.removeFromInventory(cursor, new_rec['orderId'])

            flash(u'سفارش تایید و آماده ارسال شد!', 'success')
            return redirect(request.referrer)
        else:
            flash(u'خطایی رخ داده است!', 'error')
            return redirect(request.referrer)
    else:
        flash(u'خطایی رخ داده است! (شناسه سفارش)', 'error')
        return redirect(request.referrer)

    return render_template('user_pannel.html',
        item='orderList')

@app.route('/user-pannel/ready-to-ship', methods=['GET'])
@token_required
def readyToShip_orders():

    return render_template('user_pannel.html',
        item='readyToShip',
        inventory = utils.inventory(cursor),
        readyToShip_orders = utils.readyToShip_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/today-orders', methods=['GET'])
@token_required
def today_orders():

    return render_template('user_pannel.html',
        item='todayOrders',
        inventory = utils.inventory(cursor),
        today_orders = utils.today_orders(cursor)['today'],
        states = utils.states(cursor)
        )

@app.route('/user-pannel/all-orders', methods=['GET'])
@token_required
def all_orders():

    return render_template('user_pannel.html',
        item='allOrders',
        inventory = utils.inventory(cursor),
        all_orders = utils.all_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/finish-process/<orderId>', methods=['GET'])
@token_required
def finish_process(orderId):
    new_rec = cursor.ready_to_ship.find_one({'orderId': orderId})
    cursor.orders.update_many(
        {'orderId': orderId},
        {'$set':{'status': 81}}
        )
    cursor.status.update_many(
        {'orderId': orderId},
        {'$set':{'status': 81}}
        )
    cursor.ready_to_ship.remove({'orderId': orderId})
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
    flash(u'فرآیند سفارش با موفقیت به پایان رسید!', 'success')
    return redirect(request.referrer)

@app.route('/user-pannel/canceled-orders', methods=['GET'])
@token_required
def canceled_orders():

    return render_template('user_pannel.html',
        item='cnlOrders',
        inventory = utils.inventory(cursor),
        canceled_orders = utils.canceled_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/cancel-order/<orderId>', methods=['GET'])
@token_required
def cancel_orders(orderId):
    rec = cursor.temp_orders.find_one({'orderId': orderId})
    cursor.canceled_orders.insert_one(rec)
    for i in range(len(rec['products'])):
        if rec['vendorName'] == u'سفارش موردی':
            vinvent = cursor.case_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['80']-= rec['products'][i]['count']
            cursor.case_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
        else:
            vinvent = cursor.vestano_inventory.find_one({'productId':rec['products'][i]['productId']})
            vinvent['status']['80']-= rec['products'][i]['count']
            cursor.vestano_inventory.update_many(
                {'productId': vinvent['productId']},
                {'$set':{'status': vinvent['status']}}
                )
    cursor.temp_orders.remove({'orderId': orderId})
    flash(u'سفارش مورد نظر لغو شد!', 'danger')
    return redirect(request.referrer)

@app.route('/pending-order/<orderId>', methods=['GET'])
@token_required
def pending_orders(orderId):
    rec = cursor.temp_orders.find_one({'orderId': orderId})
    rec['status'] = 82
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
    rec = cursor.canceled_orders.find_one({'orderId': orderId})
    cursor.canceled_orders.remove({'orderId': orderId})
    flash(u'سفارش حذف شد!', 'danger')
    return redirect(request.referrer)

@app.route('/edit-order/<orderId>', methods=['GET', 'POST'])
@token_required
def edit_orders(orderId):
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

            cursor.case_orders.update_many(
                {'orderId': orderId},
                {'$set':{
                'vendorName' : u'سفارش موردی',
                'senderFirstName' : request.form.get('s_first_name'),
                'senderLastName' : request.form.get('s_last_name'),
                'senderCellNumber' : request.form.get('s_cell_number'),
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
                }
                )

        else:
            temp_order = {
            'vendorName' : u'روژیاپ',
            'registerFirstName' : request.form.get('first_name'),
            'registerLastName' : request.form.get('last_name'),
            'registerCellNumber' : request.form.get('cell_number'),
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

        flash(u'ثبت شد!', 'success')

        print(utils.test_temp_order(temp_order))

        cursor.canceled_orders.remove({'orderId': orderId})
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
    if 'username' in session:
        ordered_products = []
        username = session['username']
        if item == 'ordering':
            if request.method == 'POST':
                data = {
                'firstName': request.form.get('first_name').encode('utf-8').decode('unicode-escape'),
                'lastName': request.form.get('last_name').encode('utf-8').decode('unicode-escape'),
                'cellNumber': request.form.get('cell_number')
                }
                if not v.validate(data, schema):
                    error_keys = v.errors.keys()
                    f_error_keys = []
                    for field in error_keys:
                        if field == 'firstName':
                            f_error_keys.append(u'نام')
                        elif field == 'lastName':
                            f_error_keys.append(u'نام خانوادگی')
                        elif field == 'cellNumber':
                            f_error_keys.append(u'شماره موبایل')

                    error_fields = " , ".join(f_error_keys)
                    if len(error_keys) > 1:
                        flash(u'فیلدهای '+error_fields+u' معتبر نیستند!', 'error')
                    else:
                        flash(u'فیلد '+error_fields+u' معتبر نیست!', 'error')
                    return redirect(request.referrer)

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

                temp_order = {
                'vendorName' : u'روژیاپ',
                'registerFirstName' : request.form.get('first_name'),
                'registerLastName' : request.form.get('last_name'),
                'registerCellNumber' : request.form.get('cell_number'),
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
    if 'username' in session:
        ordered_products = []
        username = session['username']
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
            'person': session['username']
            }
            record['record'].append(first_add)

            cursor.case_inventory.insert_one(record)
            flash(u'محصول جدید ثبت شد. شناسه کالا: ' + str(record['productId']), 'success')

        if sub_item == 'new':
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
            'person': session['username']
            }
            record['record'].append(first_add)

            cursor.vestano_inventory.insert_one(record)
            flash(u'محصول جدید ثبت شد. شناسه کالا: ' + str(record['productId']), 'success')

        if sub_item == 'inc':
            result = cursor.vestano_inventory.find_one({'productId': request.form.get('product')})
            print(result)
            add = {
            'action': 'add',
            'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
            'count': int(request.form.get('count')),
            'person': session['username']
            }
            print(add)
            result['record'].append(add)
            cursor.vestano_inventory.update_many(
                {'productId': request.form.get('product')},
                {'$set':{
                'datetime': add['datetime'],
                'price': int(request.form.get('price')),
                'count': result['count'] + int(request.form.get('count')),
                'percentDiscount': int(request.form.get('percentDiscount')),
                'record': result['record']
                }
                }
                )
            flash(u'ثبت شد!', 'success')

        if sub_item == 'edit':
            result = cursor.case_inventory.find_one({'productId': request.form.get('product')})
            if result:
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
            else:
                result = cursor.vestano_inventory.find_one({'productId': request.form.get('product')})
                cursor.vestano_inventory.update_many(
                    {'productId': request.form.get('product')},
                    {'$set':{
                    'datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                    'productName': request.form.get('productName'),
                    'price': int(request.form.get('price')),
                    'percentDiscount': int(request.form.get('percentDiscount')),
                    'weight': int(request.form.get('weight')),
                    'vendor': request.form.get('vendor')
                    }
                    }
                    )
            
            flash(u'ثبت شد!', 'success')

        if sub_item == 'pack':
            record = {'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
            record['productName'] = request.form.get('packName')
            record['price'] = int(request.form.get('price'))
            #record['weight'] = int(request.form.get('weight'))
            record['count'] = int(request.form.get('count'))
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
                    pack_product = {}
                    pack_product['productId'] = request.form.get('product_'+str(i))
                    pack_product['count'] = int(request.form.get('count_'+str(i)))
                    pack_product['weight'] = int(request.form.get('weight_'+str(i)))
                    pack_product['price'] = int(request.form.get('price_'+str(i)))
                    pack_product['percentDiscount'] = int(request.form.get('discount_'+str(i)))
                    weight += int(request.form.get('weight_'+str(i)))
                    pack_products.append(pack_product)
                    
                    #vi_result = cursor.vestano_inventory.find_one({'productId': request.form.get('product_'+str(i))})
                    #if vi_result:
                        #if (int(request.form.get('count_'+str(i))))*(record['count']) > vi_result['count']:
                            #flash(u'موجودی کالای ' + vi_result['productName'] +u' کافی نیست!', 'danger')
                            #return redirect(request.referrer)

            #for j in range(1, 100):
                #if request.form.get('product_'+str(j)):
                    #vi_result = cursor.vestano_inventory.find_one({'productId': request.form.get('product_'+str(j))})
                    #if vi_result:
                        #dec = {
                        #'action': 'to_pack',
                        #'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
                        #'count': (int(request.form.get('count_'+str(j))))*(record['count']),
                        #'person': session['username']
                        #}
                        #vi_result['record'].append(dec)
                        #cursor.vestano_inventory.update_many(
                            #{'productId': request.form.get('product_'+str(j))},
                            #{'$set': {
                            #'count' : vi_result['count'] - (int(request.form.get('count_'+str(j))))*(record['count']),
                            #'record': vi_result['record']
                            #}
                            #}
                            #)

            record['record'] = []
            first_add = {
            'action': 'add',
            'datetime' : record['datetime'],
            'count': int(request.form.get('count')),
            'person': session['username']
            }
            record['record'].append(first_add)

            record['pack_products'] = pack_products
            record['weight'] = weight
            record['productId'] = str(utils.AddStuff(record))
            record['status'] = utils.add_empty_status()
            cursor.vestano_inventory.insert_one(record)
            flash(u'بسته جدید ایجاد شد. شناسه کالا: ' + str(record['productId']), 'success')

        if sub_item == 'release':
            result = cursor.vestano_inventory.find_one({'productId': request.form.get('product')})
            print(result)
            dec = {
            'action': 'release',
            'datetime' : jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M'),
            'count': int(request.form.get('count')),
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
        for_edit_invent = utils.for_edit_invent(cursor),
        sub_item=sub_item,
        productId_result=productId_result
        )


@app.route('/user-pannel/inventory', methods=['GET', 'POST'])
@token_required
def inventory():

    return render_template('user_pannel.html',
        item="inventory",
        inventory = utils.inventory(cursor),
        states = utils.states(cursor),
        sum = utils.inventory_sumation(cursor)
        )

@app.route('/delete-stuff/<productId>', methods=['GET'])
@token_required
def delete_from_inventory(productId):
    cursor.vestano_inventory.remove({'productId': productId})
    flash(u'کالای مورد نظر از موجودی انبار حذف شد!', 'success')

    return redirect(request.referrer)

@app.route('/user-pannel/accounting', methods=['GET', 'POST'])
@token_required
def accounting():

    return render_template('user_pannel.html',
        item="accounting",
        accounting = utils.accounting(cursor)
        )

@app.route('/about')
def about():

    return render_template('about.html')

@app.route('/register', methods=['GET', 'POST'])
@token_required
def register():
    if session['role'] == 'admin':
        if request.method == 'POST':
            users = {'created_date': datetime.datetime.now()}
            users['name'] = request.form.get('name')
            users['email'] = request.form.get('email')
            users['phone'] = request.form.get('phone')
            users['username'] = request.form.get('username')
            users['role'] = request.form.get('role')
            new_password = request.form.get('password')
            confirm = request.form.get('confirm')
            users['password'] = sha256_crypt.hash(str(request.form.get('password')))
            
            result = cursor.users.find_one({"username": users['username']})

            if result:
                flash(u'نام کاربری تکراری است. لطفا نام کاربری دیگری انتخاب کنید', 'danger')
            else:
                if new_password == confirm:
                    users['user_id'] = str(uuid.uuid4())
                    if request.form.get('role') == 'api':
                        cursor.api_users.insert_one(users)
                    else:
                        cursor.users.insert_one(users)
                    flash(u'ثبت نام شما با موفقیت انجام شد. لطفا وارد شوید', 'success')
                else:
                    flash(u'کلمه عبور مطابقت ندارد', 'error')
    else:
        flash(u'دسترسی لازم را ندارید!', 'danger')

    return render_template('register.html')

@app.route('/change-password', methods=['GET', 'POST'])
@token_required
def change_password():
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
    session.pop('role', None)
    session.pop('jdatetime', None)
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

    return render_template('includes/_inventoryDetails.html',
        details = utils.inventory_details(cursor, status, productId)
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
    os.startfile('E:/projects/VESTANO/Vestano/static/pdf/caseOrders/orderId_'+orderId+'.pdf')
    #os.startfile('http://vestanops.com/static/pdf/caseOrders/orderId_'+orderId+'.pdf')

    return redirect(request.referrer)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug = True)