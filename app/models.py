from sqlalchemy import Column, Integer, String, DateTime
from db import Base
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from db import Base

class SearchTxt(Base):
    __tablename__ = "searchtxt"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="검색어 ID")
    text = Column(String(100), unique=True, nullable=False, comment="검색어 텍스트")
    created_at = Column(DateTime, default=datetime.now, comment="생성 시간")

class InstaPost(Base):
    __tablename__ = "insta_posts"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="게시물 ID")
    searchtxt_id = Column(Integer, ForeignKey("searchtxt.id"), nullable=False, comment="연결된 검색어 ID")
    
    user_id = Column(String(100), comment="인스타그램 사용자 ID")
    content = Column(Text, comment="게시물 본문")
    post_time = Column(DateTime, comment="게시물 작성 시간")
    like = Column(Integer, comment="좋아요 수")
    url = Column(String(255), unique=True, comment="게시물 URL") # 게시물의 고유 url 중복 방지
    hashtags = Column(Text, comment="해시태그 목록 (쉼표 구분)")
    hashtag_count = Column(Integer, comment="해시태그 개수")
    crawl_time = Column(DateTime, default=datetime.now, comment="크롤링 시점")

    # 관계 설정
    searchtxt = relationship("SearchTxt", backref="posts")