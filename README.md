# 日語沉浸学習器

用自己喜欢的视频学日语。上传视频 + 字幕，实时 MeCab 词性分析、点词查义、DeepL 翻译、生词本收藏，全部本地运行。

![界面预览](preview.png)

---

## 功能

- 🎬 **视频 + 字幕同步**：自动高亮当前字幕，点击列表跳转
- 🔤 **MeCab 词性分析**：名词/动词/助词/形容词等颜色区分，带假名标注
- 📖 **点词查义**：本地 JMdict 词典 + Jisho 兜底，支持 DeepL 翻译释义
- 🌐 **DeepL 翻译**：整体字幕翻译，带缓存（同一字幕不重复消耗 API 额度）
- 📚 **生词本**：收藏单词，本地持久化
- ⭐ **收藏句子**：收藏例句，可添加笔记
- 🔁 **精听模式**：每句循环3遍，前两遍字幕模糊，第三遍显示
- ⚡ **变速播放**：0.75× / 1× / 1.25× / 1.5×
- 📱 **移动端适配**：手机也能用，底部操作栏

---

## 快速开始

### 1. 安装依赖

```bash
pip3 install fugashi unidic-lite
```

### 2. （可选）下载 JMdict 中文词典

提供比 Jisho 更好的中文释义。下载 `jmdict_zh.json` 放到 `~/Desktop/`。

> 没有也能用，会自动 fallback 到 Jisho 英文词典。

### 3. 启动服务器

把 `server.py` 和 `nihongo.html` 放在同一个文件夹，然后：

```bash
python3 server.py
```

### 4. 打开浏览器

```
http://localhost:8765
```

---

## 使用方法

1. 点击 **🎬 选择视频** 加载本地视频文件（MP4 / MOV / WebM）
2. 点击 **📋 选择字幕** 加载 SRT 字幕文件
3. 字幕自动进行 MeCab 词性分析（约几秒）
4. 点击 **🌐 翻译** 按钮翻译字幕（需要 DeepL API Key）
5. 点击任意单词查看释义，可加入生词本

---

## DeepL API Key

在设置（⚙️）中填入 DeepL API Key。

- 免费版每月 50 万字符，自学够用
- 申请地址：https://www.deepl.com/pro-api

---

## 视频和字幕放哪里

默认读取路径：

```
视频：~/Downloads/日本語youtube/
字幕：~/Downloads/日本語youtube/字幕/
```

也可以直接点击上传按钮选择本地文件。

---

## 项目结构

```
nihongo.html   # 前端（单文件，所有 UI + JS）
server.py      # 后端（MeCab 分析、DeepL 代理、视频服务）
```

---

## 技术栈

- **前端**：纯 HTML / CSS / JS，无框架
- **词性分析**：[fugashi](https://github.com/polm/fugashi) + [unidic-lite](https://github.com/polm/unidic-lite)
- **词典**：JMdict（本地）+ Jisho API（fallback）
- **翻译**：DeepL API（用户自己的 Key）
- **后端**：Python3 标准库，无额外依赖（除 fugashi）

---

## 灵感来源

受 [Migaku](https://migaku.com/) 和 [miraa](https://miraa.app/) 启发，面向中文母语者的本地化实现。

---

## License

MIT
