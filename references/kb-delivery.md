# 落库与提交：目录、去重、enrich、闸门

## 1. 先查有没有写过

```bash
grep -rln '<source-url>' --include='*.md' . | head
grep -rln '<slug>' --include='*.md' ai-tools system-design programming sre database | head
grep -rln -F '<article.title>' --include='*.md' ai-tools system-design programming sre database | head
```

X Article 常是团队博客的改写版：URL grep 会漏（分享的是 `x.com/i/article/<id>`），slug grep 也会漏（slug 是纯数字）。必须用 `article.title` 再 grep 一次。命中说明页面已存在，读该页的来源块与 X 版结尾，确认是同一篇文章，然后保留原有 `source:`，把 X URL 作为版本注记加进去，带日期与版本来历。

## 2. 命中已有页面 → enrich，不新建

- 取全文，列出它有哪些节和事实、页面缺哪些，只补缺口。
- 老页面通常缺开头那个统计数字，也常常完全没有 `## 局限`：两处都先查。
- 早期从列表摘要攒的页面，常缺版本号、脚手架命令、端点名、配置项、故障注入实测——按节补，不重写已有节。
- 顺手修错掉的 `authors:`：取署名或页脚，不要用出版物品牌名。
- 回执报改动前后字节数，commit message 用 `enrich`。

回执里说某件事还没做之前，先查仓库：

```bash
git log --oneline -- <path>
git merge-base --is-ancestor <hash> origin/master; echo $?
```

已经合进 master 的活不要再让人重提，直接给已有 commit hash，只点名真正缺的。

## 3. 两个页面同源 → 合并

写之前用 `grep -rln '<source-url>'` 排除。若两个活页面已经共享同一个 `source:`，停下，按 `kb-frontmatter-standard` 第 9 步合并：留更全的一篇，把另一篇独有的节搬进来，重写所有入链，`git rm` 掉被并的那篇。

## 4. 目录与文件名

按主题选目录，不看 URL 前缀：

- `ai-tools/anthropic-engineering/`：Anthropic 的工程与 research / red-team 文章（关于 agent 或编码）
- `ai-tools/harness/`：运行时与 agent 工作流工程
- `ai-tools/eval-engineering/`：评估与判分
- `ai-tools/ml-research/`：训练与后训练
- `ai-tools/patterns/`：生成物的设计、可读性、交互模式
- `ai-tools/inference/`：serving 与推理工程
- `infrastructure/`：GPU 集群与平台可靠性
- `sre/`、`database/`、`system-design/`
- `papers/`：论文笔记

拿不准就 `ls` 该目录看邻居放哪。相邻主题已有页面时，新页面放同一目录，结尾加 `## 相关页面`，每条用相对路径加一句「它答什么 / 本文答什么」。只有链接不算写完。

文件名用描述性 kebab-case。

## 5. frontmatter

```yaml
---
title: "<完整中文标题>"
tags:
  - agent-harness
  - multi-agent
date: <原文署名日期 YYYY-MM-DD>
source: "<canonical article URL>"
authors: "<author names>"
read_at: <YYYY-MM-DD>
category: ai-agents
---
```

`date:` 是原文署名日期，`read_at:` 是今天，两个都要写；`wiki_fm_guard.py` 缺 `date:` 报 W1，严格模式会卡提交。

标签复用已有值，不要造变体：

```bash
for t in agent-runtime agent-harness multi-agent orchestration; do printf "%-18s %s\n" "$t" "$(grep -rl --include='*.md' "  - $t$" ai-tools | wc -l)"; done
```

`tags:` 这一行可能消失而下面 `  - ` 列表还在——眼睛看着正常，实际页面等于没有标签。补回键值：

```python
fm = re.sub(r'(^title:.*\n)(?=  - )', r'\1tags:\n', fm, count=1, flags=re.M)
```

提交前扫全库，不只扫今天这一篇：几周前写的页面带着同样缺陷，只查单页会漏掉：

```bash
cd ~/.openclaw/workspace && python3 - <<'EOF'
import re,glob
bad=[]
for p in glob.glob('**/*.md', recursive=True):
    if p.startswith(('node_modules','.git','memory/','papers/')): continue
    t=open(p, encoding='utf-8', errors='ignore').read()
    m=re.match(r'^---\n(.*?)\n---\n', t, re.S)
    if not m: continue
    fm=m.group(1)
    if 'tags' not in re.findall(r'^([a-zA-Z_]+):', fm, re.M) and re.search(r'^  - ', fm, re.M):
        bad.append(p)
print('missing tags key:', len(bad))
print('\n'.join(bad))
EOF
```

修完用正则复验 `tags` 存在且后面至少三条 `  - ` 行，不要依赖装了 YAML 解析器。报缺陷时列出受影响页面；若重写器在下一轮又复现同一损坏，它是嫌疑对象而不是已证原因，两件事不要混说。

## 6. 图片

存 `<workspace>/image/<slug>-<n>.<ext>`，页面里按目录层级写相对路径：`ai-tools/harness/` 下的页面要 `../../image/<slug>-1.png`。用邻居核对一次：

```bash
grep -rn '](.*image/' ai-tools/harness/*.md | head -3
```

## 7. 提交前跑闸门

```bash
cd ~/.openclaw/workspace
python3 scripts/wiki_fm_guard.py          # frontmatter 守卫
python3 scripts/wiki_lint.py --moc        # 重新生成 MOC-*.md，页面才不算未索引
python3 scripts/wiki_tags.py --check      # 新页面应报 0 处 tag 改动
bash scripts/git-knowledge-commit.sh -m "docs: add <slug>"
```

`git-knowledge-commit.sh` 只暂存领域目录，`notes/` 不动，改过 `notes/` 页面要自己 `git add`。读它打印的 `master <old>..<new>` 那一行，回执用这个 hash。

然后 `git status --porcelain`：`wiki_lint.py --moc` 会重写各域 MOC 与 `reports/lint.md`，提交脚本都不管，所以还要补一次 `chore: regenerate MOC and lint report` 并 push。push 完工作区还脏，就是没做完。

## 8. 并入现有文章（「不要新建」）

把「不要新建」「放到相近主题的文章里」「放到…题目的知识文档中」都当追加指令，不新建页面。先读 `references/append-hosts.md`：里面是宿主搜索方法、题库编号规则、`notes/coding-agent-toolkit.md` 的经验条写法、追加后的 diff 检查。回执要说明宿主是哪一篇、为什么是它。
