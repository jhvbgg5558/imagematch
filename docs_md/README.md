# imagematch Markdown 文档入口

当前项目已切换到新的工程化任务口径。

当前主任务是：

- 目标不变：论证基于遥感正射影像，能否实现对无人机影像的初步地理定位（检索）
- 新输入定义：query 是任意单张无人机影像
- query 不带地理信息
- query 不保证为正射影像
- 不再依赖旧任务中的同尺度裁块、query 中心点真值、统一外部分辨率预处理

重要说明：

- 旧任务资料已归档到 `../old/`
- 旧脚本、旧输出、旧方案、旧对话、旧预处理结果均不再作为当前任务依据
- 当前正式结果为空，需要按新任务重新建立数据链路和验证链路

建议阅读顺序：

1. [PROJECT_PROGRESS.md](./PROJECT_PROGRESS.md)
2. [EXPERIMENT_PROTOCOL.md](./EXPERIMENT_PROTOCOL.md)
3. [DATA_ASSETS.md](./DATA_ASSETS.md)
4. [RESULTS_INDEX.md](./RESULTS_INDEX.md)
5. [CODE_STYLE.md](./CODE_STYLE.md)
6. [knowledge_graph/README.md](./knowledge_graph/README.md)

## Knowledge Graph Wiki

`docs_md/knowledge_graph/` 是当前项目的 Markdown 知识图谱层。它借鉴 Karpathy LLM Wiki 思路：现有 `docs_md/*.md` 仍是 source-of-truth，知识图谱目录只做结构化编译、互链索引和维护入口，不作为新的实验结论来源。
