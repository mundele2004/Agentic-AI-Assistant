from pathlib import Path

TEMP_DIR = Path("data/temp")

TEMP_DIR.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(uploaded_file):
    """
    Save Streamlit uploaded file to data/temp/
    """

    file_path = TEMP_DIR / uploaded_file.name

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return str(file_path)