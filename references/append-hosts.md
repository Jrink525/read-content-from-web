# 并入现有页面：找宿主、按宿主写法追加

## 找宿主

```bash
grep -rh '^title:' --include='*.md' . | grep -Ei '<中文主题词>|<英文关键词>'
grep -ril '<英文关键词>' --include='*.md' programming ai-tools | head -20
grep -n '^## ' <best-candidate>.md | tail -20
```

Pick the page whose structure already matches the incoming material — same language, same 「错误做法 → 正确做法」 or before/after pattern, existing numbered sections — and name the page and the reason in the reply.

## 通用合并规则

- Append as the next numbered top-level section and add it to the page's 目录; follow the host's heading style instead of importing the standalone skeleton.
- Extend frontmatter instead of replacing it: add the new topic tags, append the new source to `authors`, add `related: [<url>]`, keep the original `source`.
- Drop what the host already covers; keep host numbering and anchors intact so existing links survive.
- After appending, run `git diff --stat <page>` and confirm the change is insertions only apart from the header lines you edited. Do not judge survival by the `len()` your write script prints: it counts characters, so on a Chinese page it reads far below `wc -c` and looks like the file shrank.
- Run `python3 scripts/wiki_lint.py --moc`, then commit only the edited page; the diff is one file plus the regenerated MOC.

## 宿主是题库（面试题、高频题、题库）

When the incoming material is another source's question list, keep the source's own numbers instead of continuing the host's count: one `## 附录：<来源> 的 N 道<题>（<日期>）` section naming the source URL and author, then `### N. <原题>` underneath. Fusing the two numberings erases which questions came from which source.

Update any count the host's H1 states once the appendix changes the total, and add the incoming topic tags beside the existing ones.

## 宿主是「我的编码经验文档」

「记录到我的编码经验文档」指 `notes/coding-agent-toolkit.md`（AI Coding 工具与 Skill 积累清单），不建新页。按现有节的样子追加：

- 标题用 `## 来源：<作者>《<标题>》（<YYYY-MM-DD>）`，下面三行写推文 URL、作者、背景一句话。
- 原文自己的分组和编号原样保留；作者把同一个编号写了两遍就照抄并在节里说明该编号重复，不要重编，否则读者无法与原文对照。
- 加 `### 我的提炼（N 条，非原文）` 写跨条目的那条判断，再加 `### 与本清单其他来源的呼应` 点名先前各节及其与本来源的共同点。
- 插在 `## 相关阅读` 之前，用 `git diff --stat` 确认只有新增。
- 用 `git add notes/coding-agent-toolkit.md` 后提交推送：知识库提交脚本不碰 `notes/`。

## 宿主是长文知识页

当宿主是同一主题的知识页而非题库时，只补宿主缺的机制与数字，不改写已有节；新节标题用宿主已有的层级（`##` 与 `###`）而不是另起一套。
