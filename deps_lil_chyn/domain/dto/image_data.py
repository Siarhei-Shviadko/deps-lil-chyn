from dataclasses import dataclass
from enum import Enum
from io import BytesIO

import cv2
import numpy as np
from docx.image.image import Image as DocxImage
from docx.shape import InlineShape as DocxInlineShape
from PIL import Image

from .shape import Shape

__all__ = ["ImageData", "ImageExtension"]


class ImageExtension(str, Enum):
    PNG = ".png"
    JPG = ".jpg"


@dataclass
class ImageData:
    content: bytes
    shape: Shape

    cv2_encode_params_mapping = {
        ImageExtension.PNG: [cv2.IMWRITE_PNG_COMPRESSION, 6],
        ImageExtension.JPG: [cv2.IMWRITE_JPEG_OPTIMIZE, 1],
    }

    def __init__(self, content: bytes, width: int, height: int):
        self.content = content
        self.shape = Shape(width=width, height=height)

    @property
    def width(self) -> int:
        return self.shape.width

    @property
    def height(self) -> int:
        return self.shape.height

    @classmethod
    def from_ndarray(cls, array: np.ndarray, extension: ImageExtension) -> "ImageData":
        is_success, buffer = cv2.imencode(
            extension, array, cls.cv2_encode_params_mapping[extension]
        )
        if not is_success:
            raise RuntimeError("Could not encode image data.")
        content_bytes = buffer.tobytes()

        return ImageData(
            content=content_bytes,
            width=int(array.shape[1]),
            height=int(array.shape[0]),
        )

    @classmethod
    def from_pil_image(
        cls,
        image: Image.Image,
        extension: ImageExtension = ImageExtension.PNG,
    ) -> "ImageData":
        rgb_image = image.convert("RGB")
        rgb_array = np.asarray(rgb_image, dtype=np.uint8)
        bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
        rgb_image.close()
        del rgb_array, rgb_image

        return cls.from_ndarray(array=bgr_array, extension=extension)

    @classmethod
    def from_docx_image(
        cls,
        image: DocxImage,
        docx_inline_shape: DocxInlineShape,
        extension: ImageExtension = ImageExtension.PNG,
    ) -> "ImageData":
        extension_to_pil_fmt = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}

        height_ratio = docx_inline_shape.height / image.height
        width_ratio = docx_inline_shape.width / image.width
        width = int(width_ratio * image.px_width)
        height = int(height_ratio * image.px_height)

        with BytesIO(image.blob) as image_stream:
            with Image.open(
                image_stream, formats=[extension_to_pil_fmt[image.ext]]
            ) as pil_image:
                resized_image = pil_image.resize((width, height))
                return cls.from_pil_image(image=resized_image, extension=extension)
