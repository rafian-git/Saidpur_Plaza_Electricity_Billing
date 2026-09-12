import sqlite3
import os

DB_NAME = 'database.db'

def init_database():
    conn = sqlite3.connect(DB_NAME)
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

    # ২. কাস্টমার টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            meter_no TEXT,
            owner_name TEXT,
            mobile_no TEXT,
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
            billing_msg_sent INTEGER DEFAULT 0,
            overdue_msg_sent INTEGER DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
    ''')
    
    # সেফটি চেক: যদি টেবিলটি অনেক পুরানো হয় এবং এই কলামগুলো না থাকে, তবে স্বয়ংক্রিয়ভাবে যোগ করে নেবে
    try:
        cursor.execute("ALTER TABLE bills ADD COLUMN billing_msg_sent INTEGER DEFAULT 0;")
    except sqlite3.OperationalError:
        pass # কলাম ইতিমধ্যে থাকলে ইগনোর করবে

    try:
        cursor.execute("ALTER TABLE bills ADD COLUMN overdue_msg_sent INTEGER DEFAULT 0;")
    except sqlite3.OperationalError:
        pass # কলাম ইতিমধ্যে থাকলে ইগনোর করবে

    # ৪. মাসিক কনফিগারেশন টেবিল
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

    # ৬. অডিট লগ টেবিল
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ডিফল্ট এডমিন ইউজার না থাকলে ইনসার্ট করা (डुप्लिकेट এড়াতে OR IGNORE ব্যবহার করা নিরাপদ)
    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, password, role) 
        VALUES (1, 'admin', '123456', 'admin')
    ''')
    
    conn.commit()
    conn.close()
    print("ডাটাবেস সফলভাবে তৈরি ও আপডেট হয়েছে!")

if __name__ == '__main__':
    init_database()
    