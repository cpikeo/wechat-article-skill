# 真实来源编辑评估集

这套评估不训练渲染器，也不把审美换算成分数。它回答三个问题：改动能否追溯，事实／语气／限定是否保留，同一输入能否稳定复现。

## 样本与权利

|ID|类型|来源|文本权利与处理|
|---|---|---|---|
|business|商业分析|Our World in Data，*Do workers in richer countries work longer hours?*（2020-12-21，现已归档）|[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；仓库保存评估用中文摘译|
|news|新闻报道|中文维基新闻，微软裁员报道（2025-07-03）|[CC BY 4.0](https://zh.wikinews.org/wiki/Wikinews:版权信息)；保存评估摘录|
|tutorial|技术教程|Python 3 教程，`range()`|[PSF License Version 2](https://docs.python.org/zh-cn/3/license.html)；保存评估摘录|
|profile|人物故事|中文维基百科“屠呦呦”|[CC BY-SA 4.0](https://zh.wikipedia.org/wiki/Wikipedia:著作权信息)；摘录及其改编按同许可处理|
|opinion|观点评论|梁启超《最苦与最乐》，维基文库校对文本|[公有领域标记](https://zh.wikisource.org/zh-hans/最苦與最樂)；保存评估摘录|

许可页于 2026-11-02 逐项复核；具体证据说明与精确来源 URL 写入 `cases.json`。仓库 MIT 许可不重新许可这些第三方摘录；引用或再发布时须遵守各自条款。

## 对照方法

1. `*.original.md` 是已发布来源的摘录或标明的中文摘译，不伪装成完整原文。
2. `*.edited.md` 是面向公众号阅读场景的优化稿。每项改动在 `cases.json` 记录位置、问题、动作、可观察收益和保留条件；没有收益说明的改动会使评估失败。
3. `preserve` 同时出现在原稿和优化稿；`edited_require` 必须在优化稿可见；`edited_forbid` 不得残留。
4. 优化稿必须通过 Gate 1/2；相同输入重复渲染和编辑诊断必须得到相同结果。
5. `RESULTS.md` 由脚本生成并以数据集 SHA-256 防止报告与样本漂移。

```bash
python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md
```

## 盲测

生成 A/B 稿时，答案 key 必须放在另一个目录：

```bash
python3 tests/editorial_eval.py \
  --blind-dir /tmp/wechat-blind \
  --key-file /tmp/wechat-key.json \
  --seed reviewer-01
```

给读者的任务不是打“高级感分数”，而是逐项指出：

- 哪一版更快兑现标题；证据在何处；限制是否还在。
- 哪一版存在跳步、重复或事实／观点混写；引用具体段落。
- 哪项改动损失了事实、作者语气或限定条件。
- 两版都成立时可以判定“无需偏好”。

**当前仓库没有独立外部读者盲选结果。** 脚本验证的是盲测包、改动台账和确定性不变量，不能把同一团队的自评冒充独立结论。逐项外部核真、真实账号草稿和手机端验收也单独标为未执行。
