# Editorial Evaluation Results · V6

- 数据集指纹：`b6e79758a487ed103bbe00b28210a129a0c3703838deb6880b9080c99596b4b9`
- 样本：6 篇真实来源摘录／翻译，覆盖商业分析、新闻报道、技术教程、人物故事、观点评论、深度长文
- 方法：原稿／优化稿字面与结构检查；逐项修改台账；保留项；Gate 1/2；同输入重复渲染；可分离 key 的 A/B 盲测包
- 评价口径：只列可观察证据，不将确定性检查包装成文笔分数
- 边界：此处为仓库中既有编辑样稿的回归，不是一次受控、可重复的真实模型生成实验

## 可复现结果

| 样本 | 类型 | 修改记录 | 保留不变量 | 正文字数（原→优化） | Gate 1/2 | 事实字面保留 | 台账 | 重复任务 |
|---|---|---:|---:|---:|---|---|---|---|
| business | 商业分析 | 2 | 6 | 429→534 | PASS | PASS | PASS | 一致 |
| news | 新闻报道 | 2 | 6 | 422→467 | PASS | PASS | PASS | 一致 |
| tutorial | 技术教程 | 2 | 5 | 385→495 | PASS | PASS | PASS | 一致 |
| profile | 人物故事 | 2 | 7 | 303→438 | PASS | PASS | PASS | 一致 |
| opinion | 观点评论 | 2 | 4 | 684→723 | PASS | PASS | PASS | 一致 |
| longform | 深度长文 | 1 | 5 | 1371→1371 | PASS | PASS | PASS | 一致 |

**确定性检查：PASS。**

## Browser visual evidence · 2026-11-02

- **PASS（浏览器回归，不是审美评分）**：`tests/visuals.py` 渲染 6 篇真实来源样稿 × 4 个宽度（320/360/390/430px）；正文不横向溢出、不拆数值原子，正文≥15px，表格/注释≥12px。六篇样稿无嵌图，素材加载断言为空；图片路径/上传边界另由回归覆盖。
- 同一篇商业分析稿在六主题、四宽度运行；390px 颜色中和后 15 对主题均仍有结构差异，平均像素差 0.05604–0.08943（仅作“换色后是否塌成相同结构”的回归线索，不是美学结论）。
- 详细浏览器报告与截图在执行时生成到 Git 忽略的 `evaluation/visual-review/`；不作为运行时依赖或微信兼容证据。

## 本轮审计与文件处置

| 发现与证据 | 处置 |
|---|---|
| README 链接指向仓库中不存在的 `AUDIT.md`；README/Skill 仍写 V5 | 修复链接，统一文档与运行时为 V6 |
| `evaluation/logs/*.log` 为旧运行输出/机器路径，不能证明当前状态 | 删除 5 个历史日志；截图与临时报告只生成到忽略目录 |
| 旧主题测试要求每个配置轴唯一，容易把差异数量当作设计质量 | 改为配置/可读性检查；另用真实稿去色截图核对结构差异 |
| 旧 `tests/visuals.py` 只看原稿/改稿的 320/390px，不测主题去色结构 | 改为六篇真实样稿四宽度 + 同稿六主题评估 |
| `render.py` 解析、组件、Gate 与交付共享同一契约 | 保持单体渲染器；没有为了模块数量拆分或加运行时依赖 |

## BLOCKED / UNVERIFIED

- **真实模型执行六类文章编辑与重复性评估：BLOCKED。** 当前环境没有可控模型 API/评估运行器；现有样稿不是本轮新生成的受控模型输出。
- **独立外部盲评：UNVERIFIED。** A/B 包可生成，但没有独立读者结果，不报告偏好胜负。
- **逐项第二来源事实核真：UNVERIFIED。** 字面比对不等于核真；来源页与许可备注不代表本轮逐条核对了事实。
- **微信真实账号、草稿后台、iOS/Android 真机与实际裁切：UNVERIFIED。** 本地浏览器不证明微信兼容。
- 六主题真实样稿/四宽度/去色结构截图由 `python3 tests/visuals.py` 单独执行，截图不是盲评结论；不提交截图产物。

## 复现

```bash
python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md
python3 tests/editorial_eval.py --blind-dir /tmp/wechat-blind --key-file /tmp/wechat-key.json --seed reviewer-01
python3 tests/visuals.py
```
