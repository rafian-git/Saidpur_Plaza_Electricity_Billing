import sqlite3

def update_passwords():
    # আপনার ডাটাবেস ফাইলের নাম এখানে দিন (যদি অন্য নাম হয় পরিবর্তন করে নেবেন)
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # সবার জন্য ডিফল্ট পাসওয়ার্ড হিসেবে '123456' সেট করা হচ্ছে (আপনি চাইলে নিজের মতো বদলাতে পারেন)
    # অথবা সবার পাসওয়ার্ড প্লেইন টেক্সট করে দেওয়া হচ্ছে:
    cursor.execute("UPDATE users SET password = '123456'")
    
    conn.commit()
    conn.close()
    print("সকল ইউজারের পাসওয়ার্ড সফলভাবে প্লেইন টেক্সট ('123456') এ পরিবর্তন করা হয়েছে!")

if __name__ == '__main__':
    update_passwords()
    