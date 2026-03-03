<template>
   <div class="app-container">
      <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
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
            <el-select v-model="queryParams.parseStatus" placeholder="请选择状态" clearable style="width: 200px">
               <el-option label="待解析" value="0" />
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
            >上传文档</el-button>
         </el-col>
         <el-col :span="1.5">
            <el-button
               type="danger"
               plain
               icon="Delete"
               :disabled="multiple"
               @click="handleDelete"
               v-hasPermi="['rag:doc:remove']"
            >删除</el-button>
         </el-col>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
      </el-row>

      <el-table v-loading="loading" :data="docList" @selection-change="handleSelectionChange">
         <el-table-column type="selection" width="55" align="center" />
         <el-table-column prop="fileName" label="文件名称" min-width="200" show-overflow-tooltip />
         <el-table-column prop="fileType" label="类型" width="80">
            <template #default="scope">
               <el-tag :type="scope.row.fileType === 'pdf' ? 'danger' : 'primary'">
                  {{ scope.row.fileType?.toUpperCase() }}
               </el-tag>
            </template>
         </el-table-column>
         <el-table-column prop="fileSize" label="大小" width="100">
            <template #default="scope">
               {{ formatFileSize(scope.row.fileSize) }}
            </template>
         </el-table-column>
         <el-table-column prop="chunkCount" label="切片数" width="80" />
         <el-table-column prop="parseStatus" label="解析状态" width="100">
            <template #default="scope">
               <el-tag :type="getParseStatusType(scope.row.parseStatus)">
                  {{ getParseStatusText(scope.row.parseStatus) }}
               </el-tag>
            </template>
         </el-table-column>
         <el-table-column label="上传时间" align="center" prop="createTime" width="180">
            <template #default="scope">
               <span>{{ parseTime(scope.row.createTime) }}</span>
            </template>
         </el-table-column>
         <el-table-column label="操作" align="center" class-name="small-padding fixed-width" width="180">
            <template #default="scope">
               <el-button link type="primary" icon="Refresh" @click="handleReparse(scope.row)" v-hasPermi="['rag:doc:edit']" v-if="scope.row.parseStatus !== '1'">重新解析</el-button>
               <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['rag:doc:remove']">删除</el-button>
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

      <el-dialog title="上传文档" v-model="uploadOpen" width="500px" append-to-body>
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
            <el-form-item label="文件" prop="file">
               <el-upload
                  ref="uploadFileRef"
                  :auto-upload="false"
                  :limit="1"
                  accept=".pdf,.docx"
                  :on-change="handleFileChange"
                  :on-exceed="handleExceed"
               >
                  <template #trigger>
                     <el-button type="primary">选择文件</el-button>
                  </template>
                  <template #tip>
                     <div class="el-upload__tip">仅支持 PDF、Word 文档</div>
                  </template>
               </el-upload>
            </el-form-item>
         </el-form>
         <template #footer>
            <div class="dialog-footer">
               <el-button type="primary" @click="submitUpload">确 定</el-button>
               <el-button @click="uploadOpen = false">取 消</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
</template>

<script setup name="Document">
import { listDocument, uploadDocument, delDocument, reparseDocument } from "@/api/rag/document";
import { listKnowledgeBase } from "@/api/rag/knowledgeBase";

const { proxy } = getCurrentInstance();

const docList = ref([]);
const kbOptions = ref([]);
const uploadOpen = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const total = ref(0);
const multiple = ref(true);
const selectedFiles = ref([]);
const uploadFile = ref(null);

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

function getList() {
  loading.value = true;
  listDocument(queryParams.value).then(response => {
    docList.value = response.data || [];
    total.value = docList.value.length;
    loading.value = false;
  });
}

function getKbList() {
  listKnowledgeBase({ status: '0' }).then(response => {
    kbOptions.value = response.data || [];
  });
}

function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

function handleSelectionChange(selection) {
  selectedFiles.value = selection;
  multiple.value = !selection.length;
}

function handleUpload() {
  uploadForm.value = { kbId: undefined };
  uploadFile.value = null;
  uploadOpen.value = true;
}

function handleFileChange(file) {
  uploadFile.value = file.raw;
}

function handleExceed() {
  proxy.$modal.msgWarning("只能上传一个文件");
}

function submitUpload() {
  proxy.$refs["uploadRef"].validate(valid => {
    if (valid) {
      if (!uploadFile.value) {
        proxy.$modal.msgWarning("请选择文件");
        return;
      }
      uploadDocument(uploadForm.value.kbId, uploadFile.value).then(response => {
        proxy.$modal.msgSuccess(response.msg || "上传成功");
        uploadOpen.value = false;
        getList();
      });
    }
  });
}

function handleReparse(row) {
  proxy.$modal.confirm('是否重新解析该文档?').then(function() {
    return reparseDocument(row.docId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("重新解析任务已提交");
  }).catch(() => {});
}

function handleDelete(row) {
  const docIds = row?.docId || selectedFiles.value.map(item => item.docId).join(',');
  proxy.$modal.confirm('是否确认删除选中的文档?').then(function() {
    return delDocument(docIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getParseStatusType(status) {
  const types = { '0': 'info', '1': 'warning', '2': 'success', '3': 'danger' };
  return types[status] || 'info';
}

function getParseStatusText(status) {
  const texts = { '0': '待解析', '1': '解析中', '2': '成功', '3': '失败' };
  return texts[status] || '未知';
}

getKbList();
getList();
</script>
