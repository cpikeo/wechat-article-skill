# 运行记录：in-session-v7（含首轮失败与修改，不做「一次就过」的包装）

- 协议与提示词：`prompts/edit.md`（版本 v7-eval-1）+ `prompts/type-*.md`，冻结在 `run.json` 的 `manifest_sha256`。
- 输入：`evaluation/cases/*.original.md`（仓库既有真实来源摘录，本次未改动）。
- 执行者：本会话的单一 agent，`temperature` 等采样参数**无法钉住**（已在 `run.json.declared_limits` 里写明）。
- 重复：每类 3 次，同一提示词、同一输入、独立重写。
- 性质：这是**会话内重复性实验**，不是独立实验室复跑；第三方可用同一 prompts 与输入复跑覆盖 `runs/`。

## 首轮（raw 输出，未做任何修改）

| 样本 | 首次 Gate 2 | 失败原因（机器原话） |
|---|---|---|
| business run-3 | FAIL | `data 缺少紧邻来源 note` |
| news run-2 | FAIL | `data 缺少紧邻来源 note` |
| profile run-1 | FAIL | `data 缺少紧邻来源 note` |
| tutorial run-2 | FAIL | `PROMISE-COUNT`：标题「三个参数」与可见结构不一致 |

这四条是**执行者的写作缺陷**，不是工具误报：

1. 三个 `::: data` 块下方没有紧跟 `::: note 来源与口径`，只在文末有一条完整来源。
   Skill 的规则是「来源要贴近证据」，文末脚注不算。已按规则补上紧邻来源。
2. tutorial run-2 的标题写「三个参数」，兑现位置是有序列表（3 项），
   但当时的数量承诺把「最长有序列表」当成唯一信号，而文中还有另一个 4 步自查列表。

## 因此产生的两处工具修正（有回归测试）

| 修正 | 原因 | 回归 |
|---|---|---|
| 数量承诺改为「显式编号标题 / 全部 H2 / **任意**有序列表」三者任一兑现 | 原实现固定取一个信号，且只取最长的有序列表，会把合法标题判成 must | `tests/v7.py` + `tests/run.py` 既有承诺用例 |
| `--against` 的事实变化分级：搬进 `data/bars` 块、只做年份概括 → 「建议改」；其余仍为「必须改」 | 「数值搬进块内、单位写在块标题」是排版决定，不是删事实；把它算成丢失会让编辑报告失真 | `tests/v7.py` 事实分级用例 |

## 内容修正（修正后重跑的是同一批文件，旧文本已覆盖）

| 样本 | 问题 | 修正 |
|---|---|---|
| news run-2 | 我把「2025年」加到原稿只有「7月2日」的日期上，等于**凭空补精度**；又写了只到日的「7月3日」，丢了年份 | 改用原稿讯头「【2025年7月3日讯】」，并保留「7月2日」原样 |
| news run-3 | 标题承诺「1.5万人」，正文只写「超过1.5万」 | 正文补成「超过1.5万人」 |
| profile run-1 | 我写了「（2026-11 访问）」——**访问日期是编造的**；data 块把「2015年10月5日」压成「2015」，丢了日月 | 删掉自造的访问日期，改为附来源链接；块内恢复「2011年9月」「2015年10月5日」 |

这些正是 `--against` 与标题承诺台账要抓的东西：新增必须回源，精度不得静默降级。

## 修正后的状态

- 18 篇全部 Gate 1/2 PASS（见 `REPORT.md` 逐篇明细）。
- 无源新增事实：0。
- 未兑现标题承诺：0。
- 仍有「搬进块内 / 精度概括」若干：它们是**待人工确认**项，不是通过项，见报告对应列。

## 已知未解决（本轮没有修，不当作通过）

| 现象 | 证据 | 为什么没修 |
|---|---|---|
| longform 三次重复都保留了 459 字的原段，超过「单段 ≤260 字」的建议 | 报告「最长段」列 459.00 ± 0.00 | 指令同时要求「不改原句」，两次重复都选择了保原段。分段不等于改句，但如何在公版散文里划线需要编辑判断，不适合写成硬规则。已在 `SKILL.md` 写明：长段按场景/动作节点分段，句子不动 |
| opinion 的「标明未知」0/3 | 报告 col「标明未知」 | 评论体裁不要求 unknown 块（只有新闻/分析要求）；指标仍按同一口径统计，读表时不要把它当失败 |
| 标题承诺里的量词变体（「1.5万人」vs「1.5万」）需要归一化比较 | 修正前 news run-3 误报 | 已修：比较时允许去掉末尾「人」；其他量词（元/年/倍）尚未穷举 |

## 复现

```bash
python3 tests/model_eval.py --manifest --run-dir evaluation/model-eval/runs/in-session-v7
python3 tests/model_eval.py --record --run-dir evaluation/model-eval/runs/in-session-v7 \
  --model "…" --temperature "…" --repeats 3
python3 tests/model_eval.py --report --run-dir evaluation/model-eval/runs/in-session-v7 \
  --out evaluation/model-eval/REPORT.md
# 盲评包（答案 key 单独存放，不入库）
python3 tests/model_eval.py --blind --run-dir evaluation/model-eval/runs/in-session-v7 \
  --out evaluation/model-eval/x --key /tmp/wechat-blind-key.json
```

## 第三轮：验收自身的自我印证

第一轮修的是稿子，第二轮修的是工具；这一轮修的是**验收方法**。

我按规则表写的那份 AI 腔负例（`tests/v7.py` 的 `SLOP`）全绿，并不能说明「AI 腔能被抓到」——它只说明「按规则写的东西会被规则抓到」。于是不看规则、只按常见 AI 文风另写一段（套语开头、「首先/其次/再次/最后」、「让我们一起努力，一起成长」、「总之，需要持续投入、持续优化、持续改进」），`prose_clues()` 命中 **0** 条。

新增三条线索后（`PROSE-ORDINAL` / `PARALLEL-HEAD` / `HOLLOW-CLOSE`）该样稿命中 3 条；同时用 18 篇评估稿 + 六组案例做反向检查，新增命中 **0**。这条反向检查现在是常驻用例（`_style_hits_in_corpus()`），
今后任何「只对自造负例有效」的规则都会在真实语料上暴露。

方法上的结论：**负例的写法必须独立于规则表**，否则回归只能证明规则自洽，不能证明它有判别力。
