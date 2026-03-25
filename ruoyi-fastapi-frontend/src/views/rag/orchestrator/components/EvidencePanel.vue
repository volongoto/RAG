<template>
  <el-card class="evidence-panel" shadow="hover">
    <template #header>
      <div class="evidence-header">
        <span>{{ title }}</span>
        <el-tag size="small" effect="plain">{{ citations.length }} 条</el-tag>
      </div>
    </template>

    <el-empty v-if="citations.length === 0" description="暂无证据片段" :image-size="72" />

    <el-collapse v-else v-model="activeItems">
      <el-collapse-item
        v-for="(item, index) in citations"
        :key="item.chunkId || item.chunk_id || `${index}`"
        :name="`${index}`"
      >
        <template #title>
          <div class="evidence-title">
            <el-tag size="small" type="primary">证据 {{ index + 1 }}</el-tag>
            <span class="evidence-name">{{ item.fileName || item.docName || '未命名文档' }}</span>
            <span v-if="item.page || item.pageNum" class="evidence-page">页码 {{ item.page || item.pageNum }}</span>
            <el-tag size="small" type="success" effect="light">
              {{ formatScore(item.retrievalScore || item.similarity) }}
            </el-tag>
          </div>
        </template>
        <div class="evidence-content">{{ item.snippet || item.content }}</div>
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>

<script setup name="EvidencePanel">
const props = defineProps({
  citations: {
    type: Array,
    default: () => []
  },
  title: {
    type: String,
    default: '证据片段'
  }
})

const activeItems = ref(['0'])

watch(
  () => props.citations,
  (value) => {
    activeItems.value = value?.length ? ['0'] : []
  },
  { immediate: true, deep: true }
)

function formatScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '无分数'
  }
  return `相似度 ${(Number(value) * 100).toFixed(1)}%`
}
</script>

<style scoped>
.evidence-panel {
  margin-top: 20px;
}

.evidence-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.evidence-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.evidence-name {
  font-weight: 600;
  color: #303133;
}

.evidence-page {
  color: #909399;
  font-size: 12px;
}

.evidence-content {
  padding: 12px;
  border-radius: 10px;
  background: #f7fafc;
  color: #303133;
  line-height: 1.7;
  white-space: pre-wrap;
}
</style>
