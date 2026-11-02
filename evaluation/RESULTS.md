# Editorial Evaluation Results · V5

- 数据集指纹：`b6e79758a487ed103bbe00b28210a129a0c3703838deb6880b9080c99596b4b9`
- 样本：6 篇真实已发布来源摘录／翻译，覆盖商业分析、新闻报道、技术教程、人物故事、观点评论、深度长文
- 方法：原稿／优化稿对照；逐项修改台账；保留项与删除项检查；同输入重复渲染与诊断；可分离 key 的 A/B 盲测包
- 评价口径：只列可观察证据，不使用未经校准的主观分数

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

## 盲测与真实性边界

- A/B 文件名和映射可由 `tests/editorial_eval.py --blind-dir … --key-file …` 生成；key 必须与稿件分目录保存。
- **独立外部读者盲选：未执行。** 仓库不能把同一团队的自评冒充独立偏好结论。
- **来源在线可用性与逐项事实复核：本次 CI 未联网执行。** 每篇保留来源、日期／更新状态和许可；这不等于事实已由第二来源核真。
- **微信真实账号：未验证。** 本报告不覆盖草稿 API 回读、后台重开、手机端样式、图片或封面裁切。

## 复现

```bash
python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md
python3 tests/editorial_eval.py --blind-dir /tmp/wechat-blind --key-file /tmp/wechat-key.json --seed reviewer-01
```
