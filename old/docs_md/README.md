# imagematch Markdown 文档入口

这个目录用于集中管理项目中长期有效、适合频繁查阅的 Markdown 文档。

当前项目主线是：

- 任务：基于遥感正射影像，实现对无人机影像的初步地理定位（检索）
- 当前正式实验口径：`200m query vs 200m satellite`
- 当前正式最优方案：`DINOv2 + FAISS` 粗检索 + `SuperPoint + LightGlue` 融合重排

建议阅读顺序：

1. [PROJECT_PROGRESS.md](./PROJECT_PROGRESS.md)
2. [EXPERIMENT_PROTOCOL.md](./EXPERIMENT_PROTOCOL.md)
3. [DATA_ASSETS.md](./DATA_ASSETS.md)
4. [RESULTS_INDEX.md](./RESULTS_INDEX.md)
5. [CODE_STYLE.md](./CODE_STYLE.md)
6. [REPORT_STYLE_GUIDE.md](./REPORT_STYLE_GUIDE.md)

常用目录：

- 项目脚本：`D:\aiproject\imagematch\scripts`
- 实验结果：`D:\aiproject\imagematch\output`
- 方案文档：`D:\aiproject\imagematch\方案`
- 历史对话/阶段日志：`D:\aiproject\imagematch\对话`

当前最重要的正式文档：

- `D:\aiproject\imagematch\方案\粗检索 + 局部几何验证重排\严格同尺度三方法对比实验结果解读_2026-03-17.docx`
- `D:\aiproject\imagematch\对话\严格同尺度跨视角定位实验进展与交接说明_2026-03-17.docx`
