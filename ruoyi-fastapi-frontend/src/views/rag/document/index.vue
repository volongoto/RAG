<template>
  <div class="app-container">
    <el-form ref="queryRef" :model="queryParams" :inline="true" v-show="showSearch">
      <el-form-item label="知识库" prop="kbId">
        <el-select v-model="queryParams.kbId" placeholder="请选择知识库" clearable style="width: 200px">
          <el-option
            v-for="kb in kbOptions"
            :key="kb.kbId"
            :label="kb.kbName"
            :value="kb.kbId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="文件名称" prop="fileName">
        <el-input
          v-model="queryParams.fileName"
          placeholder="请输入文件名称"
          clearable
          style="width: 200px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="解析状态" prop="parseStatus">
        <el-select v-model="queryParams.parseStatus" placeholder="请选择解析状态" clearable style="width: 200px">
          <el-option label="排队中" value="0" />
          <el-option label="解析中" value="1" />
          <el-option label="成功" value="2" />
          <el-option label="失败" value="3" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="primary"
          plain
          icon="Upload"
          @click="handleUpload"
          v-hasPermi="['rag:doc:add']"
        >
          上传文档
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="!hasSelection"
          @click="handleDelete()"
          v-hasPermi="['rag:doc:remove']"
        >
          删除
        </el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="docList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column prop="fileName" label="文件名称" min-width="220" show-overflow-tooltip />
      <el-table-column prop="fileType" label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.fileType === 'pdf' ? 'danger' : 'primary'">
            {{ row.fileType?.toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="fileSize" label="大小" width="110">
        <template #default="{ row }">
          {{ formatFileSize(row.fileSize) }}
        </template>
      </el-table-column>
      <el-table-column prop="chunkCount" label="切片数" width="90" />
      <el-table-column prop="parseStatus" label="解析状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getParseStatusType(row.parseStatus)">
            {{ getParseStatusText(row.parseStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="解析进度" min-width="280">
        <template #default="{ row }">
          <div class="parse-progress-cell">
            <el-progress
              v-if="isProcessing(row)"
              :percentage="getParseProgress(row)"
              :stroke-width="8"
              :status="row.parseStatus === '1' ? 'warning' : undefined"
            />
            <el-progress
              v-else-if="row.parseStatus === '2'"
              :percentage="100"
              :stroke-width="8"
              status="success"
            />
            <div
              v-if="getParseMessage(row)"
              class="parse-progress-text"
              :class="{ 'is-error': row.parseStatus === '3' }"
            >
              {{ getParseMessage(row) }}
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="上传时间" align="center" prop="createTime" width="180">
        <template #default="{ row }">
          <span>{{ parseTime(row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width" width="190">
        <template #default="{ row }">
          <el-button
            v-if="!isProcessing(row)"
            link
            type="primary"
            icon="Refresh"
            @click="handleReparse(row)"
            v-hasPermi="['rag:doc:edit']"
          >
            重新解析
          </el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(row)"
            v-hasPermi="['rag:doc:remove']"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <el-dialog
      v-model="uploadOpen"
      title="上传文档"
      width="560px"
      append-to-body
      @close="resetUploadDialog"
    >
      <el-form ref="uploadRef" :model="uploadForm" :rules="uploadRules" label-width="100px">
        <el-form-item label="知识库" prop="kbId">
          <el-select v-model="uploadForm.kbId" placeholder="请选择知识库" style="width: 100%">
            <el-option
              v-for="kb in kbOptions"
              :key="kb.kbId"
              :label="kb.kbName"
              :value="kb.kbId"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            ref="uploadFileRef"
            :auto-upload="false"
            :limit="20"
            multiple
            accept=".pdf,.docx"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :on-exceed="handleExceed"
          >
            <template #trigger>
              <el-button type="primary">选择文件</el-button>
            </template>
            <template #tip>
              <div class="el-upload__tip">
                支持 PDF、DOCX，单次最多 20 个文件。提交后将按队列顺序解析。
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" :loading="uploading" @click="submitUpload">确定</el-button>
          <el-button :disabled="uploading" @click="uploadOpen = false">取消</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Document">
import { delDocument, listDocument, reparseDocument, uploadDocument } from "@/api/rag/document";
import { listKnowledgeBase } from "@/api/rag/knowledgeBase";

const { proxy } = getCurrentInstance();

const queryRef = ref();
const uploadRef = ref();
const uploadFileRef = ref();

const docList = ref([]);
const kbOptions = ref([]);
const selectedRows = ref([]);
const uploadFiles = ref([]);
const uploadOpen = ref(false);
const uploading = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const total = ref(0);
const pollTimer = ref(null);

const hasSelection = computed(() => selectedRows.value.length > 0);

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    kbId: undefined,
    fileName: undefined,
    parseStatus: undefined
  },
  uploadForm: {
    kbId: undefined
  },
  uploadRules: {
    kbId: [{ required: true, message: "请选择知识库", trigger: "change" }]
  }
});

const { queryParams, uploadForm, uploadRules } = toRefs(data);

function stopPolling() {
  if (pollTimer.value) {
    clearTimeout(pollTimer.value);
    pollTimer.value = null;
  }
}

function isProcessing(row) {
  return ["0", "1"].includes(row?.parseStatus);
}

function schedulePolling() {
  stopPolling();
  if (!docList.value.some(item => isProcessing(item))) {
    return;
  }
  pollTimer.value = setTimeout(() => getList(true), 3000);
}

function getList(isBackground = false) {
  if (!isBackground) {
    loading.value = true;
  }
  return listDocument(queryParams.value)
    .then(response => {
      docList.value = response.data || [];
      total.value = response.total ?? docList.value.length;
    })
    .finally(() => {
      if (!isBackground) {
        loading.value = false;
      }
      schedulePolling();
    });
}

function getKbList() {
  return listKnowledgeBase({ status: "0" }).then(response => {
    kbOptions.value = response.data || [];
  });
}

function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function resetQuery() {
  queryRef.value?.resetFields();
  handleQuery();
}

function handleSelectionChange(selection) {
  selectedRows.value = selection;
}

function resetUploadDialog() {
  uploadRef.value?.resetFields();
  uploadFiles.value = [];
  uploadFileRef.value?.clearFiles();
}

function handleUpload() {
  resetUploadDialog();
  uploadOpen.value = true;
}

function syncUploadFiles(fileList) {
  uploadFiles.value = fileList
    .map(item => item.raw)
    .filter(Boolean);
}

function handleFileChange(_file, fileList) {
  syncUploadFiles(fileList);
}

function handleFileRemove(_file, fileList) {
  syncUploadFiles(fileList);
}

function handleExceed() {
  proxy.$modal.msgWarning("单次最多上传 20 个文件");
}

function buildUploadSummary(successFiles, failedFiles) {
  const lines = [];
  if (successFiles.length) {
    lines.push(`成功 ${successFiles.length} 个：${successFiles.join("、")}`);
  }
  if (failedFiles.length) {
    lines.push(`失败 ${failedFiles.length} 个：`);
    failedFiles.slice(0, 10).forEach(item => {
      lines.push(`${item.name}: ${item.message}`);
    });
    if (failedFiles.length > 10) {
      lines.push(`其余 ${failedFiles.length - 10} 个文件请查看重试结果`);
    }
  }
  return lines.join("\n");
}

async function submitUpload() {
  const valid = await uploadRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  if (!uploadFiles.value.length) {
    proxy.$modal.msgWarning("请选择至少一个文件");
    return;
  }

  uploading.value = true;
  const successFiles = [];
  const failedFiles = [];

  try {
    for (const file of uploadFiles.value) {
      try {
        const response = await uploadDocument(uploadForm.value.kbId, file);
        successFiles.push(file.name || "未命名文件");
        if (response?.msg) {
          console.log(`[rag-upload] ${file.name}: ${response.msg}`);
        }
      } catch (error) {
        failedFiles.push({
          name: file.name || "未命名文件",
          message: error?.message || "上传失败"
        });
      }
    }

    if (successFiles.length) {
      uploadOpen.value = false;
      resetUploadDialog();
      await getList();
    }

    if (!failedFiles.length) {
      proxy.$modal.msgSuccess(`已上传 ${successFiles.length} 个文件，任务已进入解析队列`);
      return;
    }

    proxy.$modal.alertWarning(buildUploadSummary(successFiles, failedFiles));
  } finally {
    uploading.value = false;
  }
}

function handleReparse(row) {
  proxy.$modal.confirm("是否重新解析该文档？")
    .then(() => reparseDocument(row.docId))
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("重新解析任务已提交");
    })
    .catch(() => {});
}

function handleDelete(row) {
  const docIds = row?.docId || selectedRows.value.map(item => item.docId).join(",");
  if (!docIds) {
    proxy.$modal.msgWarning("请先选择要删除的文档");
    return;
  }

  proxy.$modal.confirm("是否确认删除选中的文档？")
    .then(() => delDocument(docIds))
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

function formatFileSize(bytes) {
  if (!bytes) {
    return "0 B";
  }
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, index)).toFixed(2))} ${sizes[index]}`;
}

function getParseStatusType(status) {
  const types = { "0": "info", "1": "warning", "2": "success", "3": "danger" };
  return types[status] || "info";
}

function getParseStatusText(status) {
  const texts = { "0": "排队中", "1": "解析中", "2": "成功", "3": "失败" };
  return texts[status] || "未知";
}

function getParseProgress(row) {
  if (Number.isFinite(Number(row?.parseProgress))) {
    return Math.max(0, Math.min(100, Number(row.parseProgress)));
  }
  if (row?.parseStatus === "2") {
    return 100;
  }
  return row?.parseStatus === "1" ? 1 : 0;
}

function getParseMessage(row) {
  return row?.parseMessage || row?.parseError || getParseStatusText(row?.parseStatus);
}

onMounted(() => {
  getKbList();
  getList();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped>
.parse-progress-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.parse-progress-text {
  font-size: 12px;
  line-height: 1.4;
  color: var(--el-text-color-secondary);
}

.parse-progress-text.is-error {
  color: var(--el-color-danger);
}
</style>
