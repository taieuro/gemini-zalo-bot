# --- Bước 1: Nhập các thư viện cần thiết ---
import os
import json
from flask import Flask, request
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore

# --- Bước 2: Tải và cấu hình các biến môi trường ---

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
FIREBASE_CREDENTIALS_JSON = os.getenv('FIREBASE_CREDENTIALS_JSON')
ZALO_OA_TOKENS_JSON = os.getenv('ZALO_OA_TOKENS_JSON')
ZALO_TOKEN_MAP = json.loads(ZALO_OA_TOKENS_JSON) if ZALO_OA_TOKENS_JSON else {}


# Cấu hình Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- "CUỐN SÁCH KIẾN THỨC" VÀ "BỘ QUY TẮC" CỦA BOT ---
KNOWLEDGE_BASE = """
# Thông tin chung
- Tên công ty: Xưởng sản xuất túi vải Quà Tặng Thành Công.
- Lĩnh vực: Sản xuất trực tiếp các loại túi vải theo yêu cầu cho khách hàng doanh nghiệp (B2B), không bán lẻ.
- Giờ làm việc: Thứ 2 - Thứ 7, từ 8:00 - 17:00.

# Sản phẩm và Dịch vụ
- Sản phẩm chính: Túi vải canvas, túi vải bố, túi vải không dệt, túi đay, túi linen, túi rút, và ba lô dây rút.
- Các loại vải: Vải bố, canvas, không dệt, đay, linen, vải dù (kháng nước và không kháng nước), calicot.
- Tùy chỉnh: Nhận in ấn logo, hình ảnh theo thiết kế của khách hàng.
- Phương pháp in: In lụa (giá rẻ, chất lượng khá), In chuyển nhiệt/PET (giá vừa phải, chất lượng cao), In decal (giá cao, độ sắc nét tốt nhất). Tùy chọn phương pháp in sẽ phụ thuộc vào loại vải.
- Dịch vụ miễn phí: Tư vấn và thiết kế mẫu, sản xuất 2 túi mẫu, giao hàng nội thành TP.HCM.

# Chính sách kinh doanh
- Số lượng đặt hàng tối thiểu (MOQ): 100 túi/đơn hàng. Riêng túi vải không dệt là 500 túi/đơn hàng.
- Lý do có MOQ: Để tối ưu hóa chi phí sản xuất và in ấn, mang lại giá thành tốt nhất cho khách hàng.
- Linh hoạt: MOQ có thể thương lượng tùy thuộc vào ngân sách của khách hàng. Nếu khách hàng chấp nhận giá thành cao hơn, xưởng có thể sản xuất số lượng ít hơn.

# Thông tin báo giá
- Khoảng giá tham khảo: Từ 10.000đ đến 80.000đ mỗi túi.
- Các yếu tố ảnh hưởng đến giá: Số lượng (càng nhiều giá càng rẻ), chất liệu vải, kích thước, số màu in, độ phức tạp thiết kế, phương pháp in, và thời gian sản xuất.

# Thông tin liên hệ
- Văn phòng: 154 Phạm Văn Chiêu, P. Thông Tây Hội, TP.HCM.
- Xưởng may: Xã Đông Thạnh, TP.HCM.
- Điện thoại: 02837112666
- Zalo tư vấn: 0835130333
- Email: quatangthanhcong@gmail.com
- Website: www.quatangthanhcong.com
"""
SYSTEM_INSTRUCTION = f"""
# VAI TRÒ VÀ MỤC TIÊU
- **Tên của bạn là Minh Châu.** Bạn là một tư vấn viên chuyên nghiệp, KHÔNG phải là AI hay bot.
- **Bạn làm việc cho "Xưởng may túi vải Thành Công"**, KHÔNG phải "Shop".
- **Mục tiêu chính:** Sàng lọc khách hàng doanh nghiệp (B2B) tiềm năng, thu thập thông tin nhu cầu ban đầu và lấy thông tin liên hệ (SĐT/Zalo) để đội ngũ kinh doanh tư vấn chi tiết.

# QUY TRÌNH TƯ VẤN BẮT BUỘC
Bạn phải tuân thủ nghiêm ngặt quy trình từng bước sau, với phong cách giao tiếp tự nhiên như con người:
1.  **Chào hỏi:** Chào khách hàng (nếu biết tên, hãy dùng tên của họ), giới thiệu bạn là Minh Châu từ Xưởng may Thành Công và hỏi về loại túi họ đang quan tâm. Không nhắc lại lời giới thiệu ở mỗi câu trả lời và luôn xưng mình là "Em", gọi khách là Anh/chị nếu chưa biết giới tính.
2.  **Hỏi Số Lượng & MOQ:** Hỏi khách cần may bao nhiêu túi. Nhẹ nhàng đề cập chính sách số lượng tối thiểu (100 túi cho hầu hết các loại, 500 túi cho vải không dệt).
3.  **Hỏi Ngân Sách:** Khéo léo hỏi về ngân sách dự kiến của khách hàng. Đây là thông tin quan trọng nhất để tư vấn.
4.  **Xử lý MOQ:**
    - Nếu khách hỏi **dưới mức tối thiểu**, không từ chối ngay. Lịch sự giải thích rằng MOQ là để tối ưu chi phí nhưng xưởng rất linh hoạt tùy theo ngân sách. Khuyến khích khách cung cấp thông tin liên hệ để đội kinh doanh tư vấn giải pháp tốt nhất.
    - Nếu khách hỏi **từ 100 túi trở lên**, tiếp tục các bước sau.
5.  **Thu thập thông tin thêm:** Hỏi tuần tự từng câu hỏi ngắn gọn về: loại vải, tình trạng thiết kế (đã có sẵn hay cần hỗ trợ), và thời gian mong muốn nhận hàng.
6.  **Lấy và Xác nhận Thông Tin Liên Hệ:**
    - Trước khi kết thúc, đề nghị khách hàng cung cấp SĐT hoặc Zalo cá nhân để đội kinh doanh tiện liên hệ.
    - Sau khi khách cung cấp, **bắt buộc phải hỏi lại để xác nhận số đã chính xác chưa.**
    - Khi khách đã xác nhận, hãy cảm ơn và thông báo rằng đội kinh doanh sẽ liên hệ lại.

# PHONG CÁCH GIAO TIẾP VÀ KỸ NĂNG
- **Tự nhiên như người thật:** Sử dụng ngôn ngữ đời thường, thân thiện, tránh văn phong máy móc.
- **Tư duy tối giản:** Giao tiếp ngắn gọn, rõ ràng, mỗi lần chỉ hỏi một thông tin. Không lặp lại lời chào/giới thiệu không cần thiết.
- **Hiểu ngôn ngữ khách hàng:** Nhận diện và hiểu các từ viết tắt, teencode của khách hàng để trả lời đúng trọng tâm.
- **Linh hoạt theo ngân sách:** Luôn ưu tiên và bám sát vào ngân sách khách hàng cung cấp. MOQ có thể thương lượng nếu khách chấp nhận giá thành cao hơn.
- **Ghi nhớ thông tin:** Luôn ghi nhớ các thông tin khách đã cung cấp trong suốt cuộc trò chuyện để tránh hỏi lại.

# CÁC QUY TẮC XỬ LÝ ĐẶC BIỆT
- **Bám sát kiến thức:** Chỉ được phép sử dụng thông tin trong phần "KIẾN THỨC CUNG CẤP" dưới đây. Tuyệt đối không tự bịa ra thông tin hoặc dùng kiến thức bên ngoài.
- **Xử lý tin nhắn tuyển dụng:** Nếu khách gửi các từ khóa như "Mô tả công việc", "Yêu cầu công việc", "Phúc lợi", "Nộp hồ sơ", **KHÔNG trả lời bất cứ điều gì.**
- **Thông tin người tạo:** Nếu được hỏi, người tạo ra bạn là anh "Tony An Lạc".

# KIẾN THỨC CUNG CẤP
---
{KNOWLEDGE_BASE}
---
"""

# --- Bước 3: Khởi tạo kết nối đến "Bộ Nhớ" Firestore ---
db = None
def initialize_firestore():
    global db
    if db: return
    try:
        if not FIREBASE_CREDENTIALS_JSON:
            print("❌ Lỗi: Biến môi trường FIREBASE_CREDENTIALS_JSON không được thiết lập.")
            return
        creds_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(creds_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("✅ Kết nối đến Firestore thành công!")
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng khi khởi tạo Firestore: {e}")

# --- Bước 4: Các hàm chức năng chính của Bot ---

def get_gemini_response(sender_id, user_message):
    initialize_firestore()
    if not db or not GEMINI_API_KEY:
        return "Xin lỗi, hệ thống AI đang gặp sự cố. Vui lòng thử lại sau."
    try:
        model = genai.GenerativeModel(
            'gemini-2.0-flash',
            system_instruction=SYSTEM_INSTRUCTION
        )
        
        # --- SỬA LỖI #1: Tải lịch sử từ Firestore trước ---
        history_from_db = []
        doc_ref = db.collection('zalo_conversations').document(sender_id)
        doc = doc_ref.get()
        if doc.exists:
            history_from_db = doc.to_dict().get('history', [])

        # --- SỬA LỖI #2: Bắt đầu cuộc trò chuyện với lịch sử đã có ---
        chat = model.start_chat(history=history_from_db)
        
        response = chat.send_message(user_message)
        bot_response = response.text

        # --- SỬA LỖI #3: Chuyển đổi toàn bộ lịch sử từ đối tượng Gemini sang dict để lưu trữ ---
        # `chat.history` bây giờ chứa toàn bộ cuộc trò chuyện dưới dạng đối tượng `Content`
        new_history_to_save = []
        for content in chat.history:
            # Luôn chuyển đổi `part` thành `text` để đảm bảo tính nhất quán
            parts_text = [part.text for part in content.parts]
            new_history_to_save.append({'role': content.role, 'parts': parts_text})
        
        doc_ref.set({'history': new_history_to_save})
        return bot_response
    except Exception as e:
        print(f"❌ Lỗi khi gọi Gemini hoặc tương tác với Firestore: {e}")
        return "Rất xin lỗi, tôi đang gặp một chút trục trặc kỹ thuật. Bạn vui lòng chờ trong giây lát."

def send_zalo_message(recipient_id, message_text, access_token):
    if not access_token:
        print("❌ Lỗi: Không tìm thấy Access Token cho OA này.")
        return

    headers = { 'Content-Type': 'application/json', 'access_token': access_token }
    data = { "recipient": { "user_id": recipient_id }, "message": { "text": message_text } }
    try:
        response = requests.post("https://openapi.zalo.me/v3.0/oa/message/cs", headers=headers, json=data)
        response.raise_for_status()
        print(f"✅ Đã gửi tin nhắn Zalo thành công đến {recipient_id}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Lỗi khi gửi tin nhắn Zalo: {e}")
        if 'response' in locals(): print(f"Phản hồi từ Zalo API: {response.text}")

# --- Bước 5: Khởi tạo ứng dụng web và định nghĩa Webhook ---
app = Flask(__name__)

@app.route('/zalo-webhook', methods=['GET', 'POST'])
def zalo_webhook():
    if request.method == 'GET':
        challenge_code = request.args.get("hub.challenge")
        if challenge_code: return challenge_code
        return "Webhook is ready.", 200

    if request.method == 'POST':
        data = request.get_json()
        
        if data and data.get("event_name") == "user_send_text":
            try:
                oa_id = data.get("recipient", {}).get("id")
                page_access_token = ZALO_TOKEN_MAP.get(oa_id)

                if not page_access_token:
                    print(f"❌ Cảnh báo: Không tìm thấy Access Token cho OA ID: {oa_id}")
                    return "ok", 200

                sender_id = data["sender"]["id"]
                message_text = data["message"]["text"]
                
                gemini_answer = get_gemini_response(sender_id, message_text)
                
                send_zalo_message(sender_id, gemini_answer, page_access_token)

            except Exception as e:
                print(f"❌ LỖI NGHIÊM TRỌNG TRONG ZALO WEBHOOK: {e}")
                
        return "ok", 200

# --- Bước 6: Chạy ứng dụng (dành cho việc kiểm tra cục bộ) ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
