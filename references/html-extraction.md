# HTML 正文抽取的两个特例

默认抽取（SKILL.md 第 3 步：去 script/style/svg，块级标签换行，去标签）先跑。下面两种页面在默认抽取之后还要再切一刀，读到这条参考说明命中了其中之一。

## WordPress 语法高亮插件把代码块输出两遍

Enlighter、Geshi、Prism 这类插件会同时输出一份纯文本和一份 token 流。去标签后第二份长得像 `str (p.relative_to(ROOT))` —— 括号和点号前面多了空格。保留纯文本那份、丢掉 token 那份；检查命令是 `grep -c 'def run_python' page.txt`，文章只定义一次而这个计数为 2 就说明重复还在。只按保留的那份算源文本长度。

## 营销站博客（Next.js 的 `/blog/...`）要按 `<main>` 裁切

关联文章列表内联在 `<main>` 里，而且会把别的整篇文章重复好几遍，必须在切完之后截掉：

```python
start = raw.find('<main')
body = raw[start:raw.find('</main>', start)]
for marker in ('More on this topic', 'Recommended posts', 'Related articles', 'Read next'):
    i = body.find(marker)
    if i > 0:
        body = body[:i]
```

验收：最后一个标题必须是文章自己的结论或 FAQ。末尾如果一个标题名不同、还带日期的 `h1`，说明关联列表没被切掉。

## 不要用 `<article>` 包住整段抽取

有些主题把正文放在 `<article>` 外面，加了这个约束会静默截断。真要加，就把输出字符数和页面大小对一遍再决定。
