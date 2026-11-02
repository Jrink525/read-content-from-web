---
name: read-content-from-web
description: "X post/Article, blog, GitHub PR, Medium, WeChat, Cloudflare URL: extract and translate, then answer in chat or file a sourced Chinese KB page with cited quotes and a commit."
title: "Read Content from Web"
tags:
  - skills
source: "original-url"
---

# 读网页 → 中文长文 / 问答 / 入库

一个入口覆盖全部来源：X 帖子、X Article、普通文章、博客、GitHub PR/issue、Medium、微信公众号、Cloudflare 保护页。产出三选一：直接回答问题、在对话里归纳、写成知识库页面并推送。

## 0. 先定模式

用户给链接时，看动词决定深度：

| 请求 | 做什么 |
|---|---|
| 「读一下」「这个讲了什么」「这个特性核心价值」 | 只抽正文 + 对话作答。**不建页面、不提交、不写路径** |
| 「读取整理」「整理入库」「帮我记下来」 | 抽正文 → 写页面 → 跑闸门 → 提交推送 → 回执 |
| 「不要新建」「放到…那篇里」「并入」 | 抽正文 → 追加进宿主页面（`references/append-hosts.md`） |
| 只说「整理」（紧接一次问答之后） | 对刚读那篇执行完整流程，正文已在 `.tmp/<slug>.txt`，不重抓 |

没有链接、只有命令（`/read_content_from_web`）时：先确认是哪一篇，别猜。上下文里只有一篇就用它，回执按第 9 节重写一遍。

## 1. 判定来源

| URL 形状 | 首选方法 |
|---|---|
| `x.com/.../status/...`、`twitter.com/...` | fxtwitter API（见 2.1） |
| `medium.com/...`、`towardsdatascience.com/...`、挂自定义域名的 Medium（`netflixtechblog.com`） | `https://freedium-mirror.cfd/<原 URL>` |
| `github.com/<owner>/<repo>/pull|issues/<n>` | `references/github-pr-source.md` |
| `mp.weixin.qq.com/s/...` | 直取 HTML 提取 `js_content`（见 2.4） |
| `baeldung.com` 等 Cloudflare 页 | `r.jina.ai`（见 2.5） |
| 其它 | 直接 `curl` + 抽取（见 2.2） |

统一取数命令（Chrome UA，压缩传输）：

```bash
curl -sL --compressed --max-time 40 \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" \
  "<url>" -o page.html
```

`wc -c page.html` 小于 10 KB 且正文含 `Attention Required` / `Just a moment` 就是 Cloudflare，走 2.5。

## 2. 抓取与抽取

### 2.1 X / Twitter

```bash
mkdir -p ~/.openclaw/workspace/.tmp/x-<user> && cd ~/.openclaw/workspace/.tmp/x-<user>
curl -s "https://api.fxtwitter.com/<user>/status/<id>" -H "User-Agent: Mozilla/5.0" -o tweet.json
python3 - <<'EOF'
import json
t = json.load(open('tweet.json'))['tweet']
print(t['created_at'])
print(t['text'])
c = t.get('card') or {}
print('CARD:', c.get('url'), '|', c.get('title'))
print('replies:', t.get('replies'), 'quotes:', t.get('quotes'))
print('article?', bool(t.get('article')))
EOF
```

- 只取数字 status id，去掉 `?s=…&t=…` 追踪参数。备用域名 `api.vxtwitter.com`。
- **推文正文只有一条链接**，通常就是 X Article，而且同一个响应里就带全文——先抽，不要再去抓 `x.com/i/article/...`。
- `card.url` 是作者的长文地址；**先看 `tweet.article`，没有才退回 `card.url`**。两个都没有、账号又是公司工程号时，用标题 + 最有辨识度的数字做 `web_search` 找博客版。
- fxtwitter 已把 `note_tweet` merges 进 `text`，长推不用额外请求。
- `article` 存在时，源文本已经在手上：不要抓文章页，也不要去找镜像。

X Article 正文抽取（block 类型 + entityMap，必须都读到，否则页面静默丢掉所有代码块和配图）：

```bash
python3 - <<'EOF'
import json
from collections import Counter
a = json.load(open('tweet.json'))['tweet'].get('article')
print('TITLE:', a['title'], '| blocks:', len(a['content']['blocks']))
print('TYPES:', Counter(b['type'] for b in a['content']['blocks']))
ents = {e['key']: e['value'] for e in a['content'].get('entityMap') or []}
for b in a['content']['blocks']:
    if b['type'] == 'atomic':
        for r in b.get('entityRanges') or []:
            ent = ents.get(str(r['key'])) or {}
            data = ent.get('data') or {}
            kind = ent.get('type')
            if kind == 'MEDIA':
                ids = [m.get('mediaId') for m in data.get('mediaItems') or [] if m.get('mediaId')]
                print('[IMG %s] %s' % (','.join(ids), data.get('caption') or ''))
            elif data.get('markdown'):
                print('[MD]'); print(data['markdown'])
            elif kind == 'TWEET':
                print('[EMBED tweetId=%s]' % data.get('tweetId'))
        continue
    if b.get('text', '').strip():
        print(f"[{b['type']}] {b['text']}")
EOF
```

块类型实测出现过：`unstyled`、`header-one`、`header-two`、`header-three`、`blockquote`、`unordered-list-item`、`ordered-list-item`、`code-block`、`atomic`。先打 `Counter` 再抽取，没映射的类型会以 `[type] text` 出现而不是消失。

读三件事：

| 东西 | 在哪 | 丢了会怎样 |
|---|---|---|
| 正文与标题层级 | `blocks[].text` / `type` | 标题级别因文而异（有一篇 11 节全用 `header-one`），按 type 映射，不要假定 `header-two` |
| 链接、代码、表格 | `entityMap[key].value.data.url` / `.markdown` | `atomic` 块自己没有 text，只读 text 会全丢 |
| 配图 | `article.media_entities[].media_info.original_img_url` | `article.content.media` 常年为空，只读它会静默丢图 |

`MEDIA` 实体多数带 `data.caption`，**先读 `type` 再读 `data`**；caption 分支写在前面会打印图说却丢掉 mediaId，后面下载就没位置可映射。

图片与内嵌推文的完整流程（mediaId → block 位置、下载脚本、magic-byte 校验、无图时改图说、内嵌推文解析）见 `references/x-article-figures.md`，下载器是 `scripts/x-article-images.py`。

**写之前先数图**：抽取文本里的 `[IMG ...]` 数、页面里的 `![]` 数、`image/<slug>-*` 文件数必须三者相等。有文件没引用、或有引用没文件，说明图序错位。

`media_entities` 多数条目 `original_img_url` 为 `None`（视频占位），只保留下载到的 jpg/png；一张都下不到就不配图，**不要拿视频封面冒充正文图**。`atomic` 只有 `data.caption` 时，每条写成一行 `> **原文图说**：<中译>`，并用 `grep -c '!\[' <page>.md` 确认结果是 0——`x.com/i/article/<id>` 是文章页不是图片，拿它拼 `![]()` 只会得到死链。

### 2.2 一般网页

去 script/style/svg/noscript，块级标签换行，再去标签：

```python
import re, html
raw = open('page.html', encoding='utf-8', errors='ignore').read()
raw = re.sub(r'(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>', ' ', raw)
raw = re.sub(r'(?is)</(p|div|h[1-6]|li|tr|pre|blockquote)>', '\n', raw)
raw = re.sub(r'(?is)<br\s*/?>', '\n', raw)
text = html.unescape(re.sub(r'(?is)<[^>]+>', ' ', raw))
text = re.sub(r'[ \t]+', ' ', text)
text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
open('page.txt', 'w').write(text)
print('chars:', len(text))
```

打印字符数是硬要求：截断必须看得见。

- **不要把抽取范围限制在 `<article>` 里**。有些主题把正文放在外面，结果静默截断。若用了，比较打印大小与页面大小，不对就去掉限制重跑。
- 正文低于 2 K 字符：要么真的短，要么抽取失败——先判断再相信。
- Next.js 站的 `__NEXT_DATA__` 通常只有 schema 元数据，正文是服务端渲染的；`<main>` 抽取已得 10 K+ 字符时不要去找 JSON。
- WordPress 语法高亮插件会重复输出代码块；营销页常把关联文章截掉。命中这两类读 `references/html-extraction.md`（检查命令 + 验收标尺）。

站点特例：

- **Anthropic**（`/engineering/<slug>`、`/research/<slug>`、`/news/<slug>`）：正文服务端渲染，但列表页可能不再输出普通 `href`，整份列表在 flight payload 里。`href="/(engineering|research)/[a-z0-9-]+"` 在 300 KB+ 页面上返回 0 条时，解转义后从 payload 取：

```python
u = open('page.html', encoding='utf-8', errors='ignore').read().replace('\\"', '"')
slugs = re.findall(r'"slug":\{"_type":"slug","current":"([a-z0-9\\-]+)"\}', u)
dates = re.findall(r'"publishedOn":"([^"]+)"', u)
```

日期取文章自己的 `publishedOn`；sitemap 的 `lastmod` 会在部署时批量重写，可能比真实发布日期晚一天以上。`/news/<slug>` 与 `/research/<slug>` 都 200 且标题相同时，`source:` 保留 `<link rel="canonical">` 的地址，并写明它归在哪个栏目（Frontier Red Team / research / news），归档位置决定哪个 watcher 会看到它。

- **Hugging Face**（`huggingface.co/blog/<org>/<slug>`）：`og:` 标签没用（`og:description` 只有 `A Blog post by <org> on <org>`），署名从正文取：

```bash
grep -oE '"datePublished": *"[^"]+"' page.html | head -1
grep -oE '"Authors":\[[^]]*\]' page.html | head -1
```

`datePublished` 进 `date:`；`Authors` 是 handle 列表（如 `["burtenshaw","sergiopaniego"]`），把 handle 写进 `authors:`，不要猜全名。图在 `https://huggingface.co/buckets/<user>/<bucket>/resolve/<name>.png?download=true`，用浏览器 UA 下载后逐张验证文件头是 PNG。

- **X 文章页返回登录壳**时用 `tweet.article`；个人博客则抓站点索引，按标题关键词 grep href，描述性 slug 比猜更可靠。写之前确认抓到的页面确实含那篇文章的标题与数字。

### 2.3 Medium

```
https://freedium-mirror.cfd/https://medium.com/...
```

失败依次降级：`freedium.cfd` → `freedium-tnrt.onrender.com` → Google cache。`web_fetch` 的 `maxChars` 给到 100000。

### 2.4 微信公众号

`web_fetch` 与 `r.jina.ai` 都拿不到，直接下 HTML 再正则取 `js_content`：

```bash
curl -sL --max-time 15 \
  -H "User-Agent: Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36 MicroMessenger/8.0.49" \
  -H "Referer: https://mp.weixin.qq.com/" \
  "https://mp.weixin.qq.com/s/..." -o wechat.html
```

```python
import re, html
h = open('wechat.html', encoding='utf-8', errors='ignore').read()
m = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', h, re.DOTALL)
c = m.group(1) if m else ''
c = re.sub(r'<br\s*/?>', '\n', c)
c = re.sub(r'</(p|div)>', '\n', c)
c = re.sub(r'<[^>]+>', ' ', c)
c = re.sub(r'&nbsp;', ' ', c)
c = re.sub(r'\u200b', '', c)
c = re.sub(r'[ \t]+', ' ', c)
c = re.sub(r'\n{3,}', '\n\n', c)
print(len(html.unescape(c).strip()))
```

微信浏览器 UA + `Referer: https://mp.weixin.qq.com/` 两个条件一起用才稳。HTML 很大（带 Referer 后可达 3 MB+），超时给足。图片在 `mmbiz.qpic.cn` / `mmbiz.qlogo.cn`：`re.findall(r'data-src=["\'](https?://mmbiz\.qpic\.cn[^"\']+)["\']', h)`。抽出来的文本可能夹推广段落，写完删掉。

### 2.5 Cloudflare 保护页

`r.jina.ai` 能过 WAF，**必须 POST 空 JSON body**（GET 会要求 auth）：

```bash
curl -sL --max-time 20 "https://r.jina.ai/<原 URL>" \
  -H "Content-Type: application/json" -d '{}'
```

返回 Markdown，带 `Title:` / `URL Source:` / `Published Time:` 头。响应有长度上限，长文可能被截断。

## 3. 线程与链接

X 帖若是作者自述线程，按已装的 `x-thread-extraction` skill 读登录态页面与 GraphQL 解码，再解析每个 `t.co` 并按最终 URL 去重：

```bash
for c in <codes>; do printf "%s -> " "$c"; curl -sIL --max-time 20 -o /dev/null -w "%{url_effective}\n" "https://t.co/$c"; done
```

自述线程通常带出相关文章：早期工作流、角色设计、重写版、产品理由。这些是「作者自己的早期帖子」，不要写成第三方报道。登录态页面只渲染自述线程加少量回复，**报告实际看到的条数**，不要暗示读过全部回复；只有作者自己的回复时，直接说明并把它们当来源集。

## 4. 建 claim map

每个来源记五项：日期、一句话主张、点名的系统、数字、值得逐字引用的一句。按日期排序——从脚本到系统的演化通常就是文章主轴，每个来源对应一个阶段。

来源点名了规范 / SDK / 仓库却没给链接时，去解析而不是写「原文未给链接」：

```bash
for u in <candidates>; do printf "%s -> " "$u"; curl -s -o /dev/null -w "%{http_code}\n" -L --max-time 15 -A "Mozilla/5.0" "$u"; done
```

200 之后用 `https://api.github.com/repos/<owner>/<repo>` 确认 star、license、`created_at`、`pushed_at`，读 README 取命令。结果单独一节标「核对」，数字旁写读取日期；没查到的才留在「局限」。

每天会变的数（star、版本、价格、用户数）读取时复核权威端点，原文数字与当前数字并列，标明核对日期。

## 5. 读完之后：四条纪律

这四条解决「读完了，整理出来却是复述目录」。

1. **闭卷提取，再回原文核对。** 读完先合上原文，凭记忆写下 3–5 条主张；写完再打开逐条核对。识别（眼熟）不等于提取（能重建）。对不上的地方就是理解断点，回原文补读，不要改写措辞绕过去。判据：每条主张都能在原文找到逐字支撑，顺序是原文的论证顺序。
2. **每节结论先行。** 该节第一句写可判定的结论，后面才是证据、引用与代码。判据：删掉该节最后一段，该节仍然成立。
3. **先连接，再收集。** 保存前找 2–3 篇已有页面，各写一句「它回答什么问题」，再写「本文回答什么问题」，文末 `## 相关页面` 每条都写全两半。只有链接算没写完。
4. **写不出来就标未理解。** 卡住的地方是理解断点，不是文笔问题：标 `> 未理解：<哪一步说不清>`，汇总进 `## 局限`。禁止用「可以看出」「这体现了」「不难发现」「众所周知」填空；每出现一次，后面必须跟具体机制或数字。

**原文没说的不要补成事实。** 数字只写原文给的；自己的推论标「推论」，不与原文判断混排在同一段。

## 6. 写页面

骨架按来源类型选，读 `references/article-skeletons.md`：多源工程长文、单源工程博客、代码教程、产品发布、课程/资源、面试问答、概念解释、观点立场、架构设计文档、厂商工作流贴、中文原文、索引页。

篇幅档位：

| 来源体量 | 汉字 |
|---|---|
| 单篇长文 | 5,000–7,000 |
| 多源 | 6,000–9,000 |
| 清洗后 10–15 K 字符短教程 | 3,000–4,500 |
| 清洗后 4–6 K 字符短 X Article | 2,500–3,500 |
| 索引页（散文不足 3 K 字符） | 2,000–3,000 |

短篇的增量放在核对、原文未答的问题、原文没写的失效模式，**不复述章节凑长度**。动笔前先 `grep -n` 出原文全部小标题，数清章节数与顺序：漏一节就是漏一段论证。

引用形状：

- 每条数字必须在来源里出现；引文用「」，保留作者措辞。
- 原文按 bullet 分行写的句子，逐条各引一行 blockquote；合并两条就是制造作者没写过的话。
- 图表里的数字写成「原文图表」，不从图上估数值；读不到的图列进「局限」。
- 本机无法执行的代码，正文与回执都写「未实跑，按 SDK 语义核对」，不要写成已验证。
- 模型无视觉能力时，一次读图失败就停，不要反复试；已插入的截图用中性 alt `原文配图（原文无图说）`，并在「局限」写明内容未核。

原文是中文（抽取正文过半是汉字）：不翻译、不标译文，引文照抄原文数字写法，核对按前缀比——`references/chinese-source.md`。

厂商工作流贴（N 方法、自家命令、零测量）：`references/vendor-workflow-post.md`。

## 7. 引文核对（提交前必跑）

完整流程、脚本与误报处理见 `references/quote-check.md`。最少要跑两条：英文块引用逐条测、页面内联英文片段逐条测。一次跑出 `0 quotes` 而页面明明有英文引用，说明检测器错了，不是页面干净。

中文引文按前缀比。改到每条都 OK 再提交；引号里的一句改写，是读者从页面上唯一查不出来的错误。

## 8. 落库

目录、去重、enrich、同源合并、文件名、图片相对路径、MOC、提交脚本的细节见 `references/kb-delivery.md`。要点：

- 先按 URL、slug、`article.title` 三次 grep，X Article 常是博客版的改写，前两次都会漏。
- 命中就 enrich，不新建；两个活页面同源就合并。
- frontmatter 必带 `title / tags / date / source / authors / read_at / category`，`date` 是署名日期，`read_at` 是今天。
- 图片存 `<workspace>/image/<slug>-<n>.<ext>`，页面按层级写 `../`。

提交闸门：

```bash
cd ~/.openclaw/workspace
python3 scripts/wiki_fm_guard.py
python3 scripts/wiki_lint.py --moc
python3 scripts/wiki_tags.py --check
bash scripts/git-knowledge-commit.sh -m "docs: add <slug>"
git status --porcelain
```

`--moc` 会重写各域 MOC 与 `reports/lint.md`，这两个提交脚本都不管：补一次 `chore: regenerate MOC and lint report` 并 push。push 完工作区还脏就是没做完。

## 9. 回执格式

统一三段，加补充发现，末尾路径与 hash：

```
✅ 文章已整理并推送（commit `xxx`）
**文件：** <category>/<slug>.md

**What（是什么）：** 核心内容 / 解决了什么问题 / 关键对象
**How（怎么做的）：** 核心方案与步骤，给 1–2 个关键机制或代码示例
**Why（为什么/意义）：** 解决的痛点、适用场景、亮点与局限

**补充**（可选）：3–4 条读者猜不到的发现，每条一句结论 + 原文证据
```

- 只发文字，路径写成纯路径。**只有用户明确要文件时才加 `MEDIA:` 一行**——附件加摘要等于同一内容发两遍。
- 方法要写清用了几个来源。
- 数字只用原文给过的；「读者猜不到的发现」是原创判断，要能在原文找到支撑。
- 表格在 Telegram / WhatsApp 里换成 bullet。

## 10. 追问

页面写完，用户常就同一篇继续问。全部从页面或抽出的原文取事实，不凭记忆复述。

- **摘要**（「主要讲了什么」）：归成 3–5 个主题组，每组给作者原判断并保留数字与原话，末尾一句写局限；不按小节顺序复述，不新增评价。
- **要点清单**（「核心观点」「15 条分别是什么」）：只输出条目，标题加一句要点，写完就停，不追加局限、提醒或推荐。
- **字数上限**（「控制在 270 字内」）：先删解释只留标题，再压措辞，最后才删条目；写完用 `python3 -c "import sys;print(len(open(sys.argv[1]).read()))" <f>.txt` 数字符确认，不凭感觉估。
- **一句话客观陈述**：只输出一句，句式「<作者> 在《<英文原题>》中提出，<主体> 还需要解决 <分类枚举>」，按原文分类与顺序，不加第一人称、bullet、emoji、话题标签。
- 这几类回答只给文字，不写文件、不提交、不附路径，除非另要。
- **「这个特性核心价值是什么」**：抽完正文就结束，按四层答——一句话核心价值、技术上它是什么（并说清与 settings / skill / 斜杠命令这类既有扩展机制的差别）、两三个实例各证明哪一档价值、边界与风险，最后一句自己的判断，末尾提一句可以整理进知识库。

### 「这个能力能不能在别的运行时用」

先找官方兼容性表，不要从概念推断。功能页地址猜不中（`/docs/en/mods` 404）时，从相邻页导航取真实路径：

```bash
grep -oE 'href="[^"]*(mod|plugin|hooks)[^"]*"' page.html | sort -u
```

按行读表格，扁平化会把表头和行混成一句：

```python
import re, html
h = re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>', '', open('page.html', encoding='utf-8', errors='ignore').read())
for tb in re.findall(r'(?is)<table.*?</table>', h):
    if 'SDK' not in tb and 'claude -p' not in tb: continue
    for r in re.findall(r'(?is)<tr.*?</tr>', tb):
        print(' | '.join(html.unescape(re.sub(r'<[^>]+>', '', c)).strip()
                         for c in re.findall(r'(?is)<t[hd].*?</t[hd]>', r)))
```

答案分两列：**逻辑跑不跑**与**界面出不出**是独立的两件事，同一能力一行 Yes、一行 No 是常态。说「支持」要给开关与最低版本（在类型参考里 grep 配置项名，例如插件用 `plugins` 启动加载、中途 `reloadPlugins({ addPlugins })`），否则下一轮会被追问「具体怎么开」。

把多篇已有知识库页面合并成对照长文、且没有新 URL 时，改用 `kb-comparative-article`。

## Pitfalls

- 每节结论写在末尾，整篇读起来像慢慢推导；改成结论先行，同样事实短一半。
- agent 数、运行时数在帖子之间会变：当前数字用最新一篇，旧文只引它自己那段时间。
- 自述线程的 `t.co` 是同一作者的早期帖，不要当成外部报道。
- 博客索引列全站文章，按标题关键词匹配，不要猜 slug。
- 登录墙后的 X Article 页不是抽取失败：博客版才是权威版。
- `papers/` 草稿 + KB 页面同源，会被 lint 当成重复来源组：只在 KB 路径写一次，草稿放 `.tmp/`。
- 作者的单位与职位来自 bio（`curl -s https://api.fxtwitter.com/<user>`），不是上下文推断。bio 写 `Working on @company` 就写「在某公司做工程」，升格成「联合创始人」是来源里没有的事实。
- 博客署名日期可能早于正文讨论的软件版本：`date:` 用署名日期，再核对文中点名的版本与产品，晚于署名日期就在「局限」写明，不要让页面暗示那项能力当时已存在。
- 页面讨论过之后单独来一句「修正一下」，指的是那个文件：查文件、指出具体缺陷、修、提交，再报告错在哪；重写上一条聊天消息不算修正。

## 交付前自检

- [ ] 抽取字符数打过印，没有截断
- [ ] 小标题数与顺序跟原文一致，没有漏节
- [ ] 每个数字都能在原文找到
- [ ] 引文核对（块引用 + 内联英文）0 未匹配
- [ ] 图数三方相等：`[IMG]` / `![]` / 文件
- [ ] frontmatter 七个字段齐，tags 复用已有值
- [ ] `## 局限` 存在，写清原文没测什么
- [ ] `## 相关页面` 每条写全「它答什么 / 本文答什么」
- [ ] MOC 重生成，残留改动补提交
- [ ] 回执走第 9 节格式，带路径与 commit hash

## 目录与体量

```
ai-tools/  autoresearch/ career/ codex/ enterprise/ harness/ eval-engineering/ …
database/  spring/  sre/  system-design/  programming/  infrastructure/
papers/  image/  skills/  notes/  memory/
```

单目录超过 20 篇 `.md` 就考虑拆子域；`_organize.py` 会在超过阈值时自动拆。

## 增强模式

| 类型 | 补什么 |
|---|---|
| 技术文章 | 代码示例、最佳实践、面试问答 |
| 对比 / 评测 | 改成对照表 |
| 教程 | 前置条件、常见坑 |
| 新闻 / 发布 | 背景、意义分析 |
| 长文分析 | 结构化摘要与要点 |
| 论文列表 | 每篇独立条目存 `papers/` |
| 单篇 → 全面指南 | 拆知识点确保 MECE，再从 X / Medium / 博客补全，最后写成循序渐进的上手文档 |
