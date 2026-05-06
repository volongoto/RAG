from pathlib import Path

import pytest
from docx.opc.exceptions import PackageNotFoundError

import module_rag.service.parser.document_parser as document_parser_module
from module_rag.service.parser.document_parser import DocxParser


class _FakeStyle:
    def __init__(self, name: str):
        self.name = name


class _FakeParagraph:
    def __init__(self, text: str, style_name: str):
        self.text = text
        self.style = _FakeStyle(style_name)


class _BrokenStyleParagraph:
    text = 'Readable paragraph with missing style'

    @property
    def style(self):
        raise KeyError('missing paragraph style')


class _FakeDocument:
    def __init__(self, paragraphs, tables=None):
        self.paragraphs = paragraphs
        self.tables = tables or []


class _UnreadableDocument:
    @property
    def paragraphs(self):
        raise KeyError('broken document body')

    tables = []


@pytest.mark.asyncio
async def test_docx_parser_retries_conversion_when_docx_package_open_fails(monkeypatch, tmp_path):
    source_path = tmp_path / 'renamed.docx'
    source_path.write_bytes(b'not-a-real-docx')

    converted_dir = tmp_path / 'converted'
    converted_dir.mkdir()
    converted_path = converted_dir / 'renamed.docx'
    converted_path.write_bytes(b'converted-docx')

    open_calls: list[str] = []

    def fake_document(path: str):
        open_calls.append(path)
        if path == str(source_path):
            raise PackageNotFoundError(f"Package not found at '{path}'")
        return _FakeDocument(
            [
                _FakeParagraph('Converted title', 'Heading 1'),
                _FakeParagraph('Converted body', 'Normal'),
            ]
        )

    def fake_convert(self, file_path: str, source_label: str | None = None) -> str:
        assert file_path == str(source_path)
        assert source_label == 'WPS/Word'
        return str(converted_path)

    monkeypatch.setattr(document_parser_module, 'Document', fake_document)
    monkeypatch.setattr(DocxParser, '_detect_word_file_format', lambda self, file_path: 'docx')
    monkeypatch.setattr(DocxParser, '_convert_office_file_to_docx', fake_convert)

    paragraphs = await DocxParser().parse(str(source_path))

    assert open_calls == [str(source_path), str(converted_path)]
    assert paragraphs == [
        {
            'content': 'Converted title',
            'page_num': None,
            'paragraph_index': 0,
            'is_heading': True,
        },
        {
            'content': 'Converted body',
            'page_num': None,
            'paragraph_index': 1,
            'is_heading': False,
        },
    ]
    assert not converted_path.exists()
    assert not converted_dir.exists()


@pytest.mark.asyncio
async def test_docx_parser_keeps_text_when_paragraph_style_is_broken(monkeypatch, tmp_path):
    source_path = tmp_path / 'broken-style.docx'
    source_path.write_bytes(b'fake-docx')

    monkeypatch.setattr(
        document_parser_module,
        'Document',
        lambda path: _FakeDocument([_BrokenStyleParagraph()]),
    )
    monkeypatch.setattr(DocxParser, '_detect_word_file_format', lambda self, file_path: 'docx')

    paragraphs = await DocxParser().parse(str(source_path))

    assert paragraphs == [
        {
            'content': 'Readable paragraph with missing style',
            'page_num': None,
            'paragraph_index': 0,
            'is_heading': False,
        }
    ]


@pytest.mark.asyncio
async def test_docx_parser_retries_normalized_docx_when_text_extraction_fails(monkeypatch, tmp_path):
    source_path = tmp_path / 'broken-body.docx'
    source_path.write_bytes(b'fake-docx')

    converted_dir = tmp_path / 'converted'
    converted_dir.mkdir()
    converted_path = converted_dir / 'broken-body.docx'
    converted_path.write_bytes(b'converted-docx')

    document_calls: list[str] = []

    def fake_document(path: str):
        document_calls.append(path)
        if path == str(source_path):
            return _UnreadableDocument()
        return _FakeDocument([_FakeParagraph('Recovered text', 'Normal')])

    def fake_convert(self, file_path: str, source_label: str | None = None) -> str:
        assert file_path == str(source_path)
        assert source_label == 'WPS/Word'
        return str(converted_path)

    monkeypatch.setattr(document_parser_module, 'Document', fake_document)
    monkeypatch.setattr(DocxParser, '_detect_word_file_format', lambda self, file_path: 'docx')
    monkeypatch.setattr(DocxParser, '_convert_office_file_to_docx', fake_convert)

    paragraphs = await DocxParser().parse(str(source_path))

    assert document_calls == [str(source_path), str(converted_path)]
    assert paragraphs == [
        {
            'content': 'Recovered text',
            'page_num': None,
            'paragraph_index': 0,
            'is_heading': False,
        }
    ]
    assert not converted_path.exists()
    assert not converted_dir.exists()
