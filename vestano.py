#coding: utf-8
from flask import Flask, render_template, flash, redirect, url_for, session, request, jsonify
from flask import Response, logging, Markup, abort, after_this_request, make_response
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from functools import wraps
from flask_spyne import Spyne
from spyne.protocol.soap import Soap11
from spyne.model.primitive import Unicode, Integer, String
from spyne.model.complex import Array, Iterable, ComplexModel
import random2
import uuid
import jwt
import datetime
import jdatetime
import json
import utils

#Config mongodb
cursor = utils.config_mongodb()

app = Flask(__name__)

app.secret_key = 'secret@vestano@password_hash@840'

spyne = Spyne(app)

#Create namespace
class Products(ComplexModel):
    __namespace__ = "products"
    productName = Unicode
    count = Integer
    price = Integer
    weight = Integer
    percentDiscount = Integer
    description = Unicode

class SomeSoapService(spyne.Service):
    __service_url_path__ = '/soap/VestanoWebService'
    __in_protocol__ = Soap11(validator='lxml')
    __out_protocol__ = Soap11()

    @spyne.srpc(String, String, Unicode, Unicode, Unicode, String, Integer, Integer, Unicode, String,
        Array(Products), Integer, Integer, String, String, _returns=String)
    def NewOrder(username, password, vendorName, registerFirstName, registerLastName, registerCellNumber,
        stateCode, cityCode, registerAddress, registerPostalCode, products, serviceType, payType, orderDate, orderTime):
        if username:
            if password:
                user_result = cursor.api_users.find_one({"username": username})
                if user_result:
                    if sha256_crypt.verify(password, user_result['password']):
                        p_list = []
                        price = 0
                        count = 0
                        weight = 0
                        discount = 0
                        for i in range(len(products)):
                            p_dict = {}
                            p_dict['productName'] = products[i].productName
                            p_dict['count'] = products[i].count
                            p_dict['price'] = products[i].price
                            p_dict['weight'] = products[i].weight
                            p_dict['percentDiscount'] = products[i].percentDiscount
                            p_dict['description'] = products[i].description
                            price = price + products[i].price*products[i].count
                            count = count + products[i].count
                            weight = weight + products[i].weight
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
                        'status' : 'on process'
                        }

                        order = {
                        'cityCode': cityCode,
                        'price': price,
                        'weight': weight,
                        'count': count,
                        'serviceType': serviceType,
                        'payType': payType,
                        'description': '',
                        'percentDiscount': discount,
                        'firstName': registerFirstName,
                        'lastName': registerLastName,
                        'address': registerAddress,
                        'phoneNumber': '',
                        'cellNumber': registerCellNumber,
                        'postalCode': registerPostalCode,
                        'products': p_list
                        }

                        print(order)
                        print('%%%%%%%%%%%%%%%%%%%%%')

                        cursor.temp_orders.insert_one(input_data)
                        cursor.all_records.insert_one(input_data)
                        #print(utils.SoapClient(order))
                        return order_id
                    else:
                        print('The Password Does Not Match!')
                        return(jsonify('The Password Does Not Match!'))
                else:
                    print('Not Signed up Username!')
                    return(jsonify('Not Signed up Username!'))
            else:
                print('Missed Password Field!')
                return(jsonify('Missed Password Field!'))
        else:
            print('Missed Username Field!')
            return(jsonify('Missed Username Field!'))

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
        except:
            return redirect(url_for('logout'))            

        result = cursor.users.find_one({"user_id": data['user_id']})
        if result:
            if 'username' not in session:
                username = result['username']
                session['username'] = username
                session['message'] = result['name']
                session['role'] = result['role']
                session['temp_orders'] = cursor.temp_orders.estimated_document_count()
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
                session['loged_in'] = True
                TOKEN = jwt.encode({'user_id':result['user_id'],
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60)},
                    app.secret_key)
                token = TOKEN.decode('UTF-8')
                return redirect(url_for('ordering', item='ordering'))
            else:
                flash(u'کلمه عبور مطابقت ندارد', 'danger')
        else:
            flash(u'نام کاربری ثبت نشده است. لطفا  ابتدا ثبت نام کنید', 'error')

    return render_template('login.html')

@app.route('/home', methods=['GET'])
@token_required
def home():
    #parcelCode = '21868075911930365800'
    #utils.ReadyToShip(parcelCode)
    return render_template('home.html')

@app.route('/user-pannel/orderList', methods=['GET', 'POST'])
@token_required
def temp_orders():
    session['temp_orders'] = cursor.temp_orders.estimated_document_count()

    return render_template('user_pannel.html',
        item='orderList',
        inventory = utils.inventory(cursor),
        temp_orders = utils.temp_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/confirm-order/<code>', methods=['GET', 'POST'])
@token_required
def confirm_orders(code):
    print(code)
    result = cursor.temp_orders.find_one({"orderId": code})
    if result:
        (sType, pType) = utils.typeOfServicesToCode(result['serviceType'], result['payType'])
        print(sType, pType)
        new_rec = result
        price = 0
        count = 0
        weight = 0
        discount = 0
        for i in range(len(result['products'])):
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
        soap_result = {'ErrorCode' :0, 'ParcelCode': '8002123658485689'}
        print(soap_result)
        if not soap_result['ErrorCode']:

            new_rec['status'] = 'ready to ship'
            new_rec['record_datetime'] = jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')
            print(new_rec['record_datetime'])
            new_rec['ParcelCode'] = soap_result['ParcelCode']
            new_rec['username'] = session['username']

            #utils.ReadyToShip(soap_result['ParcelCode'])

            cursor.orders.insert_one(new_rec)
            cursor.temp_orders.remove({'orderId': code})

            session['temp_orders'] = cursor.temp_orders.estimated_document_count()
            flash(u'سفارش تایید و ثبت شد!', 'success')
        else:
            flash(u'خطایی رخ داده است!', 'error')
    else:
        flash(u'خطایی رخ داده است! (شناسه سفارش)', 'error')

    return render_template('user_pannel.html',
        item='orderList')

@app.route('/user-pannel/<item>', methods=['GET', 'POST'])
@token_required
def ordering(item):
    if 'username' in session:
        session['temp_orders'] = cursor.temp_orders.estimated_document_count()
        ordered_products = []
        username = session['username']
        if item == 'ordering':
            if request.method == 'POST':
                record = {'record_datetime': jdatetime.datetime.now().strftime('%Y/%m/%d %H:%M')}
                record['orderId'] = str(random2.randint(1000000, 9999999))
                record['username'] = session['username']
                record['registerFirstName'] = request.form.get('first_name')
                record['registerLastName'] = request.form.get('last_name')
                record['registerCellNumber'] = request.form.get('cell_number')
                record['stateCode'] = int(request.form.get('stateCode'))
                record['cityCode'] = int(request.form.get('cityCode'))
                record['registerAddress'] = request.form.get('address')
                record['registerPostalCode'] = request.form.get('postal_code')
                record['status'] = 'ready to ship'

                for i in range (1, 100):
                    if request.form.get('product_'+str(i)):
                        ordered_product = {}
                        ordered_product['productName'] = request.form.get('product_'+str(i))
                        ordered_product['count'] = int(request.form.get('count_'+str(i)))
                        ordered_product['price'] = int(request.form.get('price_'+str(i)))
                        ordered_product['weight'] = int(request.form.get('weight_'+str(i)))
                        ordered_product['percentDiscount'] = 0
                        ordered_product['description'] = u''

                        ordered_products.append(ordered_product)
                        print(ordered_products)

                print(request.form.get('serviceType'))
                print(request.form.get('payType'))

                (sType, pType) = utils.typeOfServicesToString(int(request.form.get('serviceType')), int(request.form.get('payType')))

                record['products'] = ordered_products
                record['serviceType'] = sType
                if len(request.form.getlist('free')):
                    record['payType'] = u'ارسال رایگان'
                    pType = u'ارسال رایگان'
                    pTypeCode = 88
                else:
                    record['payType'] = pType
                    pTypeCode = int(request.form.get('payType'))

                price = 0
                counts = 0
                weight = 0
                discount = 0
                for i in range(len(ordered_products)):
                    price = price + int(ordered_products[i]['price']) * int(ordered_products[i]['count'])
                    counts = counts + int(ordered_products[i]['count'])
                    weight = weight + int(ordered_products[i]['weight'])

                order = {
                'cityCode': record['cityCode'],
                'price': price,
                'weight': weight,
                'count': counts,
                'serviceType': record['serviceType'],
                'payType': record['payType'],
                'description': '',
                'percentDiscount': 0,
                'registerFirstName': record['registerFirstName'],
                'registerLastName': record['registerLastName'],
                'registerAddress': record['registerAddress'],
                'registerPhoneNumber': '',
                'registerCellNumber': record['registerCellNumber'],
                'registerPostalCode': record['registerPostalCode'],
                'products': ordered_products
                }

                #soap_result = utils.SoapClient(order)

                #if not soap_result['ParcelCode']:
                    #record['ParcelCode'] = soap_result['ParcelCode']
                    #cursor.orders.insert_one(record)
                    #flash(u'ثبت شد!', 'success')
                    #return redirect(url_for('ordering', item='ordering'))
                #else:
                    #flash(u'خطایی رخ داده است!', 'error')

                cursor.orders.insert_one(record)

                r = cursor.orders.find_one({'orderId':record['orderId']})
                temp_order = {
                'vendorName' : u'رژیاپ',
                'registerFirstName' : r['registerFirstName'],
                'registerLastName' : r['registerLastName'],
                'registerCellNumber' : r['registerCellNumber'],
                'stateCode' : int(r['stateCode']),
                'cityCode' : int(r['cityCode']),
                'registerAddress' : r['registerAddress'],
                'registerPostalCode' : r['registerPostalCode'],
                'products' : r['products'],
                'serviceType' : int(request.form.get('serviceType')),
                'payType' : pTypeCode,
                'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
                'orderTime': jdatetime.datetime.now().strftime('%M : %H')
                }

                print(temp_order)
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

@app.route('/user-pannel/inventory/<category>', methods=['GET', 'POST'])
@token_required
def inventory(category):
    session['temp_orders'] = cursor.temp_orders.estimated_document_count()

    return render_template('user_pannel.html',
        item="inventory",
        category=category,
        inventory = utils.inventory(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/accounting', methods=['GET', 'POST'])
@token_required
def accounting():
    session['temp_orders'] = cursor.temp_orders.estimated_document_count()

    return render_template('user_pannel.html',
        item="accounting",
        inventory = utils.inventory(cursor),
        accounting = utils.accounting(cursor),
        states = utils.states(cursor)
        )

@app.route('/about')
def about():
    session['temp_orders'] = cursor.temp_orders.estimated_document_count()
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
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/ajax', methods=['GET', 'POST'])
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

@app.route('/orders-details/<code>', methods=['GET', 'POST'])
@token_required
def details(code):

    return render_template('includes/_orderDetails.html',
        details = utils.details(cursor, code)
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug = True)