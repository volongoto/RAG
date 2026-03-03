from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_validation_decorator import NotBlank, Size


class KnowledgeBaseModel(BaseModel):
    """
    知识库表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    kb_id: Optional[int] = Field(default=None, description='知识库ID')
    kb_name: Optional[str] = Field(default=None, description='知识库名称')
    kb_type: Optional[Literal['dept', 'personal']] = Field(default=None, description='知识库类型')
    description: Optional[str] = Field(default=None, description='描述')
    dept_id: Optional[int] = Field(default=None, description='所属部门ID')
    user_id: Optional[int] = Field(default=None, description='所属用户ID')
    embedding_model: Optional[str] = Field(default='BAAI/bge-m3', description='向量模型')
    status: Optional[Literal['0', '1']] = Field(default='0', description='状态（0正常 1停用）')
    del_flag: Optional[Literal['0', '2']] = Field(default=None, description='删除标志')
    create_by: Optional[str] = Field(default=None, description='创建者')
    create_time: Optional[datetime] = Field(default=None, description='创建时间')
    update_by: Optional[str] = Field(default=None, description='更新者')
    update_time: Optional[datetime] = Field(default=None, description='更新时间')
    remark: Optional[str] = Field(default=None, description='备注')

    @NotBlank(field_name='kb_name', message='知识库名称不能为空')
    @Size(field_name='kb_name', min_length=0, max_length=200, message='知识库名称长度不能超过200个字符')
    def get_kb_name(self):
        return self.kb_name

    @NotBlank(field_name='kb_type', message='知识库类型不能为空')
    def get_kb_type(self):
        return self.kb_type

    def validate_fields(self) -> None:
        self.get_kb_name()
        self.get_kb_type()


class KnowledgeBaseQueryModel(BaseModel):
    """
    知识库查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    kb_id: Optional[int] = Field(default=None, description='知识库ID')
    kb_name: Optional[str] = Field(default=None, description='知识库名称')
    kb_type: Optional[Literal['dept', 'personal']] = Field(default=None, description='知识库类型')
    dept_id: Optional[int] = Field(default=None, description='所属部门ID')
    user_id: Optional[int] = Field(default=None, description='所属用户ID')
    status: Optional[Literal['0', '1']] = Field(default=None, description='状态')
    page_num: Optional[int] = Field(default=1, description='页码')
    page_size: Optional[int] = Field(default=10, description='每页数量')


class DeleteKnowledgeBaseModel(BaseModel):
    """
    删除知识库模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    kb_ids: str = Field(default=None, description='需要删除的知识库ID')
    update_by: Optional[str] = Field(default=None, description='更新者')
    update_time: Optional[datetime] = Field(default=None, description='更新时间')


class DocumentModel(BaseModel):
    """
    文档表对应pydantic模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    doc_id: Optional[int] = Field(default=None, description='文档ID')
    kb_id: Optional[int] = Field(default=None, description='知识库ID')
    file_name: Optional[str] = Field(default=None, description='文件名称')
    file_path: Optional[str] = Field(default=None, description='文件存储路径')
    file_size: Optional[int] = Field(default=None, description='文件大小（字节）')
    file_type: Optional[str] = Field(default=None, description='文件类型')
    chunk_count: Optional[int] = Field(default=0, description='切片数量')
    parse_status: Optional[Literal['0', '1', '2', '3']] = Field(default='0', description='解析状态')
    parse_error: Optional[str] = Field(default=None, description='解析错误信息')
    del_flag: Optional[Literal['0', '2']] = Field(default=None, description='删除标志')
    create_by: Optional[str] = Field(default=None, description='上传者')
    create_time: Optional[datetime] = Field(default=None, description='创建时间')
    update_by: Optional[str] = Field(default=None, description='更新者')
    update_time: Optional[datetime] = Field(default=None, description='更新时间')


class DocumentQueryModel(BaseModel):
    """
    文档查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    doc_id: Optional[int] = Field(default=None, description='文档ID')
    kb_id: Optional[int] = Field(default=None, description='知识库ID')
    file_name: Optional[str] = Field(default=None, description='文件名称')
    file_type: Optional[str] = Field(default=None, description='文件类型')
    parse_status: Optional[Literal['0', '1', '2', '3']] = Field(default=None, description='解析状态')
    page_num: Optional[int] = Field(default=1, description='页码')
    page_size: Optional[int] = Field(default=10, description='每页数量')


class DeleteDocumentModel(BaseModel):
    """
    删除文档模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    doc_ids: str = Field(default=None, description='需要删除的文档ID')
    update_by: Optional[str] = Field(default=None, description='更新者')
    update_time: Optional[datetime] = Field(default=None, description='更新时间')


class ChunkModel(BaseModel):
    """
    文档切片模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    chunk_id: Optional[int] = Field(default=None, description='切片ID')
    doc_id: Optional[int] = Field(default=None, description='文档ID')
    kb_id: Optional[int] = Field(default=None, description='知识库ID')
    chunk_index: Optional[int] = Field(default=None, description='切片序号')
    content: Optional[str] = Field(default=None, description='文本内容')
    metadata: Optional[dict[str, Any]] = Field(default=None, description='元数据')
    create_time: Optional[datetime] = Field(default=None, description='创建时间')


class QueryRequestModel(BaseModel):
    """
    知识查询请求模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    kb_ids: list[int] = Field(default=None, description='知识库ID列表')
    query_text: str = Field(default=None, description='查询内容')
    top_k: Optional[int] = Field(default=5, description='返回结果数量')
    include_source: Optional[bool] = Field(default=True, description='是否包含原文来源')


class SourceChunkModel(BaseModel):
    """
    来源切片模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    chunk_id: int = Field(description='切片ID')
    doc_id: int = Field(description='文档ID')
    doc_name: str = Field(description='文档名称')
    content: str = Field(description='文本内容')
    page_num: Optional[int] = Field(default=None, description='页码')
    paragraph_index: Optional[int] = Field(default=None, description='段落序号')
    similarity: Optional[float] = Field(default=None, description='相似度')


class QueryResponseModel(BaseModel):
    """
    知识查询响应模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    answer_text: str = Field(description='回答内容')
    source_chunks: Optional[list[SourceChunkModel]] = Field(default=None, description='引用的切片信息')
    response_time: Optional[int] = Field(default=None, description='响应时间（毫秒）')


class QueryLogModel(BaseModel):
    """
    查询记录模型
    """

    model_config = ConfigDict(alias_generator=to_camel, from_attributes=True, populate_by_name=True)

    log_id: Optional[int] = Field(default=None, description='日志ID')
    kb_ids: Optional[str] = Field(default=None, description='查询的知识库ID列表')
    query_text: Optional[str] = Field(default=None, description='查询内容')
    answer_text: Optional[str] = Field(default=None, description='回答内容')
    source_chunks: Optional[dict[str, Any]] = Field(default=None, description='引用的切片信息')
    query_time: Optional[datetime] = Field(default=None, description='查询时间')
    user_id: Optional[int] = Field(default=None, description='查询用户ID')
    response_time: Optional[int] = Field(default=None, description='响应时间（毫秒）')


class QueryLogQueryModel(BaseModel):
    """
    查询记录查询模型
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    log_id: Optional[int] = Field(default=None, description='日志ID')
    user_id: Optional[int] = Field(default=None, description='查询用户ID')
    query_text: Optional[str] = Field(default=None, description='查询内容')
    begin_time: Optional[str] = Field(default=None, description='开始时间')
    end_time: Optional[str] = Field(default=None, description='结束时间')
    page_num: Optional[int] = Field(default=1, description='页码')
    page_size: Optional[int] = Field(default=10, description='每页数量')
