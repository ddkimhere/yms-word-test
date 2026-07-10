import streamlit as st
import random
import re

# 1. 페이지 기본 설정 (넓게 쓰기)
st.set_page_config(page_title="YMS 단어 테스트 (Python)", layout="wide")

st.title("📝 YMS TEST GENERATOR (Streamlit 버전)")
st.markdown("파이썬 기반으로 완벽하게 이식된 단어 시험지 프로그램입니다.")

# ---------------------------------
# 왼쪽 사이드바: 입력 및 컨트롤러
# ---------------------------------
with st.sidebar:
    st.header("📘 1. 클래스 및 교재 정보")
    book_title = st.text_input("책 제목", placeholder="예: 고등 필수 Voca")
    book_unit = st.text_input("출제 범위 (Unit)", placeholder="예: Unit 01-03")

    st.header("📊 2. 단어 데이터 입력")
    word_input = st.text_area("엑셀에서 복사해 넣으세요", height=250, 
                              placeholder="apple 사과\nbanana 바나나")

    st.header("⚙️ 3. 출제 세부 옵션")
    col1, col2 = st.columns(2)
    with col1:
        word_count = st.number_input("문항 수", min_value=1, value=20)
    with col2:
        test_type = st.selectbox("시험 유형", ["혼합형 (Mix)", "영어 보고 뜻 쓰기", "뜻 보고 영어 쓰기"])

    generate_btn = st.button("⚡ 시험지 생성하기", use_container_width=True, type="primary")

# ---------------------------------
# 메인 화면: 시험지 출력 영역
# ---------------------------------
if generate_btn:
    if not word_input.strip():
        st.error("단어를 텍스트 상자에 입력해주세요!")
    else:
        # 1. 지능형 단어 분석기 (JS 파서를 Python으로 완벽 이식)
        lines = word_input.strip().split('\n')
        parsed_words = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            eng, kor = "", ""
            if '\t' in line:
                parts = line.split('\t')
                eng, kor = parts[0], parts[1] if len(parts) > 1 else ""
            elif ',' in line:
                parts = line.split(',')
                eng, kor = parts[0], parts[1] if len(parts) > 1 else ""
            else:
                # 정규식을 이용한 지능형 한글 탐지
                match = re.match(r'^(.*?)\s+([가-힣].*)$', line)
                if match:
                    eng, kor = match.group(1), match.group(2)
                else:
                    parts = line.split()
                    if len(parts) >= 2:
                        eng = parts[0]
                        kor = " ".join(parts[1:])

            if eng and kor:
                parsed_words.append({"eng": eng.strip(), "kor": kor.strip()})

        if not parsed_words:
            st.error("단어를 분석할 수 없습니다. 형식을 확인해주세요.")
        else:
            # 2. 셔플 및 문항 추출
            random.shuffle(parsed_words)
            selected_words = parsed_words[:word_count]
            half_point = (len(selected_words) + 1) // 2

            # 3. YMS 스타일 시험지 렌더링
            st.markdown("---")
            
            # 헤더 영역
            h_col1, h_col2 = st.columns([1, 1])
            with h_col1:
                st.markdown("**YMS** *your mastery solution*")
            with h_col2:
                st.markdown(f"<div style='text-align: right'><b>{book_title if book_title else '단어 테스트'}</b></div>", unsafe_allow_html=True)
            
            st.markdown(f"**Date:** 2026. 07. 11 &nbsp;&nbsp;|&nbsp;&nbsp; **Unit:** {book_unit} &nbsp;&nbsp;|&nbsp;&nbsp; **Name:** ______________ &nbsp;&nbsp;|&nbsp;&nbsp; **Score:** ______ / 100")
            
            st.markdown("<h2 style='text-align: center; margin-top: 20px; margin-bottom: 30px; letter-spacing: 5px;'>VOCABULARY TEST</h2>", unsafe_allow_html=True)

            # 문제 2단 배치
            q_col1, q_col2 = st.columns(2)

            for i, word in enumerate(selected_words):
                # 반반 혼합 로직
                if test_type == "영어 보고 뜻 쓰기":
                    is_eng_question = True
                elif test_type == "뜻 보고 영어 쓰기":
                    is_eng_question = False
                else:
                    is_eng_question = i < half_point

                question_text = word['eng'] if is_eng_question else word['kor']
                
                # HTML과 CSS를 활용해 문제 정렬
                display_html = f"""
                <div style="border-bottom: 1px dashed #ccc; padding: 10px 0; display: flex; justify-content: space-between;">
                    <span style="width: 30px; color: #888; font-weight: bold;">{i+1:02d}.</span>
                    <span style="font-weight: bold; width: 45%;">{question_text}</span>
                    <span style="color: #ccc;">····➔</span>
                    <span style="flex-grow: 1; border-bottom: 1px solid #999; margin-left: 10px;"></span>
                </div>
                """

                # 번호가 짝수냐 홀수냐에 따라 왼쪽/오른쪽 컬럼으로 분배
                if i % 2 == 0:
                    q_col1.markdown(display_html, unsafe_allow_html=True)
                else:
                    q_col2.markdown(display_html, unsafe_allow_html=True)