# Notion-Folder-Opener

一个极简、稳定的本地“链接→打开文件/文件夹”工具：
在 **Notion/网页/文档** 里放一个短链接，点击后浏览器会访问本机服务并在你的电脑上**打开目标文件夹或文件**。

* ✅ 支持 **open**（打开目标）与 **reveal**（在资源管理器中定位/选中该文件）
* ✅ 支持 **短链**（美观、好记）
* ✅ 支持 **批量生成**（一次多条路径）
* ✅ 自带 **历史列表页**（查看/删除短链）
* ✅ 本地运行、无需外网，跨平台（Windows/macOS/Linux）

---

## ✨ 功能特性

* **短链生成**：`/gen` 返回完整链接与短链（`/s/<token>`），前端默认展示短链更美观
* **批量生成**：页面一次粘贴多行路径，或带“别名 | 路径”，一键生成多条短链
* **历史列表**：查看已生成短链（token/路径/动作/时间），支持一键删除
* **安全签名**：链接携带 `HMAC-SHA256` 签名（覆盖 `path+action`），防篡改
* **可选动作**：

  * `open`：打开文件夹或用默认程序打开文件（默认）
  * `reveal`：定位/高亮选中文件（若是文件夹则打开该文件夹）
* **轻量依赖**：FastAPI + SQLite（内置，无需额外安装）

---

## 🗂 项目结构

```
notion_link_opener/
├── notion_link_opener.py      # FastAPI 后端（含短链、批量、历史API）
└── static/
    ├── index.html             # 前端：单条/批量生成器（推荐入口）
    └── links.html             # 前端：短链历史列表（查看/删除）
# 运行后自动生成：
data/
└── links.db                   # 短链数据库（SQLite）
```

---

## 🚀 快速开始

> 需要 Python 3.8+（建议 3.10+）

```bash
pip install fastapi uvicorn pydantic
python notion_link_opener.py
```

打开浏览器访问：

```
http://127.0.0.1:6060
```

* 在 **“单条生成”** 中输入绝对路径，选择动作，点击“生成链接”，复制 **短链** 到 Notion/文档即可。
* 在 **“批量生成”** 中每行一条输入：

  * 仅路径：`D:/CODE/fastapi_app`
  * 或“别名 | 路径”：`proj1 | D:/docs/报告.pdf`

> 🪟 Windows 建议：在资源管理器里选中文件/文件夹 → **Shift + 右键 → 复制为路径** → 粘贴到页面；页面会帮你把 `\` 转成 `/`。

---

## 🔌 在 Notion 里使用

* 复制生成的**短链**（如 `http://127.0.0.1:6060/s/abc123`）到 Notion/文档
* 点击时浏览器会跳到本机的完整链接并在你的电脑上打开目标
* **前提**：这台电脑正在运行本服务（`python notion_link_opener.py`）

> 注意：此工具用于本机打开，不支持跨机器（远端机器无法打开你本地的文件）。

---

## ⚙️ 配置

* **HOST/PORT**
  如需变更，请直接修改 `notion_link_opener.py` 顶部常量 `HOST / PORT`（默认仅监听本机）。

---

## 🌐 前端页面

* 生成器（推荐入口）：`/static/index.html`（首页会自动跳转）
* 历史列表：`/static/links.html`（可从生成器右上角进入）

页面特性：

* 自动格式化路径（去引号、`\`→`/`）
* 展示短链为主，可展开查看完整链接
* 单条/批量复制短链
* 批量输入支持：

  ```
  D:/CODE/fastapi_app
  proj1 | D:/docs/报告.pdf
  music | D:/Music/playlist.m3u8
  ```

---

## 🧭 API 文档（简明）

### 1）生成链接（单条）

**GET** `/gen`

| 参数       | 必填 | 说明                            |
| -------- | -- | ----------------------------- |
| `target` | ✅  | 绝对路径（如 `D:/CODE/fastapi_app`） |
| `action` | 否  | `open`（默认）或 `reveal`          |
| `alias`  | 否  | 自定义短链 token（字母数字），可覆盖同名       |

**返回**

```json
{
  "full_url": "http://127.0.0.1:6060/open?path=...&action=open&sig=...",
  "short_url": "http://127.0.0.1:6060/s/abc123",
  "token": "abc123"
}
```

### 2）生成链接（批量）

**POST** `/gen_batch`  `Content-Type: application/json`

```json
{
  "action": "open",
  "items": [
    {"target": "D:/CODE/fastapi_app"},
    {"alias": "proj1", "target": "D:/docs/报告.pdf"}
  ]
}
```

**返回**

```json
{
  "action": "open",
  "items": [
    {
      "target": "D:/CODE/fastapi_app",
      "alias": null,
      "token": "A1b2XyZ",
      "short_url": "http://127.0.0.1:6060/s/A1b2XyZ",
      "full_url": "http://127.0.0.1:6060/open?path=...&action=open&sig=..."
    },
    {
      "target": "D:/docs/报告.pdf",
      "alias": "proj1",
      "token": "proj1",
      "short_url": "http://127.0.0.1:6060/s/proj1",
      "full_url": "http://127.0.0.1:6060/open?path=...&action=open&sig=..."
    }
  ]
}
```

### 3）短链跳转

**GET** `/s/{token}` → 302 到完整 `/open?...` 链接

### 4）执行打开

**GET** `/open`

| 参数       | 必填 | 说明                               |
| -------- | -- | -------------------------------- |
| `path`   | ✅  | Base64-URL 编码后的绝对路径              |
| `action` | 否  | `open`（默认）或 `reveal`             |
| `sig`    | ✅  | HMAC-SHA256 签名（基于 `path+action`） |

> 正常情况下无需手动调用 `/open`，点击短链会自动跳过去。

### 5）历史列表（API）

* **GET** `/api/links?limit=500` → 返回最近短链列表
* **DELETE** `/api/links/{token}` → 删除指定短链

---

## 🧪 常见问题

* **点击短链没反应？**
  确认本机已运行服务（终端有“服务已启动: [http://127.0.0.1:6060”），且浏览器能访问首页。](http://127.0.0.1:6060”），且浏览器能访问首页。)
* **404 / Not Found？**
  确认访问的是 `/gen`、`/s/{token}` 或首页 `/`。静态文件已挂在 `/static`，不要覆盖根路由。
* **路径校验失败？**
  必须是**绝对路径**，Windows 建议使用“复制为路径”，页面会自动把 `\` 变为 `/`。
* **签名错误？**
  修改了 `NFO_SECRET` 或手工改了链接参数会导致签名不匹配；重新生成链接即可。
* **历史太多？**
  去 “短链历史” 页面删除不需要的记录，或删除 `data/links.db` 清空（会丢失所有短链）。

---

## 🛡️ 安全建议

* **仅监听本机**（默认 `127.0.0.1`），不要直接暴露到公网
* **修改密钥** `NFO_SECRET` 为足够长的随机字符串
* 链接 **默认不过期**，请通过“历史列表”手动删除不再需要的短链
* 如需更强控制，可扩展：**白名单根目录**、**一次性短链**、**动作白名单** 等

---

## 🧰 进阶

* **Windows 开机自启**
  `Win + R` → 输入 `shell:startup` → 把 `notion_link_opener.py` 的快捷方式（目标指向 python 运行该脚本）放进去
* **PyInstaller 打包**

  ```bash
  pip install pyinstaller
  pyinstaller -F -n notion_link_opener notion_link_opener.py
  ```

  生成的 EXE 更方便注册自定义协议、设置自启等

---

## 📄 许可

本项目示例以 MIT 许可开源。

---

## 🙋 支持与反馈

有新的需求（如：白名单、一次性短链、导出 CSV、协议 `nf://` 等），或遇到问题，直接在 Issue 里描述你的场景与期望行为即可。
