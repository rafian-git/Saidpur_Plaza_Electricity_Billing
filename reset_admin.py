import sqlite3
from werkzeug.security import generate_password_hash

def reset_admin():
    # আপনার ডাটাবেস ফাইলের নাম এখানে দিন (যেমন: database.db)
    conn = sqlite3.connect('database.db') 
    cursor = conn.cursor()
    
    # নতুন ইউজারনেম এবং পাসওয়ার্ড সেট করুন
    new_username = 'admin' 
    new_password = generate_password_hash('123456') # এখানে নতুন পাসওয়ার্ড দিন
    
    # ডাটাবেসে আপডেট করুন
    cursor.execute("UPDATE users SET password = ?, role = 'admin' WHERE username = ?", 
                   (new_password, new_username))
    
    conn.commit()
    conn.close()
    print("সফলভাবে পাসওয়ার্ড রিসেট হয়েছে! এখন 'admin' ইউজারনেম এবং '123456' পাসওয়ার্ড দিয়ে লগইন করুন।")

if __name__ == '__main__':
    reset_admin()
    