import streamlit as st
import streamlit.components.v1 as components
import random
import re
import os
import json
from datetime import datetime

st.set_page_config(page_title="YMS 단어 테스트 생성기", layout="wide")

try:
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import firestore
    firebase_imported = True
except ImportError:
    firebase_imported = False

# ==========================================
# 1. Firebase 클라우드 연결 (기억상실 강제 적용)
# ==========================================
def init_firebase():
    if not firebase_imported:
        return None, "❌ 파이어베이스 라이브러리가 설치되지 않았습니다."
        
    # 💡 [핵심 패치] 스트림릿이 쥐고 있는 예전 불량 열쇠 기억을 강제로 전부 삭제!
    if firebase_admin._apps:
        for app_name in list(firebase_admin._apps.keys()):
            firebase_admin.delete_app(firebase_admin.get_app(app_name))

    # 새 열쇠로 완전히 처음부터 다시 연결 시도
    try:
        if "firebase_credentials" in st.secrets:
            secrets_val = st.secrets["firebase_credentials"]
            if isinstance(secrets_val, str):
                key_dict = json.loads(secrets_val)
            else:
                key_dict = dict(secrets_val)
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
            return firestore.client(), "✅ 클라우드 서버 연결 완료"
            
        elif os.path.exists('firebase_key.json'):
            cred = credentials.Certificate('firebase_key.json')
            firebase_admin.initialize_app(cred)
            return firestore.client(), "✅ 로컬 키 파일 인증 완료"
            
        else:
            return None, "💡 오프라인 모드 (Secrets 금고 확인 필요)"
    except Exception as e:
        return None, f"❌ 인증 실패 (열쇠 형태 불량): {str(e)}"

db, status_msg = init_firebase()

# ==========================================
# 2. 데이터 세션 상태 초기화
# ==========================================
if 'cloud_data' not in st.session_state: st.session_state.cloud_data = {}
if 'input_title' not in st.session_state: st.session_state.input_title = ""
if 'input_unit' not in st.session_state: st.session_state.input_unit = ""
if 'input_text' not in st.session_state: st.session_state.input_text = ""

# ==========================================
# 3. 화면 구성 (사이드바 컨트롤러 영역)
# ==========================================
with st.sidebar:
    st.header("📝 YMS TEST GENERATOR")
    st.caption(f"시스템 상태: {status_msg}")
    st.markdown("---")
    
    st.subheader("☁️ 클라우드 단어장 보관함")
    
    if db is not None:
        if st.button("🔄 클라우드 단어 목록 동기화", use_container_width=True):
            with st.spinner("서버에서 리스트를 가져오는 중..."):
                try:
                    docs = db.collection('yms_vocabularies').get(timeout=8)
                    st.session_state.cloud_data = {doc.id: doc.to_dict() for doc in docs}
                    st.toast("동기화 성공! ✨")
                except Exception as e:
                    st.error(f"동기화 실패 (무한 로딩 차단됨): {e}")
        
        if st.session_state.cloud_data:
            cloud_keys = list(st.session_state.cloud_data.keys())
            selected_key = st.selectbox("불러올 단어장 선택", ["▼ 단어장을 선택하세요"] + cloud_keys)
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("📥 불러오기", use_container_width=True):
                    if selected_key != "▼ 단어장을 선택하세요":
                        tgt = st.session_state.cloud_data[selected_key]
                        st.session_state.input_title = tgt.get('title', '')
                        st.session_state.input_unit = tgt.get('unit', '')
                        st.session_state.input_text = tgt.get('text', '')
                        st.rerun()
            with col_b:
                if st.button("🗑️ 삭제", use_container_width=True):
                    if selected_key != "▼ 단어장을 선택하세요":
                        db.collection('yms_vocabularies').document(selected_key).delete(timeout=5)
                        del st.session_state.cloud_data[selected_key]
                        st.success("삭제 완료")
                        st.rerun()
        else:
            st.info("💡 위의 동기화 버튼을 누르면 클라우드 단어장을 로드합니다.")
    else:
        st.warning("⚠️ 클라우드가 연결되지 않았습니다.")

    st.markdown("---")

    st.subheader("📘 1. 교재 정보")
    book_title = st.text_input("책 제목", key="input_title", placeholder="예: 고등 필수 Voca")
    book_unit = st.text_input("출제 범위 (Unit)", key="input_unit", placeholder="예: Unit 01-03")

    st.subheader("📊 2. 단어 데이터 입력")
    
    if st.button("☁️ 현재 데이터를 클라우드에 저장"):
        if db is not None and book_title and st.session_state.input_text:
            try:
                save_key = f"{book_title}::{book_unit}" if book_unit else f"{book_title}::전체"
                db.collection('yms_vocabularies').document(save_key).set({
                    "title": book_title, 
                    "unit": book_unit, 
                    "text": st.session_state.input_text,
                    "updatedAt": datetime.now()
                }, timeout=8)
                st.success(f"클라우드 저장 완료! 💾")
                st.session_state.cloud_data[save_key] = {"title": book_title, "unit": book_unit, "text": st.session_state.input_text}
            except Exception as e:
                st.error(f"🚨 저장 실패:\n{e}")
        else:
            st.error("책 제목과 단어 데이터를 모두 기입해 주세요.")

    word_input = st.text_area("엑셀 데이터 복사/붙여넣기", key="input_text", height=180)

    st.subheader("⚙️ 3. 출제 옵션")
    word_count = st.number_input("출제 문항 수", min_value=1, value=20)
    test_type = st.selectbox("시험 유형", ["YMS 반반 정렬 (Mix)", "영어 보고 뜻 쓰기", "뜻 보고 영어 쓰기"])

    generate_btn = st.button("⚡ 시험지 + 답지 생성하기", type="primary", use_container_width=True)

# ==========================================
# 4. 메인 화면 출력 영역 (인쇄 양식)
# ==========================================
if "❌" in status_msg:
    st.error(f"⚠️ 클라우드 연결 실패:\n\n{status_msg}\n\n[Reboot app]을 눌러도 이 메시지가 뜬다면 Secrets 금고 안의 내용이 잘못 복사된 것입니다.")

if generate_btn:
    if not word_input.strip():
        st.error("입력창에 단어를 기입해 주세요!")
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
            st.error("단어 분석에 실패했습니다.")
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
                <div class="flex justify-between items-end border-b border-slate-200 pb-2">
                    <div class="flex items-center w-1/2">
                        <span class="w-8 font-bold text-slate-400 text-sm">{num}.</span>
                        <span class="font-bold text-slate-800 text-sm tracking-tight">{question_text}</span>
                    </div>
                    <span class="text-slate-300 mx-2 text-xs">····➔</span>
                    <div class="flex-1 border-b border-slate-300 h-5"></div>
                </div>
                """
                answer_html += f"""
                <div class="flex justify-between items-end border-b border-slate-200 pb-2">
                    <div class="flex items-center w-1/2">
                        <span class="w-8 font-bold text-slate-400 text-sm">{num}.</span>
                        <span class="font-bold text-slate-800 text-sm tracking-tight">{question_text}</span>
                    </div>
                    <span class="text-slate-300 mx-2 text-xs">····➔</span>
                    <div class="flex-1 border-b border-slate-300 h-5 text-center">
                        <span class="text-orange-600 font-extrabold text-sm">{answer_text}</span>
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
                    body {{ font-family: 'Noto Sans KR', sans-serif; background-color: #f8fafc; padding: 20px; }}
                    .btn-container {{ position: fixed; top: 20px; right: 20px; z-index: 1000; display: flex; gap: 12px; }}
                    .print-btn {{ color: white; padding: 14px 24px; border-radius: 12px; font-weight: 900; cursor: pointer; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15); transition: all 0.2s; border: none; font-size: 14px; }}
                    .btn-test {{ background: #1e3a8a; }} .btn-test:hover {{ background: #2563eb; transform: translateY(-2px); }}
                    .btn-ans {{ background: #ea580c; }} .btn-ans:hover {{ background: #f97316; transform: translateY(-2px); }}
                    .paper {{ background: white; max-width: 820px; margin: 0 auto 50px auto; padding: 50px; box-shadow: 0 4px 20px rgba(15,23,42,0.04); border-top: 8px solid #1e3a8a; border-radius: 8px; }}
                    .paper.ans-sheet {{ border-top: 8px solid #ea580c; }}
                    @media print {{ body {{ background: white; padding: 0; }} .btn-container {{ display: none !important; }} .paper {{ box-shadow: none; margin: 0; padding: 20px; border-top: none; }} .page-break {{ page-break-before: always; }} }}
                </style>
                <script>
                    function printTestSheet() {{
                        document.getElementById('answer-sheet').style.display = 'none';
                        document.getElementById('page-break-element').style.display = 'none';
                        document.getElementById('test-sheet').style.display = 'block';
                        window.print();
                        document.getElementById('answer-sheet').style.display = '';
                        document.getElementById('page-break-element').style.display = '';
                    }}
                    function printAnswerSheet() {{
                        document.getElementById('test-sheet').style.display = 'none';
                        document.getElementById('page-break-element').style.display = 'none';
                        document.getElementById('answer-sheet').style.display = 'block';
                        window.print();
                        document.getElementById('test-sheet').style.display = '';
                        document.getElementById('page-break-element').style.display = '';
                    }}
                </script>
            </head>
            <body>
                <div class="btn-container">
                    <button class="print-btn btn-test" onclick="printTestSheet()">🖨️ 학생용 시험지 인쇄</button>
                    <button class="print-btn btn-ans" onclick="printAnswerSheet()">🔑 채점용 답지 인쇄</button>
                </div>
                <div id="test-sheet" class="paper">
                    <div class="border-2 border-blue-900/80 p-5 mb-8 rounded-md bg-slate-50/50">
                        <div class="flex justify-between items-end border-b-2 border-blue-900 pb-3 mb-3">
                            <div class="text-xs font-black tracking-widest text-blue-900 uppercase">YMS <span class="text-[10px] font-normal text-slate-400 italic lowercase">your mastery solution</span></div>
                            <div class="text-lg font-black tracking-tight text-slate-900">{display_title}</div>
                        </div>
                        <div class="flex justify-between text-xs font-bold text-slate-600">
                            <div>Date: {today_date}</div>
                            <div>Unit: {display_unit}</div>
                            <div>Name: __________________</div>
                            <div class="text-orange-600 font-black px-2 py-0.5 border border-orange-200 rounded bg-orange-50/50">Score: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; / 100</div>
                        </div>
                    </div>
                    <div class="text-center mb-10">
                        <h2 class="text-2xl font-black tracking-[0.25em] border-b-2 inline-block border-slate-800 pb-1.5 px-12 uppercase text-slate-900">Vocabulary Test</h2>
                    </div>
                    <div class="grid grid-cols-2 gap-x-16 gap-y-5">{test_html}</div>
                </div>
                <div id="page-break-element" class="page-break"></div>
                <div id="answer-sheet" class="paper ans-sheet">
                    <div class="border-2 border-orange-900/70 p-5 mb-8 bg-orange-50/30 rounded-md">
                        <div class="flex justify-between items-end border-b-2 border-orange-600 pb-3 mb-3">
                            <div class="text-xs font-black tracking-widest text-orange-600 uppercase">YMS <span class="text-[10px] font-normal italic lowercase text-slate-400">Answer Key</span></div>
                            <div class="text-lg font-black tracking-tight text-orange-900">{display_title} (정답지)</div>
                        </div>
                        <div class="flex justify-between text-xs font-bold text-orange-800">
                            <div>Date: {today_date}</div>
                            <div>Unit: {display_unit}</div>
                            <div class="font-extrabold text-blue-900">※ YMS 원장님/강사 채점 가이드 문서입니다.</div>
                        </div>
                    </div>
                    <div class="text-center mb-10">
                        <h2 class="text-2xl font-black tracking-[0.25em] border-b-2 inline-block border-orange-600 text-orange-600 pb-1.5 px-12 uppercase">Answer Key</h2>
                    </div>
                    <div class="grid grid-cols-2 gap-x-16 gap-y-5">{answer_html}</div>
                </div>
            </body>
            </html>
            """
            components.html(full_html, height=1200, scrolling=True)
else:
    st.info("👈 좌측 대시보드에 단어 목록을 채워넣은 후 [⚡ 시험지 + 답지 생성하기] 버튼을 누르면 인쇄 미리보기가 활성화됩니다.")
