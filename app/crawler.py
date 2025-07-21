import re
import csv
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import pickle
import urllib.parse
import time
from logger import setup_logger
from db import SessionLocal
from sqlalchemy.orm import Session
from models import SearchTxt, InstaPost
from datetime import datetime
from redis_client import redis_client


USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'

class InstaCrawler:
    def __init__(self):
        self.driver = self.get_driver()
        self.db_session = SessionLocal()
        self.db_buffer = []

    def get_driver(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(f'user-agent={USER_AGENT}')
        # chrome_options.add_argument('--headless') 
        chrome_options.add_argument('--window-size=1920x1080')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-javascript')
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    def login(self):
        cookie_path = 'insta_cookies.pkl'
        self.driver.get('https://www.instagram.com/')
        self.driver.implicitly_wait(10)

        # 저장한 쿠키를 추가하여 로그인 상태로 변환
        with open(cookie_path, "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                if "sameSite" in cookie:
                    del cookie["sameSite"]
                self.driver.add_cookie(cookie)
        self.driver.get("https://www.instagram.com/")
    
    def run(self, hashtags):
        db = SessionLocal()
        self.login()
        for tag in hashtags:
            self.logger = setup_logger(tag)
            self.logger.info(f"[INFO] 해시태그 #{tag} 수집 시작")
            self.search_tag(tag)
            with SessionLocal() as db:
                searchtxt_id = self.get_or_create_searchtxt(db, tag)
            self.crawl_posts(searchtxt_id)
        
        # 남은 데이터 저장
        if self.db_buffer:
            self.db_session.add_all(self.db_buffer)
            self.db_session.commit()
        self.driver.quit()

    def get_or_create_searchtxt(self, db: Session, tag: str) -> int:
        '''
        검색어 테이블 조회 후 없으면 생성
        '''
        search = db.query(SearchTxt).filter_by(text=tag).first()
        if not search:
            search = SearchTxt(text=tag)
            db.add(search)
            db.commit()
            db.refresh(search)
        
        return search.id

    def search_tag(self, tag):
        '''
        검색어 입력후 이동
        '''
        query = urllib.parse.quote(tag)
        search_url = f'https://www.instagram.com/explore/search/keyword/?q={query}'
        self.driver.get(search_url)
        sleep(5)

    def get_url_key(self, url: str) -> str:
        '''
        URL -> Redis Key 변환'''
        return f"insta:visited:{url}"

    def is_duplicate_url(self, url: str) -> bool:
        '''
        중복 확인
        '''
        key = self.get_url_key(url)
        return redis_client.exists(key)

    def mark_url_as_visited(self, url: str):
        '''
        Redis 저장 (TTL 7일)'''
        key = self.get_url_key(url)
        redis_client.set(key, 1, ex=60 * 60 * 24 * 7)

    def crawl_posts(self, searchtxt_id):
        '''
        게시물 크롤링
        '''
        check_point = True
        wait = WebDriverWait(self.driver, 20)
        first_post = wait.until(EC.presence_of_element_located((By.CLASS_NAME, '_aagu'))) # 첫번째 게시물이 로드될때 까지 대기
        first_post.click()
        duplication_cnt = 0 # 중복 게시물
        time.sleep(2) # 첫 게시물의 user_id를 못가져오는 경우 때문에 2초 정지
        while check_point:
            
            # user id 수집
            try:
                start_tt = time.time()
                try:
                    wait = WebDriverWait(self.driver, 20)
                    user_id_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft")))
                    user_id = user_id_element.text
                except:
                    user_id = 'error'

                self.logger.info(f'[+] {user_id}의 게시물 수집중')
                
                # 해당 게시물의 url 수집
                try:
                    current_url = self.driver.current_url
                except:
                    current_url = 'error'
        
                # 게시물 본문 수집
                try:
                    content = self.driver.find_element(By.CSS_SELECTOR, 'h1._ap3a._aaco._aacu._aacx._aad7._aade').text
                except:
                    content = 'error'

                # 게시물 시간 수집
                try:
                    time_raw = self.driver.find_elements(By.CLASS_NAME, '_a9ze._a9zf')
                    create_time_str = time_raw[0].get_attribute('datetime')
                    create_time = datetime.fromisoformat(create_time_str) if create_time_str else None
                except:
                    create_time = None

                # 좋아요 수 수집
                like_cnt = 0
                try:
                    start_time = time.time()
                    while time.time() - start_time < 1:
                        spans = self.driver.find_elements(By.CSS_SELECTOR, "section span")
                        for span in spans:
                            text = span.text.strip()
                            if re.match(r'^[\d,.]+$', text):
                                like_cnt = int(text.replace(",", "").replace(".", ""))
                                break
                        if like_cnt > 0:
                            break
                        sleep(0.1)
                    self.logger.info(f'좋아요수 : {like_cnt}')
                except Exception as e:
                    self.logger.warning(f"[likes 예외] {e}")


                hashtag = re.findall(r'#\w+', content) if isinstance(content, str) else []
                hashtag_cnt = len(hashtag) if hashtag else 0

                tt = time.time() - start_tt
                
                # 크롤링 시간
                crawl_time = datetime.now()
            
                self.logger.info(f'[+] {user_id}의 게시물 수집 완료 {tt:.2f}')

                post = InstaPost(
                    searchtxt_id = searchtxt_id,
                    user_id=user_id,
                    content=content,
                    post_time=create_time,
                    like=like_cnt,
                    url=current_url,
                    hashtags=','.join(hashtag),
                    hashtag_count=hashtag_cnt,
                    crawl_time = crawl_time
                )
                
                # Redis 중복 확인
                duplication_tt = time.time()
                in_db = self.is_duplicate_url(current_url)
                self.logger.info(f'[+] 게시물 중복 확인 시간 {time.time() - duplication_tt}')

                if not in_db:
                    self.db_buffer.append(post)
                    self.mark_url_as_visited(current_url)
                else:
                    self.logger.info(f'중복 게시물 => user_id: {user_id}, url: {current_url}')
                    duplication_cnt += 1
                
                    if duplication_cnt > 10:
                        self.logger.info(f'[!] 중복 게시물 {duplication_cnt}개 초과, 크롤링 중단')
                        check_point = False

                # 100개 단위로 db 저장
                if len(self.db_buffer) >= 100:
                    self.db_session.add_all(self.db_buffer)
                    self.db_session.commit()
                    self.logger.info(f'[+] db 저장')
                    self.db_buffer.clear()

                try:
                    self.driver.find_element(By.CLASS_NAME, '_aaqg._aaqh').click()
                    sleep(1)
                except:
                    check_point = False

            except Exception as e:
                self.logger.error(f"[ERROR] {e}")
                self.driver.quit()
