from flask import Flask, render_template, flash, redirect, url_for, session, request, logging, jsonify
from pymongo import MongoClient
from passlib.hash import sha256_crypt
import datetime
import jdatetime
import xlrd
import json
import utils

#Config mongodb
cursor = utils.config_mongodb()

app = Flask(__name__)

app.secret_key = 'secret@vestano@password_hash@840'
   
@app.route('/')
def home():
    return render_template('home.html')

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

                ordered_products = {'product':[], 'counts':[], 'price':[], 'weight':[]}
                for i in range (1, 100):
                    if request.form.get('product_'+str(i)):
                        ordered_products['product'].append(request.form.get('product_'+str(i)))
                        ordered_products['counts'].append(request.form.get('count_'+str(i)))
                        ordered_products['price'].append(request.form.get('price_'+str(i)))
                        ordered_products['weight'].append(request.form.get('weight_'+str(i)))

                record['ordered_products'] = ordered_products
                record['serviceType'] = request.form.get('serviceType')
                record['payType'] = request.form.get('payType')
                record['free'] = request.form.getlist('free')

                price = 0
                counts = 0
                weight = 0
                for i in range(len(ordered_products['product'])):
                    price = price + int(ordered_products['price'][i])
                    counts = counts + int(ordered_products['counts'][i])
                    weight = weight + int(ordered_products['weight'][i])

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

                print(utils.SoapClient(order))

                flash('ثبت شد!', 'success')

                return redirect(url_for('ordering', item='ordering'))
    else:
        flash('لطفا ابتدا وارد شوید', 'error')
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
            flash('نام کاربری تکراری است. لطفا نام کاربری دیگری انتخاب کنید', 'danger')
        else:
            if new_password == confirm:            
                cursor.users.insert_one(users)
                flash('ثبت نام شما با موفقیت انجام شد. لطفا وارد شوید', 'success')
            else:
                flash('کلمه عبور مطابقت ندارد', 'error')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        result = cursor.users.find_one({"username": username})

        if result:
            if sha256_crypt.verify(password, result['password']):
                flash(result['name'] + ' عزیز خوش آمدید', 'success-login')
                session['username'] = username
                session['message'] = result['name']
                return redirect(url_for('ordering', item='ordering'))
            else:
                flash('کلمه عبور مطابقت ندارد', 'danger')
        else:
            flash('نام کاربری ثبت نشده است. لطفا  ابتدا ثبت نام کنید', 'error')

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
        flash('لطفا ابتدا وارد شوید', 'error')
        return redirect(request.referrer)
        
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug = True)