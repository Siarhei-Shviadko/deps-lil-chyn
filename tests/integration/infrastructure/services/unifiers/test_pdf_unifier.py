from uuid import uuid4


def test_pdf_unifier(pdf_unifier, fake_storage_service):
    files = ["tests/data/vector.pdf", "tests/data/raster.pdf"]
    image_paths = [
        "vector/original/0.png",
        "raster/original/0.png",
        "raster/original/1.png",
    ]
    pages_number = 3
    pages_with_positional_text_number = 1
    document_id = uuid4().hex

    for file_path in files:
        with open(file_path, "r+b") as f:
            fake_storage_service.upload(path=file_path, content=f.read(), replace_if_exists=True)

    unified_data = pdf_unifier.unify(document_id=document_id, files=files)

    assert len(unified_data.images) == pages_number
    assert len(unified_data.positional_texts) == pages_with_positional_text_number
    assert unified_data.document_id == document_id

    for image_path in image_paths:
        try:
            fake_storage_service.download(image_path)
        except Exception as e:
            assert False, f"FakeStorageService.download_content: {e}"
