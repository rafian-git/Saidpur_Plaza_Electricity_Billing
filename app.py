import os
import csv
import sqlite3
import qrcode
import base64
from io import BytesIO
from io import StringIO
from flask import make_response
import io
import math
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session
from flask import request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from functools import wraps
from flask import session, flash, redirect, url_for
from flask import send_file, request
import requests
from flask import request, jsonify
from flask import render_template, make_response

# প্রজেক্টের মেইন ডিরেক্টরি সেটআপ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
DB_PATH = os.path.join(BASE_DIR, 'database.db')

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.secret_key = 'saidpur_plaza_secure_intelligence_key_2026'

def get_db_connection():
    # গ্লোবাল DB_PATH ব্যবহার করা ভালো
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                flash('দয়া করে আগে লগইন করুন।', 'danger')
                return redirect(url_for('login'))
            
            # .lower() ব্যবহার করা হলো যাতে ছোট-বড় হাতের অক্ষরের কোনো ঝামেলা না হয়
            user_role = session['role']
            if user_role not in allowed_roles:
                flash('এই পেজে প্রবেশ করার আপনার অনুমতি নেই!', 'danger')
                return redirect(url_for('dashboard')) # অথবা অন্য কোনো পেজ
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# অ্যাপ শুরুর সময় ডেটাবেজ চেক
if not os.path.exists(DB_PATH):
    init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        # প্লেইন টেক্সট পাসওয়ার্ড সরাসরি চেক করা হচ্ছে
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        
        flash('ভুল ইউজারনেম বা পাসওয়ার্ড!', 'danger')

    return render_template('login.html')

@app.route('/')
def index():
    return redirect(url_for('customer_login')) # সরাসরি customer login পেজে রিডাইরেক্ট করা হলো

@app.route('/generate_qr')
def generate_qr():
    # সরাসরি পেমেন্ট লিংক বা ডেটা রিসিভ করা
    data = request.args.get('data')
    if not data:
        # যদি ডাটা না থাকে, তবে ডিফল্ট একটি লিংক বা কাস্টমার পোর্টাল বসিয়ে দেওয়া যেতে পারে
        data = "https://bill.srtrading.com.bd/customer/portal/payment"
        
    # কিউআর কোড জেনারেট করা
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return send_file(buffer, mimetype='image/png')

# ডাটাবেজ ইনিশিয়ালাইজেশন
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # ১. ইউজার টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    # ২. কাস্টমারস বা ওনার টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            meter_no TEXT,
            owner_name TEXT,
            plaza_name TEXT,
            floor_no TEXT,
            block_no TEXT,
            shop_no TEXT,
            unit_rate REAL DEFAULT 0.0,
            allocated_load REAL DEFAULT 0.0,
            rate_per_kw REAL DEFAULT 0.0,
            initial_reading REAL DEFAULT 0.0,
            password TEXT DEFAULT '123456',
            connection_status TEXT DEFAULT 'Connected',
            disconnect_reason TEXT DEFAULT ''
        )
    ''')

    # ৩. বিদ্যুৎ বিল টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_no TEXT,
            customer_id INTEGER,
            meter_no TEXT,
            owner_name TEXT,
            plaza_name TEXT,
            floor_no TEXT,
            block_no TEXT,
            shop_no TEXT,
            bill_month TEXT,
            bill_issue_date TEXT,
            due_date TEXT NOT NULL,
            curr_reading_date TEXT,
            prev_reading_date TEXT,
            current_reading REAL DEFAULT 0.0,
            previous_reading REAL DEFAULT 0.0,
            units_consumed REAL DEFAULT 0.0,
            energy_charge REAL DEFAULT 0.0,
            demand_charge REAL DEFAULT 0.0,
            misc_charge REAL DEFAULT 0.0,
            principal_amount REAL DEFAULT 0.0,
            vat REAL DEFAULT 0.0,
            current_month_total REAL DEFAULT 0.0,
            arrears REAL DEFAULT 0.0,
            total_payable INTEGER,
            late_fee REAL DEFAULT 0.0,
            total_payable_after_due INTEGER,
            note_1 TEXT,
            note_2 TEXT,
            note_3 TEXT,
            is_locked INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Unpaid',
            paid_amount REAL DEFAULT 0.0,
            payment_date TEXT,
            payment_method TEXT,
            received_by TEXT,
            prepared_by TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
    ''')

    # ৪. মাসিক বিল কনফিগারেশন টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_month TEXT NOT NULL,
            misc_charge REAL DEFAULT 0.0,
            bill_issue_date TEXT,
            due_date TEXT,
            curr_reading_date TEXT,
            prev_reading_date TEXT,
            note_1 TEXT,
            note_2 TEXT,
            note_3 TEXT
        )
    ''')
    
    # ৫. পেমেন্ট টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            customer_id TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            payment_method TEXT,
            received_by TEXT,
            FOREIGN KEY (bill_id) REFERENCES bills (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # আইডি কার্ড ম্যানেজমেন্টের টেবিল
    conn.execute('''
        CREATE TABLE IF NOT EXISTS id_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            card_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            designation TEXT,
            mobile_no TEXT,
            shop_no TEXT,
            blood_group TEXT,
            father_name TEXT,
            mother_name TEXT,
            nid_or_birth TEXT,
            pres_village TEXT,
            pres_post TEXT,
            pres_upazila TEXT,
            pres_district TEXT,
            perm_village TEXT,
            perm_post TEXT,
            perm_upazila TEXT,
            perm_district TEXT,
            signature_img TEXT,
            photo_img TEXT,
            fp_right_thumb TEXT,
            fp_right_index TEXT,
            fp_left_thumb TEXT,
            fp_left_index TEXT,
            secret_card_number TEXT,
            expire_date DATE,
            authorized_signature TEXT
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,          -- কোন গেট বা মেশিনের আইডি (যেমন: Gate-1)
            card_id TEXT,            -- সদস্যের আইডি নাম্বার
            name TEXT,               -- সদস্যের নাম
            category TEXT,           -- staff, merchant, employee
            status TEXT,             -- 'Granted' (অনুমোদিত) অথবা 'Denied' (প্রত্যাখ্যাত)
            reason TEXT,             -- কারণ (যেমন: Valid, Expired Card, Not Found)
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ইউজার টেবিল বা অন্য ডিফল্ট ডাটা ইনসার্ট করার কাজ এখানে থাকবে...
    users = [
        ('admin', '123456', 'admin'),
        ('mod', '123456', 'moderator'),
        ('view', '123456', 'viewer')
    ]
    for username, password, role in users:
        cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
                       (username, password, role))
    
    conn.commit()

    # কলাম যুক্ত করার কাজগুলো কানেকশন বন্ধ হওয়ার আগেই করতে হবে
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN mobile_no TEXT;")
        conn.commit()
    except Exception as e:
        pass  

    try:
        conn.execute("ALTER TABLE bills ADD COLUMN billing_msg_sent INTEGER DEFAULT 0;")
        conn.commit()
    except Exception as e:
        pass  

    try:
        conn.execute("ALTER TABLE bills ADD COLUMN overdue_msg_sent INTEGER DEFAULT 0;")
        conn.commit()
    except Exception as e:
        pass

    # customers টেবিলে disconnect_reason কলাম যোগ করার নিরাপদ কুয়েরি
    try:
        conn.execute("ALTER TABLE customers ADD COLUMN disconnect_reason TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass # কলামটি আগে থেকেই থাকলে ইগনোর করবে
        
    # সবশেষে একদম একবারই কানেকশন বন্ধ হবে
    conn.close()
    print("Database Initialized Successfully with Normal Passwords!")

def get_current_month_config():
    conn = get_db_connection()
    # সবচেয়ে নতুন বা সর্বশেষ সেটিংসটি নিয়ে আসবে
    config = conn.execute('SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    return dict(config) if config else None

# ডাটাবেজ ইনিশিয়ালের সময় যেন কোনো ক্র্যাশ না হয়
try:
    init_db()
except Exception as e:
    print(f"Database Init Warning: {e}")

@app.route('/dashboard')
@role_required(['admin', 'moderator', 'viewer'])
def dashboard():
    # ১. সেশন থেকে রোল নিন
    user_role = session.get('role', 'admin') 
    
    # ২. ডাটাবেস কানেকশন এবং ডেটা ক্যালকুলেশন
    conn = get_db_connection()
    config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    
    # sqlite3.Row থেকে নিরাপদে bill_month বের করার লজিক
    current_bill_month = config['bill_month'] if config and 'bill_month' in config.keys() else None

    def get_val(query, params=()):
        try:
            row = conn.execute(query, params).fetchone()
            return row[0] if row and row[0] is not None else 0
        except Exception:
            return 0

    if current_bill_month:
        stats = {
            'total_customers': get_val("SELECT COUNT(*) FROM customers"),
            'total_billed': get_val("SELECT SUM(total_payable) FROM bills WHERE bill_month = ?", (current_bill_month,)),
            'total_collected': get_val("SELECT SUM(total_payable) FROM bills WHERE bill_month = ? AND status = 'Paid'", (current_bill_month,)),
            'total_bills': get_val("SELECT COUNT(*) FROM bills WHERE bill_month = ?", (current_bill_month,)),
            'total_unpaid_amount': get_val("SELECT SUM(total_payable) FROM bills WHERE bill_month = ? AND status != 'Paid'", (current_bill_month,))
        }
    else:
        stats = {
            'total_customers': get_val("SELECT COUNT(*) FROM customers"),
            'total_billed': 0,
            'total_collected': 0,
            'total_bills': 0,
            'total_unpaid_amount': 0
        }
    
    # শুধুমাত্র পেন্ডিং থাকা অনলাইন পেমেন্টগুলো ফিল্টার করে আনা
    pending_online_payments = conn.execute('''
        SELECT p.*, b.customer_id, b.total_payable 
        FROM payments p 
        JOIN bills b ON p.bill_id = b.id 
        WHERE p.status = 'Pending'
    ''').fetchall()
    
    conn.close()
    
    # এখানে stats এবং config উভয়ই পাস করা হলো যেন ড্যাশবোর্ডে সঠিকভাবে ডেটা শো করে
    return render_template('dashboard.html', payments=pending_online_payments, stats=stats, config=config)

# ১. পেমেন্ট অ্যাপ্রুভ বা রিজেক্ট করার রাউট (অটোমেটিক SMS সহ)
@app.route('/admin/process_payment/<int:payment_id>/<action>')
@role_required(['admin'])
def process_payment(payment_id, action):
    conn = get_db_connection()
    try:
        # পেমেন্ট এবং এর সাথে সম্পর্কিত বিলের তথ্য বের করা
        payment = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        
        if not payment:
            flash('সংশ্লিষ্ট পেমেন্ট রেকর্ডটি পাওয়া যায়নি!', 'danger')
            conn.close()
            return redirect(request.referrer or url_for('dashboard'))
            
        payment_dict = dict(payment)
        bill_id = payment_dict['bill_id']
        paid_amount = payment_dict['amount']

        # বিল এবং গ্রাহকের আইডি বের করা
        bill = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
        if not bill:
            flash('সংশ্লিষ্ট বিলটি পাওয়া যায়নি!', 'danger')
            conn.close()
            return redirect(request.referrer or url_for('dashboard'))
            
        bill_dict = dict(bill)
        customer_id = bill_dict['customer_id']

        if action == 'approve':
            # পেমেন্ট এবং বিল দুটোই 'Paid' করা
            conn.execute("UPDATE payments SET status='Paid' WHERE id=?", (payment_id,))
            conn.execute("UPDATE bills SET status='Paid', paid_amount=? WHERE id=?", (paid_amount, bill_id))
            conn.commit()
            
            flash('পেমেন্ট সফলভাবে অনুমোদিত (Approved) হয়েছে!', 'success')
            
            # গ্রাহকের মোবাইল নম্বর বের করে অটোমেটিক পেমেন্ট সাকসেস এসএমএস পাঠানো
            customer = conn.execute("SELECT mobile_no FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
            mobile_no = customer['mobile_no'] if customer else None

            if mobile_no:
                BULK_SMS_API_KEY = "kJazA95mE7D2mnPPqaRu"
                BULK_SMS_SENDER_ID = "SR Trading"
                
                # আপনার চাওয়া নির্দিষ্ট ফরম্যাটের মেসেজ
                msg = f"গ্রাহক আইডি {customer_id}, সম্মানিত গ্রাহক, আপনার বিদ্যুৎ বিল {paid_amount} টাকা সফলভাবে পরিশোধিত হয়েছে।"
                
                api_url = "https://bulksmsbd.net/api/smsapi"
                payload = {
                    "api_key": BULK_SMS_API_KEY,
                    "senderid": BULK_SMS_SENDER_ID,
                    "number": mobile_no,
                    "message": msg
                }

                try:
                    response = requests.post(api_url, data=payload, timeout=10)
                    if response.status_code == 200:
                        flash('গ্রাহককে পেমেন্ট সফলতার অটোমেটিক এসএমএস পাঠানো হয়েছে!', 'success')
                    else:
                        flash(f'পেমেন্ট এপ্রুভ হয়েছে তবে এসএমএস পাঠানো যায়নি: {response.text}', 'warning')
                except Exception as e:
                    flash(f'এসএমএস গেটওয়ে কানেকশন এরর: {str(e)}', 'warning')
            else:
                flash('গ্রাহকের মোবাইল নম্বর না থাকায় অটোমেটিক এসএমএস পাঠানো সম্ভব হয়নি।', 'warning')

        elif action == 'reject':
            # পেমেন্ট 'Rejected' এবং বিল আবার 'Unpaid' করে দেওয়া
            conn.execute("UPDATE payments SET status='Rejected' WHERE id=?", (payment_id,))
            conn.execute("UPDATE bills SET status='Unpaid' WHERE id=?", (bill_id,))
            conn.commit()
            flash('পেমেন্ট বাতিল (Rejected) করা হয়েছে!', 'danger')
            
    except Exception as e:
        flash(f'এরর: {str(e)}', 'danger')
    finally:
        conn.close()
        
    return redirect(request.referrer or url_for('dashboard'))


# ২. পেন্ডিং পেমেন্টস পেজ রেন্ডার করার রাউট
@app.route('/admin/pending_payments')
@role_required(['admin'])
def pending_payments():
    conn = get_db_connection()
    payments = conn.execute('''
        SELECT p.*, b.customer_id, b.total_payable 
        FROM payments p 
        JOIN bills b ON p.bill_id = b.id 
        WHERE p.status = 'Pending'
    ''').fetchall()
    conn.close()
    return render_template('admin_pending.html', payments=payments)
 
@app.route('/download_report/<string:month>')
@role_required(['admin', 'moderator', 'viewer'])
def download_report(month):
    conn = get_db_connection()
    bills = conn.execute('SELECT * FROM bills WHERE bill_month = ?', (month,)).fetchall()
    conn.close()

    if not bills:
        flash(f'{month} মাসের কোনো বিল ডাটা পাওয়া যায়নি!', 'warning')
        return redirect(url_for('dashboard'))

    def generate():
        header = ['ID', 'Customer ID', 'Month', 'Principal', 'VAT', 'Total Payable', 'Status']
        yield ','.join(header) + '\n'
        for bill in bills:
            row = [
                str(bill['id']),
                str(bill['customer_id']),
                bill['bill_month'],
                str(bill['principal_amount']),
                str(bill['vat']),
                str(bill['total_payable']),
                'Paid' if bill['status'] == 'Paid' else 'Unpaid'
            ]
            yield ','.join(row) + '\n'

    return Response(generate(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment;filename=Report_{month}.csv'})

# 👤 ক. গ্রাহক ইনপুট বাটন (এডমিন প্যানেল)
@app.route('/customer/manage', methods=['GET', 'POST'])
@role_required(['admin'])
def customers():
    conn = get_db_connection()
    try:    
        if request.method == 'POST':
            action = request.form.get('action')
            c_id = request.form.get('customer_id', '').strip()
            meter = request.form.get('meter_no', '').strip()
            owner = request.form.get('owner_name', '').strip()
            mobile = request.form.get('mobile_no', '').strip()
            plaza = request.form.get('plaza_name', '').strip()
            floor = request.form.get('floor_no', '').strip()
            block = request.form.get('block_no', '').strip()
            shop = request.form.get('shop_no', '').strip()
            u_rate = float(request.form.get('unit_rate', 0) or 0)
            load = float(request.form.get('allocated_load', 0) or 0)
            rate_kw = float(request.form.get('rate_per_kw', 0) or 0)
            init_r = float(request.form.get('initial_reading', 0) or 0)
            status = request.form.get('connection_status', 'Active')
            disconnect_reason = request.form.get('disconnect_reason', '').strip()

            # যদি স্ট্যাটাস সক্রিয় থাকে, তবে কারণ স্বয়ংক্রিয়ভাবে ফাঁকা করে দেওয়া নিরাপদ
            if status in ['Active', 'Connected']:
                disconnect_reason = ''

            if action == 'add':
                try:
                    conn.execute('''
                        INSERT INTO customers (customer_id, meter_no, owner_name, mobile_no, plaza_name, floor_no, block_no, shop_no,
                                               unit_rate, allocated_load, rate_per_kw, initial_reading, connection_status, disconnect_reason)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (c_id, meter, owner, mobile, plaza, floor, block, shop, u_rate, load, rate_kw, init_r, status, disconnect_reason))
                    conn.commit()
                    flash('নতুন গ্রাহকের ডেটা সফলভাবে সিস্টেমে যুক্ত হয়েছে!', 'success')
                except sqlite3.IntegrityError:
                    flash('ত্রুটি: এই গ্রাহক আইডিটি ইতিমধ্যে বিদ্যমান!', 'danger')

            elif action == 'edit':
                old_c_id = request.form.get('old_customer_id', '').strip()
                new_c_id = request.form.get('customer_id', '').strip()

                try:
                    conn.execute('''
                        UPDATE customers SET
                            customer_id=?, meter_no=?, owner_name=?, mobile_no=?, shop_no=?,
                            unit_rate=?, allocated_load=?, rate_per_kw=?, 
                            initial_reading=?, connection_status=?, disconnect_reason=?
                        WHERE customer_id=?
                    ''', (new_c_id, meter, owner, mobile, shop, u_rate, load, rate_kw, init_r, status, disconnect_reason, old_c_id))
                    conn.commit()
                    flash('গ্রাহকের তথ্য ও আইডি সফলভাবে আপডেট হয়েছে!', 'success')
                except sqlite3.IntegrityError:
                    flash('ত্রুটি: এই নতুন গ্রাহক আইডিটি ইতিমধ্যে অন্য কারো নামে বিদ্যমান!', 'danger')
                
            return redirect(url_for('customers'))
            
        customers_rows = conn.execute('SELECT * FROM customers ORDER BY customer_id ASC').fetchall()
        customers = [dict(row) for row in customers_rows]
        return render_template('customers.html', customers=customers)

    except Exception as e:
        flash(f'এরর: {str(e)}', 'danger')
        return redirect(url_for('customers'))
    finally:
        conn.close()

# মোবাইল মেসেজিং প্যানেল পেজ রেন্ডার করার রাউট
@app.route('/mobile_messaging')
@role_required(['admin', 'moderator'])
def mobile_messaging():
    conn = get_db_connection()
    try:
        config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
        current_bill_month = config['bill_month'] if config else ''

        messaging_customers = []
        if current_bill_month:
            raw_msg_data = conn.execute('''
                SELECT c.customer_id, c.owner_name, c.mobile_no, b.id as bill_id, b.total_payable, b.total_payable_after_due, 
                       b.due_date, b.billing_msg_sent, b.overdue_msg_sent, b.status
                FROM customers c
                LEFT JOIN bills b ON c.customer_id = b.customer_id AND b.bill_month = ?
                ORDER BY c.customer_id ASC
            ''', (current_bill_month,)).fetchall()

            today_date = datetime.now().date()
            global_due_date = config['due_date'] if config else None

            for row in raw_msg_data:
                row_dict = dict(row)
                due_str = row_dict.get('due_date') or global_due_date
                is_overdue = False
                
                if due_str:
                    for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                        try:
                            due_obj = datetime.strptime(str(due_str).strip(), fmt).date()
                            if today_date > due_obj and row_dict.get('status') != 'Paid':
                                is_overdue = True
                            break
                        except ValueError:
                            continue
                row_dict['is_overdue'] = is_overdue
                messaging_customers.append(row_dict)

        return render_template('mobile_messaging.html', messaging_customers=messaging_customers)

    except Exception as e:
        print("MESSAGING ERROR:", str(e))
        flash(f'এরর: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

# ৩. মেসেজ পাঠানোর রাউট (Billing, Overdue, Custom, Bulk)
@app.route('/send_message', methods=['POST'])
@role_required(['admin', 'moderator'])
def send_message():
    role = session.get('role')
    action_type = request.form.get('action_type')  # billing, overdue, custom, bulk
    customer_id = request.form.get('customer_id')
    custom_text = request.form.get('custom_text', '')

    conn = get_db_connection()
    config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    
    if not config:
        flash('প্রথমে মাসিক বিল কনফিগারেশন সেট করুন!', 'danger')
        conn.close()
        return redirect(url_for('mobile_messaging'))
    
    bill_month = config['bill_month']
    global_due_date = config['due_date']
    today_date = datetime.now().date()

    BULK_SMS_API_KEY = "kJazA95mE7D2mnPPqaRu" 
    BULK_SMS_SENDER_ID = "SR Trading"
    api_url = "https://bulksmsbd.net/api/smsapi"

    # ==========================================
    # বাল্ক মেসেজ হ্যান্ডলিং (সকলকে একসাথে পাঠানো)
    # ==========================================
    if action_type == 'bulk':
        bulk_type = request.form.get('bulk_type') # billing অথবা custom হতে পারে
        
        if role == 'moderator' and bulk_type == 'custom':
            flash('মডারেটর হিসেবে কাস্টম বাল্ক মেসেজ পাঠানোর অনুমতি নেই!', 'danger')
            conn.close()
            return redirect(url_for('mobile_messaging'))
        
        # বর্তমান মাসের সকল গ্রাহক এবং তাদের বিলের তথ্য ফেচ করা
        all_customers_bills = conn.execute('''
            SELECT c.customer_id, c.mobile_no, b.id as bill_id, b.total_payable, b.billing_msg_sent
            FROM customers c
            LEFT JOIN bills b ON c.customer_id = b.customer_id AND b.bill_month = ?
            WHERE c.mobile_no IS NOT NULL AND c.mobile_no != ''
        ''', (bill_month,)).fetchall()

        success_count = 0
        fail_count = 0

        for row in all_customers_bills:
            row_dict = dict(row)
            mobile_no = row_dict['mobile_no']
            msg = ""
            update_sql = ""

            if bulk_type == 'billing':
                # যদি ইতিমধ্যে বিলিং মেসেজ পাঠানো না হয়ে থাকে
                if row_dict.get('billing_msg_sent') != 1 and row_dict.get('bill_id'):
                    due_date = global_due_date
                    msg = f"গ্রাহক আইডি {row_dict['customer_id']}, সম্মানিত গ্রাহক, আপনার {bill_month} মাসের বিদ্যুৎ বিল {row_dict['total_payable']} টাকা। বিল পরিশোধের শেষ তারিখ {due_date}।"
                    update_sql = "UPDATE bills SET billing_msg_sent = 1 WHERE id = ?"
                else:
                    continue # ইতিমধ্যে পাঠানো থাকলে বা বিল না থাকলে স্কিপ করবে

            elif bulk_type == 'custom':
                if not custom_text.strip():
                    break
                msg = custom_text

            if msg:
                payload = {
                    "api_key": BULK_SMS_API_KEY,
                    "senderid": BULK_SMS_SENDER_ID,
                    "number": mobile_no,
                    "message": msg
                }
                try:
                    response = requests.post(api_url, data=payload, timeout=10)
                    if response.status_code == 200:
                        success_count += 1
                        if update_sql and row_dict.get('bill_id'):
                            conn.execute(update_sql, (row_dict['bill_id'],))
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1

        conn.commit()
        conn.close()
        flash(f'বাল্ক মেসেজ পাঠানো সম্পন্ন হয়েছে! সফল: {success_count}টি, ব্যর্থ/স্কিপ: {fail_count}টি', 'success')
        return redirect(url_for('mobile_messaging'))

    # ==========================================
    # একক (Single) গ্রাহকের মেসেজ হ্যান্ডলিং
    # ==========================================
    bill = conn.execute("SELECT * FROM bills WHERE customer_id = ? AND bill_month = ?", (customer_id, bill_month)).fetchone()
    
    if not bill:
        flash('সংশ্লিষ্ট মাসের কোনো বিল পাওয়া যায়নি!', 'warning')
        conn.close()
        return redirect(url_for('mobile_messaging'))

    bill_dict = dict(bill)
    
    due_date = bill_dict.get('due_date') or global_due_date
    due_date_obj = today_date
    if due_date:
        for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
            try:
                due_date_obj = datetime.strptime(str(due_date).strip(), fmt).date()
                break
            except ValueError:
                continue

    customer_row = conn.execute("SELECT mobile_no FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    mobile_no = bill_dict.get('mobile_no') or (customer_row['mobile_no'] if customer_row else None)

    if not mobile_no:
        flash('এই গ্রাহকের কোনো মোবাইল নম্বর সংরক্ষিত নেই!', 'danger')
        conn.close()
        return redirect(url_for('mobile_messaging'))

    msg = ""
    update_query = ""

    if action_type == 'billing':
        if bill_dict.get('billing_msg_sent') == 1:
            flash('এই গ্রাহককে ইতিমধ্যে বিলিং মেসেজ পাঠানো হয়েছে!', 'warning')
            conn.close()
            return redirect(url_for('mobile_messaging'))
        
        msg = f"গ্রাহক আইডি {customer_id}, সম্মানিত গ্রাহক, আপনার {bill_month} মাসের বিদ্যুৎ বিল {bill_dict['total_payable']} টাকা। বিল পরিশোধের শেষ তারিখ {due_date}।"
        update_query = "UPDATE bills SET billing_msg_sent = 1 WHERE id = ?"

    elif action_type == 'overdue':
        if today_date <= due_date_obj:
            flash('এখনো বিল পরিশোধের শেষ তারিখ পার হয়নি, তাই বিলম্বিত মেসেজ পাঠানো যাবে না!', 'danger')
            conn.close()
            return redirect(url_for('mobile_messaging'))
        
        msg = f"গ্রাহক আইডি {customer_id}, সম্মানিত গ্রাহক, আপনার বকেয়া বিদ্যুৎ বিল {bill_dict.get('total_payable_after_due', bill_dict['total_payable'])} টাকা দ্রুত পরিশোধ করুন। অন্যথায় যেকোন সময় আপনার বিদ্যুৎ সংযোগটি বিচ্ছিন্ন করা হতে পারে।"
        update_query = "UPDATE bills SET overdue_msg_sent = 1 WHERE id = ?"

    elif action_type == 'custom':
        if role != 'admin':
            flash('শুধুমাত্র এডমিন কাস্টম মেসেজ পাঠাতে পারেন!', 'danger')
            conn.close()
            return redirect(url_for('mobile_messaging'))
        msg = custom_text

    payload = {
        "api_key": BULK_SMS_API_KEY,
        "senderid": BULK_SMS_SENDER_ID,
        "number": mobile_no,
        "message": msg
    }

    try:
        response = requests.post(api_url, data=payload, timeout=10)
        if response.status_code == 200:
            if update_query:
                conn.execute(update_query, (bill_dict['id'],))
                conn.commit()
            flash(f'মেসেজ সফলভাবে পাঠানো হয়েছে! (নম্বর: {mobile_no})', 'success')
        else:
            flash(f'এসএমএস পাঠাতে ব্যর্থ হয়েছে। সার্ভার রেসপন্স: {response.text}', 'danger')
    except Exception as e:
        flash(f'এসএমএস গেটওয়ে কানেকশনে সমস্যা: {str(e)}', 'danger')

    conn.close()
    return redirect(url_for('mobile_messaging'))

# 🔌 নতুন বাটন: "সংযোগ" প্যানেল রুট (এডমিন)
@app.route('/admin/connection_status', methods=['GET', 'POST'])
@role_required(['admin'])
def connection_status():
    conn = get_db_connection()
    search_query = request.args.get('search', '')

    if request.method == 'POST':
        c_id = request.form.get('customer_id')
        c_status = request.form.get('connection_status')
        reason = request.form.get('disconnect_reason', '')

        if c_status == 'Connected':
            reason = ''

        conn.execute('UPDATE customers SET connection_status = ?, disconnect_reason = ? WHERE customer_id = ?',
                     (c_status, reason, c_id))
        conn.commit()
        flash(f'গ্রাহক আইডি {c_id} এর সংযোগ অবস্থা সফলভাবে আপডেট করা হয়েছে!', 'success')

        return redirect(url_for('connection_status', search=search_query))

    if search_query:
        customers_list = conn.execute('''
            SELECT customer_id, owner_name, shop_no, meter_no, connection_status, disconnect_reason
            FROM customers
            WHERE customer_id LIKE ? OR owner_name LIKE ? OR shop_no LIKE ?
            ORDER BY customer_id ASC
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        customers_list = conn.execute('SELECT customer_id, owner_name, shop_no, meter_no, connection_status, disconnect_reason FROM customers ORDER BY customer_id ASC').fetchall()

    conn.close()
    return render_template('customers.html', customers=customers_list, search_query=search_query)

# 📝 খ. বিল ইনপুট বাটন
@app.route('/bill/input', methods=['GET', 'POST'])
@role_required(['admin', 'moderator'])
def meter_reading():
    user_role = session.get('user_role') or session.get('role')
    if not user_role:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # ১. কনফিগারেশন চেক
    config = conn.execute('SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1').fetchone()
    if not config:
        conn.close()
        flash('ত্রুটি: দয়া করে প্রথমে মাসিক বিল কনফিগারেশন সেট করুন!', 'danger')
        return redirect(url_for('dashboard'))

    search_query = request.args.get('search', '')

    # ২. POST রিকোয়েস্ট হ্যান্ডলিং
    if request.method == 'POST':
        c_id = request.form.get('customer_id')
        curr_read_raw = request.form.get('current_reading')
        
        if c_id and curr_read_raw:
            curr_read = float(curr_read_raw)
            cust = conn.execute('SELECT * FROM customers WHERE customer_id = ?', (c_id,)).fetchone()
            
            if cust and cust['connection_status'] != 'Disconnected':
                # লক স্ট্যাটাস চেক
                check_lock = conn.execute('SELECT is_locked FROM bills WHERE customer_id=? AND bill_month=?',
                                         (c_id, config['bill_month'])).fetchone()
                
                if not (check_lock and check_lock['is_locked'] == 1 and user_role == 'moderator'):
                    # হিসাবনিকাশ
                    last_bill = conn.execute('SELECT current_reading FROM bills WHERE customer_id=? ORDER BY id DESC LIMIT 1', (c_id,)).fetchone()
                    prev_read = last_bill['current_reading'] if last_bill else cust['initial_reading']
                    
                    unpaid_bill = conn.execute("SELECT total_payable_after_due, paid_amount FROM bills WHERE customer_id=? AND status!='Paid' ORDER BY id DESC LIMIT 1", (c_id,)).fetchone()
                    arrears = (unpaid_bill['total_payable_after_due'] - unpaid_bill['paid_amount']) if unpaid_bill else 0.0
                    
                    units_consumed = max(0, curr_read - prev_read)
                    energy_charge = units_consumed * cust['unit_rate']
                    demand_charge = cust['allocated_load'] * cust['rate_per_kw']
                    misc_charge = config['misc_charge']
                    principal_amount = energy_charge + demand_charge + misc_charge
                    vat = principal_amount * 0.05
                    total_payable = math.ceil(principal_amount + vat + arrears)
                    late_fee = math.ceil(principal_amount * 0.05)
                    total_payable_after_due = total_payable + late_fee
                    lock_status = 1 if user_role == 'moderator' else 0

                    # --- সংশোধিত লজিক ---
                    bill_month_str = str(config['bill_month']) # নিশ্চিত করুন এটি স্ট্রিং
                    # যদি ফরম্যাট 'July 2026' হয়, তবে এটি ঠিক আছে
                    parts = bill_month_str.split()
                    month_str = parts[0]
                    year_str = parts[1]

                    month_map = {
                        'January': '01', 'February': '02', 'March': '03', 'April': '04', 
                        'May': '05', 'June': '06', 'July': '07', 'August': '08', 
                        'September': '09', 'October': '10', 'November': '11', 'December': '12'
                    }
                    month_code = month_map.get(month_str, '00')
                    customer_code = str(c_id).zfill(6) # আইডি ৬ সংখ্যার করা ভালো, যেমন 10001 -> 10001
                    bill_no = f"{year_str}{month_code}{customer_code}"
                    
                    # এখন ইনসার্ট কুয়েরিতে AUTOINCREMENT ব্যবহার করুন
                    conn.execute('''
                        INSERT OR REPLACE INTO bills (
                            bill_no, customer_id, meter_no, owner_name, bill_month, plaza_name, floor_no, block_no, shop_no,
                            bill_issue_date, due_date, curr_reading_date, prev_reading_date,
                            current_reading, previous_reading, units_consumed, energy_charge, demand_charge,
                            misc_charge, principal_amount, vat, current_month_total, arrears,
                            total_payable, late_fee, total_payable_after_due, note_1, note_2, note_3, is_locked, status, prepared_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        bill_no, c_id, cust['meter_no'], cust['owner_name'], config['bill_month'], cust['plaza_name'], cust['floor_no'], cust['block_no'], cust['shop_no'],
                        config['bill_issue_date'], config['due_date'], config['curr_reading_date'], config['prev_reading_date'],
                        curr_read, prev_read, units_consumed, energy_charge, demand_charge,
                        misc_charge, principal_amount, vat, (principal_amount + vat), arrears,
                        total_payable, late_fee, total_payable_after_due, config['note_1'], config['note_2'], config['note_3'], lock_status, 'Pending', session.get('username')
                    ))

                    conn.commit()
                    flash(f'বিল সফলভাবে তৈরি হয়েছে! বিল নম্বর: {bill_no}', 'success')
        
        conn.close()
        return redirect(url_for('meter_reading', search=search_query))

    # ৩. GET রিকোয়েস্ট: গ্রাহকদের তালিকা তৈরি
    if search_query:
        customers_list = conn.execute('''
            SELECT c.*, 
            COALESCE((SELECT b.current_reading FROM bills b WHERE b.customer_id = c.customer_id ORDER BY b.id DESC LIMIT 1), c.initial_reading) as display_prev_reading,
            (SELECT id FROM bills WHERE customer_id = c.customer_id ORDER BY id DESC LIMIT 1) as latest_bill_id,
            (SELECT COUNT(*) FROM bills WHERE customer_id = c.customer_id AND bill_month = ?) as bill_generated
            FROM customers c
            WHERE c.customer_id LIKE ? OR c.owner_name LIKE ? OR c.shop_no LIKE ?
            ORDER BY c.customer_id ASC
        ''', (config['bill_month'], f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        customers_list = conn.execute('''
            SELECT c.*, 
            COALESCE((SELECT b.current_reading FROM bills b WHERE b.customer_id = c.customer_id ORDER BY b.id DESC LIMIT 1), c.initial_reading) as display_prev_reading,
            (SELECT id FROM bills WHERE customer_id = c.customer_id ORDER BY id DESC LIMIT 1) as latest_bill_id,
            (SELECT COUNT(*) FROM bills WHERE customer_id = c.customer_id AND bill_month = ?) as bill_generated
            FROM customers c
            ORDER BY c.customer_id ASC
        ''', (config['bill_month'],)).fetchall()

    conn.close()
    return render_template('meter_reading.html', customers=customers_list, config=config, search_query=search_query, role=user_role)

@app.route('/billing_dashboard')
@role_required(['admin', 'moderator'])
def billing_dashboard():
    conn = get_db_connection()
    customers = conn.execute("SELECT * FROM customers ORDER BY customer_id ASC").fetchall()
    conn.close()
    return render_template('billing_dashboard.html', customers=customers)

@app.route('/search_customer_history', methods=['GET'])
@role_required(['admin', 'moderator', 'viewer'])
def search_customer_history():
    c_id = request.args.get('c_id', '').strip()
    if not c_id:
        flash('দয়া করে গ্রাহক আইডি প্রদান করুন!', 'warning')
        return redirect(url_for('billing_dashboard')) # অথবা আপনার কাঙ্খিত পেজ
    
    # সরাসরি নির্দিষ্ট গ্রাহকের হিস্ট্রি রাউটে পাঠিয়ে দেওয়া
    return redirect(url_for('customer_history', c_id=c_id))

@app.route('/customer_history/<string:c_id>')
@role_required(['admin', 'moderator', 'viewer'])
def customer_history(c_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    customer = conn.execute('SELECT * FROM customers WHERE customer_id = ?', (c_id,)).fetchone()
    raw_history = conn.execute('SELECT * FROM bills WHERE customer_id = ? ORDER BY id DESC', (c_id,)).fetchall()
    
    config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    current_bill_month = config['bill_month'] if config and 'bill_month' in config.keys() else None
    
    conn.close()

    if not customer:
        flash('গ্রাহক পাওয়া যায়নি!', 'danger')
        return redirect(url_for('billing_dashboard'))

    today_date = datetime.now().date()
    
    # ── একই মাসের একাধিক বিল থাকলে শুধুমাত্র সর্বশেষ (সবচেয়ে বড় ID) বিলটি রাখা ──
    seen_months = set()
    unique_raw_history = []
    for b in raw_history:
        b_month = b['bill_month']
        if b_month not in seen_months:
            seen_months.add(b_month)
            unique_raw_history.append(b)

    history = []
    for b in unique_raw_history:
        bill_dict = dict(b)
        
        due_date_str = bill_dict.get('due_date')
        due_date_obj = today_date
        if due_date_str:
            for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                try:
                    due_date_obj = datetime.strptime(str(due_date_str).strip(), fmt).date()
                    break
                except ValueError:
                    continue
        
        is_previous_month = current_bill_month and bill_dict.get('bill_month') != current_bill_month
        
        if bill_dict.get('status') == 'Paid':
            bill_dict['is_late'] = False
            display_amt = bill_dict.get('paid_amount') or bill_dict['total_payable']
        elif is_previous_month or today_date > due_date_obj:
            bill_dict['is_late'] = True
            display_amt = math.ceil(bill_dict['total_payable_after_due']) if bill_dict.get('total_payable_after_due') else bill_dict['total_payable']
        else:
            bill_dict['is_late'] = False
            display_amt = math.ceil(bill_dict['total_payable']) if bill_dict.get('total_payable') else 0
            
        bill_dict['payable_display'] = display_amt

        # ── নতুন সংযোজন: আংশিক পরিশোধের ক্ষেত্রে অবশিষ্ট বকেয়া (Remaining Due) হিসাব করা ──
        paid_amt = float(bill_dict.get('paid_amount') or 0)
        # যদি স্ট্যাটাস আংশিক পরিশোধ হয় অথবা পেইড অ্যামাউন্ট মোট প্রদেয়ের চেয়ে কম থাকে
        if bill_dict.get('status') == 'Partially Paid' or (0 < paid_amt < display_amt):
            bill_dict['remaining_due'] = max(0.0, display_amt - paid_amt)
        elif bill_dict.get('status') == 'Paid':
            bill_dict['remaining_due'] = 0.0
        else:
            bill_dict['remaining_due'] = display_amt

        history.append(bill_dict)

    return render_template('customer_history.html', customer=customer, history=history)

@app.route('/customer/download_receipt/<int:bill_id>')
def download_payment_receipt(bill_id):
    conn = get_db_connection()
    # বিল এবং সংশ্লিষ্ট গ্রাহকের তথ্য নিয়ে আসা
    bill = conn.execute('''
        SELECT b.*, c.owner_name, c.meter_no, c.shop_no, c.plaza_name, c.mobile_no 
        FROM bills b 
        JOIN customers c ON b.customer_id = c.customer_id 
        WHERE b.id = ?
    ''', (bill_id,)).fetchone()
    conn.close()
    
    if not bill or bill['status'] != 'Paid':
        flash('রসিদটি পাওয়া যায়নি অথবা বিলটি এখনও পরিশোধিত নয়!', 'danger')
        return redirect(url_for('customer_dashboard')) # আপনার গ্রাহক ড্যাশবোর্ডের রাউট
        
    # রসিদের এইচটিএমএল পেজ রেন্ডার করে রিটার্ন করা
    return render_template('payment_receipt.html', bill=bill)

@app.route('/generate_bill', methods=['POST'])
def generate_bill():
    conn = get_db_connection()
    try:
        c_id = request.form.get('customer_id')
        month = request.form.get('bill_month')
        user_name = session.get('username', 'Unknown')

        raw_total = float(request.form.get('total_payable', 0))
        total = math.ceil(raw_total)

        conn.execute('''
            INSERT INTO bills (customer_id, total_payable, bill_month, prepared_by)
            VALUES (?, ?, ?, ?)
        ''', (c_id, total, month, user_name))

        conn.commit()
        flash('বিল সফলভাবে তৈরি হয়েছে!', 'success')

    except Exception as e:
        flash(f'এরর হয়েছে: {e}', 'danger')

    finally:
        conn.close()

    return redirect(url_for('meter_reading'))

from flask import make_response

# WeasyPrint নিরাপদ ইমপোর্ট করার পদ্ধতি
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    WEASYPRINT_AVAILABLE = False


@app.route('/print_bill/<int:bill_id>')
@role_required(['admin', 'moderator', 'viewer'])
def bill_print(bill_id):
    conn = get_db_connection()
    # এখানে JOIN ব্যবহার করে গ্রাহকের তথ্যসহ বিলের ডাটা আনুন
    bill = conn.execute('''
        SELECT b.*, c.owner_name as customer_name, c.meter_no, c.shop_no, c.floor_no
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.id = ?
    ''', (bill_id,)).fetchone()

    conn.close()

    if bill is None:
        flash('দুঃখিত, এই বিলটি খুঁজে পাওয়া যায়নি!', 'danger')
        return redirect(url_for('billing_dashboard'))

    return render_template('billing_dashboard.html', bill=bill)


@app.route('/download_bill/<int:bill_id>')
@role_required(['admin', 'moderator', 'viewer'])
def download_bill(bill_id):
    conn = get_db_connection()
    bill = conn.execute('''
        SELECT b.*, c.owner_name as customer_name, c.meter_no, c.shop_no, c.floor_no
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.id = ?
    ''', (bill_id,)).fetchone()
    conn.close()

    if bill is None:
        flash('দুঃখিত, এই বিলটি খুঁজে পাওয়া যায়নি!', 'danger')
        return redirect(url_for('billing_dashboard'))
    
    # ১. এইচটিএমএল রেন্ডার করা (আপনার টেমপ্লেটের নাম bill_view.html হলে সেটি দেবেন)
    html_string = render_template('bill_view.html', bill=bill)
    
    # ২. লোকাল পিসিতে WeasyPrint না থাকলে সেফ হ্যান্ডেল করা
    if not WEASYPRINT_AVAILABLE:
        flash('লোকাল পিসিতে WeasyPrint লাইব্রেরি নেই বলে পিডিএফ ডাউনলোড করা যাচ্ছে না, তবে এটি অনলাইন সার্ভারে ঠিকমতো কাজ করবে।', 'warning')
        return redirect(url_for('billing_dashboard'))
    
    # ৩. অনলাইন সার্ভারে পিডিএফ তৈরি করা
    pdf = HTML(string=html_string).write_pdf()
    
    # ৪. পিডিএফ ডাউনলোড হিসেবে পাঠানো
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Bill_{bill_id}.pdf'
    return response

# ========================================================================= 
# 🔄 এডমিন স্পেশাল বিল এডিট / কিস্তি / মওকুফ রুট 
# =========================================================================
@app.route('/admin/edit_bill/<int:bill_id>', methods=['POST'])
@role_required(['admin'])
def admin_edit_bill(bill_id):
    conn = get_db_connection()
    try:
        t_payable = request.form.get('total_payable')
        t_after_due = request.form.get('total_payable_after_due')
        paid_amount = request.form.get('paid_amount') # আংশিক বা পূর্ণ পরিশোধিত টাকা
        status = request.form.get('status')
        installment_note = request.form.get('installment_note', '')
        
        # বর্তমান লোকাল সময় (তারিখ ও সময়সহ) সঠিকভাবে বের করা
        current_local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # রিডাইরেক্ট করার জন্য বিলের সাপেক্ষে customer_id বের করে নেওয়া
        bill_row = conn.execute("SELECT customer_id FROM bills WHERE id = ?", (bill_id,)).fetchone()
        customer_id = bill_row['customer_id'] if bill_row else None

        # ডাটাবেসে updated_at কলাম না থাকলে তা অটো যোগ করার সেফটি চেক
        try:
            conn.execute("SELECT updated_at FROM bills LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute("ALTER TABLE bills ADD COLUMN updated_at TEXT")
            except Exception:
                pass

        # বিলের তথ্য, পেইড অ্যামাউন্ট, স্ট্যাটাস, নোট এবং লোকাল আপডেটের সময় আপডেট করা
        conn.execute('''
            UPDATE bills 
            SET total_payable = ?, total_payable_after_due = ?, paid_amount = ?, status = ?, note = ?, updated_at = ?, is_locked = 0 
            WHERE id = ?
        ''', (t_payable, t_after_due, paid_amount, status, installment_note, current_local_time, bill_id))

        # অডিট লগ যুক্ত করা
        conn.execute("INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)", 
                    (session.get('user_id'), 'EDIT_BILL', f'বিল আইডি {bill_id} এডিট বা আংশিক পরিশোধ/মওকুফ আপডেট করা হয়েছে'))
        
        conn.commit()
        flash('বিলের তথ্য, পরিশোধিত পরিমাণ ও কিস্তি নোট সফলভাবে আপডেট হয়েছে!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'এরর হয়েছে: {e}', 'danger')
    finally:
        conn.close()

    if customer_id:
        return redirect(url_for('customer_history', c_id=customer_id))
    return redirect(url_for('bill_collection'))

# 💳 পেমেন্ট বাটন রুট
@app.route('/bill/payment', methods=['GET', 'POST'])
@role_required(['admin', 'moderator'])
def bill_collection():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    today_date = datetime.now().date()
    today_str = today_date.strftime('%d-%m-%Y')
    
    config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    current_bill_month = config['bill_month'] if config and 'bill_month' in config.keys() else None

    # কুয়েরি তৈরি (যেখানে বিলগুলো আনা হচ্ছে)
    if search_query:
        bills_list = conn.execute('''
            SELECT bills.*, customers.owner_name, customers.shop_no, customers.customer_id
            FROM bills JOIN customers ON bills.customer_id = customers.customer_id
            WHERE (customers.owner_name LIKE ? OR customers.shop_no LIKE ? OR bills.customer_id LIKE ?)
            AND bills.status != 'Paid' ORDER BY bills.customer_id ASC
        ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        bills_list = conn.execute('''
            SELECT bills.*, customers.owner_name, customers.shop_no, customers.customer_id
            FROM bills JOIN customers ON bills.customer_id = customers.customer_id
            WHERE bills.status != 'Paid' ORDER BY bills.customer_id ASC
        ''').fetchall()

    processed_bills = []
    for b in bills_list:
        bill_dict = dict(b)
        
        due_date_str = bill_dict.get('due_date')
        due_date_obj = today_date
        if due_date_str:
            for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                try:
                    due_date_obj = datetime.strptime(str(due_date_str).strip(), fmt).date()
                    break
                except ValueError:
                    continue
        
        is_previous_month = current_bill_month and bill_dict.get('bill_month') != current_bill_month
        
        # বিলম্বে বা সঠিক সময়ে প্রদেয় মোট টাকা নির্ধারণ
        if is_previous_month or today_date > due_date_obj:
            total_due_amt = math.ceil(bill_dict['total_payable_after_due'] if bill_dict.get('total_payable_after_due') else bill_dict['total_payable'])
            bill_dict['is_late'] = True
        else:
            total_due_amt = math.ceil(bill_dict['total_payable'] if bill_dict.get('total_payable') else 0)
            bill_dict['is_late'] = False

        # ── অত্যন্ত জরুরি লজিক: মোট প্রদেয় থেকে ইতিমধ্যে পরিশোধিত বা আংশিক টাকা বাদ দেওয়া ──
        already_paid = float(bill_dict.get('paid_amount') or 0)
        bill_dict['payable_now'] = max(0.0, total_due_amt - already_paid)
        bill_dict['already_paid'] = already_paid

        processed_bills.append(bill_dict)

    if request.method == 'POST':
        bill_id = request.form.get('bill_id')
        bill_row = conn.execute('SELECT * FROM bills WHERE id = ?', (bill_id,)).fetchone()
        
        if bill_row:
            cust_id = bill_row['customer_id']
            due_date_str = bill_row['due_date']
            due_date_obj = today_date
            if due_date_str:
                for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                    try:
                        due_date_obj = datetime.strptime(str(due_date_str).strip(), fmt).date()
                        break
                    except ValueError:
                        continue

            is_previous_month = current_bill_month and bill_row['bill_month'] != current_bill_month
            if is_previous_month or today_date > due_date_obj:
                actual_total = math.ceil(bill_row['total_payable_after_due'] if bill_row['total_payable_after_due'] else bill_row['total_payable'])
            else:
                actual_total = math.ceil(bill_row['total_payable'])
                
            # পূর্বে দেওয়া আংশিক টাকা হিসাব করা
            prev_paid = float(bill_row['paid_amount'] or 0)
            remaining_balance = max(0.0, actual_total - prev_paid)

            try:
                input_amount = float(request.form.get('pay_amount', 0))
            except ValueError:
                input_amount = 0.0

            # ইউজার ইনপুট দেওয়া টাকার অংক যাচাই (অবশিষ্ট বকেয়ার পরিমাণের সাথে মিল রেখে)
            if input_amount <= 0 or input_amount > remaining_balance + 1.0:
                flash(f'ত্রুটি: সঠিক অঙ্ক বসান! অবশিষ্ট প্রদেয় টাকা: {remaining_balance}', 'danger')
            else:
                new_total_paid = prev_paid + input_amount
                
                # যদি নতুন মোট পরিশোধিত টাকা মূল বিলের সমান বা বেশি হয়, তবে স্ট্যাটাস 'Paid', অন্যথায় 'Partially Paid'
                if new_total_paid >= actual_total - 1.0:
                    new_status = 'Paid'
                else:
                    new_status = 'Partially Paid'

                # ১. পেমেন্টস টেবিলে রেকর্ড ইনসার্ট করা
                conn.execute('''
                    INSERT INTO payments (bill_id, customer_id, amount, payment_date, payment_method, received_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (bill_id, cust_id, input_amount, today_str, 'Cash', session['username']))

                # ২. বিলস টেবিলে নতুন paid_amount, স্ট্যাটাস এবং updated_at আপডেট করা
                conn.execute('''
                    UPDATE bills SET paid_amount=?, status=?, payment_date=?, payment_method=?, received_by=?, updated_at=CURRENT_TIMESTAMP 
                    WHERE id=?
                ''', (new_total_paid, new_status, today_str, 'Cash', session['username'], bill_id))

                conn.commit()
                flash('পেমেন্ট সফলভাবে রিসিভ হয়েছে!', 'success')
        else:
            flash('ত্রুটি: বিলটি পাওয়া যায়নি!', 'danger')

        conn.close()
        return redirect(url_for('bill_collection', search=search_query))
    
    conn.close()
    return render_template('bill_collection.html', bills=processed_bills, search_query=search_query)

@app.route('/admin/daily_collection', methods=['GET'])
@role_required(['admin'])
def daily_collection():
    selected_date = request.args.get('date')
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    if not selected_date:
        search_date = datetime.now().strftime('%Y-%m-%d')
    else:
        try:
            for fmt in ('%Y-%m-%d', '%d-%b-%Y', '%d-%m-%Y', '%d-%m-%y'):
                try:
                    dt = datetime.strptime(selected_date, fmt)
                    search_date = dt.strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue
            else:
                search_date = selected_date
        except Exception:
            search_date = selected_date

    # শুধুমাত্র নির্দিষ্ট তারিখের আপডেট হওয়া বা পরিশোধ/আংশিক পরিশোধ/মওকুফ হওয়া বিলগুলো নিয়ে আসা
    try:
        collections = conn.execute('''
            SELECT b.*, c.owner_name, c.shop_no, c.meter_no 
            FROM bills b 
            JOIN customers c ON b.customer_id = c.customer_id 
            WHERE (b.status IN ('Paid', 'Partially Paid', 'Waived', 'Pending') OR b.paid_amount > 0)
              AND date(b.updated_at) = ?
            ORDER BY b.id DESC
        ''', (search_date,)).fetchall()
    except sqlite3.OperationalError:
        collections = conn.execute('''
            SELECT b.*, c.owner_name, c.shop_no, c.meter_no 
            FROM bills b 
            JOIN customers c ON b.customer_id = c.customer_id 
            WHERE (b.status IN ('Paid', 'Partially Paid', 'Waived', 'Pending') OR b.paid_amount > 0)
            ORDER BY b.id DESC
        ''').fetchall()
    
    # মোট কালেকশন (পরিশোধিত বা আংশিক পরিশোধিত টাকার যোগফল)
    total_collection = sum(row['paid_amount'] for row in collections if row['paid_amount']) if collections else 0.0
    
    conn.close()
    
    return render_template('daily_collection.html', 
                           collections=collections, 
                           total_collection=total_collection, 
                           selected_date=search_date)

# 📅 গ. মাসিক বিলের তথ্য ইনপুট বাটন
@app.route('/bill/monthly_bill_configuration', methods=['GET', 'POST'])
@role_required(['admin'])
def monthly_config():
    conn = get_db_connection()

    if request.method == 'POST':
        bill_month = request.form.get('bill_month')
        misc_charge = float(request.form.get('misc_charge', 0.0))
        bill_issue_date = request.form.get('bill_issue_date')
        due_date = request.form.get('due_date')
        curr_reading_date = request.form.get('curr_reading_date')
        prev_reading_date = request.form.get('prev_reading_date')
        note_1 = request.form.get('note_1')
        note_2 = request.form.get('note_2')
        note_3 = request.form.get('note_3')

        conn.execute('''
            INSERT INTO monthly_config
            (bill_month, misc_charge, bill_issue_date, due_date, curr_reading_date, prev_reading_date, note_1, note_2, note_3)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (bill_month, misc_charge, bill_issue_date, due_date, curr_reading_date, prev_reading_date, note_1, note_2, note_3))

        conn.commit()
        conn.close()
        flash('কনফিগারেশন সফলভাবে সেভ হয়েছে!', 'success')
        return redirect(url_for('dashboard'))

    config_row = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    config = dict(config_row) if config_row else None

    return render_template('monthly_config.html', config=config)

# 📄 ঘ. বিল ভিউ বাটন
@app.route('/bill/view/<int:bill_id>')
def view_bill(bill_id):
    # এডমিন, মডারেটর কিংবা কাস্টমার উভয়ের জন্যই এক্সেস নিশ্চিত করা
    role = session.get('role')
    customer_id = session.get('customer_id')
    
    if not role and not customer_id:
        flash('দয়া করে প্রথমে লগইন করুন!', 'danger')
        return redirect(url_for('customer_login'))
        
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # বিলের তথ্য এবং গ্রাহক আইডি আনা
    bill = conn.execute('''
        SELECT b.*, 
               c.owner_name, c.meter_no, c.plaza_name, c.floor_no, 
               c.block_no, c.shop_no, c.allocated_load, c.rate_per_kw, c.unit_rate
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.id = ?
    ''', (bill_id,)).fetchone()
    
    # সিকিউরিটি চেক: কাস্টমার হলে সে কেবল নিজের বিলই দেখতে পারবে
    if customer_id and bill and str(bill['customer_id']) != str(customer_id):
        conn.close()
        flash('আপনার এই বিলটি দেখার অনুমতি নেই!', 'danger')
        return redirect(url_for('customer_dashboard'))

    config_row = conn.execute('SELECT note_1, note_2, note_3, bill_month FROM monthly_config ORDER BY id DESC LIMIT 1').fetchone()
    conn.close() 

    if not bill:
        flash('বিলটি খুঁজে পাওয়া যায়নি!', 'danger')
        # সঠিকভাবে রিডাইরেক্ট হ্যান্ডেল করা
        return redirect(url_for('customer_view_bills' if customer_id else 'meter_reading'))

    username = session.get('username', 'কর্তৃপক্ষ')

    return render_template('bill_view.html', bill=bill, config=config_row, username=username)

@app.context_processor
def inject_user_role():
    # session থেকে তথ্য নিন
    username = session.get('username', 'Guest')
    user_role = session.get('user_role', 'None')
    
    return dict(username=username, user_role=user_role)
    

# 📥 ঙ. ডাটা এক্সপোর্ট বাটন
@app.route('/data/export')
@role_required(['admin', 'moderator', 'viewer'])
def data_export():
    conn = get_db_connection()
    bills_list = conn.execute('''
        SELECT bills.*, customers.owner_name, customers.meter_no, customers.shop_no
        FROM bills JOIN customers ON bills.customer_id = customers.customer_id
    ''').fetchall()
    conn.close()

    # স্ট্রিং-এর পরিবর্তে মেমোরি বাফার ব্যবহার করা বেশি নিরাপদ
    output = io.StringIO()
    # BOM যুক্ত করা যাতে বাংলা টেক্সট এক্সেল-এ সঠিকভাবে ওপেন হয়
    output.write('\ufeff') 
    
    writer = csv.writer(output)
    writer.writerow(['গ্রাহক আইডি', 'মালিকের নাম', 'মিটার নং', 'দোকান নং', 'বিল মাস', 'ব্যবহৃত ইউনিট', 'চলতি বিল', 'বকেয়া বিল', 'মোট পরিশোধযোগ্য', 'বিলম্ব মাশুল', 'শেষ তারিখের পর মোট', 'স্ট্যাটাস'])

    for b in bills_list:
        writer.writerow([
            b['customer_id'], b['owner_name'], b['meter_no'], b['shop_no'], 
            b['bill_month'], b['units_consumed'], b['current_month_total'], 
            b['arrears'], b['total_payable'], b['late_fee'], 
            b['total_payable_after_due'], b['status']
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=Saidpur_Plaza_Monthly_Report.csv'
    response.headers['Content-type'] = 'text/csv; charset=utf-8'
    return response

# ⚙️ চ. সেটিং বাটন
@app.route('/admin/admin_settings', methods=['GET', 'POST'])
@role_required(['admin'])
def admin_settings():
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        
        # এখানে 'role' সংগ্রহ করা হচ্ছে (ফর্মের name এর সাথে মিলিয়ে নিন)
        role = request.form.get('user_role') 
        if not role:
            role = 'user' # ডিফল্ট ভ্যালু

        if action == 'add':
            # প্লেইন পাসওয়ার্ড সরাসরি ব্যবহার করা হচ্ছে
            # এখন role ভেরিয়েবলটি নিশ্চিতভাবে খালি নয়
            conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                         (username, password, role))
                         
        elif action == 'update':
            # update এর জন্য আলাদাভাবে রোল চেক
            role_update = request.form.get('role') 
            if not role_update:
                role_update = 'user'
            
            # ফর্ম থেকে পাসওয়ার্ড ইনপুট নেওয়া হচ্ছে
            new_password = request.form.get('password')
            
            # চেক করা হচ্ছে পাসওয়ার্ড ফিল্ডটি খালি কি না
            if new_password and new_password.strip() != "":
                # যদি নতুন পাসওয়ার্ড দেওয়া হয়, তবে পাসওয়ার্ড এবং রোল উভয়ই আপডেট হবে
                conn.execute('UPDATE users SET password = ?, role = ? WHERE username = ?',
                             (new_password, role_update, username))
            else:
                # যদি পাসওয়ার্ড ফিল্ড খালি রাখা হয়, তবে শুধু রোল আপডেট হবে (পাসওয়ার্ড আগেরটাই থাকবে)
                conn.execute('UPDATE users SET role = ? WHERE username = ?',
                             (role_update, username))
                         
        elif action == 'delete':
            conn.execute('DELETE FROM users WHERE username = ?', (username,))

        conn.commit()
        flash(f'ইউজার {username} সফলভাবে {action} করা হয়েছে!', 'success')
        return redirect(url_for('admin_settings'))

    users_list = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return render_template('admin_settings.html', users=users_list)

# ফোল্ডার যেখানে কিউআর কোড সেভ হবে
UPLOAD_FOLDER = 'static'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# ফোল্ডারটি নিশ্চিত করুন
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload-qr', methods=['POST'])
def upload_qr_code():
    if 'qr_image' not in request.files:
        flash('কোন ফাইল সিলেক্ট করা হয়নি')
        return redirect(request.url)
    
    file = request.files['qr_image']
    
    if file.filename == '':
        flash('ফাইল সিলেক্ট করুন')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        flash('কিউআর কোড সফলভাবে আপলোড হয়েছে!')
        return redirect(url_for('admin_settings')) # আপলোডের পর এডমিন সেটিংসে ফিরে যাবে
    
    flash('শুধুমাত্র PNG/JPG ফাইল আপলোড করা যাবে')
    return redirect(request.url)

# 📱 গ্রাহক পোর্টাল মডিউল
@app.route('/customer/customer_login', methods=['GET', 'POST'])
def customer_login():
    if 'customer_id' in session: 
        return redirect(url_for('customer_dashboard'))
    
    if request.method == 'POST':
        c_id = request.form.get('customer_id', '').strip()
        passwd = request.form.get('password', '').strip()
        
        conn = get_db_connection()
        cust = conn.execute('SELECT * FROM customers WHERE customer_id=?', (c_id,)).fetchone()
        conn.close()

        if cust:
            # প্লেইন টেক্সট পাসওয়ার্ড চেক (অথবা ডিফল্ট '123456')
            if cust['password'] == passwd:
                session['customer_id'] = cust['customer_id']
                session['customer_name'] = cust['owner_name']
                return redirect(url_for('customer_dashboard'))
            else:
                flash('ভুল পাসওয়ার্ড!', 'danger')
        else:
            flash('গ্রাহক আইডি পাওয়া যায়নি!', 'danger')

    return render_template('customer_login.html')

@app.route('/customer/forgot_password', methods=['GET', 'POST'])
def customer_forgot_password():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id', '').strip()
        phone = request.form.get('phone', '').strip()
        new_password = request.form.get('new_password', '').strip()
        
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # গ্রাহক আইডি এবং মোবাইল নম্বর ম্যাচ করছে কি না চেক করা
        customer = conn.execute('SELECT * FROM customers WHERE customer_id = ? AND phone = ?', (customer_id, phone)).fetchone()
        
        if customer:
            # নতুন পাসওয়ার্ড আপডেট করা
            conn.execute('UPDATE customers SET password = ? WHERE customer_id = ?', (new_password, customer_id))
            conn.commit()
            flash('আপনার পাসওয়ার্ড সফলভাবে পরিবর্তন করা হয়েছে। এখন নতুন পাসওয়ার্ড দিয়ে লগইন করুন।', 'success')
            conn.close()
            return redirect(url_for('customer_login'))
        else:
            flash('প্রদানকৃত গ্রাহক আইডি অথবা মোবাইল নম্বর সঠিক নয়!', 'danger')
            conn.close()
            
    return render_template('customer_forgot_password.html')

@app.route('/customer/dashboard')
def customer_dashboard():
    # সেশন থেকে লগইন করা গ্রাহকের আইডি বা তথ্য বের করা
    customer_id = session.get('customer_id') # অথবা আপনার সিস্টেমে যেভাবে সেশন হ্যান্ডেল করা হয়
    
    if not customer_id:
        flash('দয়া করে প্রথমে লগইন করুন!', 'warning')
        return redirect(url_for('customer_login'))
        
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # গ্রাহকের তথ্য নিয়ে আসা
    customer = conn.execute('SELECT * FROM customers WHERE customer_id = ?', (customer_id,)).fetchone()
    
    # বিলের হিস্ট্রি নিয়ে আসা (যদি আগের সেই অবশিষ্ট বকেয়া বা remaining_due লজিক এখানেও রাখতে চান)
    raw_history = conn.execute('SELECT * FROM bills WHERE customer_id = ? ORDER BY id DESC', (customer_id,)).fetchall()
    
    # কনফিগ বা অন্যান্য লজিক...
    config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    current_bill_month = config['bill_month'] if config and 'bill_month' in config.keys() else None
    
    today_date = datetime.now().date()
    
    # একই মাসের একাধিক বিল হ্যান্ডেল করার লজিক (প্রয়োজন হলে)
    seen_months = set()
    unique_raw_history = []
    for b in raw_history:
        b_month = b['bill_month']
        if b_month not in seen_months:
            seen_months.add(b_month)
            unique_raw_history.append(b)

    history = []
    for b in unique_raw_history:
        bill_dict = dict(b)
        
        due_date_str = bill_dict.get('due_date')
        due_date_obj = today_date
        if due_date_str:
            for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                try:
                    due_date_obj = datetime.strptime(str(due_date_str).strip(), fmt).date()
                    break
                except ValueError:
                    continue
        
        is_previous_month = current_bill_month and bill_dict.get('bill_month') != current_bill_month
        
        if bill_dict.get('status') == 'Paid':
            bill_dict['is_late'] = False
            display_amt = bill_dict.get('paid_amount') or bill_dict['total_payable']
        elif is_previous_month or today_date > due_date_obj:
            bill_dict['is_late'] = True
            display_amt = math.ceil(bill_dict['total_payable_after_due']) if bill_dict.get('total_payable_after_due') else bill_dict['total_payable']
        else:
            bill_dict['is_late'] = False
            display_amt = math.ceil(bill_dict['total_payable']) if bill_dict.get('total_payable') else 0
            
        bill_dict['payable_display'] = display_amt

        # অবশিষ্ট বকেয়া (Remaining Due) হিসাব করা
        paid_amt = float(bill_dict.get('paid_amount') or 0)
        if bill_dict.get('status') == 'Partially Paid' or (0 < paid_amt < display_amt):
            bill_dict['remaining_due'] = max(0.0, display_amt - paid_amt)
        elif bill_dict.get('status') == 'Paid':
            bill_dict['remaining_due'] = 0.0
        else:
            bill_dict['remaining_due'] = display_amt

        history.append(bill_dict)

    conn.close()

    # ── অত্যন্ত জরুরি: এখানে আবশ্যিকভাবে customer=customer এবং history=history পাস করতে হবে ──
    return render_template('customer_dashboard.html', customer=customer, history=history)

@app.route('/customer/portal/view_bills')
def customer_view_bills():
    customer_id = session.get('customer_id')
    
    if not customer_id:
        return redirect(url_for('customer_login'))
        
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row 
    
    config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    current_bill_month = config['bill_month'] if config and 'bill_month' in config.keys() else None

    customer = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    
    raw_history = conn.execute('''
        SELECT * FROM bills 
        WHERE customer_id = ? 
        ORDER BY id DESC LIMIT 50
    ''', (customer_id,)).fetchall()
    
    conn.close()

    today_date = datetime.now().date()
    
    # ── ডুপ্লিকেট মাস ফিল্টার করার লজিক ──
    seen_months = set()
    unique_raw_history = []
    for b in raw_history:
        b_month = b['bill_month']
        if b_month not in seen_months:
            seen_months.add(b_month)
            unique_raw_history.append(b)

    history = []
    for b in unique_raw_history[:24]:  # ফিল্টার করার পর সর্বশেষ ২৪ মাস পর্যন্ত দেখাবে
        bill_dict = dict(b)
        
        due_date_str = bill_dict.get('due_date')
        due_date_obj = today_date
        if due_date_str:
            for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                try:
                    due_date_obj = datetime.strptime(str(due_date_str).strip(), fmt).date()
                    break
                except ValueError:
                    continue
        
        is_previous_month = current_bill_month and bill_dict.get('bill_month') != current_bill_month
        
        if bill_dict.get('status') == 'Paid':
            bill_dict['is_late'] = False
            display_amt = bill_dict.get('paid_amount') or bill_dict.get('total_payable', 0)
        elif is_previous_month or today_date > due_date_obj:
            bill_dict['is_late'] = True
            display_amt = math.ceil(bill_dict['total_payable_after_due']) if bill_dict.get('total_payable_after_due') else bill_dict.get('total_payable', 0)
        else:
            bill_dict['is_late'] = False
            display_amt = math.ceil(bill_dict['total_payable']) if bill_dict.get('total_payable') else 0
            
        bill_dict['payable_display'] = display_amt
        history.append(bill_dict)
    
    return render_template('customer_view_bills.html', customer=customer, history=history)

@app.route('/customer/portal/payment')
def payment_portal():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))

    c_id = session['customer_id']
    conn = get_db_connection()
    latest_bill = conn.execute('SELECT total_payable, total_payable_after_due, due_date, status FROM bills WHERE customer_id = ? ORDER BY id DESC LIMIT 1', (c_id,)).fetchone()

    conn.close()

    payable_amount = 0
    if latest_bill and latest_bill['status'] != 'Paid':
        today = datetime.now().date()
        due_date_str = latest_bill['due_date']
        
        print(f"--- DEBUG --- Today: {today}, Due Date from DB: {due_date_str}") # টার্মিনালে প্রিন্ট করে দেখার জন্য
        
        is_expired = False
        if due_date_str:
            try:
                due_date = datetime.strptime(str(due_date_str).strip(), '%Y-%m-%d').date()
                if today > due_date:
                    is_expired = True
            except Exception as e:
                print(f"Date parse error 1: {e}")
                try:
                    due_date = datetime.strptime(str(due_date_str).strip(), '%d-%m-%Y').date()
                    if today > due_date:
                        is_expired = True
                except Exception as e2:
                    print(f"Date parse error 2: {e2}")
                    pass

        print(f"Is Expired?: {is_expired}") # ডেট পার হয়েছে কি না তা টার্মিনালে দেখাবে
        
        if is_expired and latest_bill['total_payable_after_due']:
            payable_amount = latest_bill['total_payable_after_due']
        else:
            payable_amount = latest_bill['total_payable']

    print(f"Final Payable Amount: {payable_amount}") # চূড়ান্ত কত টাকা পাঠাচ্ছে তা দেখাবে

    qr_image_path = 'static/bangla_qr.jpg'
    dynamic_qr_link = f"bankqr://pay?merchant=Saidpur_Plaza&customer_id={c_id}&amount={payable_amount}"

    return render_template('payment_portal.html', amount=payable_amount, qr_path=qr_image_path, qr_link=dynamic_qr_link, id=c_id)

@app.route('/customer/pay/<customer_id>')
def public_payment_counter(customer_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # গ্রাহক খুঁজে বের করা
    customer = conn.execute('SELECT * FROM customers WHERE customer_id = ?', (customer_id,)).fetchone()
    
    if not customer:
        conn.close()
        return "গ্রাহক খুঁজে পাওয়া যায়নি!", 404
        
    # ঐ গ্রাহকের সর্বশেষ আনপেইড বা বকেয়া বিলের সব তথ্য আনা
    latest_bill = conn.execute('''
        SELECT id, total_payable, total_payable_after_due, due_date, status 
        FROM bills 
        WHERE customer_id = ? AND status != 'Paid' 
        ORDER BY id DESC LIMIT 1
    ''', (customer_id,)).fetchone()
    
    conn.close()
    
    payable_amount = 0
    bill_id = None
    
    if latest_bill:
        bill_id = latest_bill['id']
        today = datetime.now().date()
        due_date_str = latest_bill['due_date']
        
        is_expired = False
        if due_date_str:
            try:
                due_date = datetime.strptime(str(due_date_str).strip(), '%Y-%m-%d').date()
                if today > due_date:
                    is_expired = True
            except Exception:
                try:
                    due_date = datetime.strptime(str(due_date_str).strip(), '%d-%m-%Y').date()
                    if today > due_date:
                        is_expired = True
                except Exception:
                    pass
        
        if is_expired and latest_bill['total_payable_after_due']:
            payable_amount = latest_bill['total_payable_after_due']
        else:
            payable_amount = latest_bill['total_payable'] if latest_bill['total_payable'] else 0

    # সরাসরি পাবলিক পেমেন্ট টেমপ্লেট রেন্ডার করবে (কোনো লগইন লাগবে না)
    return render_template('payment_portal.html', id=customer_id, amount=payable_amount, bill_id=bill_id)
    
@app.route('/submit_trxid', methods=['POST'])
def submit_trxid():
    customer_id = request.form.get('customer_id')
    amount = request.form.get('amount')
    trx_id = request.form.get('trx_id', '').strip()
    
    if not trx_id:
        flash('দয়া করে ট্রানজেকশন আইডি (TrxID) দিন।', 'danger')
        # যদি customer_id থাকে, তবে আবার পেমেন্ট কাউন্টারে ফেরত পাঠাবে
        if customer_id:
            return redirect(url_for('public_payment_counter', customer_id=customer_id))
        return redirect(url_for('customer_dashboard'))

    conn = get_db_connection()
    
    # ট্রানজেকশন আইডি ইতিমধ্যে ব্যবহার করা হয়েছে কি না চেক করা
    existing_trx = conn.execute('SELECT * FROM payments WHERE trx_id = ?', (trx_id,)).fetchone()
    if existing_trx:
        flash('এই ট্রানজেকশন আইডি (TrxID) ইতিপূর্বে ব্যবহার করা হয়েছে!', 'danger')
        conn.close()
        if customer_id:
            return redirect(url_for('public_payment_counter', customer_id=customer_id))
        return redirect(url_for('customer_dashboard'))

    today_str = datetime.now().strftime('%d-%m-%Y')
    
    try:
        bill = conn.execute("SELECT * FROM bills WHERE customer_id = ? AND status != 'Paid' ORDER BY id DESC LIMIT 1", (customer_id,)).fetchone()
        
        if bill:
            bill_id = bill['id']
            
            # ১. পেমেন্ট টেবিলে স্ট্যাটাস 'Pending' বা যাচাইাধীন হিসেবে সেভ করা
            conn.execute('''
                INSERT INTO payments (bill_id, customer_id, amount, trx_id, payment_date, payment_method, received_by, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending')
            ''', (bill_id, customer_id, amount, trx_id, today_str, 'Online/BKash', 'Online Customer'))

            # ২. বিলের স্ট্যাটাস Pending রাখা এবং updated_at আপডেট করা
            conn.execute('''
                UPDATE bills SET status='Pending', updated_at=CURRENT_TIMESTAMP WHERE id=?
            ''', (bill_id,))

            conn.commit()
            flash('আপনার পেমেন্ট আইডি সফলভাবে জমা হয়েছে। অ্যাডমিন কর্তৃক যাচাই করার পর এটি আপডেট করা হবে।', 'success')
        else:
            flash('কোনো বকেয়া বিল পাওয়া যায়নি!', 'warning')
            
    except Exception as e:
        conn.rollback()
        flash(f'ত্রুটি ঘটেছে: {str(e)}', 'danger')
    
    conn.close()
    
    # সফলভাবে সাবমিট শেষে কাস্টমার ড্যাশবোর্ডে বা পেমেন্ট কাউন্টারে রিডাইরেক্ট করা
    if customer_id:
        return redirect(url_for('public_payment_counter', customer_id=customer_id))
    return redirect(url_for('customer_dashboard'))

def check_and_fix_database():
    conn = get_db_connection()
    try:
        # payments টেবিলে trx_id কলাম আছে কি না চেক করা
        cursor = conn.execute("PRAGMA table_info(payments)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'trx_id' not in columns:
            conn.execute("ALTER TABLE payments ADD COLUMN trx_id TEXT")
            conn.commit()
    except Exception as e:
        print("Database update error:", e)
    conn.close()

# অ্যাপ চালু হওয়ার সময় বা ডেটাবেজ কানেকশনের পর এটি কল করতে পারেন
check_and_fix_database()



@app.route('/customer/portal/change_password', methods=['GET', 'POST'])
def customer_change_password():
    if 'customer_id' not in session: return redirect(url_for('customer_login'))
    
    if request.method == 'POST':
        current_pass = request.form.get('current_password', '').strip()
        new_pass = request.form.get('new_password', '').strip()
        confirm_pass = request.form.get('confirm_password', '').strip()

        # ১. কনফার্ম পাসওয়ার্ড চেক সবার আগে
        if new_pass != confirm_pass:
            flash('নতুন পাসওয়ার্ড এবং কনফার্ম পাসওয়ার্ড মিলছে না!', 'danger')
            return redirect(url_for('customer_change_password'))

        conn = get_db_connection()
        cust = conn.execute('SELECT password FROM customers WHERE customer_id=?', (session['customer_id'],)).fetchone()

        # ২. বর্তমান পাসওয়ার্ড সঠিক কি না যাচাই (প্লেইন টেক্সট তুলনা)
        if cust and cust['password'] == current_pass:
            # নতুন পাসওয়ার্ড সরাসরি সেভ করা হচ্ছে
            conn.execute('UPDATE customers SET password=? WHERE customer_id=?', (new_pass, session['customer_id']))
            conn.commit()
            flash('পাসওয়ার্ড সফলভাবে পরিবর্তিত হয়েছে!', 'success')
        else:
            flash('বর্তমান পাসওয়ার্ড ভুল!', 'danger')

        conn.close()

    return render_template('customer_change_password.html')

# ১. ম্যানেজমেন্ট হোম পেজ (যেখানে তিনটি ক্যাটাগরি বা ট্যাব থাকবে)
@app.route('/id_card_management/<category>')
@role_required(['admin'])
def id_card_management(category):
    if category not in ['staff', 'merchant', 'employee']:
        flash('অ বৈধ ক্যাটাগরি!', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cards = conn.execute("SELECT * FROM id_cards WHERE category = ? ORDER BY id DESC", (category,)).fetchall()
    conn.close()
    
    return render_template('id_card_management.html', cards=cards, current_category=category)


# ২. নতুন আইডি কার্ড বা ব্যক্তি ইনপুট ফর্ম (Add)
@app.route('/id_card/add/<category>', methods=['GET', 'POST'])
@role_required(['admin'])
def add_id_card(category):
    if request.method == 'POST':
        # ফর্ম থেকে ডাটা সংগ্রহ
        card_id = request.form.get('card_id')
        name = request.form.get('name')
        designation = request.form.get('designation', '') if category == 'staff' else ''
        mobile_no = request.form.get('mobile_no')
        shop_no = request.form.get('shop_no')
        blood_group = request.form.get('blood_group')
        father_name = request.form.get('father_name')
        mother_name = request.form.get('mother_name')
        nid_or_birth = request.form.get('nid_or_birth')
        
        # ঠিকানা
        pres_village = request.form.get('pres_village')
        pres_post = request.form.get('pres_post')
        pres_upazila = request.form.get('pres_upazila')
        pres_district = request.form.get('pres_district')
        
        perm_village = request.form.get('perm_village')
        perm_post = request.form.get('perm_post')
        perm_upazila = request.form.get('perm_upazila')
        perm_district = request.form.get('perm_district')
        
        secret_card_number = request.form.get('secret_card_number')
        expire_date = request.form.get('expire_date')
        
        # ছবি এবং স্বাক্ষর আপলোড হ্যান্ডলিং
        photo = request.files.get('photo_img')
        signature = request.files.get('signature_img')
        auth_sig = request.files.get('authorized_signature')
        
        photo_filename = ''
        signature_filename = ''
        auth_sig_filename = ''
        
        if photo and photo.filename:
            photo_filename = secure_filename(f"photo_{card_id}_{photo.filename}")
            photo.save(os.path.join('static/uploads', photo_filename))
            
        if signature and signature.filename:
            signature_filename = secure_filename(f"sig_{card_id}_{signature.filename}")
            signature.save(os.path.join('static/uploads', signature_filename))

        if auth_sig and auth_sig.filename:
            auth_sig_filename = secure_filename(f"auth_sig_{card_id}_{auth_sig.filename}")
            auth_sig.save(os.path.join('static/uploads', auth_sig_filename))

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO id_cards (
                    category, card_id, name, designation, mobile_no, shop_no, blood_group, 
                    father_name, mother_name, nid_or_birth, pres_village, pres_post, 
                    pres_upazila, pres_district, perm_village, perm_post, perm_upazila, 
                    perm_district, signature_img, photo_img, secret_card_number, expire_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                category, card_id, name, designation, mobile_no, shop_no, blood_group,
                father_name, mother_name, nid_or_birth, pres_village, pres_post,
                pres_upazila, pres_district, perm_village, perm_post, perm_upazila,
                perm_district, signature_filename, photo_filename, secret_card_number, expire_date
            ))
            conn.commit()
            flash('সফলভাবে নতুন আইডি কার্ডের তথ্য সংরক্ষণ করা হয়েছে!', 'success')
        except Exception as e:
            flash(f'এরর: {str(e)}', 'danger')
        finally:
            conn.close()
            
        return redirect(url_for('id_card_management', category=category))
        
    return render_template('add_id_card.html', category=category)


# ৩. ডিলিট অপশন (চাকরি বা ব্যবসা ছাড়লে সীমাবদ্ধ করতে)
@app.route('/id_card/delete/<int:id>', methods=['POST'])
@role_required(['admin'])
def delete_id_card(id):
    conn = get_db_connection()
    card = conn.execute("SELECT category FROM id_cards WHERE id = ?", (id,)).fetchone()
    category = card['category'] if card else 'staff'
    
    conn.execute("DELETE FROM id_cards WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    flash('সফলভাবে রেকর্ড মুছে ফেলা হয়েছে এবং প্লাজায় প্রবেশাধিকার বাতিল করা হয়েছে।', 'success')
    return redirect(url_for('id_card_management', category=category))

@app.route('/api/verify_access', methods=['POST'])
def verify_access():
    data = request.get_json()
    device_id = data.get('device_id', 'Default-Gate')
    secret_card_number = data.get('secret_card_number')  # বা ফিঙ্গারপ্রিন্ট আইডি
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM id_cards WHERE secret_card_number = ?", (secret_card_number,)).fetchone()
    
    today_date = datetime.now().date()
    status = "Denied"
    reason = "Card Not Found"
    name = "Unknown"
    category = "Unknown"
    card_id = "N/A"
    
    if user:
        user_dict = dict(user)
        name = user_dict['name']
        category = user_dict['category']
        card_id = user_dict['card_id']
        expire_date_str = user_dict['expire_date']
        
        # ৪. মেয়াদ উত্তীর্ণ (Expiry Date) চেক করা
        is_expired = False
        if expire_date_str:
            for fmt in ('%Y-%m-%d', '%d-%m-%Y'):
                try:
                    exp_obj = datetime.strptime(str(expire_date_str).strip(), fmt).date()
                    if today_date > exp_obj:
                        is_expired = True
                    break
                except ValueError:
                    continue
        
        if is_expired:
            reason = "Card Expired"
            status = "Denied"
        else:
            status = "Granted"
            reason = "Access Allowed"
    else:
        reason = "Invalid Access Credential"

    # ৫. এন্ট্রি বা লগ ডাটাবেসে সেভ করা
    conn.execute('''
        INSERT INTO access_logs (device_id, card_id, name, category, status, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (device_id, card_id, name, category, status, reason))
    conn.commit()
    conn.close()
    
    # মেশিনের জন্য JSON রেসপন্স (মেশিন এই রেসপন্স পেলে রিলের মাধ্যমে দরজা খুলবে)
    return jsonify({
        "status": status,
        "message": reason,
        "name": name,
        "category": category
    })

@app.route('/access_logs')
@role_required(['admin', 'moderator', 'viewer'])
def view_access_logs():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # ফর্ম থেকে ফিল্টার বা ডাউনলোড প্যারামিটার নেওয়া
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    selected_gate = request.args.get('gate', '')
    search_query = request.args.get('search', '').strip()
    action = request.args.get('action', '') # 'view' অথবা 'download'

    query = "SELECT * FROM access_logs WHERE 1=1"
    params = []

    if start_date and end_date:
        query += " AND DATE(timestamp) BETWEEN ? AND ?"
        params.extend([start_date, end_date])

    if selected_gate:
        query += " AND device_id = ?"
        params.append(selected_gate)

    if search_query:
        query += " AND (card_id LIKE ? OR name LIKE ?)"
        params.extend([f'%{search_query}%', f'%{search_query}%'])

    query += " ORDER BY id DESC"
    logs = conn.execute(query, params).fetchall()

    # ড্রপডাউনের জন্য ইউনিক গেইট বা ডিভাইস লিস্ট নিয়ে আসা
    gates = conn.execute("SELECT DISTINCT device_id FROM access_logs WHERE device_id IS NOT NULL").fetchall()

    # যদি ডাউনলোড করতে চায় (CSV ফরম্যাটে)
    if action == 'download':
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Timestamp', 'Device ID', 'Card ID', 'Name', 'Category', 'Status', 'Reason'])
        for row in logs:
            cw.writerow([row['id'], row['timestamp'], row['device_id'], row['card_id'], row['name'], row['category'], row['status'], row['reason']])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=access_logs_report.csv"
        output.headers["Content-type"] = "text/csv"
        conn.close()
        return output

    conn.close()
    return render_template('access_logs.html', logs=logs, gates=gates, start_date=start_date, end_date=end_date, selected_gate=selected_gate, search_query=search_query)

# 🚪 সিস্টেম লগআউট
@app.route('/logout')
def logout():
    is_customer = 'customer_id' in session
    session.clear()
    flash('সিস্টেম থেকে নিরাপদে লগআউট করা হয়েছে।', 'info')
    if is_customer:
        return redirect(url_for('customer_login'))
    return redirect(url_for('login'))

@app.route('/customer/logout')
def customer_logout():
    # কাস্টমার সেশন ক্লিয়ার করা
    session.pop('customer_id', None)
    flash('সফলভাবে লগআউট করা হয়েছে!', 'success')
    return redirect(url_for('customer_login'))

def update_database():
    conn = sqlite3.connect('database.db')
    try:
        # উদাহরণস্বরূপ bills টেবিলে একটি নতুন note কলাম যোগ করা
        conn.execute("ALTER TABLE bills ADD COLUMN note TEXT")
        conn.commit()
        print("নতুন কলাম সফলভাবে যুক্ত করা হয়েছে!")
    except Exception as e:
        print("কলামটি সম্ভবত আগেই ছিল বা এরর এসেছে:", str(e))
    finally:
        conn.close()

if __name__ == '__main__':
    update_database()  # এখানে ফাংশনটি কল করে দিতে হবে
    app.run(debug=True, port=5000)
