import sqlite3
import os

DB_NAME = 'database.db'

import os

DB_NAME = 'database.db'

try:
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print("পুরানো ডাটাবেজ সফলভাবে মুছে ফেলা হয়েছে।")
except PermissionError:
    print("সতর্কতা: ডাটাবেজ ফাইলটি অন্য কোনো প্রসেসে চালু আছে! দয়া করে ফ্লাস্ক সার্ভার বন্ধ করে আবার চেষ্টা করুন।")

def init_database():
    # ফাইল মুছে ফেলা (সতর্কতা: এটি সব ডাটা মুছে ফেলবে)
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ১. ইউজার টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        role TEXT NOT NULL)''')

    # ২. কাস্টমার টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
                        customer_id TEXT PRIMARY KEY,
                        meter_no TEXT NOT NULL,
                        owner_name TEXT NOT NULL,
                        plaza_name TEXT NOT NULL,
                        floor_no TEXT NOT NULL,
                        block_no TEXT NOT NULL,
                        shop_no TEXT NOT NULL,
                        unit_rate REAL DEFAULT 0.0,
                        allocated_load REAL DEFAULT 0.0,
                        rate_per_kw REAL DEFAULT 0.0,
                        initial_reading REAL DEFAULT 0.0,
                        password TEXT DEFAULT '123456',
                        connection_status TEXT DEFAULT 'Connected',
                        disconnect_reason TEXT DEFAULT'')''')

    # ৩. বিদ্যুৎ বিল টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS bills (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bill_no TEXT,
                        customer_id INTEGER,
                        meter_no TEXT,
                        owner_name TEXT,
                        bill_month TEXT,
                        plaza_name TEXT,
                        floor_no TEXT,
                        block_no TEXT,
                        shop_no TEXT,
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
                        FOREIGN KEY (customer_id) REFERENCES customers (customer_id))''')
    
    # ৪. মাসিক কনফিগারেশন টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS monthly_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bill_month TEXT NOT NULL,
                        misc_charge REAL DEFAULT 0.0,
                        bill_issue_date TEXT,
                        due_date TEXT,
                        curr_reading_date TEXT,
                        prev_reading_date TEXT,
                        note_1 TEXT,
                        note_2 TEXT,
                        note_3 TEXT)''')
    
    # ৫. পেমেন্ট টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bill_id INTEGER NOT NULL,
                        customer_id TEXT NOT NULL,
                        amount REAL NOT NULL,
                        payment_date TEXT NOT NULL,
                        payment_method TEXT,
                        received_by TEXT,
                        FOREIGN KEY (bill_id) REFERENCES bills (id))''')
    
    # ডিফল্ট এডমিন ইউজার ইনসার্ট (প্লেইন পাসওয়ার্ড সহ)
    admin_pass = '123456'
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                   ('admin', admin_pass, 'admin'))
    
    conn.commit()
    conn.close()
    print("৫টি টেবিলসহ ডাটাবেস সফলভাবে তৈরি হয়েছে।")

if __name__ == '__main__':
    init_database()
