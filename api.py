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

class User(ComplexModel):
    __namespace__ = "user"
    username = String
    password = String

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
                user_result = cursor.users.find_one({"username": username})
                if user_result:
                    if sha256_crypt.verify(password, user_result['password']):
                        p_list = []
                        for i in range(len(products)):
                            p_dict = {}
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
                            sType = u'پست سفارشی'
                        elif serviceType==3:
                            sType = u'مطبئع'

                        if payType==88:
                            pType = u'ارسال رایگان'
                        elif payType==1:
                            pType = u'پرداخت در محل'
                        elif payType==2:
                            pType = u'پرداخت آنلاین'

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

                        cursor.temp_orders.insert_one(input_data)
                        cursor.all_records.insert_one(input_data)
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

    #def NewOrder(username,password,productsId,cityCode,serviceType,payType,
        #registerFirstName,registerLastName,registerAddress,registerPhoneNumber,registerMobile):

    #@spyne.srpc(Unicode, Integer, _returns=Iterable(Unicode))
    #@spyne.srpc(Array(User), _returns=String)
    #def datetime(v):
        #print('varification: ', v)
        #for i in range (len(v)):
            #if (v[i].username == 'jan') and (v[i].password == '123'):
                #print('The test passed!')
                #print(jdatetime.datetime.now())
            #else:
                #print('wrong username or password!')

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
            flash(u'توکن منقضی شده  است. لطفا مجددا وارد شوید.', 'danger')
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
            flash('توکن معتبر نیست!', 'danger')
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
    #utils.api_test()
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

    return render_template('home.html')

@app.route('/user-pannel/orderList', methods=['GET', 'POST'])
@token_required
def temp_orders():

    return render_template('user_pannel.html',
        item='orderList',
        inventory = utils.inventory(cursor),
        temp_orders = utils.temp_orders(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/<item>', methods=['GET', 'POST'])
@token_required
def ordering(item):
    if 'username' in session:
        ordered_products = []
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

                for i in range (1, 100):
                    if request.form.get('product_'+str(i)):
                        ordered_product = {}
                        ordered_product['productName'] = request.form.get('product_'+str(i))
                        ordered_product['count'] = int(request.form.get('count_'+str(i)))
                        ordered_product['price'] = int(request.form.get('price_'+str(i)))
                        ordered_product['weight'] = int(request.form.get('weight_'+str(i)))
                        ordered_product['percentDiscount'] = 0
                        ordered_product['description'] = u'تست'

                        ordered_products.append(ordered_product)
                        print(ordered_products)

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

                print(order)

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

    return render_template('user_pannel.html',
        item="inventory",
        category=category,
        inventory = utils.inventory(cursor),
        states = utils.states(cursor)
        )

@app.route('/user-pannel/accounting', methods=['GET', 'POST'])
@token_required
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
@token_required
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
                users['user_id'] = str(uuid.uuid4())
                cursor.users.insert_one(users)
                flash(u'ثبت نام شما با موفقیت انجام شد. لطفا وارد شوید', 'success')
            else:
                flash(u'کلمه عبور مطابقت ندارد', 'error')

    return render_template('register.html')

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