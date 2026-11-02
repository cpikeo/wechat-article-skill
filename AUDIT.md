# V3.0.0 Release Audit

审计日期：2026-11-02（Asia/Shanghai）

基线：`07ed833592b3028bd5ef21b8b5a2fa8846f53a9a`

发布版本：`3.0.0`

人格集合：**恰好六个**——`paper`、`letter`、`ink`、`frost`、`bone`、`folio`

## 1. 结论

V3 把仓库从“Markdown 转内联样式 HTML”提升为一条仍保持单体、零运行时第三方依赖的 **Editorial Intelligence × Visual Design × WeChat Publishing** 流水线：先判断读者、场景、目标、主张、证据与限制，再决定构图、人格、素材和移动端节奏，最后才渲染与发布。

成熟能力没有被删减：Markdown／DOCX、资源路径安全、Gate 1／2／3、草稿默认、单次发布授权、素材复用、正文／来源／资源哈希与发布前完整性检查仍在。新增能力集中在可观察的编辑诊断、六套真实组件系统、中文移动排版、真实来源评估和配置—渲染器—样张一致性，没有引入框架或运行时依赖。

**发布判断：代码与本地浏览器证据通过；真实微信账号链路仍未验证，因此不能宣称“微信真机已通过”。**

## 2. 实际编辑评估

五组样本均为已发布来源的摘录／标明摘译；每项改动都记录位置、问题、动作、收益与保留条件。结果由 `tests/editorial_eval.py` 生成，完整证据见 [`evaluation/RESULTS.md`](evaluation/RESULTS.md)。

| 样本 | 类型 | 修改台账 | 保留不变量 | 正文字数（原→优化） | Gate 1/2 | 重复渲染／诊断 |
|---|---|---:|---:|---:|---|---|
| business | 商业分析 | 2 | 6 | 428→535 | PASS | 一致 |
| news | 新闻报道 | 2 | 6 | 421→461 | PASS | 一致 |
| tutorial | 技术教程 | 2 | 5 | 397→511 | PASS | 一致 |
| profile | 人物故事 | 2 | 7 | 302→437 | PASS | 一致 |
| opinion | 观点评论 | 2 | 4 | 683→722 | PASS | 一致 |

可分离答案 key 的 A/B 包已由自动化测试实际生成并检查；**独立外部读者尚未执行盲选**，所以没有伪造“优化版胜率”或主观分数。逐项外部事实核真同样未执行。

### 来源许可复核

2026-11-02 逐页复核并把证据 URL 与说明写入 `evaluation/cases.json`：

- Our World in Data：CC BY 4.0；原页明确已归档、停止更新。
- 中文维基新闻：2025-01-30 后文字为 CC BY 4.0；本样本发布于 2025-07-03。审计时纠正了早先写成 CC BY 2.5 的元数据。
- Python 文档：PSF License Version 2；3.8.6 起文档代码示例另可用 BSD-0。
- 中文维基百科：摘录改编按 CC BY-SA 4.0 处理。
- 维基文库《最苦与最乐》：作品页标记其在美国及作者终身加 80 年或更短期限地区属于公有领域。

许可复核只确认再利用条件，不等于对每条事实做了第二来源核真。

## 3. 六人格不是换色

同一篇商业分析优化稿的 390px 对照基线保存在 [`evaluation/visual/`](evaluation/visual/README.md)。完整四宽度证据由 Gate 3 生成并由 CI 上传。

| 人格 | 标题／章标 | 引文／重点 | 表格／信息 | 图片处理 | 空间节奏 |
|---|---|---|---|---|---|
| `paper` 静纸 | 小号索引章标、理性无衬线 | 短线与开放引文 | 开放表格、列式数据 | flush | 中等、基线清楚 |
| `letter` 暖信笺 | 无编号人声标题、较轻字重 | 无侧线 voice 引文、暖底重点 | 暖色表头、堆叠数据 | soft | 段间更松、转场柔和 |
| `ink` 酌墨 | 衬线标题、圆章编号 | 收束的深色反白重点 | 墨线表格、ledger 数据 | inkline | 书卷式、章节留白大 |
| `frost` 北霜 | `01 /` 报表章标、紧凑粗体 | 侧线报告式重点 | 冷色表头、ticker 数据 | report | 六套中最紧凑 |
| `bone` 素作 | 衬线 atelier 标题、无显式编号 | 台纸 lead、上下细线重点 | 规格线表格、specimen 数据 | mat | 六套中最舒展 |
| `folio` 特稿 | 大号红色编号、强标题 | 紧凑黑底反白 | 黑色表头、feature 数据 | folio | 强重心、特稿张力 |

配置中的 `lead/heading/h3/peak/divider/quote/image/data/table/list/type` 都进入真实组件分支；测试先去除颜色，再验证六套组件输出仍各不相同。`assets/themes.html` 带配置 SHA-256，必须可由当前 `themes.json + render.py` 精确再生成。

## 4. 四宽度视觉审阅

同稿六人格的 **320／360／390／430px 共 24 张全文图已逐张打开通读**；六张 390px 发布基线被保留。浏览器同时逐元素检查正文、图片、表格、表头和单元格边界，并验证复制后的正文与内联样式没有混入预览工具栏、脚本、base64 或本地标记。

结论：

- 四个宽度均无横向溢出；标题、正文、来源、章节转场和表格保持可读。
- 320px 初次通读发现四字表头出现“三字＋孤字”，近似数值“约2500小时／不足1600小时”会拆开单位。已改为先兑现短表头与数值单位的最小宽度，再把余量给长文本列；确实放不下的多列数值表由 Gate 2 阻断。修复后六人格四宽度全部重跑通过。
- `letter` 与 `bone` 较大的单元格内距曾暴露 2–3px 数值溢出；宽度模型现按六人格最大内距和真实 CJK 字体度量留余量，修复后通过。
- `paper` 层级克制清楚；`letter` 的人声和暖色场明显；`ink` 的衬线、圆章和墨色重点成立；`frost` 的报告节奏最紧；`bone` 的台纸与留白最舒展；`folio` 的红章标与黑色信息块最强。差异来自信息结构与字重／构件，不只是色彩。
- 真实商业稿判断为“无需插图”，所以六人格同稿图不伪造装饰图。六套图片处理在可再生主题样张中验证；comparison／sequence 的阅读顺序和去样式降级另有浏览器回归。
- 样稿未配置封面，预览明确显示缺口；没有把占位区当作真实封面裁切通过。

这些结论来自本地 Chromium + Noto Sans CJK 的模拟证据；微信客户端字体回退、后台清洗和真机截图仍是未验证项。

## 5. 测试账本

| 检查 | 结果 | 证据／边界 |
|---|---|---|
| `python3 -m py_compile scripts/*.py tests/*.py` | PASS | Python 语法 |
| `python3 tests/run.py` | PASS | 13 个回归章节；10 个 unittest；含安全、DOCX、平台、素材、配置、预检与发布保护 |
| `python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md` | PASS | 五类真实来源、台账、不变量、重复任务、报告指纹 |
| `python3 tests/run.py --shots --shoot examples/draft-handoff.md` | PASS | 320／360／390／430px、六人格同稿、组合构图、复制样式 |
| 配置—渲染器—样张一致性 | PASS | 六人格结构轴唯一；`themes.html` 精确可再生且摘要一致 |
| HTML 结构反例 | PASS | 错误嵌套、多余闭合、未闭合标签均会失败 |
| 发布完整性与授权 | PASS（模拟） | 旧渲染器、旧主题配置、改写正文／来源／资源、待补资源、持久发布授权、确认标题不符均被拒绝 |
| 页面级来源许可 | PASS（人工复核） | 许可 URL 与证据写入 `cases.json`；CI 不联网 |
| 独立外部读者 A/B | **UNVERIFIED** | 包与 key 机制已验证，尚未邀请独立读者 |
| 逐项第二来源事实核真 | **UNVERIFIED** | 保留来源和限制，不冒充外部核真 |
| 微信草稿 API 回读／后台重开 | **UNVERIFIED** | 无真实账号凭证与权限 |
| 微信 iOS／Android 真机、封面 2.35:1／1:1 | **UNVERIFIED** | Chromium 模拟不能替代真机 |

本地最终回归没有已知失败项。未验证项不计作通过。

## 6. 文件审计与简化

### 移动／删除旧路径

| 旧路径 | 新路径 | 原因 |
|---|---|---|
| `scripts/selftest.py` | `tests/run.py` | 开发回归不属于用户运行时；保留并扩展全部安全／发布保护，不以减文件为由删测试 |
| `scripts/fixtures.py` | `tests/fixtures.py` | 合成语料只服务开发测试；运行时目录不再混入 fixture 生成器 |

旧路径随重命名删除，没有保留转发壳或重复实现。

### 修改／新增

| 路径 | 处理与理由 |
|---|---|
| `SKILL.md` | V3 唯一判断入口：编辑 brief、论证审计、事实边界、改动台账、视觉概念、移动验收与发布边界 |
| `README.md` | 收敛为实际工作流、命令、目录和已验证／未验证边界 |
| `assets/themes.json` | 保持恰好六人格，增加真实组件与类型／节奏轴 |
| `assets/themes.html` | 由当前配置和渲染器重建的可展示样张；因可再生且有比较价值而保留 |
| `scripts/render.py` | 编辑诊断、六套组件、中文表格宽度、组合构图、决策侧车与配置摘要；复用 `safety.py` 的路径／哈希／对比度逻辑 |
| `scripts/check.py` | 增加错误嵌套、多余闭合和未闭合标签检查 |
| `scripts/publish.py` | 发布前校验渲染器版本、主题配置、来源、正文和资源；继续默认草稿与单次授权 |
| `tests/run.py` | 统一开发回归、四宽度浏览器证据、同稿六人格和真实评估入口 |
| `tests/editorial_eval.py` | 五类真实来源、元数据、台账、不变量、重复性、A/B key 分离与报告一致性 |
| `evaluation/` | 原稿／优化稿、来源许可、结果报告和六人格发布基线 |
| `.github/workflows/ci.yml` | 分开运行非浏览器回归与 Gate 3，并上传完整截图 artifact |
| `examples/draft-handoff.md` | 增加视觉概念、信息形态和移动风险交接字段 |
| `references/publish.md` | 记录 V3 完整性预检边界 |
| `AUDIT.md` | 本次发布的树、改动理由、证据和未验证项 |

### 重复逻辑结论

- `render.py` 与 `publish.py` 共用 `safety.py` 的 `local_path/sha256`；发布端直接读取渲染端导出的版本与主题摘要，不另造第二套主题解析。
- `tests/run.py` 复用真实 `render/publish/check` 入口；`tests/fixtures.py` 只生成语料和资源，不复制生产逻辑。
- 完整截图工作目录 `assets/shots/` 可重建且体积大，继续忽略；只保留六张有发布展示价值的 390px 基线。缓存与 `__pycache__` 不入库。
- 没有新增框架、包管理层或运行时第三方依赖；Playwright 只用于显式开发截图和 CI。

## 7. 完整发布树

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── AUDIT.md
├── LICENSE.txt
├── README.md
├── SKILL.md
├── assets/
│   ├── themes.html
│   └── themes.json
├── config.example.json
├── evaluation/
│   ├── README.md
│   ├── RESULTS.md
│   ├── cases.json
│   ├── cases/
│   │   ├── business.edited.md
│   │   ├── business.original.md
│   │   ├── news.edited.md
│   │   ├── news.original.md
│   │   ├── opinion.edited.md
│   │   ├── opinion.original.md
│   │   ├── profile.edited.md
│   │   ├── profile.original.md
│   │   ├── tutorial.edited.md
│   │   └── tutorial.original.md
│   └── visual/
│       ├── README.md
│       ├── personality_bone.png
│       ├── personality_folio.png
│       ├── personality_frost.png
│       ├── personality_ink.png
│       ├── personality_letter.png
│       └── personality_paper.png
├── examples/
│   └── draft-handoff.md
├── references/
│   ├── direction.md
│   ├── platform.md
│   └── publish.md
├── scripts/
│   ├── check.py
│   ├── extract_docx.py
│   ├── publish.py
│   ├── render.py
│   └── safety.py
└── tests/
    ├── editorial_eval.py
    ├── fixtures.py
    └── run.py
```

`assets/shots/`、`config.json`、素材缓存、发布审计日志与 Python 缓存是本地／CI 运行产物，不属于发布树。

## 8. 发布与回滚

- 版本号已在 `SKILL.md` 与运行时统一为 `3.0.0`。
- 发布提交应打注释标签 `v3.0.0`；提交与标签是否成功推送，以本次交付末尾的 Git 结果为准。
- 回滚基线是 `07ed833592b3028bd5ef21b8b5a2fa8846f53a9a`。
- 在真实账号验证前，不修改“微信真机未验证”的结论；首次账号验收应另存草稿回读、后台重开、iOS／Android、封面双裁切和正式发布授权记录。
