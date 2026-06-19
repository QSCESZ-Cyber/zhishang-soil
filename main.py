from flask import Flask, render_template, request, jsonify, redirect, session
import pymysql
import random
from datetime import datetime, timedelta
import hashlib
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)
# 密钥从环境变量读取
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# 数据库配置全部取自环境变量，不再写死本地
db_config = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "cursorclass": pymysql.cursors.DictCursor
}

def auto_create_database():
    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            charset="utf8mb4"
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DB_NAME')} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ 数据库自动创建完成")
    except Exception as e:
        print("❌ 创建数据库失败", e)

# 云数据库一般提前手动建库，线上可以注释此行避免权限不足
# auto_create_database()

def get_db():
    return pymysql.connect(**db_config)

def encrypt_password(pwd):
    salt = "your_random_salt"
    return hashlib.sha256((pwd + salt).encode()).hexdigest()

def login_required():
    if 'user_phone' not in session:
        return redirect('/')
    return None

@app.route('/')
def index():
    return render_template('index1.html')

@app.route('/home_page')
def home_page():
    chk = login_required()
    if chk: return chk
    return render_template('home_page.html')

@app.route('/device_selector')
def device_selector():
    chk = login_required()
    if chk: return chk
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM devices WHERE user_id=(SELECT id FROM users WHERE phone=%s)", (session['user_phone'],))
    devs = cur.fetchall()
    db.close()
    return render_template('device_selector.html', devices=devs)

@app.route('/device')
def device():
    chk = login_required()
    if chk: return chk
    return render_template('device.html')

@app.route('/my')
def my():
    chk = login_required()
    if chk: return chk
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE phone=%s", (session['user_phone'],))
    uid = cur.fetchone()['id']

    cur.execute("SELECT nickname, avatar_data FROM user_profile WHERE user_id=%s", (uid,))
    row = cur.fetchone()
    nickname = "未设置昵称"
    avatar = ""
    if row:
        if row['nickname']: nickname = row['nickname']
        if row['avatar_data']: avatar = row['avatar_data']

    cur.execute("SELECT COUNT(*) cnt FROM devices WHERE user_id=%s", (uid,))
    cnt = cur.fetchone()['cnt']
    db.close()
    return render_template('user.html', nickname=nickname, avatar=avatar, device_count=cnt)

@app.route('/add_device')
def add_device():
    chk = login_required()
    if chk: return chk
    return render_template('add_device.html')

@app.route('/edit_nickname', methods=['POST'])
def edit_nickname():
    chk = login_required()
    if chk: return chk
    nn = request.form.get('nickname','').strip()
    if not nn: return "昵称不能为空"
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE phone=%s", (session['user_phone'],))
    uid = cur.fetchone()['id']
    cur.execute("SELECT id FROM user_profile WHERE user_id=%s", (uid,))
    if cur.fetchone():
        cur.execute("UPDATE user_profile SET nickname=%s WHERE user_id=%s", (nn, uid))
    else:
        cur.execute("INSERT INTO user_profile (user_id, nickname) VALUES (%s,%s)", (uid, nn))
    db.commit()
    db.close()
    return redirect('/my')

@app.route('/do_add_device', methods=['POST'])
def do_add_device():
    if 'user_phone' not in session:
        return jsonify(ok=False, msg="请登录")
    did = request.form.get('device_id')
    dnm = request.form.get('device_name')
    loc = request.form.get('location')
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE phone=%s", (session['user_phone'],))
    uid = cur.fetchone()['id']
    try:
        cur.execute("INSERT INTO devices (device_id, device_name, location, user_id) VALUES (%s,%s,%s,%s)",
                    (did, dnm, loc, uid))
        db.commit()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, msg=str(e))
    finally:
        db.close()

@app.route('/login', methods=['POST'])
def login():
    phone = request.form.get('phone', '').strip()
    pwd = request.form.get('password', '').strip()

    if len(phone) != 11:
            return jsonify({"ok": False, "msg": "手机号必须是11位"})
    if len(pwd) < 6:
            return jsonify({"ok": False, "msg": "密码不能少于6位"})

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE phone=%s", (phone,))
    u = cur.fetchone()

    if not u:
        db.close()
        return jsonify({"ok": False, "msg": "该手机号未注册"})

    if u['password'] != encrypt_password(pwd):
        db.close()
        return jsonify({"ok": False, "msg": "密码错误"})

    session['user_phone'] = phone
    session['user_id'] = u['id']
    db.close()

    return jsonify({"ok": True, "msg": "登录成功"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/send_code', methods=['POST'])
def send_code():
    phone = request.form.get('phone')
    code = ''.join(random.choices('0123456789',k=6))
    exp = datetime.now() + timedelta(minutes=5)
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM sms_codes WHERE phone=%s", (phone,))
    cur.execute("INSERT INTO sms_codes (phone, code, expire_time) VALUES (%s,%s,%s)",
                (phone, code, exp))
    db.commit()
    db.close()
    return jsonify(msg="发送成功")

@app.route('/register', methods=['POST'])
def register():
    phone = request.form.get('phone', '').strip()
    pwd = request.form.get('password', '').strip()

    if len(pwd) < 6:
        return jsonify({"ok": False, "msg": "密码不能少于6位"})

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE phone=%s", (phone,))
    if cur.fetchone():
        db.close()
        return jsonify({"ok": False, "msg": "该手机号已被注册"})

    cur.execute("INSERT INTO users (phone, password) VALUES (%s,%s)",
                (phone, encrypt_password(pwd)))
    db.commit()
    db.close()

    return jsonify({"ok": True, "msg": "注册成功"})

@app.route('/forget_password')
def forget_pwd():
    return render_template('forget_password.html')

@app.route('/reset_password')
def reset_pwd():
    return render_template('reset_password.html')

@app.route('/do_change_password', methods=['POST'])
def do_change_pwd():
    if 'user_phone' not in session:
        return jsonify(ok=False)
    old = request.form.get('old_pwd')
    neo = request.form.get('new_pwd')
    db = get_db()
    cur = db.cursor()
    e_old = encrypt_password(old)
    cur.execute("SELECT * FROM users WHERE phone=%s AND password=%s",
                (session['user_phone'], e_old))
    if not cur.fetchone():
        db.close()
        return jsonify(ok=False, msg="原密码错误")
    e_neo = encrypt_password(neo)
    cur.execute("UPDATE users SET password=%s WHERE phone=%s",
                (e_neo, session['user_phone']))
    db.commit()
    db.close()
    return jsonify(ok=True)

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    try:
        if 'user_phone' not in session:
            return jsonify({"ok": False})

        data = request.get_json()
        avatar = data.get('avatar', '')

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE phone=%s", (session['user_phone'],))
        user_id = cursor.fetchone()['id']

        cursor.execute("SELECT * FROM user_profile WHERE user_id=%s", (user_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE user_profile SET avatar_data=%s WHERE user_id=%s", (avatar, user_id))
        else:
            cursor.execute("INSERT INTO user_profile (user_id, nickname, avatar_data) VALUES (%s,%s,%s)",
                           (user_id, "未设置", avatar))

        db.commit()
        db.close()
        return jsonify({"ok": True})
    except Exception as e:
        print("错误：", e)
        return jsonify({"ok": False})

@app.route('/api/devices')
def api_devices():
    if 'user_phone' not in session:
        return jsonify([])
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT * FROM devices 
        WHERE user_id=(SELECT id FROM users WHERE phone=%s)
    """, (session['user_phone'],))
    res = cur.fetchall()
    db.close()
    return jsonify(res)

@app.route('/api/devices/<device_id>/update', methods=['POST'])
def update_device(device_id):
    if 'user_phone' not in session:
        return jsonify(ok=False)

    data = request.get_json()
    new_device_id = data.get('device_id')
    device_name = data.get('device_name')
    location = data.get('location', '')

    if not new_device_id or not device_name:
        return jsonify(ok=False)

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE devices 
        SET device_id=%s, device_name=%s, location=%s
        WHERE device_id=%s 
        AND user_id=(SELECT id FROM users WHERE phone=%s)
    """, (new_device_id, device_name, location, device_id, session['user_phone']))

    db.commit()
    db.close()
    return jsonify(ok=True)

@app.route('/api/devices/<did>/realtime')
def api_realtime(did):
    if 'user_phone' not in session:
        return jsonify(temperature=0, humidity=0, timestamp="无数据")

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT temperature,humidity,create_time 
        FROM sensor_data 
        WHERE device_id=%s 
        AND user_id=(SELECT id FROM users WHERE phone=%s)
        ORDER BY create_time DESC LIMIT 1
    """, (did, session['user_phone']))
    row = cur.fetchone()
    db.close()

    if not row:
        return jsonify(temperature=0, humidity=0, timestamp="无数据")
    return jsonify(
        temperature=round(float(row['temperature']),1),
        humidity=round(float(row['humidity']),1),
        timestamp=str(row['create_time'])
    )

@app.route('/api/devices/<did>/history')
def api_history(did):
    if 'user_phone' not in session:
        return jsonify([])

    l = request.args.get('limit',20,type=int)
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT temperature,humidity,create_time 
        FROM sensor_data 
        WHERE device_id=%s 
        AND user_id=(SELECT id FROM users WHERE phone=%s)
        ORDER BY create_time DESC LIMIT %s
    """, (did, session['user_phone'], l))
    rows = cur.fetchall()
    db.close()

    rows.reverse()
    out = []
    for r in rows:
        out.append({
            "temperature": round(float(r['temperature']),1),
            "humidity": round(float(r['humidity']),1),
            "timestamp": str(r['create_time'])
        })
    return jsonify(out)

@app.route('/api/device/history/day/<did>')
def api_day(did):
    if 'user_phone' not in session:
        return jsonify([])

    days = request.args.get('days',7,type=int)
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT DATE(create_time) day, AVG(temperature) t_avg, AVG(humidity) h_avg
        FROM sensor_data 
        WHERE device_id=%s 
        AND user_id=(SELECT id FROM users WHERE phone=%s)
        AND create_time >= DATE_SUB(NOW(),INTERVAL %s DAY)
        GROUP BY DATE(create_time) ORDER BY day ASC
    """, (did, session['user_phone'], days))
    rows = cur.fetchall()
    db.close()

    out = []
    for r in rows:
        out.append({
            "day": str(r['day']),
            "t_avg": round(float(r['t_avg']),1),
            "h_avg": round(float(r['h_avg']),1)
        })
    return jsonify(out)

@app.route('/api/devices/<did>', methods=['DELETE'])
def api_del(did):
    if 'user_phone' not in session:
        return jsonify(ok=False)
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM devices WHERE device_id=%s AND user_id=(SELECT id FROM users WHERE phone=%s)",
                (did, session['user_phone']))
    db.commit()
    db.close()
    return jsonify(ok=True)

def init_tables():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        phone VARCHAR(11) UNIQUE NOT NULL,
        password VARCHAR(64) NOT NULL
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_info (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT UNIQUE NOT NULL,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_profile (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT UNIQUE NOT NULL,
        nickname VARCHAR(50),
        avatar_data LONGTEXT,  
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INT PRIMARY KEY AUTO_INCREMENT,
        device_id VARCHAR(50) NOT NULL,
        device_name VARCHAR(100),
        location VARCHAR(200),
        user_id INT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sms_codes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        phone VARCHAR(11),
        code VARCHAR(6),
        expire_time DATETIME
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INT PRIMARY KEY AUTO_INCREMENT,
        device_id VARCHAR(50) NOT NULL,
        user_id INT NOT NULL,    
        temperature FLOAT,
        humidity FLOAT,
        create_time DATETIME DEFAULT NOW(),
        INDEX idx_user_device (user_id, device_id)  
    )
    """)
    db.commit()
    db.close()

# 线上必须关闭debug
if __name__ == '__main__':
    init_tables()
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))