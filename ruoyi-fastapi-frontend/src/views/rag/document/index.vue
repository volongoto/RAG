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
      title="批量上传文档"
      width="900px"
      append-to-body
      :close-on-click-modal="!uploading"
      :close-on-press-escape="!uploading"
      :show-close="!uploading"
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
        <el-form-item label="批量文件">
          <div class="upload-panel">
            <div class="upload-toolbar">
              <div class="upload-toolbar-actions">
                <el-button type="primary" @click="openFileSelector">选择文件</el-button>
                <el-button @click="openDirectorySelector">选择目录</el-button>
                <el-button :disabled="uploading || !uploadItems.length" @click="clearUploadItems">
                  清空列表
                </el-button>
              </div>
              <div class="upload-toolbar-tip">
                <div>仅会加入 {{ uploadAllowedExtensionText }} 文件。上传成功后会进入后端解析队列，按队列顺序处理。</div>
                <div
                  v-for="tip in uploadConstraintTips"
                  :key="tip"
                >
                  {{ tip }}
                </div>
              </div>
            </div>

            <input
              ref="fileInputRef"
              class="native-upload-input"
              type="file"
              :accept="uploadAccept"
              multiple
              @change="handleFileInputChange"
            />
            <input
              ref="directoryInputRef"
              class="native-upload-input"
              type="file"
              :accept="uploadAccept"
              multiple
              webkitdirectory
              directory
              @change="handleDirectoryInputChange"
            />

            <div class="upload-summary">
              <el-tag type="info">总计 {{ uploadStats.total }}</el-tag>
              <el-tag type="info">待提交 {{ uploadStats.queued }}</el-tag>
              <el-tag type="warning">上传中 {{ uploadStats.uploading }}</el-tag>
              <el-tag type="success">成功 {{ uploadStats.success }}</el-tag>
              <el-tag type="danger">失败 {{ uploadStats.error }}</el-tag>
            </div>

            <el-empty v-if="!uploadItems.length" description="请选择文件或目录" />
            <el-table v-else :data="uploadItems" row-key="id" max-height="320">
              <el-table-column type="index" width="60" align="center" label="#" />
              <el-table-column prop="fileName" label="文件名称" min-width="180" show-overflow-tooltip />
              <el-table-column label="目录路径" min-width="220" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="path-text">{{ row.relativeDir || '--' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="大小" width="110">
                <template #default="{ row }">
                  {{ formatFileSize(row.fileSize) }}
                </template>
              </el-table-column>
              <el-table-column label="上传状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="getUploadStatusType(row.status)">
                    {{ getUploadStatusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="message" label="结果" min-width="240" show-overflow-tooltip />
              <el-table-column label="操作" align="center" width="90">
                <template #default="{ row }">
                  <el-button
                    link
                    type="primary"
                    :disabled="uploading && row.status === 'uploading'"
                    @click="removeUploadItem(row)"
                  >
                    移除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" :loading="uploading" @click="submitUpload">
            {{ uploading ? '队列提交中' : '开始提交' }}
          </el-button>
          <el-button :disabled="uploading" @click="uploadOpen = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Document">
import { delDocument, getDocumentUploadPolicy, listDocument, reparseDocument, uploadDocument } from "@/api/rag/document";
import { listKnowledgeBase } from "@/api/rag/knowledgeBase";

const LARGE_HINT_FILE_COUNT_THRESHOLD = 100;
const LARGE_HINT_TOTAL_SIZE_BYTES = 1024 * 1024 * 1024;
const DEFAULT_UPLOAD_POLICY = Object.freeze({
  allowedExtensions: ["pdf", "docx"],
  submitConcurrency: 2,
  queueSize: 0,
  maxTotalSizeBytes: 0,
  maxSingleFileSizeBytes: 200 * 1024 * 1024
});

const UPLOAD_STATUS_MAP = {
  queued: { text: "待提交", type: "info" },
  uploading: { text: "上传中", type: "warning" },
  success: { text: "已入队", type: "success" },
  error: { text: "上传失败", type: "danger" }
};

const { proxy } = getCurrentInstance();

const queryRef = ref();
const uploadRef = ref();
const fileInputRef = ref();
const directoryInputRef = ref();

const docList = ref([]);
const kbOptions = ref([]);
const selectedRows = ref([]);
const uploadItems = ref([]);
const uploadOpen = ref(false);
const uploading = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const total = ref(0);
const pollTimer = ref(null);
const uploadPolicyLoaded = ref(false);
const uploadPolicy = reactive({
  allowedExtensions: [...DEFAULT_UPLOAD_POLICY.allowedExtensions],
  submitConcurrency: DEFAULT_UPLOAD_POLICY.submitConcurrency,
  queueSize: DEFAULT_UPLOAD_POLICY.queueSize,
  maxTotalSizeBytes: DEFAULT_UPLOAD_POLICY.maxTotalSizeBytes,
  maxSingleFileSizeBytes: DEFAULT_UPLOAD_POLICY.maxSingleFileSizeBytes
});

const hasSelection = computed(() => selectedRows.value.length > 0);
const uploadStats = computed(() =>
  uploadItems.value.reduce(
    (stats, item) => {
      stats.total += 1;
      stats[item.status] += 1;
      return stats;
    },
    { total: 0, queued: 0, uploading: 0, success: 0, error: 0 }
  )
);
const normalizedAllowedExtensions = computed(() =>
  (uploadPolicy.allowedExtensions?.length ? uploadPolicy.allowedExtensions : DEFAULT_UPLOAD_POLICY.allowedExtensions)
    .map(extension => String(extension).toLowerCase())
);
const uploadAccept = computed(() =>
  normalizedAllowedExtensions.value
    .map(extension => `.${extension}`)
    .join(",")
);
const uploadAllowedExtensionText = computed(() =>
  normalizedAllowedExtensions.value
    .map(extension => extension.toUpperCase())
    .join("、")
);
const uploadConstraintTips = computed(() => {
  const tips = [];
  if (
    uploadPolicy.maxSingleFileSizeBytes > 0 &&
    uploadPolicy.maxSingleFileSizeBytes <= LARGE_HINT_TOTAL_SIZE_BYTES
  ) {
    tips.push(`单个文件不超过 ${formatFileSize(uploadPolicy.maxSingleFileSizeBytes)}`);
  }
  if (uploadPolicy.queueSize > 0 && uploadPolicy.queueSize <= LARGE_HINT_FILE_COUNT_THRESHOLD) {
    tips.push(`单次最多 ${uploadPolicy.queueSize} 个文件`);
  }
  if (
    uploadPolicy.maxTotalSizeBytes > 0 &&
    uploadPolicy.maxTotalSizeBytes <= LARGE_HINT_TOTAL_SIZE_BYTES
  ) {
    tips.push(`单次总大小不超过 ${formatFileSize(uploadPolicy.maxTotalSizeBytes)}`);
  }
  return tips;
});

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

function clearNativeInput(inputElement) {
  if (inputElement) {
    inputElement.value = "";
  }
}

function resetUploadDialog() {
  uploadRef.value?.resetFields();
  uploadItems.value = [];
  clearNativeInput(fileInputRef.value);
  clearNativeInput(directoryInputRef.value);
}

async function handleUpload() {
  await loadUploadPolicy();
  resetUploadDialog();
  uploadForm.value.kbId = queryParams.value.kbId;
  uploadOpen.value = true;
}

function normalizeLimitBytes(value) {
  const parsedValue = Number(value);
  if (!Number.isFinite(parsedValue) || parsedValue <= 0) {
    return 0;
  }
  return Math.floor(parsedValue);
}

function normalizeQueueSize(value) {
  const parsedValue = Number(value);
  if (!Number.isFinite(parsedValue) || parsedValue <= 0) {
    return 0;
  }
  return Math.floor(parsedValue);
}

function normalizeConcurrency(value) {
  const parsedValue = Number(value);
  if (!Number.isFinite(parsedValue) || parsedValue < 1) {
    return 1;
  }
  return Math.floor(parsedValue);
}

async function loadUploadPolicy(force = false) {
  if (uploadPolicyLoaded.value && !force) {
    return uploadPolicy;
  }

  try {
    const response = await getDocumentUploadPolicy();
    const policy = response?.data || {};
    uploadPolicy.allowedExtensions = Array.isArray(policy.allowedExtensions) && policy.allowedExtensions.length
      ? policy.allowedExtensions.map(item => String(item).toLowerCase())
      : [...DEFAULT_UPLOAD_POLICY.allowedExtensions];
    uploadPolicy.submitConcurrency = normalizeConcurrency(
      policy.submitConcurrency ?? DEFAULT_UPLOAD_POLICY.submitConcurrency
    );
    uploadPolicy.queueSize = normalizeQueueSize(policy.queueSize ?? DEFAULT_UPLOAD_POLICY.queueSize);
    uploadPolicy.maxTotalSizeBytes = normalizeLimitBytes(
      policy.maxTotalSizeBytes ?? DEFAULT_UPLOAD_POLICY.maxTotalSizeBytes
    );
    uploadPolicy.maxSingleFileSizeBytes = normalizeLimitBytes(
      policy.maxSingleFileSizeBytes ?? DEFAULT_UPLOAD_POLICY.maxSingleFileSizeBytes
    );
    uploadPolicyLoaded.value = true;
  } catch (error) {
    uploadPolicy.allowedExtensions = [...DEFAULT_UPLOAD_POLICY.allowedExtensions];
    uploadPolicy.submitConcurrency = DEFAULT_UPLOAD_POLICY.submitConcurrency;
    uploadPolicy.queueSize = DEFAULT_UPLOAD_POLICY.queueSize;
    uploadPolicy.maxTotalSizeBytes = DEFAULT_UPLOAD_POLICY.maxTotalSizeBytes;
    uploadPolicy.maxSingleFileSizeBytes = DEFAULT_UPLOAD_POLICY.maxSingleFileSizeBytes;
    uploadPolicyLoaded.value = false;
    console.warn("[rag-upload] failed to load upload policy, fallback to defaults", error);
  }

  return uploadPolicy;
}

function getFileExtension(fileName = "") {
  return fileName.includes(".") ? fileName.split(".").pop().toLowerCase() : "";
}

function isSupportedFile(file) {
  return new Set(normalizedAllowedExtensions.value).has(getFileExtension(file?.name));
}

function buildUploadItemId(file) {
  return [file.webkitRelativePath || file.name || "", file.size || 0, file.lastModified || 0].join("__");
}

function createUploadItem(file) {
  const relativePath = file.webkitRelativePath || "";
  return {
    id: buildUploadItemId(file),
    file,
    fileName: file.name || "未命名文件",
    relativePath,
    relativeDir: relativePath ? relativePath.split("/").slice(0, -1).join("/") : "",
    fileSize: file.size || 0,
    status: "queued",
    message: "等待提交"
  };
}

function getPendingUploadItems() {
  return uploadItems.value.filter(item => ["queued", "error"].includes(item.status));
}

function getTotalUploadSize(items = []) {
  return items.reduce((totalSize, item) => totalSize + Number(item?.fileSize || 0), 0);
}

function validateUploadBatch(items = []) {
  const issues = [];
  const maxQueueSize = normalizeQueueSize(uploadPolicy.queueSize);
  const maxTotalSizeBytes = normalizeLimitBytes(uploadPolicy.maxTotalSizeBytes);
  const maxSingleFileSizeBytes = normalizeLimitBytes(uploadPolicy.maxSingleFileSizeBytes);

  if (maxQueueSize > 0 && items.length > maxQueueSize) {
    issues.push(`当前最多可提交 ${maxQueueSize} 个文件`);
  }

  if (maxSingleFileSizeBytes > 0) {
    const oversizedCount = items.filter(item => Number(item?.fileSize || 0) > maxSingleFileSizeBytes).length;
    if (oversizedCount > 0) {
      issues.push(`存在 ${oversizedCount} 个文件超过单文件限制（${formatFileSize(maxSingleFileSizeBytes)}）`);
    }
  }

  const totalSize = getTotalUploadSize(items);
  if (maxTotalSizeBytes > 0 && totalSize > maxTotalSizeBytes) {
    issues.push(`待提交文件总大小 ${formatFileSize(totalSize)}，超过限制 ${formatFileSize(maxTotalSizeBytes)}`);
  }

  return {
    valid: issues.length === 0,
    message: issues.join("\n")
  };
}

function buildSelectionSummary(selectionResult) {
  const lines = [];
  if (selectionResult.addedCount) {
    lines.push(`已加入 ${selectionResult.addedCount} 个可上传文件`);
  }
  if (selectionResult.unsupportedCount) {
    lines.push(`已忽略 ${selectionResult.unsupportedCount} 个非 ${uploadAllowedExtensionText.value} 文件`);
  }
  if (selectionResult.duplicateCount) {
    lines.push(`已跳过 ${selectionResult.duplicateCount} 个重复文件`);
  }
  if (selectionResult.singleFileLimitCount) {
    lines.push(`已忽略 ${selectionResult.singleFileLimitCount} 个超过单文件限制的文件（上限 ${formatFileSize(uploadPolicy.maxSingleFileSizeBytes)}）`);
  }
  if (selectionResult.queueLimitCount) {
    lines.push(`超出当前批量文件数限制，未加入 ${selectionResult.queueLimitCount} 个文件（上限 ${uploadPolicy.queueSize} 个）`);
  }
  if (selectionResult.totalSizeLimitCount) {
    lines.push(`超出当前批量总大小限制，未加入 ${selectionResult.totalSizeLimitCount} 个文件（上限 ${formatFileSize(uploadPolicy.maxTotalSizeBytes)}）`);
  }
  return lines.join("\n");
}

function notifySelectionResult(selectionResult) {
  const summary = buildSelectionSummary(selectionResult);
  if (!summary) {
    return;
  }
  const hasIssue =
    selectionResult.unsupportedCount ||
    selectionResult.duplicateCount ||
    selectionResult.singleFileLimitCount ||
    selectionResult.queueLimitCount ||
    selectionResult.totalSizeLimitCount;
  if (hasIssue) {
    proxy.$modal.alertWarning(summary);
    return;
  }
  proxy.$modal.msgSuccess(summary);
}

function appendUploadFiles(files) {
  const selectionResult = {
    addedCount: 0,
    unsupportedCount: 0,
    duplicateCount: 0,
    singleFileLimitCount: 0,
    queueLimitCount: 0,
    totalSizeLimitCount: 0
  };

  if (!files.length) {
    return selectionResult;
  }

  const maxQueueSize = normalizeQueueSize(uploadPolicy.queueSize);
  const maxTotalSizeBytes = normalizeLimitBytes(uploadPolicy.maxTotalSizeBytes);
  const maxSingleFileSizeBytes = normalizeLimitBytes(uploadPolicy.maxSingleFileSizeBytes);
  const existingIds = new Set(uploadItems.value.map(item => item.id));
  const nextItems = [...uploadItems.value];
  let pendingCount = getPendingUploadItems().length;
  let pendingTotalSize = getTotalUploadSize(getPendingUploadItems());

  files.forEach(file => {
    if (!isSupportedFile(file)) {
      selectionResult.unsupportedCount += 1;
      return;
    }

    const nextItem = createUploadItem(file);
    if (existingIds.has(nextItem.id)) {
      selectionResult.duplicateCount += 1;
      return;
    }

    if (maxSingleFileSizeBytes > 0 && nextItem.fileSize > maxSingleFileSizeBytes) {
      selectionResult.singleFileLimitCount += 1;
      return;
    }

    if (maxQueueSize > 0 && pendingCount >= maxQueueSize) {
      selectionResult.queueLimitCount += 1;
      return;
    }

    if (maxTotalSizeBytes > 0 && pendingTotalSize + nextItem.fileSize > maxTotalSizeBytes) {
      selectionResult.totalSizeLimitCount += 1;
      return;
    }

    existingIds.add(nextItem.id);
    nextItems.push(nextItem);
    pendingCount += 1;
    pendingTotalSize += nextItem.fileSize;
    selectionResult.addedCount += 1;
  });

  uploadItems.value = nextItems;
  return selectionResult;
}

function handleFileInputChange(event) {
  const selectionResult = appendUploadFiles(Array.from(event?.target?.files || []));
  clearNativeInput(event?.target);
  notifySelectionResult(selectionResult);
}

function handleDirectoryInputChange(event) {
  const selectionResult = appendUploadFiles(Array.from(event?.target?.files || []));
  clearNativeInput(event?.target);
  notifySelectionResult(selectionResult);
}

function openFileSelector() {
  fileInputRef.value?.click();
}

function openDirectorySelector() {
  directoryInputRef.value?.click();
}

function clearUploadItems() {
  if (uploading.value) {
    return;
  }
  uploadItems.value = [];
  clearNativeInput(fileInputRef.value);
  clearNativeInput(directoryInputRef.value);
}

function removeUploadItem(item) {
  if (uploading.value && item?.status === "uploading") {
    proxy.$modal.msgWarning("当前文件正在上传，暂时不能移除");
    return;
  }
  uploadItems.value = uploadItems.value.filter(currentItem => currentItem.id !== item.id);
}

function getUploadStatusText(status) {
  return UPLOAD_STATUS_MAP[status]?.text || "未知";
}

function getUploadStatusType(status) {
  return UPLOAD_STATUS_MAP[status]?.type || "info";
}

function formatUploadItemName(item) {
  return item.relativePath || item.fileName || "未命名文件";
}

function buildUploadSummary(successFiles, failedFiles) {
  const lines = [];
  if (successFiles.length) {
    const previewNames = successFiles.slice(0, 5);
    const suffix = successFiles.length > previewNames.length ? ` 等，共 ${successFiles.length} 个文件` : "";
    lines.push(`成功 ${successFiles.length} 个：${previewNames.join("、")}${suffix}`);
  }
  if (failedFiles.length) {
    lines.push(`失败 ${failedFiles.length} 个：`);
    failedFiles.slice(0, 10).forEach(item => {
      lines.push(`${item.name}: ${item.message}`);
    });
    if (failedFiles.length > 10) {
      lines.push(`其余 ${failedFiles.length - 10} 个文件请在列表中查看`);
    }
  }
  return lines.join("\n");
}

async function submitUpload() {
  await loadUploadPolicy();

  const valid = await uploadRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }

  const pendingItems = getPendingUploadItems();
  if (!pendingItems.length) {
    proxy.$modal.msgWarning("没有可提交的上传任务");
    return;
  }

  const validationResult = validateUploadBatch(pendingItems);
  if (!validationResult.valid) {
    proxy.$modal.alertWarning(validationResult.message);
    return;
  }

  uploading.value = true;
  const successFiles = [];
  const failedFiles = [];
  const concurrency = Math.min(normalizeConcurrency(uploadPolicy.submitConcurrency), pendingItems.length);
  let currentIndex = 0;

  const runWorker = async () => {
    while (currentIndex < pendingItems.length) {
      const taskIndex = currentIndex;
      currentIndex += 1;
      const item = pendingItems[taskIndex];
      item.status = "uploading";
      item.message = "上传中，等待服务器响应";

      try {
        const response = await uploadDocument(uploadForm.value.kbId, item.file);
        item.status = "success";
        item.message = response?.msg || "上传成功，已进入解析队列";
        successFiles.push(formatUploadItemName(item));
      } catch (error) {
        item.status = "error";
        item.message = error?.message || "上传失败";
        failedFiles.push({
          name: formatUploadItemName(item),
          message: item.message
        });
      }
    }
  };

  try {
    await Promise.all(Array.from({ length: concurrency }, () => runWorker()));
    if (successFiles.length) {
      await getList();
    }

    if (!failedFiles.length) {
      proxy.$modal.msgSuccess(`已提交 ${successFiles.length} 个文件，系统会按队列顺序解析`);
      uploadOpen.value = false;
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

.upload-panel {
  width: 100%;
}

.upload-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.upload-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.upload-toolbar-tip {
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary);
}

.upload-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.native-upload-input {
  display: none;
}

.path-text {
  color: var(--el-text-color-secondary);
}
</style>
