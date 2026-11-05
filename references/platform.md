# 公众号 HTML 的工程边界（按需读取）

设计判断与三级验收契约见 [`SKILL.md`](../SKILL.md)；本文件仅说明 `scripts/check.py` 与预览产物的工程边界。

- **封闭白名单门禁**：正文仅允许 `a/br/img/p/section/span/strong/table/tr/th/td` 与渲染器声明属性；超链接仅允许带合法主机名的 HTTP(S) URL；正文图片仅允许安全相对本地路径且须有非空 `alt`。
- **底色与出版口径**：每个主题在正文根节点写入 `background:<page>`，`page` 属于色彩角色并参与 WCAG AA 校验；可见文本先经 `scripts/typography.py` 改写，装饰性斜杠归一为 `·`，**直角引号 `「」『』` 原样保留**（把作者引号统一成弯引号属于机械改写，且会动到直接引语内部）；直接引语内部、URL、代码、技术单位与数字比受保护；编辑说明整段移除并留痕。
- **内联 CSS 逐项校验**：同时校验属性名与属性值，拒绝未知声明、重复声明、URL/脚本注入、CSS 变量、定位、`grid`、事件属性、`class/id`、异常父子嵌套、空装饰节点与小于 `12px` 的字号。
- **字体栈按平台原生排列**：`SANS` 以 PingFang SC / 苹方起头，Android 侧依次补 HarmonyOS Sans SC、MiSans、Noto/Source Han Sans；`SERIF` 必须在 Android 也有中文候选（Noto Serif SC / Source Han Serif CN），否则 `letter`/`ink`/`bone` 的衬线标题会在安卓静默退化成无衬线。字体栈写在每个文本节点的内联样式里，不依赖客户端样式表。
- **输入保真**：TXT 字面段落不执行 Markdown；DOCX 输出 `.conversion.json`，合并单元格/文本框/脚注/含文字页眉页脚等有损结构阻断。转换 PASS 只证明已支持结构提取，不证明 Word 视觉复刻。
- **代码与窄屏表格保真**：代码块以 `p/span` 配合 `white-space:pre-wrap; overflow-wrap:break-word` 输出，保留缩进且不产生横向溢出（`anywhere` 会把每行切碎，只在长标识符处断词才成立）；320px 视口下无法满足每列最小可读宽度的表格自动降级为 `section + p` 记录卡，保留全部字段与顺序，不缩字硬塞。
- **图注来自 alt**：`证据/数据/资料/实拍` 职责整句印出；其余职责只在 ≥6 个汉字且不含制作标签时印出。图注是版面内容，不是内部备注，alt 写错会直接出现在读者眼前。
- **独立预览与发布正文隔离**：`*_预览.html` 中的顶栏、宽度与字体切换、复制按钮、封面双裁切面板、原生标题/作者模拟栏与底部操作栏模拟均在 `#c` 之外，复制正文或 API 发布时不会混入。预览页写入元数据一律走 `textContent` 与 `createElement`，**不得拼 `innerHTML`**——`cover_note` 等字段来自源稿，拼字符串等于给出一个 DOM XSS 入口。AI 冒充资料/实拍/证据/数据硬拦截、视觉叙事同质化预警仍在门禁；读者版面不印制作标签。复制优先 `navigator.clipboard.write`（同时写 `text/html` 与 `text/plain`），失败回退 `execCommand('copy')` 并还原选区。预览内嵌 Base64 仅用于本地离线审阅，`data-local` 保留相对路径供手动上传或 `publish.py` 自动替换为微信素材 URL。
- **交付一致性**：交付目录非空时仅接受本工具清单且所有文件哈希一致的既有交付；拒绝覆盖手改文件。清单最后写入，源稿/正文/预览/素材/修改记录/验收同目录可核对。
- **静态通过不等于真机通过**：`check.py` 是本 Skill 的保守输出契约，不代表微信客户端清洗器的完整行为。三级验收定义与 `UNVERIFIED`/`BLOCKED` 标注规则以 `SKILL.md` 为唯一真源。
