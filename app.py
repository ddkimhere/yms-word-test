import streamlit as st
import streamlit.components.v1 as components
import random
import re
import os
import json
from datetime import datetime

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# ==========================================
# 1. Firebase 클라우드 초기화 (무한 로딩 방지 완벽 패치)
# ==========================================
if not firebase_admin._apps:
    try:
        # 1-1. 스트림릿 클라우드 금고(Secrets)에 열쇠가 있는 경우
        if "firebase_credentials" in st.secrets:
            secrets_val = st.secrets["firebase_credentials"]
            # 복사 붙여넣기 방식에 따라 딕셔너리/문자열 자동 변환
            key_dict = json.loads(secrets_val) if isinstance(secrets_val, str) else dict(secrets_val)
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
            
        # 1-2. 내 컴퓨터에 'firebase_key.json' 파일이 있는 경우
        elif os.path.exists('firebase_key.json'):
            cred = credentials.Certificate('firebase_key.json')
            firebase_admin.initialize_app(cred)
            
        else:
            st.error("⚠️ 파이어베이스 열쇠를 찾을 수 없습니다. (Secrets 세팅이나 firebase_key.json 파일을 확인해주세요)")
    except Exception as e:
        st.error(f"⚠️ 파이어베이스 열쇠 인증 실패 (내용이 잘못되었습니다): {e}")

# 🔥 인증이 완벽하게 성공했을 때만 데이터베이스 연결! (여기서 무한 로딩이 걸리던 것을 차단)
db = None
if firebase_admin._apps:
    try:
        db = firestore.client()
    except Exception as e:
        st.error(f"⚠️ 데이터베이스 연결 오류: {e}")

# 데이터 불러오기 함수
def fetch_from_cloud():
    if db is None: return {}
    try:
        docs = db.collection('yms_vocabularies').stream()
        return {doc.id: doc.to_dict() for doc in docs}
    except Exception as e:
        st.error(f"☁️ 클라우드 데이터를 불러오지 못했습니다: {e}")
        return {}

# ==========================================
# 2. 페이지 및 상태 초기화
# ==========================================
st.set_page_config(page_title="YMS 단어 테스트 (Cloud)", layout="wide")

if 'input_title' not in st.session_state: st.session_state.input_title = ""
if 'input_unit' not in st.session_state: st.session_state.input_unit = ""
if 'input_text' not in st.session_state: st.session_state.input_text = ""

# ==========================================
# 3. 화면 구성 (사이드바 - 컨트롤러)
# ==========================================
with st.sidebar:
    st.header("📝 YMS TEST GENERATOR")
    st.markdown("Firebase 클라우드 연동 버전 ☁️")
    st.markdown("---")
    
    st.subheader("☁️ 클라우드 단어장 보관함")
    
    cloud_data = fetch_from_cloud()
    cloud_keys = list(cloud_data.keys())
    
    selected_key = st.selectbox("불러올 단어장 선택", ["▼ 단어장을 선택하세요"] + cloud_keys)
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📥 불러오기", use_container_width=True):
            if selected_key != "▼ 단어장을 선택하세요":
                st.session_state.input_title = cloud_data[selected_key].get('title', '')
                st.session_state.input_unit = cloud_data[selected_key].get('unit', '')
                st.session_state.input_text = cloud_data[selected_key].get('text', '')
                st.success("클라우드에서 불러왔습니다!")
                st.rerun()
            else:
                st.warning("단어장을 선택하세요.")
    with col_b:
        if st.button("🗑️ 삭제", use_container_width=True):
            if selected_key != "▼ 단어장을 선택하세요" and db:
                db.collection('yms_vocabularies').document(selected_key).delete()
                st.success("삭제되었습니다.")
                st.rerun()

    st.markdown("---")

    st.subheader("📘 1. 교재 정보")
    book_title = st.text_input("책 제목", key="input_title", placeholder="예: 고등 필수 Voca")
    book_unit = st.text_input("출제 범위 (Unit)", key="input_unit", placeholder="예: Unit 01-03")

    st.subheader("📊 2. 단어 데이터 입력")
    if st.button("☁️ 클라우드 서버에 현재 데이터 저장"):
        if book_title and st.session_state.input_text and db:
            save_key = f"{book_title}::{book_unit}" if book_unit else f"{book_title}::전체"
            db.collection('yms_vocabularies').document(save_key).set({
                "title": book_title, 
                "unit": book_unit, 
                "text": st.session_state.input_text,
                "updatedAt": firestore.SERVER_TIMESTAMP
            })
            st.success(f"'{save_key}' 저장 완료! 💾")
            st.rerun()
        else:
            st.error("책 제목과 단어 데이터, 그리고 클라우드 연결을 확인해주세요.")

    word_input = st.text_area("엑셀 데이터 복사/붙여넣기", key="input_text", height=200)

    st.subheader("⚙️ 3. 출제 옵션")
    word_count = st.number_input("출제 문항 수", min_value=1, value=20)
    test_type = st.selectbox("시험 유형", ["YMS 반반 정렬 (Mix)", "영어 보고 뜻 쓰기", "뜻 보고 영어 쓰기"])

    generate_btn = st.button("⚡ 시험지 + 답지 생성하기", type="primary", use_container_width=True)

# ==========================================
# 4. 단어 파싱 및 인쇄용 HTML 렌더링
# ==========================================
if generate_btn:
    if not word_input.strip():
        st.error("단어를 입력해주세요!")
    else:
        parsed_words = []
        for line in word_input.strip().split('\n'):
            line = line.strip()
            if not line: continue
            
            eng, kor = "", ""
            if '\t' in line:
                parts = line.split('\t')
                eng, kor = parts[0], parts[1] if len(parts) > 1 else ""
            elif ',' in line:
                parts = line.split(',')
                eng, kor = parts[0], parts[1] if len(parts) > 1 else ""
            else:
                match = re.match(r'^(.*?)\s+([가-힣].*)$', line)
                if match:
                    eng, kor = match.group(1), match.group(2)
                else:
                    parts = line.split()
                    if len(parts) >= 2:
                        eng, kor = parts[0], " ".join(parts[1:])
            
            if eng and kor:
                parsed_words.append({"eng": eng.strip(), "kor": kor.strip()})

        if not parsed_words:
            st.error("단어를 분석할 수 없습니다.")
        else:
            random.shuffle(parsed_words)
            selected_words = parsed_words[:word_count]
            half_point = (len(selected_words) + 1) // 2

            test_html = ""
            answer_html = ""
            
            for i, word in enumerate(selected_words):
                if test_type == "영어 보고 뜻 쓰기": is_eng_q = True
                elif test_type == "뜻 보고 영어 쓰기": is_eng_q = False
                else: is_eng_q = i < half_point

                question_text = word['eng'] if is_eng_q else word['kor']
                answer_text = word['kor'] if is_eng_q else word['eng']
                num = f"{i+1:02d}"

                test_html += f"""
                <div class="flex justify-between items-end border-b border-gray-300 pb-2">
                    <div class="flex items-center w-1/2">
                        <span class="w-8 font-bold text-gray-400 text-sm">{num}.</span>
                        <span class="font-bold text-gray-800 text-sm tracking-tight">{question_text}</span>
                    </div>
                    <span class="text-gray-300 mx-2 text-xs">····➔</span>
                    <div class="flex-1 border-b border-gray-400 h-5"></div>
                </div>
                """
                answer_html += f"""
                <div class="flex justify-between items-end border-b border-gray-300 pb-2">
                    <div class="flex items-center w-1/2">
                        <span class="w-8 font-bold text-gray-400 text-sm">{num}.</span>
                        <span class="font-bold text-gray-800 text-sm tracking-tight">{question_text}</span>
                    </div>
                    <span class="text-gray-300 mx-2 text-xs">····➔</span>
                    <div class="flex-1 border-b border-gray-400 h-5 text-center">
                        <span class="text-red-600 font-black text-sm">{answer_text}</span>
                    </div>
                </div>
                """

            today_date = datetime.now().strftime("%Y. %m. %d")
            display_title = book_title if book_title else 'Vocabulary Test'
            display_unit = book_unit if book_unit else '전범위'

            full_html = f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <script src="https://cdn.tailwindcss.com"></script>
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
                    body {{ font-family: 'Noto Sans KR', sans-serif; background-color: #f1f5f9; padding: 20px; }}
                    .print-btn {{
                        position: fixed; top: 20px; right: 20px; z-index: 1000;
                        background: #0f172a; color: white; padding: 12px 24px;
                        border-radius: 8px; font-weight: 900; cursor: pointer;
                        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
                        transition: all 0.2s; border: none; font-size: 14px;
                    }}
                    .print-btn:hover {{ background: #2563eb; transform: translateY(-2px); }}
                    .paper {{
                        background: white; max-width: 800px; margin: 0 auto 40px auto;
                        padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                        border-top: 8px solid #0f172a; border-radius: 4px;
                    }}
                    @media print {{
                        body {{ background: white; padding: 0; }}
                        .print-btn {{ display: none !important; }}
                        .paper {{ box-shadow: none; margin: 0; padding: 20px; border-top: none; }}
                        .page-break {{ page-break-before: always; }}
                    }}
                </style>
            </head>
            <body>
                <button class="print-btn" onclick="window.print()">🖨️ 인쇄 / PDF 저장하기</button>

                <div class="paper">
                    <div class="border-2 border-slate-900 p-5 mb-8">
                        <div class="flex justify-between items-end border-b-2 border-slate-900 pb-3 mb-3">
                            <div class="text-sm font-black tracking-widest uppercase">YMS <span class="text-xs font-medium text-slate-500 italic lowercase">your mastery solution</span></div>
                            <div class="text-xl font-black tracking-tight">{display_title}</div>
                        </div>
                        <div class="flex justify-between text-xs font-bold text-slate-700">
                            <div>Date: {today_date}</div>
                            <div>Unit: {display_unit}</div>
                            <div>Name: __________________</div>
                            <div class="text-red-600 font-black">Score: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / 100</div>
                        </div>
                    </div>
                    <h2 class="text-center text-2xl font-black tracking-[0.2em] mb-10 border-b-2 inline-block mx-auto border-black pb-2 px-8 uppercase">Vocabulary Test</h2>
                    <div class="grid grid-cols-2 gap-x-12 gap-y-6">{test_html}</div>
                </div>

                <div class="page-break"></div>

                <div class="paper">
                    <div class="border-2 border-slate-900 p-5 mb-8 bg-red-50">
                        <div class="flex justify-between items-end border-b-2 border-red-900 pb-3 mb-3">
                            <div class="text-sm font-black tracking-widest uppercase text-red-900">YMS <span class="text-xs font-medium italic lowercase text-red-600">Answer Key</span></div>
                            <div class="text-xl font-black tracking-tight text-red-900">{display_title} (정답지)</div>
                        </div>
                        <div class="flex justify-between text-xs font-bold text-red-800">
                            <div>Date: {today_date}</div>
                            <div>Unit: {display_unit}</div>
                            <div class="font-black">※ 선생님 채점용 정답지입니다.</div>
                        </div>
                    </div>
                    <h2 class="text-center text-2xl font-black tracking-[0.2em] mb-10 border-b-2 inline-block mx-auto border-red-600 text-red-600 pb-2 px-8 uppercase">Answer Key</h2>
                    <div class="grid grid-cols-2 gap-x-12 gap-y-6">{answer_html}</div>
                </div>
            </body>
            </html>
            """
            components.html(full_html, height=1200, scrolling=True)
