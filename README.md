# wechat-article-skill（v3）

判断驱动的公众号编辑设计智能：Markdown → 直接可用的公众号 HTML。

```bash
python3 scripts/render.py 文章.md                      # 输出 HTML + 手机预览 + Gate 1/2 报告
python3 scripts/extract_docx.py 文件.docx -o 文章.md   # Word 输入
python3 scripts/publish.py --help                      # 官方 API 建草稿/发布
```

详见 [SKILL.md](SKILL.md)。回归见 [eval/cases.md](eval/cases.md)。重构报告见 [CHANGELOG-v3.md](CHANGELOG-v3.md)。
