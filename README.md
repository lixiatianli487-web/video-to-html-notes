# 视频图文讲义 · video-to-html-notes

把教学视频整理成完整覆盖原内容的图文讲义。内容按原视频顺序保留，不补充视频外的解释、不概括压缩，也不省略例子和推导步骤。

本仓库是一套可复用的 Agent 技能与辅助脚本，不是一条命令自动理解并写完讲义的软件。内容理解、截图选择和语义核对由 Agent 完成。

## 三个独立流程

```text
1. 视频链接 → 本地视频 + 带时间字幕
   ├─ B 站平台字幕：下载视频并获取字幕
   └─ 无平台字幕：本地 faster-whisper 转写、疑点定位与复核
2. 本地视频 + 字幕 → 图文讲义.md + 对应截图
3. 图文讲义.md + 截图 → 离线 HTML / PDF
```

其他平台的视频获取方式尚待研究；已经提供本地视频与字幕时，可以直接使用后两个流程。

## 使用

将仓库完整保存为技能目录，保持 `SKILL.md`、`scripts/`、`references/` 和 `assets/` 的相对位置。例如：

```bash
git clone https://github.com/lixiatianli487-web/video-to-html-notes.git ~/.codex/skills/video-to-html-notes
```

目标目录已存在时，先保留本地修改，不直接覆盖。

向 Agent 提出：

> 使用 $video-to-html-notes 把这个视频整理成完整图文讲义，先获取材料，再写 Markdown，最后导出 HTML。

也可以只要求其中一个流程。入口与详细规范见 [SKILL.md](SKILL.md)。

## 输出与依赖

- Markdown：完整正文、时间范围、相对路径截图。时间为普通文字，不附跳转链接。
- HTML：离线公式与内嵌字体、LaTeX 风格数学排版；默认图片仍在独立目录，传到其他设备时需一起携带。
- PDF：独立文件，包含图片与字体；按实际渲染页面检查分页。
- 校对材料：保留识别原稿、疑点记录和讲解点覆盖依据，不把编号齐全当作语义正确。

依赖按流程准备，无需一次安装全部：

| 用途 | 依赖 |
| --- | --- |
| 视频下载与截图 | yt-dlp、FFmpeg / ffprobe |
| 字幕规范化与质量检查 | Python 3 标准库 |
| 无平台字幕时本地转写 | faster-whisper、兼容的 PyAV；模型首次下载需联网 |
| HTML 数学公式 | Node.js；仓库随附 KaTeX 与 WOFF2 字体 |
| PDF 导出 | WeasyPrint、Pango、中文字体 |

已验证的版本与具体命令写在对应 [references](references/) 中。模型缓存、登录凭证和系统依赖不随仓库分发。

## 检查

```bash
python3 -m unittest discover -s tests -v
```

缺少 WeasyPrint 时，实际 PDF 渲染测试会跳过。自动检查不能替代讲义内容核对与 PDF 视觉检查。

## 第三方资源

`assets/katex/` 包含 KaTeX 及其字体，许可证保留于 [assets/katex/LICENSE](assets/katex/LICENSE)。

仓库只包含技能、脚本、测试与排版资源，不包含视频、完整课程字幕、个人讲义、Cookie 或模型文件。
