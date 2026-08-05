from io import BytesIO
from typing import IO, Any, Generator

import pypdfium2 as pdfium
from PIL import Image

PYPDFIUM2_ORIGINAL_DPI = 72
DEFAULT_TARGET_DPI = 300
MAX_RESULT_IMAGE_DIMENSION = 5000
MIN_SCALE_PARAMETER_VALUE = 1

__all__ = [
    "convert_pdf_to_pil_images",
    "DEFAULT_TARGET_DPI",
    "MAX_RESULT_IMAGE_DIMENSION",
]


def convert_pdf_to_pil_images(
    file_object: IO[Any], dpi: int = DEFAULT_TARGET_DPI
) -> Generator[Image.Image, None, None]:
    with pdfium.PdfDocument(file_object, autoclose=True) as pdf:
        try:
            for page_index, _ in enumerate(pdf):
                page = pdf.get_page(page_index)
                try:
                    image = page.render_topil(
                        scale=get_scale_parameter_value(
                            width=page.get_width(), height=page.get_height(), dpi=dpi
                        )
                    )
                    try:
                        dpi_changed_image = change_image_dpi(image, dpi=dpi)
                        try:
                            yield dpi_changed_image
                        finally:
                            dpi_changed_image.close()
                    finally:
                        image.close()
                finally:
                    page.close()

        finally:
            file_object.seek(0)


def get_scale_parameter_value(width: float, height: float, dpi: float) -> float:
    scale = dpi / PYPDFIUM2_ORIGINAL_DPI

    if (
        height * scale > MAX_RESULT_IMAGE_DIMENSION
        or width * scale > MAX_RESULT_IMAGE_DIMENSION
    ):
        return MIN_SCALE_PARAMETER_VALUE

    return scale


def change_image_dpi(image: Image.Image, dpi: int) -> Image.Image:
    with BytesIO() as temp_mem_file:
        image.save(temp_mem_file, format="png", dpi=(dpi, dpi), optimize=True)

        image = Image.open(temp_mem_file)
        image.load()

        return image
