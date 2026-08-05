# 408 RAG 学习助手 · 任务交接摘要

> 本文件为当前交接摘要，历史版本可在 git 历史中查看。

## 一、当前目标
408 考研 AI 学习助手（自用 + AI 应用岗简历项目）：构建全链路 RAG + 可评测体系，后续做出题差异化与错题本闭环。当前链路已稳定，进入产品化与工程化阶段。

## 二、已经实现的功能

### RAG 全链路
- 查询改写（qwen2.5:1.5b）→ 混合检索（bge-m3 向量 + BM25 + RRF）→ rerank（bge-reranker-v2-m3 fp16）→ 门控降级 → 生成（qwen2.5:7b，流式）
- 默认配置：固定切块 800/150 + 混合检索 + rerank + 门控（阈值 0.5）
- 分级降级：检索置信度不足时回退纯模型回答并提示

### 前端（Vue3 + Element Plus）
- 四个页面：对话问答、知识库管理、AI 出题、系统状态
- 侧边栏可收起，主题三色切换，输入框宽度与对话框对齐
- AI 回答为纯文本流式输出（Markdown 渲染已回退，保持丝滑）
- 对话历史按会话持久化，保留最近 15 条

### AI 出题
- 从清洗题库随机选题，答案取自题库，出题与判题秒出
- 题库可用 1175 道四选项选择题（数据结构 373 / 操作系统 436 / 组成原理 223 / 网络 143）
- 操作系统 426 道缺失答案已由本地模型（带知识点检索接地）补齐并写回 md
- 答题校验、科目与题目状态 localStorage 持久化（切页不丢）

### 引用溯源
- 回答标注 [资料N]，与参考上下文编号对应
- 结构化引用含来源/页码/章节/原文摘要，前端点击 [资料N] 定位并高亮
- 模型未标注时后端自动补充"引用依据"行，保证溯源可用

### 评测体系（核心资产）
- 基准：80 题 → 200 题（四科各 50，120 道带知识点标签）
- 断点续跑、结果归档、多轮对比、200 题一键回归 + 自动报告
- 评测结论：混合检索四科全胜纯向量（回答质量 3.79→3.99）；语义切块未胜出（要点命中 0.797 < 0.821）；rerank+门控保留；chunk 800/150 最优
- 一键生成 DOCX 总评测报告

### 交付物
- start.bat 一键启动（自动拉起 Ollama + 后端 + 前端 + 打开浏览器）

## 三、关键文件路径
- 检索：`src/retriever.py`；切块：`src/parser.py`；配置：`src/config.py`；生成：`src/generator.py`
- 出题：`src/quiz_bank.py`、`backend/quiz_service.py`
- 后端：`backend/api.py`、`backend/service.py`、`backend/database.py`
- 前端：`frontend/src/views/ChatView.vue`、`QuizView.vue`、`App.vue`、`router.js`
- 评测：`evaluate.py`；脚本：`scripts/rebuild_kb.py`、`compare_eval.py`、`chunk_eval_runner.py`、`run_regression.py`、`build_benchmark.py`、`batch_judge_os.py`、`build_eval_docx.py`
- 结果：`results/eval_results_80_*.json`、`results/regression/`、`results/regression_report.md`、`docs/EVAL_REPORT.md`
- 数据：`data/clean_md/`、`data/eval_questions_80.json`、`data/eval_questions_200.json`
- 向量库：`storage/chroma`（默认 800/150）、`chroma_bak_recursive`、`chroma_s400`、`chroma_s1200`
- 启动：`start.bat`；评测总报告：`D:\desktop\408RAG评测结果\408RAG评测报告.docx`

## 四、现存 bug / 已知问题
1. **门控偶发误报**：个别超库题 reranker 高分但无关（如"活锁" os-20，0.687 高分未触发门控），靠生成端"上下文不足拒绝"规则兜底，不产生幻觉但得分为 1
2. **引用标注不稳定**：7B 模型按提示词自觉标注的比例约 1/3，其余靠后端兜底行（不影响可用性，影响行内溯源体验）
3. **Ollama 服务不稳定**：偶发断连，需重启；大批量嵌入必须分批（200/批 + 重试）
4. **embedding 冷加载慢**：单次查询约 3s（keep_alive=0），常驻可降至约 0.3s，需权衡显存
5. **评测轮次间存在正常方差**：共同 80 题回答质量均值差约 ±0.025，判断结论需看方向一致性而非单点数值
6. 历史限制：对话历史仅保留 15 条（有意的产品取舍）

## 五、下一步计划
1. **错题本 + 学习报告**（最高优先级）：错题归因到知识点、薄弱点统计、按艾宾浩斯安排复习题
2. **RAG 可观测性面板**：改写→检索→重排→门控每一步分数与命中的可视化
3. **评测基准持续化**：200 题 → 500+ 题、CI 自动回归、报告自动发布
4. **Docker 封装**：基础版约 1-2 天，含镜像瘦身/一键脚本约 2-4 天，普通人免安装分发约 4-7 天
5. **拍照搜题**：PaddleOCR 已具备，打通图片→识别→检索→作答
6. **引用 faithfulness 二次校验**（待讨论后实施）
7. **性能优化**：embedding 常驻、查询改写缓存
8. **开源包装**：README 重写（架构图/演示/评测数据）、开源题库数据集、在线 Demo、GitHub Actions
