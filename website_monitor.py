import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import json
import os

# 創建logs目錄
if not os.path.exists('logs'):
    os.makedirs('logs')

# 配置一般日誌
logging.basicConfig(
    filename='logs/website_monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# 配置錯誤日誌
error_logger = logging.getLogger('error_logger')
error_handler = logging.FileHandler('logs/error.log', encoding='utf-8')
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
error_logger.addHandler(error_handler)

def setup_driver():
    # 設置 Chrome 選項
    chrome_options = Options()
    # chrome_options.add_argument('--headless')  # 註釋掉無頭模式
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    # 初始化 WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()  # 最大化視窗
    return driver

def login(driver, login_url, username, password):
    try:
        print("正在進行登入...")
        driver.get(login_url)
        
        # 等待登入表單加載
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[formcontrolname='account']"))
        )
        
        # 輸入帳號密碼
        username_input = driver.find_element(By.CSS_SELECTOR, "input[formcontrolname='account']")
        password_input = driver.find_element(By.CSS_SELECTOR, "input[formcontrolname='password']")
        
        username_input.send_keys(username)
        password_input.send_keys(password)
        
        print("1")
        # 點擊登入按鈕
        login_button = driver.find_element(By.CSS_SELECTOR, "button")
        login_button.click()
        print("2")
        
        # 等待登入API請求完成
        def check_login_status(driver):
            logs = driver.get_log('performance')
            for entry in logs:
                try:
                    log = json.loads(entry['message'])['message']
                    if ('Network.responseReceived' == log['method']):
                        response = log['params']['response']
                        url = response['url']
                        if 'APIPath/api/user/login' in url:
                            return response['status'] == 200
                except:
                    continue
            return False

        # 等待登入API響應或URL改變
        success = False
        timeout = time.time() + 10  # 10秒超時
        while time.time() < timeout:
            if check_login_status(driver):
                success = True
                break
            if 'library-list' in driver.current_url:
                success = True
                break
            time.sleep(0.5)
        
        if not success:
            raise Exception("登入超時或失敗")
            
        # 確認是否跳轉到library-list頁面
        if 'library-list' not in driver.current_url:
            WebDriverWait(driver, 5).until(
                lambda driver: 'library-list' in driver.current_url
            )
        
        print("登入成功！")
        return True
        
    except Exception as e:
        error_logger.error(f'登入失敗: {str(e)}')
        print(f'登入失敗: {str(e)}')
        return False

def navigate_to_page(driver, target_url):
    try:
        print(f"正在導航到目標頁面: {target_url}")
        driver.get(target_url)
        
        # 等待頁面加載完成
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        print("成功進入目標頁面")
        return True
        
    except Exception as e:
        error_logger.error(f'導航到目標頁面失敗: {str(e)}')
        print(f'導航到目標頁面失敗: {str(e)}')
        return False

def save_error_details(error_data):
    """保存詳細錯誤信息到JSON文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'logs/error_details_{timestamp}.json'
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2)
        error_logger.error(f'詳細錯誤信息已保存到: {filename}')
    except Exception as e:
        error_logger.error(f'保存錯誤詳情時發生錯誤: {str(e)}')

def process_browser_logs(driver):
    logs = driver.get_log('performance')
    for entry in logs:
        try:
            log = json.loads(entry['message'])['message']
            if 'Network.response' in log['method'] or 'Network.request' in log['method']:
                request_id = log.get('params', {}).get('requestId')
                if 'Network.responseReceived' == log['method']:
                    response = log['params']['response']
                    url = response['url']
                    if '/xhr/' in url or '/api/' in url:  # 監控 XHR 和 API 請求
                        status = response['status']
                        content_type = response.get('headers', {}).get('content-type', '')
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        if status >= 400:  # 顯示所有錯誤響應
                            print(f'\n[{current_time}] 請求失敗!')
                            print(f'URL: {url}')
                            print(f'狀態碼: {status}')
                            print(f'Content-Type: {content_type}')
                            print('-' * 80)
                            
                            error_data = {
                                'timestamp': datetime.now().isoformat(),
                                'url': url,
                                'status': status,
                                'content_type': content_type,
                                'headers': response.get('headers', {}),
                                'error_type': 'HTTP_ERROR'
                            }
                            error_logger.error(f'載入失敗: {url} - 狀態碼: {status}')
                            save_error_details(error_data)
                
                elif 'Network.loadingFailed' == log['method']:
                    params = log['params']
                    url = params.get('url', 'Unknown URL')
                    if '/xhr/' in url or '/api/' in url:
                        error_text = params.get('errorText', 'Unknown error')
                        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        print(f'\n[{current_time}] 請求失敗!')
                        print(f'URL: {url}')
                        print(f'錯誤: {error_text}')
                        print('-' * 80)
                        
                        error_data = {
                            'timestamp': datetime.now().isoformat(),
                            'url': url,
                            'error_type': 'LOADING_FAILED',
                            'error_text': error_text,
                            'params': params
                        }
                        error_logger.error(f'請求失敗: {url} - 錯誤: {error_text}')
                        save_error_details(error_data)

        except json.JSONDecodeError:
            continue
        except Exception as e:
            error_logger.error(f'處理日誌時發生錯誤: {str(e)}')
            print(f'\n處理日誌時發生錯誤: {str(e)}')

def monitor_website(login_url, target_url, username, password):
    driver = setup_driver()
    try:
        # 執行登入
        if not login(driver, login_url, username, password):
            raise Exception("登入失敗")
        
        # 導航到目標頁面
        if not navigate_to_page(driver, target_url):
            raise Exception("無法進入目標頁面")
        
        print("\n開始監控網路請求...")
        print("等待請求中...")
        print('-' * 80)
        
        while True:
            # 處理瀏覽器日誌
            process_browser_logs(driver)
            time.sleep(1)  # 縮短檢查間隔到1秒
            
    except Exception as e:
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'url': target_url,
            'error_type': 'MONITOR_ERROR',
            'error_message': str(e),
            'error_class': e.__class__.__name__
        }
        error_logger.error(f'監控過程中發生錯誤: {str(e)}')
        save_error_details(error_data)
        print(f'\n發生錯誤: {str(e)}')
    finally:
        driver.quit()

if __name__ == '__main__':
    # 設定登入資訊
    LOGIN_URL = 'http://localhost:4200/login'  # 請修改為實際的登入頁面URL
    TARGET_URL = 'http://localhost:4200/case-live/14'  # 目標監控頁面
    USERNAME = 'admin'  # 請修改為你的帳號
    PASSWORD = 'mktT0we1'  # 請修改為你的密碼
    
    print('開始監測網站...')
    try:
        monitor_website(LOGIN_URL, TARGET_URL, USERNAME, PASSWORD)
    except KeyboardInterrupt:
        print('\n監測程式已停止')