from suds.client import Client
from pymongo import MongoClient
import utils

API_URI = 'http://svc.ebazaar-post.ir/EShopService.svc?WSDL'
username = 'vestano3247'
password = 'Vestano3247'

cursor = utils.config_mongodb()

def SoapClient(order):
    client = Client(API_URI)

    price = client.service.GetDeliveryPrice(
        username = username,
        password = password,
        cityCode = 31,
        price = 500000,
        weight = 3500,
        serviceType = 1,
        payType = 1
        )

    stuff_id = client.service.AddStuff(
        username = username,
        password = password,
        name = order['name'],
        price = order['price'],
        weight = order['weight'],
        count = order['count'],
        description = order['description'],
        percentDiscount = order['percentDiscount']
        )

    ans = {
    'deliveryPrice':price.PostDeliveryPrice,
    'VatTax':price.VatTax,
    'id':str(stuff_id)
    }

    return ans

order = {
    'name' : 'باتری موبایل  ',
    'price' : 1000000,
    'weight' : 441,
    'count' : 10,
    'description' : 'تست',
    'percentDiscount' : 0
    }

print(SoapClient(order))