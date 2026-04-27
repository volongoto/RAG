import io
import zipfile
from dataclasses import dataclass
from pathlib import Path


PDF_MAGIC = b'%PDF-'
OLE_MAGIC = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'
WORD_DOCUMENT_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
WORD_MACRO_CONTENT_TYPE = 'application/vnd.ms-word.document.macroenabled.main+xml'
WORD_TEMPLATE_CONTENT_TYPE = 'application/vnd.ms-word.template.macroenabledtemplate.main+xml'
WPS_CONTENT_TYPE_HINTS = (
    'wps',
    'kswps',
    'application/vnd.ms-works',
)
SUPPORTED_DOCUMENT_EXTENSIONS = ('pdf', 'doc', 'docx', 'wps')


@dataclass(frozen=True)
class DetectedDocumentType:
    file_type: str | None
    detection_source: str
    detail: str = ''


def get_file_extension(file_name: str | None) -> str:
    return Path(file_name or '').suffix.lstrip('.').lower()


def detect_document_type(
    *,
    file_name: str | None,
    file_content: bytes,
    content_type: str | None = None,
) -> DetectedDocumentType:
    detected_by_signature = _detect_by_signature(file_content=file_content, file_name=file_name, content_type=content_type)
    if detected_by_signature.file_type is not None:
        return detected_by_signature

    detected_by_content_type = _detect_by_content_type(content_type)
    if detected_by_content_type.file_type is not None:
        return detected_by_content_type

    extension = get_file_extension(file_name)
    if extension in SUPPORTED_DOCUMENT_EXTENSIONS:
        return DetectedDocumentType(file_type=extension, detection_source='extension', detail=extension)

    return DetectedDocumentType(file_type=None, detection_source='unknown', detail=extension or 'no-extension')


def _detect_by_signature(
    *,
    file_content: bytes,
    file_name: str | None,
    content_type: str | None,
) -> DetectedDocumentType:
    header = file_content[:8]
    extension = get_file_extension(file_name)

    if file_content.startswith(PDF_MAGIC):
        return DetectedDocumentType(file_type='pdf', detection_source='signature', detail='pdf-magic')

    if header.startswith(OLE_MAGIC):
        if extension == 'wps' or _looks_like_wps_content_type(content_type):
            return DetectedDocumentType(file_type='wps', detection_source='signature', detail='ole-wps')
        return DetectedDocumentType(file_type='doc', detection_source='signature', detail='ole-doc')

    if header.startswith(b'PK'):
        openxml_type = _detect_openxml_word_type(file_content)
        if openxml_type is not None:
            return DetectedDocumentType(file_type=openxml_type, detection_source='signature', detail='openxml-word')
        if extension == 'wps' or _looks_like_wps_content_type(content_type):
            return DetectedDocumentType(file_type='wps', detection_source='signature', detail='zip-wps')

    return DetectedDocumentType(file_type=None, detection_source='signature')


def _detect_openxml_word_type(file_content: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
            if '[Content_Types].xml' not in archive.namelist():
                return None
            content_types_xml = archive.read('[Content_Types].xml').decode('utf-8', errors='ignore').lower()
    except (OSError, ValueError, zipfile.BadZipFile, KeyError):
        return None

    if WORD_DOCUMENT_CONTENT_TYPE in content_types_xml:
        return 'docx'
    if WORD_MACRO_CONTENT_TYPE in content_types_xml:
        return 'docx'
    if WORD_TEMPLATE_CONTENT_TYPE in content_types_xml:
        return 'docx'
    return None


def _detect_by_content_type(content_type: str | None) -> DetectedDocumentType:
    normalized = (content_type or '').strip().lower()
    if not normalized:
        return DetectedDocumentType(file_type=None, detection_source='content-type')

    if 'pdf' in normalized:
        return DetectedDocumentType(file_type='pdf', detection_source='content-type', detail=normalized)
    if 'wordprocessingml' in normalized or 'officedocument.wordprocessingml.document' in normalized:
        return DetectedDocumentType(file_type='docx', detection_source='content-type', detail=normalized)
    if 'msword' in normalized:
        return DetectedDocumentType(file_type='doc', detection_source='content-type', detail=normalized)
    if _looks_like_wps_content_type(normalized):
        return DetectedDocumentType(file_type='wps', detection_source='content-type', detail=normalized)
    return DetectedDocumentType(file_type=None, detection_source='content-type', detail=normalized)


def _looks_like_wps_content_type(content_type: str | None) -> bool:
    normalized = (content_type or '').strip().lower()
    return any(hint in normalized for hint in WPS_CONTENT_TYPE_HINTS)
