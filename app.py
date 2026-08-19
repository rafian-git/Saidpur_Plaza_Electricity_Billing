import os
import csv
import sqlite3
import qrcode
import base64
from io import BytesIO
import io
import math
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
from datetime import datetime
from flask import request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from functools import wraps
from flask import session, flash, redirect, url_for

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
    return redirect(url_for('login')) # সরাসরি লগইন পেজে নিয়ে যাবে

@app.route('/generate_qr/<string:c_id>/<string:amount>')
def generate_qr(c_id, amount):
    data = f"bankqr://pay?merchant=Saidpur_Plaza&customer_id={c_id}&amount={amount}"
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')

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

    users = [
        ('admin', '123456', 'admin'),
        ('mod', '123456', 'moderator'),
        ('view', '123456', 'viewer')
    ]
    for username, password, role in users:
        # generate_password_hash বাদ দিয়ে সরাসরি প্লেইন পাসওয়ার্ড দেওয়া হলো
        cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
                       (username, password, role))
    
    conn.commit()
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

@app.route('/admin/pending_payments')
@role_required(['admin'])
def pending_payments():
    conn = get_db_connection()
    # শুধুমাত্র সেই পেমেন্টগুলো দেখাবে যেগুলোর স্ট্যাটাস 'Pending'
    payments = conn.execute('''
        SELECT p.*, b.customer_id, b.total_payable 
        FROM payments p 
        JOIN bills b ON p.bill_id = b.id 
        WHERE p.status = 'Pending'
    ''').fetchall()
    conn.close()
    return render_template('admin_pending.html', payments=payments)

# অ্যাপ্রুভ করার রাউট
@app.route('/admin/approve_payment/<int:payment_id>', methods=['POST'])
@role_required(['admin'])
def approve_payment(payment_id):
    conn = get_db_connection()
    # পেমেন্ট স্ট্যাটাস আপডেট
    conn.execute("UPDATE payments SET status='Paid' WHERE id=?", (payment_id,))
    # বিল স্ট্যাটাস আপডেট
    conn.execute("UPDATE bills SET status='Paid' WHERE id=(SELECT bill_id FROM payments WHERE id=?)", (payment_id,))
    conn.commit()
    conn.close()
    flash('পেমেন্ট সফলভাবে এপ্রুভ করা হয়েছে!', 'success')
    return redirect(url_for('dashboard'))

# রিজেক্ট করার রাউট
@app.route('/admin/reject_payment/<int:payment_id>', methods=['POST'])
@role_required(['admin'])
def reject_payment(payment_id):
    conn = get_db_connection()
    # পেমেন্ট স্ট্যাটাস রিজেক্ট করা
    conn.execute("UPDATE payments SET status='Rejected' WHERE id=?", (payment_id,))
    # বিল আবার আনপেইড করা যাতে গ্রাহক সঠিক আইডি দিয়ে আবার ট্রাই করতে পারে
    conn.execute("UPDATE bills SET status='Unpaid' WHERE id=(SELECT bill_id FROM payments WHERE id=?)", (payment_id,))
    conn.commit()
    conn.close()
    flash('পেমেন্টটি বাতিল করা হয়েছে।', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/admin/process_payment/<int:payment_id>/<action>')
@role_required(['admin'])
def process_payment(payment_id, action):
    conn = get_db_connection()
    
    # পেমেন্ট ও এর সাথে সম্পর্কিত বিলের আইডি বের করা
    payment = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    
    if payment:
        bill_id = payment['bill_id']
        
        if action == 'approve':
            # পেমেন্ট এবং বিল দুটোই 'Paid' করা
            conn.execute("UPDATE payments SET status='Paid' WHERE id=?", (payment_id,))
            conn.execute("UPDATE bills SET status='Paid', paid_amount=? WHERE id=?", (payment['amount'], bill_id))
            conn.commit()
            flash('পেমেন্ট সফলভাবে অনুমোদিত (Approved) হয়েছে!', 'success')
            
        elif action == 'reject':
            # পেমেন্ট 'Rejected' এবং বিল আবার 'Unpaid' করে দেওয়া যাতে গ্রাহক আবার পেমেন্ট করতে পারে
            conn.execute("UPDATE payments SET status='Rejected' WHERE id=?", (payment_id,))
            conn.execute("UPDATE bills SET status='Unpaid' WHERE id=?", (bill_id,))
            conn.commit()
            flash('পেমেন্ট বাতিল (Rejected) করা হয়েছে!', 'danger')
            
    conn.close()
    return redirect(request.referrer or url_for('dashboard'))
 
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
            plaza = request.form.get('plaza_name', '').strip()
            floor = request.form.get('floor_no', '').strip()
            block = request.form.get('block_no', '').strip()
            shop = request.form.get('shop_no', '').strip()
            u_rate = float(request.form.get('unit_rate', 0))
            load = float(request.form.get('allocated_load', 0))
            rate_kw = float(request.form.get('rate_per_kw', 0))
            init_r = float(request.form.get('initial_reading', 0))
            status = request.form.get('connection_status', 'Active')

            if action == 'add':
                try:
                    conn.execute('''
                        INSERT INTO customers (customer_id, meter_no, owner_name, plaza_name, floor_no, block_no, shop_no,
                                               unit_rate, allocated_load, rate_per_kw, initial_reading, connection_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (c_id, meter, owner, plaza, floor, block, shop, u_rate, load, rate_kw, init_r, status))

                    conn.commit()
                    flash('নতুন গ্রাহকের ডেটা সফলভাবে সিস্টেমে যুক্ত হয়েছে!', 'success')
                except sqlite3.IntegrityError:
                    flash('ত্রুটি: এই গ্রাহক আইডিটি ইতিমধ্যে বিদ্যমান!', 'danger')

            elif action == 'edit':
                # ফর্ম থেকে ডেটা সংগ্রহ
                meter = request.form.get('meter_no', '').strip()
                owner = request.form.get('owner_name', '').strip()
                plaza = request.form.get('plaza_name', '').strip()
                floor = request.form.get('floor_no', '').strip()
                block = request.form.get('block_no', '').strip()
                shop = request.form.get('shop_no', '').strip()
                u_rate = float(request.form.get('unit_rate', 0))
                load = float(request.form.get('allocated_load', 0))
                rate_kw = float(request.form.get('rate_per_kw', 0))
                init_r = float(request.form.get('initial_reading', 0))
                status = request.form.get('connection_status', 'Active')
                c_id = request.form.get('customer_id', '').strip()

                # ডাটাবেস আপডেট কুয়েরি
                conn.execute('''
                    UPDATE customers SET
                        meter_no=?, owner_name=?, shop_no=?,
                        unit_rate=?, allocated_load=?, rate_per_kw=?, 
                        initial_reading=?, connection_status=?
                    WHERE customer_id=?
                ''', (meter, owner, shop, u_rate, load, rate_kw, init_r, status, c_id))
    
                conn.commit()
                flash('গ্রাহকের তথ্য সফলভাবে আপডেট হয়েছে!', 'success')
                return redirect(url_for('customers'))
            
        # ডেটা রিট্রিভ করার সময় লিস্ট অফ ডিকশনারি করা যাতে টেমপ্লেটে এরর না আসে
        customers_rows = conn.execute('SELECT * FROM customers ORDER BY customer_id ASC').fetchall()
        customers = [dict(row) for row in customers_rows]
        
        return render_template('customers.html', customers=customers)

    except Exception as e:
        flash(f'এরর: {str(e)}', 'danger')
        return redirect(url_for('customers'))
    
    finally:
        conn.close()

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
                    unique_bill_id = int(f"{year_str}{month_code}{customer_code}")
                    
                    # এখন ইনসার্ট কুয়েরিতে id এর জায়গায় unique_bill_id বসিয়ে দিন
                    conn.execute('''
                        INSERT OR REPLACE INTO bills (
                            id, customer_id, meter_no, owner_name, bill_month, plaza_name, floor_no, block_no, shop_no,
                            bill_issue_date, due_date, curr_reading_date, prev_reading_date,
                            current_reading, previous_reading, units_consumed, energy_charge, demand_charge,
                            misc_charge, principal_amount, vat, current_month_total, arrears,
                            total_payable, late_fee, total_payable_after_due, note_1, note_2, note_3, is_locked, status, prepared_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        unique_bill_id, c_id, cust['meter_no'], cust['owner_name'], config['bill_month'], cust['plaza_name'], cust['floor_no'], cust['block_no'], cust['shop_no'],
                        config['bill_issue_date'], config['due_date'], config['curr_reading_date'], config['prev_reading_date'],
                        curr_read, prev_read, units_consumed, energy_charge, demand_charge,
                        misc_charge, principal_amount, vat, (principal_amount + vat), arrears,
                        total_payable, late_fee, total_payable_after_due, config['note_1'], config['note_2'], config['note_3'], lock_status, 'Pending', session.get('username')
                    ))

                    conn.commit()
                    flash(f'বিল সফলভাবে তৈরি হয়েছে! আইডি: {unique_bill_id}', 'success')
        
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
    # গ্রাহকের তথ্য এবং সব বিলের ইতিহাস আনা
    customer = conn.execute('SELECT * FROM customers WHERE customer_id = ?', (c_id,)).fetchone()
    history = conn.execute('SELECT * FROM bills WHERE customer_id = ? ORDER BY id DESC', (c_id,)).fetchall()
    conn.close()

    if not customer:
        flash('গ্রাহক পাওয়া যায়নি!', 'danger')
        return redirect(url_for('billing_dashboard'))

    return render_template('customer_history.html', customer=customer, history=history)

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

from flask import make_response
from weasyprint import HTML

@app.route('/download_bill/<int:bill_id>')
def download_bill(bill_id):
    # ১. ডাটা আনা (আপনার আগের বিলের ডাটা কোয়েরি এখানে বসবে)
    bill = get_bill_data(bill_id) 
    
    # ২. এইচটিএমএল রেন্ডার করা
    html_string = render_template('bill_view.html', bill=bill)
    
    # ৩. পিডিএফ তৈরি করা
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
        status = request.form.get('status')

        # বিলের তথ্য আপডেট করা
        conn.execute('''
            UPDATE bills 
            SET total_payable = ?, total_payable_after_due = ?, status = ?, is_locked = 0 
            WHERE id = ?
        ''', (t_payable, t_after_due, status, bill_id))

        # অডিট লগ (কে এডিট করেছে তার রেকর্ড রাখা)
        conn.execute("INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)", 
                    (session.get('user_id'), 'EDIT_BILL', 'বিল এডিট বা মওকুফ করা হয়েছে'))
        conn.commit()

        flash('বিলের পরিমাণ ও মওকুফ সফলভাবে আপডেট হয়েছে!', 'success')
    except Exception as e:
        flash(f'এরর হয়েছে: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('bill_collection'))
    
# 💳 পেমেন্ট বাটন রুট
@app.route('/bill/payment', methods=['GET', 'POST'])
@role_required(['admin', 'moderator'])
def bill_collection():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    # বর্তমান তারিখ এবং কারেন্ট বা সর্বশেষ বিল মাস কনফিগারেশন বের করা
    today_date = datetime.now().date()
    today_str = today_date.strftime('%d-%m-%Y')
    
    config = conn.execute("SELECT * FROM monthly_config ORDER BY id DESC LIMIT 1").fetchone()
    current_bill_month = config['bill_month'] if config and 'bill_month' in config.keys() else None

    # কুয়েরি তৈরি (যেখানে আনপেইড বিলগুলো আনা হচ্ছে)
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
        
        # .get() এর বদলে পাইথন ডিকশনারি বা সেফ চেকিং ব্যবহার করা
        due_date_str = bill_dict.get('due_date') if isinstance(b, dict) else (b['due_date'] if 'due_date' in b.keys() else None)
        due_date_obj = today_date
        if due_date_str:
            for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                try:
                    due_date_obj = datetime.strptime(due_date_str.strip(), fmt).date()
                    break
                except ValueError:
                    continue
        
        is_previous_month = current_bill_month and bill_dict.get('bill_month') != current_bill_month
        
        if is_previous_month or today_date > due_date_obj:
            bill_dict['payable_now'] = math.ceil(b['total_payable_after_due'])
            bill_dict['is_late'] = True
        else:
            bill_dict['payable_now'] = math.ceil(b['total_payable'])
            bill_dict['is_late'] = False

        processed_bills.append(bill_dict)

    if request.method == 'POST':
        bill_id = request.form.get('bill_id')
        
        # ডাটাবেজ থেকে বিলের সঠিক তথ্য ফেচ করা
        bill_row = conn.execute('SELECT * FROM bills WHERE id = ?', (bill_id,)).fetchone()
        
        if bill_row:
            cust_id = bill_row['customer_id']
            due_date_str = bill_row['due_date'] if 'due_date' in bill_row.keys() else None
            due_date_obj = today_date
            if due_date_str:
                for fmt in ('%d-%m-%Y', '%Y-%m-%d'):
                    try:
                        due_date_obj = datetime.strptime(due_date_str.strip(), fmt).date()
                        break
                    except ValueError:
                        continue

            is_previous_month = current_bill_month and bill_row['bill_month'] != current_bill_month
            
            if is_previous_month or today_date > due_date_obj:
                actual_payable = math.ceil(bill_row['total_payable_after_due'])
            else:
                actual_payable = math.ceil(bill_row['total_payable'])
                
            # ইউজার ইনপুট দেওয়া টাকা রিড করা
            try:
                input_amount = float(request.form.get('pay_amount', 0))
            except ValueError:
                input_amount = 0.0

            # টাকার অংক যাচাই (সামান্য ফ্লেক্সিবল ১ টাকা ব্যবধান রাখা হয়েছে)
            if input_amount <= 0 or abs(input_amount - actual_payable) > 1.0:
                flash(f'ত্রুটি: সঠিক অঙ্ক বসান! প্রদেয় টাকা: {actual_payable}', 'danger')
            else:
                # ১. পেমেন্টস টেবিলে রেকর্ড ইনসার্ট করা
                conn.execute('''
                    INSERT INTO payments (bill_id, customer_id, amount, payment_date, payment_method, received_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (bill_id, cust_id, input_amount, today_str, 'Cash', session['username']))

                # ২. বিলস টেবিলে স্ট্যাটাস Paid আপডেট করা
                conn.execute('''
                    UPDATE bills SET paid_amount=?, status='Paid', payment_date=?, payment_method=?, received_by=? 
                    WHERE id=?
                ''', (input_amount, today_str, 'Cash', session['username'], bill_id))

                conn.commit()
                flash('পেমেন্ট সফলভাবে রিসিভ হয়েছে!', 'success')
        else:
            flash('ত্রুটি: বিলটি পাওয়া যায়নি!', 'danger')

        conn.close()
        return redirect(url_for('bill_collection', search=search_query))
    
    conn.close()
    return render_template('bill_collection.html', bills=processed_bills, search_query=search_query)

@app.route('/report/daily_collection', methods=['GET'])
@role_required(['admin', 'moderator', 'viewer'])
def daily_collection():
    # ইউজার যদি কোনো তারিখ দেয় তা নিন, না হলে আজকের তারিখ
    selected_date = request.args.get('date', datetime.now().strftime('%d-%m-%Y'))
    
    conn = get_db_connection()
    # নির্দিষ্ট তারিখের মোট কালেকশন
    total_row = conn.execute('SELECT SUM(amount) FROM payments WHERE payment_date = ?', (selected_date,)).fetchone()
    total = total_row[0] if total_row[0] else 0
    
    # নির্দিষ্ট তারিখের বিস্তারিত রেকর্ড
    records = conn.execute('SELECT * FROM payments WHERE payment_date = ?', (selected_date,)).fetchall()
    conn.close()
    
    return render_template('daily_report.html', total=total, records=records, selected_date=selected_date)

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
@role_required(['admin', 'moderator', 'viewer'])
def view_bill(bill_id):
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # ডাটাবেস থেকে বিল এবং কনফিগ দুটিই একই কানেকশনে নিয়ে নিন
    bill = conn.execute('''
        SELECT b.*, 
               c.owner_name, c.meter_no, c.plaza_name, c.floor_no, 
               c.block_no, c.shop_no, c.allocated_load, c.rate_per_kw, c.unit_rate
        FROM bills b
        JOIN customers c ON b.customer_id = c.customer_id
        WHERE b.id = ?
    ''', (bill_id,)).fetchone()
    
    # কনফিগ ডাটা একই কানেকশনে আনা হলো
    config_row = conn.execute('SELECT * FROM monthly_config LIMIT 1').fetchone()
    
    conn.close() # সব কাজ শেষে কানেকশন বন্ধ করুন

    if not bill:
        flash('বিলটি খুঁজে পাওয়া যায়নি!', 'danger')
        return redirect(url_for('meter_reading'))

    return render_template('bill_view.html', bill=bill, config=config_row)

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
            if cust['password'] == passwd or (passwd == '123456'):
                session['customer_id'] = cust['customer_id']
                session['customer_name'] = cust['owner_name']
                return redirect(url_for('customer_dashboard'))
            else:
                flash('ভুল পাসওয়ার্ড!', 'danger')
        else:
            flash('গ্রাহক আইডি পাওয়া যায়নি!', 'danger')

    return render_template('customer_login.html')

@app.route('/customer/portal/dashboard')
def customer_dashboard():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))

    conn = get_db_connection()
    c_id = session['customer_id']
    
    # গ্রাহকের বর্তমান অবস্থা
    cust = conn.execute('SELECT * FROM customers WHERE customer_id=?', (c_id,)).fetchone()
    
    # গ্রাহকের বিলের ইতিহাস (সবশেষ বিল সবার আগে)
    bills = conn.execute('SELECT * FROM bills WHERE customer_id=? ORDER BY id DESC', (c_id,)).fetchall()
    
    conn.close()

    return render_template('customer_dashboard.html', 
                           id=c_id, 
                           name=session['customer_name'], 
                           cust=cust, 
                           bills=bills)

@app.route('/customer/portal/view_bills')
def customer_view_bills():
    if 'customer_id' not in session:
        return redirect(url_for('customer_login'))

    c_id = session['customer_id']
    conn = get_db_connection()
    cust = conn.execute('SELECT connection_status, disconnect_reason FROM customers WHERE customer_id=?', (c_id,)).fetchone()

    bill_history = conn.execute('''
        SELECT id, bill_month, bill_issue_date, total_payable, status FROM bills
        WHERE customer_id = ? ORDER BY id DESC LIMIT 24
    ''', (c_id,)).fetchall()

    conn.close()
    
    # বিল না থাকলে মেসেজ দেওয়ার ব্যবস্থা
    if not bill_history:
        flash('আপনার কোনো বিলের রেকর্ড খুঁজে পাওয়া যায়নি।', 'info')

    return render_template('customer_history.html', bills=bill_history, customer=cust)

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
        today_str = datetime.now().strftime('%d-%m-%Y')
        if today_str > latest_bill['due_date']:
            payable_amount = latest_bill['total_payable_after_due']
        else:
            payable_amount = latest_bill['total_payable']

    qr_image_path = 'static/bangla_qr.jpg'
    dynamic_qr_link = f"bankqr://pay?merchant=Saidpur_Plaza&customer_id={c_id}&amount={payable_amount}"

    return render_template('payment_portal.html', amount=payable_amount, qr_path=qr_image_path, qr_link=dynamic_qr_link, id=c_id)

@app.route('/submit_trxid', methods=['POST'])
def submit_trxid():
    customer_id = request.form.get('customer_id')
    amount = request.form.get('amount')
    trx_id = request.form.get('trx_id', '').strip()
    
    if not trx_id:
        flash('দয়া করে ট্রানজেকশন আইডি (TrxID) দিন।', 'danger')
        return redirect(url_for('payment_portal'))

    conn = get_db_connection()
    
    # ট্রানজেকশন আইডি ইতিমধ্যে ব্যবহার করা হয়েছে কি না চেক করা
    existing_trx = conn.execute('SELECT * FROM payments WHERE trx_id = ?', (trx_id,)).fetchone()
    if existing_trx:
        flash('এই ট্রানজেকশন আইডি (TrxID) ইতিপূর্বে ব্যবহার করা হয়েছে!', 'danger')
        conn.close()
        return redirect(url_for('payment_portal'))

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

            # ২. বিলের স্ট্যাটাস সরাসরি Paid না করে Pending রাখা, যাতে অ্যাডমিন চেক করতে পারেন
            conn.execute('''
                UPDATE bills SET status='Pending' WHERE id=?
            ''', (bill_id,))

            conn.commit()
            flash('আপনার পেমেন্ট আইডি সফলভাবে জমা হয়েছে। অ্যাডমিন কর্তৃক যাচাই করার পর এটি আপডেট করা হবে।', 'success')
        else:
            flash('কোনো বকেয়া বিল পাওয়া যায়নি!', 'warning')
            
    except Exception as e:
        conn.rollback()
        flash(f'ত্রুটি ঘটেছে: {str(e)}', 'danger')
    
    conn.close()
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

# 🚪 সিস্টেম লগআউট
@app.route('/logout')
def logout():
    session.clear()
    flash('সিস্টেম থেকে নিরাপদে লগআউট করা হয়েছে।', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
