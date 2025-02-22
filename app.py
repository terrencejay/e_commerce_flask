from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import fields, ValidationError
from mysql.connector import Error
import mysql.connector


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:Password123!@localhost/Store'
db = SQLAlchemy(app)
ma = Marshmallow(app)

class Customer(db.Model):
    __tablename__ = 'Customer'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    phone_number = db.Column(db.String(10))
    email = db.Column(db.String(255), nullable=False)
    account = db.relationship('CustomerAccount', backref='customer', uselist=False)
    orders = db.relationship('Order', backref='customer')

class CustomerAccount(db.Model):
    __tablename__ = 'Accounts'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(25), unique=True, nullable=False)
    password = db.Column(db.String(25), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('Customer.id'))

order_products = db.Table('Order_product',
    db.Column('order_id', db.Integer, db.ForeignKey('Orders.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('Products.id'), primary_key=True)
)

class Order(db.Model):
    __tablename__ = 'Orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('Customer.id'))
    products = db.relationship('Product', secondary=order_products, backref=db.backref('orders', lazy='dynamic'))
    



class Product(db.Model):
    __tablename__ = 'Products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)


class CustomerSchema(ma.Schema):
    class Meta:
        fields = ("id", "name", "age", "phone_number", "email")
    orders = ma.Nested('OrderSchema', many=True)

class ProductSchema(ma.Schema):
    class Meta:
        fields = ('id', 'name', 'price')

class OrderSchema(ma.Schema):
    class Meta:
        fields = ('id', 'customer_id')  # Add other order details as needed
    products = ma.Nested('ProductSchema', many=True)

customer_schema = CustomerSchema()
customers_schema = CustomerSchema(many=True)
product_schema = ProductSchema()
products_schema = ProductSchema(many=True)
order_schema = OrderSchema()
orders_schema = OrderSchema(many=True)


@app.route("/")
def home():
    return "welcome to my store application"

@app.route("/customer", methods=["POST"])
def new_customer():
    try:
        data = request.get_json()
        customer_data = customer_schema.load(data)
        customer = Customer(**customer_data)
        db.session.add(Customer(**customer_data))
        db.session.commit()
        return customer_schema.dump(customer), 201
    except ValidationError as err:
        return jsonify(err.messages), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    
@app.route('/customers', methods = ['GET'])
def get_customers():
    customers = Customer.query.all()
    return customers_schema.dump(customers), 200

@app.route('/customer/<int:id>', methods=['GET'])
def get_customer(id):
    customer = Customer.query.get_or_404(id)
    return customer_schema.dump(customer), 200

@app.route('/customer/<int:id>', methods = ['PUT'])
def update_customer(id):
    customer = Customer.query.get_or_404(id)
    try:
        data = request.get_json()
        updated_customer = customer_schema.load(data, isinstance=customer, partial=True)
        db.session.commit()
        return customer_schema.dump(updated_customer), 200
    except ValidationError as err:
        return jsonify(err.messages), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    
@app.route('/customers/<int:id>', methods = ['DELETE'])
def delete_customer(id):
    customer = Customer.query.get_or_404(id)
    db.session.delete(customer)
    db.session.commit()
    return ' ', 204

@app.route('/products', methods = ['POST'])
def add_product():
    try:
        data = request.get_json()
        product_data = product_schema.load(data)
        new_product = Product(**product_data)
        db.session.add(Product(**product_data))
        db.session.commit()
        return product_schema.dump(new_product), 201
    except ValidationError as err:
        return jsonify(err.messages), 400
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    
@app.route('/product/<int:id>', methods=['GET'])  # Single product
def get_product(id):
    product = Product.query.get_or_404(id)
    return product_schema.dump(product), 200

@app.route('/products', methods=['GET'])  # All products
def get_products():
    products = Product.query.all()
    return products_schema.dump(products, many=True), 200

@app.route('/customer/<int:customer_id>/cart', methods=['GET'])  # Get the cart
def get_cart(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    order = customer.orders.filter_by().first()  # Get the open order (or create one)
    if order:
        return order_schema.dump(order), 200
    else:
        return jsonify({"message": "Cart is empty"}), 200  # Or create a new order here

    
@app.route('/product/<int:id>', methods = ['DELETE'])
def delete_products(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    return ' ', 204

@app.route('/customers/<int:customer_id>/orders', methods=['POST'])
def add_product_to_order(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.get_json()
    product_id = data.get('product_id')
    product = Product.query.get_or_404(product_id)

    order = customer.orders.filter_by().first()
    if not order:
        order = Order(customer_id=customer_id)
        db.session.add(order)
        db.session.commit()

    if product in order.products:  # Check if product is already in the order
        return jsonify({"message": "Product already in cart"}), 400  # Or handle differently
    else:
        order.products.append(product)
        db.session.commit()
        return order_schema.dump(order), 201
    
@app.route('/customers/<int:customer_id>/orders/<int:product_id>', methods=['DELETE'])
def remove_product_from_order(customer_id, product_id):
    customer = Customer.query.get_or_404(customer_id)
    order = customer.orders.filter_by().first()
    if not order:
        return jsonify({"message": "No open order"}), 404

    product = Product.query.get_or_404(product_id)
    if product in order.products:
        order.products.remove(product)
        db.session.commit()
        return '', 204
    else:
        return jsonify({"message": "Product not in cart"}), 404    


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        app.run(debug=True)
