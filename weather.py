import streamlit as st
import pandas as pd
import os
import re
import base64

# =========================
# 0) 파일 경로 설정
# =========================
IMAGE_DB_PATH = "image_db.xlsx"  
IMAGE_DIR = "."


# =========================
# 1) 한글 표시 매핑
# =========================
LABEL_TO_GENDER = {"여": "F", "남": "M"}
GENDER_TO_LABEL = {"F": "여", "M": "남"}

STYLE_KR = {
    "CASUAL": "캐쥬얼",
    "OFFICE": "오피스",
    "STREET": "스트릿",
    "LOVELY": "러블리",
    "MINIMAL": "미니멀",
}
KR_TO_STYLE = {v: k for k, v in STYLE_KR.items()}

FEMALE_STYLES = ["CASUAL", "OFFICE", "STREET", "LOVELY"]
MALE_STYLES   = ["CASUAL", "OFFICE", "STREET", "MINIMAL"]


# =========================
# 2) 온도 파싱
# =========================
def parse_temp_range(s: str):
    """
    '28+' -> (28, 99)
    '04-' -> (-20, 4)
    '27-23' -> (23, 27) 자동 정렬
    """
    s = str(s).strip()

    if re.match(r"^\d+\+$", s):
        low = int(s.replace("+", ""))
        return low, 99

    if re.match(r"^\d+\-$", s):
        high = int(s.replace("-", ""))
        return -20, high

    if re.match(r"^\d+\-\d+$", s):
        a, b = map(int, s.split("-"))
        return min(a, b), max(a, b)

    return None, None


@st.cache_data
def load_image_db():
    df = pd.read_excel(IMAGE_DB_PATH)
    df.columns = df.columns.str.strip().str.lower()

    required = {"gender", "style", "temp_range", "filename"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"image_db.xlsx에 필요한 컬럼이 없습니다: {missing}")

    df["gender"] = df["gender"].astype(str).str.strip().str.upper()
    df["style"] = df["style"].astype(str).str.strip().str.upper()
    df["temp_range"] = df["temp_range"].astype(str).str.strip()
    df["filename"] = df["filename"].astype(str).str.strip()

    #  혹시 filename에 "images/"가 들어가 있으면 자동 제거
    df["filename"] = df["filename"].str.replace("\\", "/", regex=False)
    df["filename"] = df["filename"].str.replace("images/", "", regex=False)
    df["filename"] = df["filename"].apply(lambda x: os.path.basename(x))  # 폴더 경로가 섞여있어도 파일명만

    df[["temp_low", "temp_high"]] = df["temp_range"].apply(
        lambda x: pd.Series(parse_temp_range(x))
    )

    df = df.dropna(subset=["temp_low", "temp_high"]).reset_index(drop=True)
    df["temp_low"] = df["temp_low"].astype(int)
    df["temp_high"] = df["temp_high"].astype(int)
    return df


def filter_by_temp(df, temp: int):
    return df[(df["temp_low"] <= temp) & (df["temp_high"] >= temp)].copy()


# =========================
# 3) Streamlit 기본 설정 + 폰트 통일
# =========================
st.set_page_config(page_title="기온별 의상 추천", layout="centered")

st.markdown(
    """
    <style>
    /* =========================
       0) 전역 텍스트/사이즈 변수
       ========================= */
    :root{
        --text-color: #222;        /* 기본 텍스트 색 */
        --muted-color: #777;       /* 설명용 텍스트 */

        --title-size: 52px;
        --subtitle-size: 52px;     /* ✅ 부제 사이즈 유지 */
        --helper-size: 15px;
        --button-size: 16px;
    }

    /* Streamlit 기본 텍스트 색 통일 */
    .stApp, .stApp *{
        color: var(--text-color) !important;
    }

    /* =========================
       1) 레이아웃
       ========================= */
    .block-container {
        max-width: 920px;
        height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding: 1.0rem;
    }
    header, footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden;}

    /* =========================
       2) 타이포그래피
       ========================= */
    .title{
        text-align: center;
        font-size: var(--title-size);
        font-weight: 800;
        letter-spacing: -1px;
        margin: 14px 0 6px 0;
        color: var(--text-color) !important;
        line-height: 1.12;
    }

    .subtitle{
        text-align: center;
        font-size: var(--subtitle-size); /* 사이즈 유지 */
        font-weight: 700;
        color: #000 !important;          /* 블랙 고정 */
        margin: 0 0 12px 0;
        line-height: 1.2;
    }

    .helper{
        text-align: center;
        font-size: var(--helper-size);
        color: var(--muted-color) !important;
        margin: 0 0 22px 0;
        line-height: 1.45;
    }

    /* =========================
       3) 버튼 / 위젯
       ========================= */
    div.stButton > button{
        border-radius: 18px !important;
        padding: 0.72rem 1.2rem !important;
        font-weight: 700 !important;
        font-size: var(--button-size) !important;
        border: 1px solid #e5e5e5 !important;
        color: var(--text-color) !important;
    }

    /* selectbox / slider 중앙 정렬 */
    .stSelectbox, .stSlider {
        max-width: 560px;
        margin: 0 auto;
    }

    /* =========================
       4) 결과 이미지
       ========================= */
    .result-wrap{
        display: flex;
        justify-content: center;
        margin-top: 8px;
        margin-bottom: 8px;
    }

    .result-wrap img{
        width: 380px;
        max-width: 92%;
        height: auto;
        border-radius: 18px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    }

    .divider{height: 18px;}
    </style>
    """,
    unsafe_allow_html=True
)


# =========================
# 4) 세션(단계형 UI)
# =========================
if "step" not in st.session_state:
    st.session_state.step = "intro1"
if "gender" not in st.session_state:
    st.session_state.gender = None
if "style" not in st.session_state:
    st.session_state.style = None
if "temp" not in st.session_state:
    st.session_state.temp = 15


def go(step_name: str):
    st.session_state.step = step_name
    st.rerun()


def reset_all():
    st.session_state.step = "intro1"
    st.session_state.gender = None
    st.session_state.style = None
    st.session_state.temp = 15
    st.rerun()


# =========================
# 5) DB 로드
# =========================
try:
    df_image = load_image_db()
except Exception as e:
    st.error(f"DB 로드 실패: {e}")
    st.stop()


# =========================
# 6) 화면
# =========================
step = st.session_state.step

# Intro 1
if step == "intro1":

    # ① 인트로 이미지 (macbg)
    intro_image_path = "./macbg.png"  

    if os.path.exists(intro_image_path):
        with open(intro_image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        st.markdown(
            f"""
            <div class="result-wrap">
                <img src="data:image/png;base64,{b64}" />
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error(f"인트로 이미지 파일 없음: {intro_image_path}")

    # 이미지 ↔ 타이틀 간격
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ② 타이틀
    st.markdown('<div class="title">온도에 맞는 옷 고르기</div>', unsafe_allow_html=True)
    st.markdown('<div class="title">어렵지 않으셨나요?</div>', unsafe_allow_html=True)

    # ③ 설명
    st.markdown(
        '<div class="helper">버튼을 눌러 단계별로 선택하면 추천 코디를 보여드릴게요.</div>',
        unsafe_allow_html=True
     #④ 버튼 중앙 정렬
    )
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("궁금해요", use_container_width=True):
            go("intro2")


# Intro 2
elif step == "intro2":

    # ① 인트로 이미지 (macbg2)
    intro2_image_path = "./macbg2.png"

    if os.path.exists(intro2_image_path):
        with open(intro2_image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        st.markdown(
            f"""
            <div class="result-wrap">
                <img src="data:image/png;base64,{b64}" />
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error(f"인트로 이미지 파일 없음: {intro2_image_path}")

    # 이미지 ↔ 문구 간격
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ② 문구
    st.markdown('<div class="title">저희가</div>', unsafe_allow_html=True)
    st.markdown('<div class="title">추천해드릴게요!</div>', unsafe_allow_html=True)

    # ③ 설명
    st.markdown(
        '<div class="helper">성별 → 스타일 → 온도를 고르면 대표 코디 1장을 추천합니다.</div>',
        unsafe_allow_html=True
    )

    # ④ 버튼
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        if st.button("시작하기", use_container_width=True):
            go("gender")

# Gender
elif step == "gender":
    st.markdown("<div class='title'>성별을</div>", unsafe_allow_html=True)
    st.markdown("<div class='title'>선택해주세요.</div>", unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    gender_label = st.radio(" ", ["여", "남"], horizontal=True, label_visibility="collapsed")
    st.session_state.gender = LABEL_TO_GENDER[gender_label]

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("처음으로", use_container_width=True):
            reset_all()
    with c2:
        if st.button("다음", use_container_width=True):
            go("style")

# Style
elif step == "style":
    if st.session_state.gender is None:
        go("gender")

    st.markdown('<div class="title">스타일을</div>', unsafe_allow_html=True)
    st.markdown('<div class="title">선택해주세요.</div>', unsafe_allow_html=True)

    # 타이틀 ↔ 선택 영역 간격
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    style_list = FEMALE_STYLES if st.session_state.gender == "F" else MALE_STYLES
    kr_options = [STYLE_KR[s] for s in style_list]
    selected_kr = st.selectbox(" ", kr_options, label_visibility="collapsed")
    st.session_state.style = KR_TO_STYLE[selected_kr]

    # 선택 영역 ↔ 버튼 간격
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("이전", use_container_width=True):
            go("gender")
    with c3:
        if st.button("다음", use_container_width=True):
            go("temp")

# Temp
elif step == "temp":
    if st.session_state.gender is None:
        go("gender")
    if st.session_state.style is None:
        go("style")

    st.markdown('<div class="title">원하는 온도를</div>', unsafe_allow_html=True)
    st.markdown('<div class="title">선택해주세요.</div>', unsafe_allow_html=True)
    st.markdown('<div class="helper">슬라이더로 온도를 조정해주세요!</div>', unsafe_allow_html=True)

    st.session_state.temp = st.slider(
        " ",
        min_value=-10,
        max_value=35,
        value=int(st.session_state.temp),
        step=1,
        label_visibility="collapsed"
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("이전", use_container_width=True):
            go("style")
    with c3:
        if st.button("추천 보기", use_container_width=True):
            go("result")

# Result
elif step == "result":
    if None in (st.session_state.gender, st.session_state.style):
        reset_all()

    gender = st.session_state.gender
    style = st.session_state.style
    temp = int(st.session_state.temp)

    st.markdown('<div class="title">추천 결과</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="helper">{GENDER_TO_LABEL[gender]} · {STYLE_KR.get(style, style)} · {temp}°C 기준</div>',
        unsafe_allow_html=True
    )

    df_filtered = df_image[(df_image["gender"] == gender) & (df_image["style"] == style)]
    df_filtered = filter_by_temp(df_filtered, temp)

    if df_filtered.empty:
        st.error("조건에 맞는 이미지가 없습니다. image_db.xlsx를 확인해주세요.")
    else:
        row = df_filtered.sample(1).iloc[0]

        # 이제 이미지가 루트에 있으므로 ./파일명으로 찾음
        image_path = os.path.join(IMAGE_DIR, row["filename"])

        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()

            st.markdown(
                f"""
                <div class="result-wrap">
                    <img src="data:image/png;base64,{b64}" />
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.error(f"이미지 파일 없음: {image_path}")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("이전", use_container_width=True):
            go("temp")
    with c3:
        if st.button("처음으로", use_container_width=True):
            reset_all()

else:
    reset_all()