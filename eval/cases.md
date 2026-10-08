# Eval：回归用例

渲染器确定性输出：同一输入永远得到同一 HTML。改了 `scripts/render.py` 或 `assets/themes.json` 就跑全套。

## 用例

| 输入 | 主题 | 覆盖 |
|---|---|---|
| `skills.md` | paper | lead、h3、无序/有序列表、quote、Peak、署名 |
| `letter.md` | letter | TOC、实图、待补位、note、quote、转场、暖底 Peak |
| `ink.md` | ink | TOC、表格、代码块、引文出处、深色 Peak、图章转场、结语变体 |

图片 `images/station.jpg` 来源 Pexels（ID 29183512，免版税），已下载到本地，不引用外链。

## 跑法

```bash
cd eval
mkdir -p /tmp/gzh-eval
for f in skills letter ink; do python3 ../scripts/render.py $f.md -o /tmp/gzh-eval/$f.html || exit 1; done
diff /tmp/gzh-eval/skills.html expected/skills_paper.html \
  && diff /tmp/gzh-eval/letter.html expected/letter_letter.html \
  && diff /tmp/gzh-eval/ink.html expected/ink_ink.html \
  && echo REGRESSION-PASS
```

期望：三次渲染 Gate 1/2 全 PASS（letter 报"待补位 1 处"是正常的）；diff 无差异。有差异时先判断是"预期的视觉改进"还是"回归"——前者更新 expected 并通读三篇预览，后者修代码。

## Gate 3 回归口径

每次更新 expected，必须通读三篇预览，按 `references/decide.md` 四问逐篇过，结论记在提交信息里。
