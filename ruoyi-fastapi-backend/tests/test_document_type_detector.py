import io
import zipfile

from module_rag.service.parser.document_type_detector import detect_document_type


def _build_word_openxml_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(
            '[Content_Types].xml',
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '</Types>'
            ),
        )
        archive.writestr('word/document.xml', '<w:document xmlns:w="test"></w:document>')
    return buffer.getvalue()


def test_detect_pdf_by_signature_even_when_extension_is_docx():
    result = detect_document_type(
        file_name='renamed.docx',
        file_content=b'%PDF-1.7\nfake',
        content_type='application/octet-stream',
    )
    assert result.file_type == 'pdf'
    assert result.detection_source == 'signature'


def test_detect_doc_by_ole_signature_even_when_extension_is_docx():
    result = detect_document_type(
        file_name='renamed.docx',
        file_content=b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1rest',
        content_type='application/octet-stream',
    )
    assert result.file_type == 'doc'
    assert result.detection_source == 'signature'


def test_detect_docx_by_openxml_signature_even_when_extension_is_wps():
    result = detect_document_type(
        file_name='sample.wps',
        file_content=_build_word_openxml_bytes(),
        content_type='application/octet-stream',
    )
    assert result.file_type == 'docx'
    assert result.detection_source == 'signature'


def test_detect_wps_by_extension_when_signature_is_unknown():
    result = detect_document_type(
        file_name='sample.wps',
        file_content=b'plain-text-content',
        content_type='application/octet-stream',
    )
    assert result.file_type == 'wps'
    assert result.detection_source == 'extension'
