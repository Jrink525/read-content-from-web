# 引文核对：提交前必须跑完

页面里的每个引号都可能是一句作者没说过的话。读者无法从页面本身发现这一点，所以这一步不能跳过。

## 1. 建语料

把抽取出的原文放进 `src`。三种情况要拼：

- 同一篇文章既有博客版又有 X Article 改写版：两份抽取文本都存，一起拼进 `src`，因为一句话可能引自任一版本。
- 正文是机器翻译：在来源块写明，并把英文引文标为「译文」，不要让页面看起来像作者原话。
- 焦点帖的 `tweet.text` 也要进语料：钩子句只在推文文本里，不会出现在 `article.content`，不加入就会误报未匹配。

## 2. 逐条测：英文块引用

```bash
python3 - <<'EOF'
import re
def norm(s):
    for a,b in [(chr(0x2019),"'"),(chr(0x2018),"'"),(chr(0x201c),'"'),(chr(0x201d),'"'),(chr(0x2014),'-'),(chr(0x2013),'-')]:
        s=s.replace(a,b)
    return re.sub(r'\s+',' ',s).strip()
src=norm(open('<source.txt>').read()); page=open('<page.md>').read()
qs=[l.lstrip('> ').strip().strip('"') for l in page.splitlines() if l.startswith('>')]
en=[q for q in qs if not re.search(r'[\u4e00-\u9fff]',q) and len(re.findall(r'[A-Za-z]',q))>20]
bad=[q for q in en if norm(q)[:55] not in src]
print(len(en),'quotes,',len(bad),'unmatched')
for q in bad: print(' ??',q[:110])
EOF
```

## 3. 逐条测：内联英文片段

检查脚本只读以 `>` 开头的行。页面如果用「」、反引号或句子中内联引用英文，上面那步会报 `0 quotes` 而什么都没验证。把每个英文片段列出来单独测：

```bash
python3 - <<'EOF'
import re
def norm(s):
    for a,b in [(chr(0x2019),"'"),(chr(0x2018),"'")]: s=s.replace(a,b)
    return re.sub(r'\s+',' ',s)
src = norm(open('<source.txt>').read())
mine = ["<page 里第一处内联英文>", "<第二处>"]
for c in mine:
    print(('OK  ' if norm(c) in src else 'MISS'), c)
EOF
```

改到每条都 OK。MISS 就是改写过或有错字，不是格式问题。

## 4. 中文引文

中文按前缀比对（标点与空格差异多，不比全等），规则和脚本见 `references/chinese-source.md`。中文页面要额外测：原文数字写法照抄（`1,660` 与 `1660` 不是同一个写法，引文里跟原文一致，正文里可以加千分位）。

## 5. 引用形状的四个硬规矩

- **原文按 bullet 分行写的句子，逐条各引一行 blockquote。** 把两条合并成一句，等于制造了一句作者没写过的话；修法是拆开引用，不是把标点磨到能过检查。
- **照抄原文的撇号与破折号**：`It’s` 不是 `It's`。不一致时改页面，不改检查器。
- **原文行内已有 `"` 的，整行原样放进 blockquote，不要在外面再套一对**；把内层改成 `'` 是改作者措辞，套成 `\"` 会在渲染页留下反斜杠。
- **图表里的数字不能从图上读**：写成「原文图表」并保留图，不估数值；读不到的图列进 `## 局限`。

## 6. 误报处理

未匹配不等于造假。去标签会把行内链接切断（原文读作 `A trace` 然后 `, transcript, or log is useful evidence…`），要求长连续字母串的检测器会漏判普通散文。处置顺序：

1. 用更短的前缀、在空白折叠后的语料里重测这一行。
2. 只有措辞真的不同，才改引文。
3. 一次跑出 `0 quotes` 而页面明明有英文 blockquote，说明检测器写错了：改成统计字母数而不是要求连续字母串，再跑一遍。

## 7. 数字与事实的二次核对

- 每天会变的数（GitHub star、版本号、价格、用户数）在读取时用权威端点复核：`curl -s https://api.github.com/repos/<owner>/<repo>`，把原文数字与当前数字并列，标明核对日期。
- 原文点名但没给链接的仓库、SDK、规范，先探测：

```bash
for u in <candidates>; do printf "%s -> " "$u"; curl -s -o /dev/null -w "%{http_code}\n" -L --max-time 15 -A "Mozilla/5.0" "$u"; done
```

拿到 200 后用 `https://api.github.com/repos/<owner>/<repo>` 确认 star、license、`created_at`、`pushed_at`，读 README 取命令。核对结果单独一节标「核对」，带读取日期；没查到的才写进「局限」。
