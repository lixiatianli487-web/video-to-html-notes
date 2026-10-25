---
name: video-to-html-notes
description: 按三个独立流程将教学视频制作成完整图文讲义：链接获取视频与字幕；视频与字幕整理为 Markdown；Markdown 导出 HTML／PDF。支持 B 站平台字幕或本地 Whisper 转写获取材料，以及离线 HTML、PDF 导出。
---

# 视频图文讲义：三个流程

严格区分以下三个流程，不将内容整理与格式导出混为一体。

```text
流程一：视频链接 → 本地视频 + 带时间字幕
         ├─ B 站有自带字幕：已实现
         └─ B 站无自带字幕：本地 Whisper 转写
流程二：本地视频 + 带时间字幕 → 图文讲义.md + 对应截图
流程三：图文讲义.md + 对应截图 → HTML／PDF（已实现）
```

## 流程一：根据链接获取视频和字幕

读取 [材料获取](references/01-acquire.md)，先判断平台是否提供字幕，再进入对应分支。

- [B 站有自带字幕](references/01-bilibili-subtitled.md)：复用已验证的下载视频、通过登录浏览器获取字幕地址、保存字幕的流程。平台 AI 字幕也属于此分支。
- [B 站无自带字幕](references/01-bilibili-no-subtitles.md)：复用视频下载，使用本地 faster-whisper 连续转写，保存识别来源和时间轴；按[疑点复核与讲解点覆盖](references/quality-review.md)集中复核候选，再接入流程二。

其他平台的获取方式尚待研究，不套用 B 站接口。已有本地视频与带时间字幕时，直接从流程二开始。

## 流程二：用视频和字幕写出 Markdown 讲义

读取 [完整图文 Markdown 讲义](references/02-write-markdown.md)。正式成果为 `图文讲义.md` 和截图，先完成正文再导出。

完整覆盖视频内容：不补充视频外的解释，不概括压缩，不省略例子和推导步骤。按原顺序整理全文，结合声音与画面校正字幕，按讲解需要插入截图。用[疑点复核与讲解点覆盖](references/quality-review.md)将源内容落实到具体讲解点、正文引文和画面依据；编号齐全不等于语义正确。

正文按“小节标题＋时间范围＋完整讲解＋对应截图”排列。标题只帮助阅读，不另外添加总结、延伸阅读或练习题。不能跳过 Markdown，直接把字幕塞进 HTML；不能用排版成功替代内容检查。

## 流程三：从 Markdown 导出阅读格式

读取 [格式导出](references/03-export.md)。以流程二完成的 `图文讲义.md` 为唯一正文来源，不重新解释、删改或补写内容。

- HTML 已实现：沿用认可的样式，时间保留为普通文字。LaTeX 风格公式支持离线显示，独立公式自然居中、字号贴近正文，无底色、边框、圆角或卡片。
- PDF 已实现：从同一 Markdown（或用户指定的技能 HTML）离线导出，使用独立打印样式，保留全文、截图、公式与章节书签；渲染页面做视觉验收。

## 共同约定

- 每个视频使用独立目录，已有任务复用材料，不重复下载。
- 原始字幕不覆盖；校正稿、正文与校对记录分开保存。原片疑义标记保留，不猜测或悄悄补写证明。
- 时间可保留，不添加时间跳转链接；文首可保留一次来源链接。
- 凭证不写入项目、讲义、日志或技能；优先复用已登录浏览器。下载工具不能解密 Cookie 不等于浏览器未登录。
- 只执行用户要求的流程。只取材料就止于流程一；只写 Markdown 就止于流程二。尚未实现的接口如实说明。

## 辅助资源

- 流程一：`scripts/normalize_bilibili_subtitles.py` 规范化平台字幕；`scripts/transcribe_local.py` 将本地音视频转为同一规范时间轴，并保留 ASR 原稿、词级时间及来源。
- 质量检查：`scripts/review_asr.py` 定位疑点并合并含前后文片段；`scripts/recheck_asr.py` 仅复核选中窗口，保留绝对时间与两版结果。
- 流程二：Agent 理解、核对并撰写 Markdown；`scripts/check_coverage.py` 校验讲解点的源编号、正文引文和画面记录，不判定语义正确，不以中间 JSON 替代正式讲义。
- 流程三：`scripts/render_html.py` 读取 Markdown 导出 HTML；`scripts/typeset_html.py` 和随附 KaTeX 处理公式，`assets/lecture.css` 控制阅读样式；`scripts/render_pdf.py` 与 `assets/lecture-print.css` 负责独立 PDF 导出与分页检查。

获取、规范化与 HTML 导出的主要脚本使用标准库；本地转写需 faster-whisper 及兼容 PyAV，PDF 排版需 WeasyPrint、Pango 和中文字体，分别见对应分支。公式排版还需 Node.js。KaTeX 与字体已随附，不需要 CDN 或 npm 安装。
