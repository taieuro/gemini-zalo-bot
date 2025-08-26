from waitress import serve
from app import app # "app" là tên biến Flask trong file app.py của bạn

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=8080)
