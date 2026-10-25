# 疑点复核与讲解点覆盖

在本地 ASR 后定位疑点；在完成 Markdown 前后核对内容。三个脚本都不自动改写转写或正文，不把模型一致、编号齐全或引文存在当作语义正确。

## 1. 把 ASR 疑点集中为复核片段

```bash
python3 SKILL_DIR/scripts/review_asr.py '识别原稿/字幕-ASR原始.json' \
  --output-dir '质量复核' --duration 实际视频秒数 --terms '术语表.json'
```

输入也可用规范字幕，但缺少的置信/词概率检查必须在输出说明。术语表可省略；格式为 `[{'canonical':'正确写法','variants':['已知可疑写法']}]` 的标准 JSON（使用双引号）。术语须来自画面、已确认的课程主题或用户材料，不凭模型猜出“正确词”。

输出“复核候选.json”“待核对清单.md”。扫描低 avg_logprob、高 no_speech_prob、低词概率、过短/过长分段、相邻重复、时间重叠/空隙、显式术语变体。阈值仅用于筛选：例如 avg_logprob < -0.8、词概率 < 0.45、短于 0.3 秒、空隙长于 4 秒；不是准确率、置信区间或删句标准。未命中不代表无错，正常停顿也可能命中。

数字、否定和限制词另列 critical_tokens，做正文核对时检查其含义与顺序。不能只因正常句含数字就认定 ASR 有错，也不能忽略“不是”“只有”“除外”等改变论断的词。

候选按时间合并，默认前后各保留 8 秒。复核时优先处理残片/术语/关键数值，再看普通低置信词和空隙。严重长空隙会标 requires_manual_scope，先明确范围，不为此自动转写数十分钟。

需要第二模型时，明确选窗口与预算：

```bash
PYTHON SKILL_DIR/scripts/recheck_asr.py '原视频.mp4' \
  --queue '质量复核/复核候选.json' --window W001 --window W006 \
  --output '质量复核/medium-片段复核.json' \
  --download-root '模型缓存目录' --language en --model medium
```

可重复 --window。默认只读本地模型，不联网；只有需下载时显式 --allow-download。默认复核音频总预算 180 秒，可按任务调整 --max-audio-seconds。分段恢复到原视频绝对时间，包含词时间；原始转写不动。不要并发加载多个大模型。

比较时只裁决候选核心位置，窗口边缘可能截句。用声音或原图处理数字、否定、专名、漏句和模型分歧；没有对应听音能力就保留 pending，不能把第二模型改成真值。生成独立“复核裁决.json”，每项包含 issue_id、status（pending / resolved_by_frame / resolved_by_audio / unresolved）、依据路径/画面时间或听音区间、原文、建议文字。模型比较记录只能作为辅助依据；不自动批量替换原稿。

## 2. 从具体讲解点核对正文

先读源字幕及关键画面，列出讲解点，再核对正文，避免从已写正文反推一个“肯定通过”的清单。尤其拆开示例中的加载、覆盖、计算、保存和恢复等不同步骤；保留假设、限制、否定、数字、单位、顺序和因果。赞助、转场及结尾也不能无记录删除。

使用“讲解点覆盖.json”，而非仅记录“第几段属于第几章”：

```json
{
  "schema_version": 1,
  "source_sha256": "实际源字幕文件的SHA256",
  "content_units": [{
    "id": "U001",
    "source_ids": [48, 49],
    "point": "第一条将12装入R0，计数为一条指令",
    "note_evidence": [{"quote": "正文中实际承载该步骤的完整句子"}],
    "review_status": "text_checked",
    "review_basis": "原语文字和中文句子对照；未听音"
  }],
  "visual_units": [{
    "id": "V001",
    "image": "图片/04-26.jpg",
    "point": "R0=12、R1=20的中间状态",
    "note_evidence": [{"quote": "正文中解释此中间状态的句子"}],
    "review_status": "preview_checked"
  }],
  "exclusions": []
}
```

上例只说明结构，不是可直接用于项目的内容；引文必须原样存在于真实正文，不能引用标题、时间或图注代替解释。一个讲解点可跨多个字幕或引用多句。画面独有的信息单列 visual_units，例如完整代码序列、地址、字段、图例、构造中间态，不只重复截图标题。源语与译文不同，语义由 Agent 理解核对，脚本不做跨语言正确性判断。

text_checked 只代表文字对照；audio_checked 需要 audio_review_note 记录真实听音依据。pending 不自动升级。画面状态区分 detail_checked、preview_checked、pending；缩略图不能标原图细节已查。残片排除必须给 source_ids、reason、status；无把握时用 provisional 并保留待核对，确认排除时才用 confirmed_exclusion。

```bash
python3 SKILL_DIR/scripts/check_coverage.py \
  --source '识别原稿/字幕-规范.json' --markdown '图文讲义.md' \
  --ledger '质量复核/讲解点覆盖.json' --output '质量复核/覆盖检查.json'
```

脚本校验源文件指纹、源编号是否遗漏/矛盾、正文引文是否仍存在、图片是否存在及每张图有无检查记录，并解析引文当前行号。删掉示例步骤、改动证据中的数字或否定、只映射章节、遗漏图片，会使旧证据失效；更新正文后必须重新检查、重新判断语义，而非只更新引文让检查通过。

默认只检查结构，仍列 pending_items；如需自动流程等待全部已声明范围完成，使用 --require-reviewed。无论退出码如何，semantic_accuracy_certified 和 audio_accuracy_certified 都不会自动变为 true。交付时明确文字对照、画面检查和听音各完成到哪里。
