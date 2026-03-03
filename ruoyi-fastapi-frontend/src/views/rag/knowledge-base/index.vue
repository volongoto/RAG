<template>
   <div class="app-container">
      <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
         <el-form-item label="知识库名称" prop="kbName">
            <el-input
               v-model="queryParams.kbName"
               placeholder="请输入知识库名称"
               clearable
               style="width: 200px"
               @keyup.enter="handleQuery"
            />
         </el-form-item>
         <el-form-item label="知识库类型" prop="kbType">
            <el-select v-model="queryParams.kbType" placeholder="请选择类型" clearable style="width: 200px">
               <el-option label="部门知识库" value="dept" />
               <el-option label="个人知识库" value="personal" />
            </el-select>
         </el-form-item>
         <el-form-item label="状态" prop="status">
            <el-select v-model="queryParams.status" placeholder="请选择状态" clearable style="width: 200px">
               <el-option label="正常" value="0" />
               <el-option label="停用" value="1" />
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
               icon="Plus"
               @click="handleAdd"
               v-hasPermi="['rag:kb:add']"
            >新增</el-button>
         </el-col>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
      </el-row>

      <el-table v-loading="loading" :data="kbList">
         <el-table-column prop="kbName" label="知识库名称" min-width="200" />
         <el-table-column prop="kbType" label="类型" width="120">
            <template #default="scope">
               <el-tag :type="scope.row.kbType === 'dept' ? 'primary' : 'success'">
                  {{ scope.row.kbType === 'dept' ? '部门知识库' : '个人知识库' }}
               </el-tag>
            </template>
         </el-table-column>
         <el-table-column prop="embeddingModel" label="向量模型" width="150" />
         <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
               <el-tag :type="scope.row.status === '0' ? 'success' : 'danger'">
                  {{ scope.row.status === '0' ? '正常' : '停用' }}
               </el-tag>
            </template>
         </el-table-column>
         <el-table-column label="创建时间" align="center" prop="createTime" width="180">
            <template #default="scope">
               <span>{{ parseTime(scope.row.createTime) }}</span>
            </template>
         </el-table-column>
         <el-table-column label="操作" align="center" class-name="small-padding fixed-width" width="200">
            <template #default="scope">
               <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['rag:kb:edit']">修改</el-button>
               <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['rag:kb:remove']">删除</el-button>
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

      <el-dialog :title="title" v-model="open" width="500px" append-to-body>
         <el-form ref="kbRef" :model="form" :rules="rules" label-width="100px">
            <el-form-item label="知识库名称" prop="kbName">
               <el-input v-model="form.kbName" placeholder="请输入知识库名称" />
            </el-form-item>
            <el-form-item label="知识库类型" prop="kbType">
               <el-select v-model="form.kbType" placeholder="请选择类型" style="width: 100%">
                  <el-option label="部门知识库" value="dept" />
                  <el-option label="个人知识库" value="personal" />
               </el-select>
            </el-form-item>
            <el-form-item label="描述" prop="description">
               <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
            </el-form-item>
            <el-form-item label="向量模型" prop="embeddingModel">
               <el-input v-model="form.embeddingModel" placeholder="请输入向量模型" />
            </el-form-item>
            <el-form-item label="状态">
               <el-radio-group v-model="form.status">
                  <el-radio value="0">正常</el-radio>
                  <el-radio value="1">停用</el-radio>
               </el-radio-group>
            </el-form-item>
            <el-form-item label="备注" prop="remark">
               <el-input v-model="form.remark" type="textarea" placeholder="请输入备注" />
            </el-form-item>
         </el-form>
         <template #footer>
            <div class="dialog-footer">
               <el-button type="primary" @click="submitForm">确 定</el-button>
               <el-button @click="cancel">取 消</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
</template>

<script setup name="KnowledgeBase">
import { listKnowledgeBase, getKnowledgeBase, addKnowledgeBase, updateKnowledgeBase, delKnowledgeBase } from "@/api/rag/knowledgeBase";

const { proxy } = getCurrentInstance();

const kbList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const total = ref(0);

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    kbName: undefined,
    kbType: undefined,
    status: undefined
  },
  rules: {
    kbName: [{ required: true, message: "知识库名称不能为空", trigger: "blur" }],
    kbType: [{ required: true, message: "知识库类型不能为空", trigger: "change" }]
  },
});

const { queryParams, form, rules } = toRefs(data);

function getList() {
  loading.value = true;
  listKnowledgeBase(queryParams.value).then(response => {
    kbList.value = response.data || [];
    total.value = kbList.value.length;
    loading.value = false;
  });
}

function cancel() {
  open.value = false;
  reset();
}

function reset() {
  form.value = {
    kbId: undefined,
    kbName: undefined,
    kbType: undefined,
    description: undefined,
    embeddingModel: 'BAAI/bge-m3',
    status: "0",
    remark: undefined
  };
  proxy.resetForm("kbRef");
}

function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加知识库";
}

function handleUpdate(row) {
  reset();
  getKnowledgeBase(row.kbId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改知识库";
  });
}

function submitForm() {
  proxy.$refs["kbRef"].validate(valid => {
    if (valid) {
      if (form.value.kbId != undefined) {
        updateKnowledgeBase(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addKnowledgeBase(form.value).then(response => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    }
  });
}

function handleDelete(row) {
  proxy.$modal.confirm('是否确认删除名称为"' + row.kbName + '"的知识库?').then(function() {
    return delKnowledgeBase(row.kbId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

getList();
</script>
