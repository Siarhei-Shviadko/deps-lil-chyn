import concurrent.futures
import logging
from io import BytesIO
from typing import Any

from deps_object_storage import ObjectStorage
from deps_unified_data.model import Bbox, UnifiedData, UnifiedDataFactory, WordBox

from deps_lil_chyn.constants import DEFAULT_PDF_MAX_PROCESSES, DEFAULT_TARGET_DPI
from deps_lil_chyn.domain.dto import FileData, ImageData
from deps_lil_chyn.domain.services import PdfToImagesConverter, VectorPdfExtractor
from deps_lil_chyn.domain.services.vector_pdf_extractor import Page
from deps_lil_chyn.infrastructure.access_management import user

from .abstract_unifier import AbstractUnifier

logger = logging.getLogger(__name__)

Confidence = float
Content = str

__all__ = ["PdfUnifier"]


class PdfUnifier(AbstractUnifier):
    extensions: set[str] = {"pdf"}

    def __init__(
        self,
        object_storage: ObjectStorage,
        vector_pdf_extractor: VectorPdfExtractor,
        target_dpi: int = DEFAULT_TARGET_DPI,
        max_processes: int = DEFAULT_PDF_MAX_PROCESSES,
    ) -> None:
        super().__init__(object_storage=object_storage)
        self._vector_pdf_extractor = vector_pdf_extractor
        self._target_dpi = target_dpi
        self._max_processes = max_processes

    def unify(self, document_id: str, files: list[str]) -> UnifiedData:
        unified_data = UnifiedDataFactory.make_unified_data(document_id)

        for file_path in files:
            self._unify_file(unified_data, file_path)

        return unified_data

    def _unify_file(self, unified_data: UnifiedData, file_path: str) -> None:
        logger.info(
            f"Downloading source file for document `{unified_data.document_id}` from `{file_path}`"
        )

        file_data, page_wordboxes = self._prepare_input(file_path)
        results = self._run_processing_pool(file_data, page_wordboxes)
        self._build_unified_data(unified_data, results)

    def _prepare_input(
        self, file_path: str
    ) -> tuple[FileData, dict[Page, list[WordBox]]]:
        file_data = self._download_file_from_storage(file_path)
        with BytesIO(file_data.content) as file_stream:
            page_wordboxes = self._vector_pdf_extractor.extract_wordboxes(file_stream)

        return file_data, page_wordboxes

    def _run_processing_pool(
        self,
        file_data: FileData,
        page_wordboxes: dict[Page, list[WordBox]],
    ) -> list[dict[str, Any]]:
        user_data = user.get(None)

        def upload_page(
            page_index: int,
            image_data: ImageData,
            wordboxes: list[WordBox],
            file_name: str,
        ) -> dict[str, Any]:
            logger.info(f"Processing page {page_index + 1} of `{file_name}`")
            user.set(user_data)

            img_file = FileData(
                path=self._get_original_image_path(file_name, f"{page_index}.png"),
                content=image_data.content,
            )

            blob_name = self._upload_file_to_storage(img_file)

            return {
                "page_index": page_index,
                "blob_name": blob_name,
                "width": image_data.shape.width,
                "height": image_data.shape.height,
                "wordboxes": self._wordboxes_to_tuples(wordboxes),
            }

        results: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_processes
        ) as executor:
            in_flight: set[concurrent.futures.Future] = set()

            with BytesIO(file_data.content) as file_stream:
                for page_index, image_data in enumerate(
                    PdfToImagesConverter.convert(file=file_stream, dpi=self._target_dpi)
                ):
                    future = executor.submit(
                        upload_page,
                        page_index,
                        image_data,
                        page_wordboxes.get(page_index, []),
                        file_data.name,
                    )
                    in_flight.add(future)

                    if len(in_flight) >= self._max_processes:
                        done, in_flight = concurrent.futures.wait(
                            in_flight, return_when=concurrent.futures.FIRST_COMPLETED
                        )
                        for completed_future in done:
                            results.append(completed_future.result())

            for future in concurrent.futures.as_completed(in_flight):
                results.append(future.result())

        return results

    def _build_unified_data(
        self,
        unified_data: UnifiedData,
        results: list[dict[str, Any]],
    ) -> None:
        for r in sorted(results, key=lambda x: x["page_index"]):
            image = (
                unified_data.image_builder.for_page(r["page_index"] + 1)
                .with_blob(r["blob_name"])
                .with_shape(width=r["width"], height=r["height"])
                .build()
            )

            if r["wordboxes"]:
                (
                    unified_data.positonal_text_builder.for_page(r["page_index"] + 1)
                    .from_image(image.id.value)
                    .with_wordboxes(raw_words=r["wordboxes"])
                    .build()
                )

    @staticmethod
    def _wordboxes_to_tuples(
        wordboxes: list[WordBox],
    ) -> list[tuple[Content, Confidence, Bbox]]:
        return [
            (wordbox.word.content, wordbox.word.confidence, wordbox.bbox)
            for wordbox in wordboxes
        ]
