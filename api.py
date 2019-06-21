# -*- coding: utf-8 -*-
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging, jsonify
from pymongo import MongoClient
from passlib.hash import sha256_crypt
from flask_spyne import Spyne
from spyne.protocol.soap import Soap11
from spyne.model.primitive import Unicode, Integer, String
from spyne.model.complex import Array, Iterable, ComplexModel
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

class User(ComplexModel):
    __namespace__ = "user"
    username = String
    password = String

class SomeSoapService(spyne.Service):
    __service_url_path__ = '/soap/VestanoWebService'
    __in_protocol__ = Soap11(validator='lxml')
    __out_protocol__ = Soap11()

    @spyne.srpc(String, String, Unicode, Integer, Unicode, Unicode, String, Integer, Integer, Unicode, String,
        Array(Products), Integer, Integer, String, String, _returns=String)
    def NewOrder(username, password, vendorName, orderId, registerFirstName, registerLastName, registerCellNumber,
        stateCode, cityCode, registerAddress, registerPostalCode, products, serviceType, payType, orderDate, orderTime):
        print('entered to NewOrder')
        print(username, password, vendorName, registerLastName, products[0].productName)
        user_result = cursor.users.find_one({"username": username})
        if user_result:
            if sha256_crypt.verify(password, user_result['password']):

                p_list = []
                p_dict = {}
                for i in range(len(products)):
                    p_dict['productName'] = products[i].productName
                    p_dict['count'] = products[i].count
                    p_dict['price'] = products[i].price
                    p_dict['weight'] = products[i].weight
                    p_dict['percentDiscount'] = products[i].percentDiscount
                    p_dict['description'] = products[i].description

                    p_list.append(p_dict)

                #(sType, pType) = utils.typeOfServices(serviceType, payType)
                if serviceType==1:
                    sType = u'پست پیشتاز'
                elif serviceType==2:
                    stype = u'پست سفارشی'
                elif serviceType==3:
                    sType = u'مطبئع'

                if payType==88:
                    pType = u'ارسال رایگان'
                elif payType==1:
                    pType = u'پرداخت در محل'
                elif payType==2:
                    pType = u'پرداخت آنلاین'

                input_data = {
                'vendorName' : vendorName,
                'orderId' : orderId,
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
                'record_time': orderTime
                }

                cursor.temp_orders.insert_one(input_data)
            else:
                return(jsonify('The Password Does Not Match!'))
        else:
            return(jsonify('Invalid or Wrong username!'))

    #def NewOrder(username,password,productsId,cityCode,serviceType,payType,
        #registerFirstName,registerLastName,registerAddress,registerPhoneNumber,registerMobile):

    #@spyne.srpc(Unicode, Integer, _returns=Iterable(Unicode))
    @spyne.srpc(Array(User), _returns=String)
    def datetime(v):
        print('varification: ', v)
        for i in range (len(v)):
            if (v[i].username == 'jan') and (v[i].password == '123'):
                print('The test passed!')
                print(jdatetime.datetime.now())
            else:
                print('wrong username or password!')
   
@app.route('/', methods=['GET', 'POST'])
def home():
    utils.api_test()
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        result = cursor.users.find_one({"username": username})

        if result:
            if sha256_crypt.verify(password, result['password']):
                flash(result['name'] + u' عزیز خوش آمدید', 'success-login')
                session['username'] = username
                session['message'] = result['name']
                return redirect(url_for('ordering', item='ordering'))
            else:
                flash(u'کلمه عبور مطابقت ندارد', 'danger')
        else:
            flash(u'نام کاربری ثبت نشده است. لطفا  ابتدا ثبت نام کنید', 'error')

    return render_template('home.html')

@app.route('/user-pannel/orderList', methods=['GET', 'POST'])
def temp_orders():

    return render_template('user_pannel.html',
        item='orderList',
        inventory = utils.inventory(cursor),
        temp_orders = utils.temp_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/<item>', methods=['GET', 'POST'])
def ordering(item):
    if 'username' in session:
        username = session['username']
        if item == 'ordering':
            if request.method == 'POST':
                record = {'datetime': jdatetime.datetime.now().strftime('%d / %m / %Y')}
                if cursor.orders.estimated_document_count():
                    record['id'] = cursor.orders.estimated_document_count()+1
                else:
                    record['id'] = 1
                record['first_name'] = request.form.get('first_name')
                record['last_name'] = request.form.get('last_name')
                record['cell_number'] = request.form.get('cell_number')
                record['stateCode'] = int(request.form.get('stateCode'))
                record['cityCode'] = int(request.form.get('cityCode'))
                record['address'] = request.form.get('address')
                record['postal_code'] = request.form.get('postal_code')

                ordered_products = []
                ordered_product = {}
                for i in range (1, 100):
                    if request.form.get('product_'+str(i)):
                        ordered_product['productName'] = request.form.get('product_'+str(i))
                        ordered_product['count'] = int(request.form.get('count_'+str(i)))
                        ordered_product['price'] = int(request.form.get('price_'+str(i)))
                        ordered_product['weight'] = int(request.form.get('weight_'+str(i)))
                        ordered_product['percentDiscount'] = 0
                        ordered_product['description'] = u'تست'

                        ordered_products.append(ordered_product)

                #ordered_products = {'product':[], 'counts':[], 'price':[], 'weight':[],
                #'percentDiscount':[], 'description':[]}
                #for i in range (1, 100):
                    #if request.form.get('product_'+str(i)):
                        #ordered_products['product'].append(request.form.get('product_'+str(i)))
                        #ordered_products['counts'].append(request.form.get('count_'+str(i)))
                        #ordered_products['price'].append(request.form.get('price_'+str(i)))
                        #ordered_products['weight'].append(request.form.get('weight_'+str(i)))
                        #ordered_products['percentDiscount'].append(0)
                        #ordered_products['description'].append(u'تست')

                record['ordered_products'] = ordered_products
                record['serviceType'] = request.form.get('serviceType')
                record['payType'] = request.form.get('payType')
                record['free'] = request.form.getlist('free')

                price = 0
                counts = 0
                weight = 0
                for i in range(len(ordered_products)):
                    price = price + int(ordered_products[i]['price'])
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
                'firstName': record['first_name'],
                'lastName': record['last_name'],
                'address': record['address'],
                'phoneNumber': '',
                'cellNumber': record['cell_number'],
                'postalCode': record['postal_code'],
                'products': ordered_products
                }

                #print(temp_order)

                cursor.orders.insert_one(record)

                #print(utils.SoapClient(order))

                r = cursor.orders.find_one({'id':record['id']})
                temp_order = {
                'vendorName' : u'رژیاپ',
                'orderId' : 100,
                'registerFirstName' : r['first_name'],
                'registerLastName' : r['last_name'],
                'registerCellNumber' : r['cell_number'],
                'stateCode' : int(r['stateCode']),
                'cityCode' : int(r['cityCode']),
                'registerAddress' : r['address'],
                'registerPostalCode' : r['postal_code'],
                'products' : r['ordered_products'],
                'serviceType' : int(r['serviceType']),
                'payType' : int(r['payType']),
                'orderDate': jdatetime.datetime.now().strftime('%d / %m / %Y'),
                'orderTime': jdatetime.datetime.now().strftime('%M : %H')
                }

                #print(temp_order)
                flash(u'ثبت شد!', 'success')

                utils.test_temp_order(temp_order)

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
def inventory(category):

    return render_template('user_pannel.html',
        item="inventory",
        category=category,
        inventory = utils.inventory(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/accounting', methods=['GET', 'POST'])
def accounting():

    return render_template('user_pannel.html',
        item="accounting",
        inventory = utils.inventory(cursor),
        accounting = utils.accounting(cursor),
        states = utils.states(cursor)
        )

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
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
                cursor.users.insert_one(users)
                flash(u'ثبت نام شما با موفقیت انجام شد. لطفا وارد شوید', 'success')
            else:
                flash(u'کلمه عبور مطابقت ندارد', 'error')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        result = cursor.users.find_one({"username": username})

        if result:
            if sha256_crypt.verify(password, result['password']):
                flash(result['name'] + u' عزیز خوش آمدید', 'success-login')
                session['username'] = username
                session['message'] = result['name']
                return redirect(url_for('ordering', item='ordering'))
            else:
                flash(u'کلمه عبور مطابقت ندارد', 'danger')
        else:
            flash(u'نام کاربری ثبت نشده است. لطفا  ابتدا ثبت نام کنید', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    session.pop('message', None)
    return redirect(url_for('home'))

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug = True)