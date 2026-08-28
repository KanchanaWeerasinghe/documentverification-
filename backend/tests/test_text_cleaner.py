from backend.app.ingestion.text_cleaner import clean_pages, clean_paragraphs, clean_text


def test_clean_text_normalizes_extraction_artifacts():
    raw = "\ufeffDose:\u00a0100\u00a0mg\u200b\r\n\r\n\r\nTake   once daily."

    assert clean_text(raw) == "Dose: 100 mg\n\nTake once daily."


def test_clean_paragraphs_discards_empty_values_and_preserves_content():
    paragraphs = ["  Medication\tName  ", "", "\u200b", "Dose: 100 mg"]

    assert clean_paragraphs(paragraphs) == ["Medication Name", "Dose: 100 mg"]


def test_clean_pages_preserves_page_boundaries():
    pages = [" Page one  ", "\n", "Page   three"]

    assert clean_pages(pages) == ["Page one", "", "Page three"]