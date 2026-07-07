import streamlit as st
import subprocess
import tempfile
from pathlib import Path
from html import escape

st.set_page_config(page_title="HWP → PDF 변환기", page_icon="📄", layout="centered")

st.title("📄 HWP → PDF 변환기")
st.caption(
    "hwp5html(HWP5 파서) → weasyprint(PDF 렌더링) 방식으로 변환합니다. "
    "복잡한 표/도형은 서식이 일부 다르게 나올 수 있고, 그 경우 텍스트만 "
    "추출한 PDF로 대체됩니다."
)


def convert_hwp_to_pdf(hwp_path: Path, work_dir: Path):
    """hwp5html로 시도하고, 실패하면 hwp5txt로 텍스트만 추출해 PDF로 만든다."""
    from weasyprint import HTML

    html_out_dir = work_dir / "html_out"
    r1 = subprocess.run(
        ["hwp5html", "--output", str(html_out_dir), str(hwp_path)],
        capture_output=True, text=True, timeout=180,
    )

    if r1.returncode == 0 and html_out_dir.exists():
        candidates = (
            list(html_out_dir.glob("index.xhtml"))
            + list(html_out_dir.glob("*.xhtml"))
            + list(html_out_dir.glob("*.html"))
        )
        if candidates:
            html_file = candidates[0]
            pdf_path = work_dir / "output.pdf"
            try:
                HTML(filename=str(html_file), base_url=str(html_out_dir)).write_pdf(str(pdf_path))
                if pdf_path.exists():
                    return pdf_path, "html", r1, None
            except Exception as e:  # weasyprint 렌더링 실패 시 텍스트로 폴백
                r1.stderr += f"\n[weasyprint error] {e}"

    # 폴백: 텍스트만 추출
    txt_path = work_dir / "output.txt"
    r2 = subprocess.run(
        ["hwp5txt", "--output", str(txt_path), str(hwp_path)],
        capture_output=True, text=True, timeout=180,
    )
    if r2.returncode == 0 and txt_path.exists():
        text = txt_path.read_text(encoding="utf-8", errors="replace")
        html_content = (
            "<html><head><meta charset='utf-8'>"
            "<style>body{font-family:'NanumGothic','UnDotum',sans-serif;"
            "white-space:pre-wrap;font-size:11pt;line-height:1.5;}</style>"
            f"</head><body>{escape(text)}</body></html>"
        )
        pdf_path = work_dir / "output_text.pdf"
        HTML(string=html_content).write_pdf(str(pdf_path))
        if pdf_path.exists():
            return pdf_path, "text", r1, r2

    return None, "failed", r1, r2


uploaded_file = st.file_uploader("HWP 파일을 선택하세요", type=["hwp"])

if uploaded_file is not None:
    st.write(f"선택한 파일: **{uploaded_file.name}** ({uploaded_file.size / 1024:.0f} KB)")

    if st.button("PDF로 변환하기", type="primary"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            input_path = work_dir / uploaded_file.name
            with open(input_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            with st.spinner("변환 중입니다... (최대 1~2분 소요될 수 있어요)"):
                try:
                    pdf_path, mode, r1, r2 = convert_hwp_to_pdf(input_path, work_dir)
                except Exception as e:
                    pdf_path, mode = None, "failed"
                    r1 = r2 = None
                    st.exception(e)

            if pdf_path is not None:
                if mode == "html":
                    st.success("변환 완료! (서식 포함)")
                else:
                    st.warning("서식 변환에는 실패해서, 텍스트만 추출한 PDF를 제공합니다.")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "⬇️ PDF 다운로드",
                        data=f.read(),
                        file_name=Path(uploaded_file.name).stem + ".pdf",
                        mime="application/pdf",
                    )
            else:
                st.error(
                    "변환에 실패했습니다. 암호가 걸려 있거나, 손상됐거나, "
                    "지원되지 않는 형식(.hwpx 등)일 수 있어요."
                )
                with st.expander("오류 상세 보기 (진단용)"):
                    if r1 is not None:
                        st.write("**hwp5html stdout:**")
                        st.code(r1.stdout or "(없음)")
                        st.write("**hwp5html stderr:**")
                        st.code(r1.stderr or "(없음)")
                    if r2 is not None:
                        st.write("**hwp5txt stdout:**")
                        st.code(r2.stdout or "(없음)")
                        st.write("**hwp5txt stderr:**")
                        st.code(r2.stderr or "(없음)")

st.divider()
st.caption(
    "⚠️ 참고: 암호가 걸린 HWP 파일, 최신 .hwpx 포맷은 지원되지 않습니다. "
    "구형 바이너리 .hwp(HWP5) 파일만 대상으로 합니다."
)
