from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import aiohttp
import asyncio
import re
import time
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'letiendung_secret_key_0969411158')
CORS(app)

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

TOKEN_CONFIG = {
    "fetch_token": "",
    "app_transaction": "",
    "hash_params": "",
    "hash_headers": "",
    "is_sandbox": False,
}

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

async def inject_gold(uid):
    url = "https://api.revenuecat.com/v1/receipts"
    body = {
        "product_id": "locket_199_1m", 
        "fetch_token": TOKEN_CONFIG['fetch_token'], 
        "app_transaction": TOKEN_CONFIG['app_transaction'],
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
    
    current_headers = HEADERS.copy()
    if TOKEN_CONFIG.get('hash_params'):
        current_headers['X-Post-Params-Hash'] = TOKEN_CONFIG['hash_params']
    if TOKEN_CONFIG.get('hash_headers'):
        current_headers['X-Headers-Hash'] = TOKEN_CONFIG['hash_headers']

    async with aiohttp.ClientSession() as session:
        for attempt in range(5):
            try:
                async with session.post(url, headers=current_headers, json=body, timeout=15) as res:
                    if res.status == 200:
                        await asyncio.sleep(2)
                        status = await check_status(uid)
                        if status and status.get('active'):
                            return {"success": True, "msg": f"Kích hoạt thành công! Hết hạn: {status.get('expires')}"}
                        return {"success": False, "msg": "Server nhận nhưng chưa cấp Gold."}
                    elif res.status == 529:
                        await asyncio.sleep(2)
                        continue
                    else:
                        try:
                            resp_json = await res.json()
                            msg = resp_json.get('message', str(res.status))
                        except:
                            msg = str(res.status)
                        return {"success": False, "msg": f"Bị từ chối: {msg}"}
            except Exception as e:
                if attempt == 4:
                    return {"success": False, "msg": f"Lỗi mạng: {str(e)}"}
                await asyncio.sleep(2)
    return {"success": False, "msg": "Thử lại quá 5 lần."}

@app.route('/')
def index():
    return render_template('index.html', is_admin=session.get('is_admin', False))

@app.route('/api/check_admin', methods=['GET'])
def check_admin():
    return jsonify({"is_admin": session.get('is_admin', False)})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if username == 'dungledev' and password == 'dunglengungo':
        session['is_admin'] = True
        return jsonify({"success": True, "msg": "Đăng nhập Admin thành công!"})
    return jsonify({"success": False, "msg": "Sai tài khoản hoặc mật khẩu!"})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('is_admin', None)
    return jsonify({"success": True})

@app.route('/api/inject', methods=['POST'])
def api_inject():
    if not session.get('is_admin'):
        return jsonify({"success": False, "msg": "Bạn không phải Admin! Không có quyền Buff."})
    data = request.json
    user_input = data.get('username', '').strip()
    if not user_input:
        return jsonify({"success": False, "msg": "Vui lòng nhập Username hoặc Link."})
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    uid = loop.run_until_complete(resolve_uid(user_input))
    
    if not uid:
        return jsonify({"success": False, "msg": "Không tìm thấy UID từ User/Link này."})
    
    result = loop.run_until_complete(inject_gold(uid))
    result['uid'] = uid
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
