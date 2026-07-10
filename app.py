import streamlit as st
import streamlit.components.v1 as components
import random
import re
import os
import json
from datetime import datetime

# ⭐️ 스트림릿 규정상 이 설정 함수가 반드시 최상단에 실행되어야 에러가 안 납니다!
st.set_page_config(page_title="YMS 단어 테스트 생성기", layout="wide")

# 임포트 오류 방지용 안전장치
try:
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import firestore
    firebase_imported = True
except ImportError:
    firebase_imported = False

# ==========================================
# 1. Firebase 클라우드 연결 함수 (호출될 때만 작동)
# ==========================================
def init_firebase():
    if not firebase_imported:
        return None, "❌ 파이어베이스 라이브러리가 설치되지 않았습니다. (requirements.txt 확인 필요)"
        
    if firebase_admin._apps:
        try:
            return firestore.client(), "✅ 클라우드 서버 연결 활성화됨"
        except:
            return None, "❌ Firestore 클라이언트 연결 실패"

    # 열쇠 찾기 시작
    try:
        # 케이스 A: 스트림릿 클라우드 비밀금고(Secrets)에 저장한 경우
        if "firebase_credentials" in st.secrets:
            secrets_val = st.secrets["firebase_credentials"]
            if isinstance(secrets_val, str):
                key_dict = json.loads(secrets_val)
            else:
                key_dict = dict(secrets_val)
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
            return firestore.client(), "✅ 클라우드 서버 연결 완료"
            
        # 케이스 B: 컴퓨터 로컬에 파일이 있는 경우
        elif os.path.exists('firebase_key.json'):
            cred = credentials.Certificate('firebase_key.json')
            firebase_admin.initialize_app(cred)
            return firestore.client(), "✅ 로컬 키 파일 인증 완료"
            
        else:
            return None, "💡 오프라인 모드 (Secrets 금고에 열쇠를 넣으면 클라우드가 활성화됩니다)"
    except Exception as e:
        return None, f"❌ 인증 실패 (Secrets 내용 확인 필요): {str(e)}"

# 앱 시작 시 화면 멈춤을 막기 위해 안전하게 호출
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
            with st.spinner("서버에서 단어장 리스트를 가져오는 중..."):
                try:
                    docs = db.collection('yms_vocabularies').stream()
                    st.session_state.cloud_data = {doc.id: doc.to_dict() for doc in docs}
                    st.toast("클라우드 동기화 성공! ✨")
                except Exception as e:
                    st.error(f"서버 동기화 실패: {e}")
        
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
                if st.button("🗑️ 서버에서 삭제", use_container_width=True):
                    if selected_key != "▼ 단어장을 선택하세요":
                        db.collection('yms_vocabularies').document(selected_key).delete()
                        del st.session_state.cloud_data[selected_key]
                        st.success("서버 삭제 완료")
                        st.rerun()
        else:
            st.info("💡 위의 동기화 버튼을 누르면 클라우드 단어장을 로드합니다.")
    else:
        st.warning("⚠️ 클라우드가 연결되지 않았습니다. (오프라인 모드로 시험지 제작은 가능)")

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
                })
                st.success(f"클라우드 저장 완료! 💾")
                st.session_state.cloud_data[save_key] = {"title": book_title, "unit": book_unit, "text": st.session_state.input_text}
            except Exception as e:
                st.error(f"저장 실패: {e}")
        else:
            st.error("책 제목, 단어 데이터를 입력하거나 클라우드 연결 상태를 확인하세요.")

    word_input = st.text_area("엑셀 데이터 복사/붙여넣기", key="input_text", height=180)

    st.subheader("⚙️ 3. 출제 옵션")
    word_count = st.number_input("출제 문항 수", min_value=1, value=20)
    test_type = st.selectbox("시험 유형", ["YMS 반반 정렬 (Mix)", "영어 보고 뜻 쓰기", "뜻 보고 영어 쓰기"])

    generate_btn = st.button("⚡ 시험지 + 답지 생성하기", type="primary", use_container_width=True)

# ==========================================
# 4. 메인 화면 출력 영역
# ==========================================
# 💡 만약 파이어베이스 연결에 실패했다면 메인 화면에 크게 이유를 띄워줍니다!
if "❌" in status_msg:
    st.error(f"⚠️ 클라우드 연결에 문제가 발생했습니다.\n\n{status_msg}\n\n스트림릿 설정 창의 [Secrets]에 복사해 넣은 내용의 중괄호({{ }})나 쉼표가 누락되었는지 확인해주세요.")

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
                <script src="
