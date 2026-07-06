import streamlit as st
import subprocess
import tempfile
import uuid
import os
from pathlib import Path

st.set_page_config(page_title="HWP → PDF 변환기", page_icon="📄", layout="centered")

st.title("📄 HWP → PDF 변환기")
st.caption(
    "HWP 파일을 업로드하면 PDF로 변환합니다. "
    "LibreOffice 엔진으로 변환하므로 복잡한 표나 이미지가 있는 문서는 "
    "서식이 원본과 다소 달라질 수 있어요."
)

uploaded_file = st.file_uploader("HWP 파일을 선택하세요", type=["hwp"])

if uploaded_file is not None:
    st.write(f"선택한 파일: **{uploaded_file.name}** ({uploaded_file.size / 1024:.0f} KB)")

    if st.button("PDF로 변환하기", type="primary"):
        # 요청마다 독립된 작업 폴더 + LibreOffice 프로필을 사용해
        # 동시 접속 시 발생하는 lock 충돌을 방지합니다.
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            profile_dir = work_dir / f"lo_profile_{uuid.uuid4().hex}"
            input_path = work_dir / uploaded_file.name

            with open(input_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # 컨테이너 환경에서 HOME이 없거나 쓰기 불가능하면
            # soffice가 프로필을 생성하지 못해 "source file could not be
            # loaded" 오류가 발생합니다. 명시적으로 쓰기 가능한 HOME을 지정합니다.
            env = os.environ.copy()
            env["HOME"] = str(work_dir)

            with st.spinner("변환 중입니다... (최대 1~2분 소요될 수 있어요)"):
                try:
                    result = subprocess.run(
                        [
                            "soffice",
                            "--headless",
                            "--invisible",
                            "--nodefault",
                            "--nofirststartwizard",
                            "--nolockcheck",
                            "--nologo",
                            "--norestore",
                            f"-env:UserInstallation=file://{profile_dir}",
                            "--convert-to", "pdf",
                            "--outdir", str(work_dir),
                            str(input_path),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120,
                        env=env,
                    )
                except subprocess.TimeoutExpired:
                    st.error("변환 시간이 초과됐어요. 파일이 너무 크거나 손상됐을 수 있어요.")
                    result = None

            if result is not None:
                pdf_path = input_path.with_suffix(".pdf")

                if result.returncode == 0 and pdf_path.exists():
                    st.success("변환 완료! 아래 버튼으로 다운로드하세요.")
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "⬇️ PDF 다운로드",
                            data=f.read(),
                            file_name=pdf_path.name,
                            mime="application/pdf",
                        )
                else:
                    st.error("변환에 실패했습니다. 파일이 손상됐거나 지원되지 않는 형식일 수 있어요.")
                    with st.expander("오류 상세 보기 (진단용)"):
                        st.write("**returncode:**", result.returncode)
                        st.write("**stdout:**")
                        st.code(result.stdout or "(없음)")
                        st.write("**stderr:**")
                        st.code(result.stderr or "(없음)")

st.divider()
with st.expander("🔧 LibreOffice 설치 상태 진단"):
    if st.button("soffice 버전 확인"):
        try:
            v = subprocess.run(
                ["soffice", "--version"], capture_output=True, text=True, timeout=30
            )
            st.code(v.stdout + v.stderr)
        except FileNotFoundError:
            st.error("soffice 명령어를 찾을 수 없어요. packages.txt에 libreoffice가 제대로 설치됐는지 확인하세요.")

st.divider()
st.caption(
    "⚠️ 참고: 암호가 걸린 HWP 파일, 최신 .hwpx 포맷, 매우 복잡한 표/개체가 있는 "
    "문서는 변환 품질이 떨어지거나 실패할 수 있습니다."
)
