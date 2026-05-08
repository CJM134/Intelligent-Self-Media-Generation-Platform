# 真实热点API接入指南

## 📋 概述

本文档提供三个平台的热点API接入方案，包括官方API和第三方API服务。

---

## 🎯 推荐方案对比

| 平台 | 推荐方案 | 优点 | 缺点 | 费用 |
|------|---------|------|------|------|
| **微博** | 天聚数行API | 稳定、免费额度 | 需注册 | 免费100次/天 |
| **抖音** | 天聚数行API | 稳定、免费额度 | 需注册 | 免费100次/天 |
| **小红书** | 爬虫方案 | 免费 | 不稳定、可能被封 | 免费 |

---

## 1️⃣ 微博热搜API

### 方案A：天聚数行API（推荐）⭐

**官网**: https://www.tianapi.com/apiview/100

**特点**：
- ✅ 免费额度：100次/天
- ✅ 稳定可靠
- ✅ 返回数据完整（标题、热度、排名、链接）
- ✅ 实时更新

**申请步骤**：
1. 访问 https://www.tianapi.com/
2. 注册账号（手机号/邮箱）
3. 进入控制台 → API密钥管理
4. 复制你的API Key
5. 订阅"微博热搜榜"接口（免费）

**接口信息**：
```
接口地址: https://apis.tianapi.com/weibo/index
请求方式: GET
请求参数:
  - key: 你的API密钥（必填）
  - num: 返回数量，默认10，最大50
```

**返回示例**：
```json
{
  "code": 200,
  "msg": "success",
  "result": {
    "list": [
      {
        "hotnum": "4521234",      // 热度值
        "hottag": "热",           // 热度标签
        "index": 1,               // 排名
        "title": "话题标题",      // 标题
        "url": "https://..."      // 链接
      }
    ]
  }
}
```

### 方案B：ALAPI（备选）

**官网**: https://www.alapi.cn/api/16/api_document

**特点**：
- 免费额度：100次/天
- 需要注册获取token

---

## 2️⃣ 抖音热搜API

### 方案A：天聚数行API（推荐）⭐

**官网**: https://www.tianapi.com/apiview/155

**特点**：
- ✅ 免费额度：100次/天
- ✅ 包含综合榜、娱乐榜、社会榜等多个榜单
- ✅ 数据完整

**申请步骤**：
1. 同微博API，使用同一个账号
2. 订阅"抖音热搜榜"接口（免费）

**接口信息**：
```
接口地址: https://apis.tianapi.com/douyinhot/index
请求方式: GET
请求参数:
  - key: 你的API密钥（必填）
  - type: 榜单类型（可选）
    - 0: 综合榜（默认）
    - 1: 娱乐榜
    - 2: 社会榜
```

**返回示例**：
```json
{
  "code": 200,
  "msg": "success",
  "result": {
    "list": [
      {
        "index": 1,
        "title": "话题标题",
        "hot": "1234567",        // 热度
        "url": "https://...",
        "mobilUrl": "https://..."
      }
    ]
  }
}
```

### 方案B：抖音开放平台（官方）

**官网**: https://developer.open-douyin.com/

**特点**：
- 官方API，最稳定
- 需要企业认证
- 审核流程较长

**适用场景**：企业用户、商业项目

---

## 3️⃣ 小红书热点API

### 方案A：第三方数据服务

小红书官方API主要面向企业用户，个人开发者可以使用以下方案：

**千瓜数据**（付费）
- 官网: https://www.qian-gua.com/
- 提供小红书热词、热门笔记数据
- 需要付费订阅

### 方案B：爬虫方案（开发使用）

**注意**：仅用于学习和个人项目，商业使用需遵守平台规则。

可以爬取小红书热门话题页面：
- URL: https://www.xiaohongshu.com/explore
- 需要处理反爬机制

---

## 🚀 快速开始

### 步骤1：注册天聚数行API

1. 访问 https://www.tianapi.com/
2. 点击右上角"注册"
3. 填写手机号/邮箱完成注册
4. 登录后进入"控制台"
5. 点击"API密钥管理"，复制你的Key

### 步骤2：订阅免费接口

1. 在天聚数行首页搜索"微博热搜"
2. 点击"免费订阅"
3. 重复以上步骤订阅"抖音热搜"

### 步骤3：配置到项目

将API Key添加到 `.env` 文件：
```env
# 智谱AI API密钥（已有）
ZHIPU_API_KEY=your_zhipu_key

# 天聚数行API密钥（新增）
TIANAPI_KEY=your_tianapi_key
```

---

## 💻 代码实现

我会帮你实现以下功能：

1. **配置管理**：在 `backend/config.py` 添加API配置
2. **API客户端**：创建 `backend/services/api_clients/` 目录
   - `tianapi_client.py` - 天聚数行API客户端
   - `xiaohongshu_scraper.py` - 小红书爬虫（可选）
3. **更新热点抓取服务**：修改 `hot_topic_fetcher.py` 使用真实API

---

## 📊 API限制说明

### 天聚数行免费版限制

| 项目 | 限制 |
|------|------|
| 每日调用次数 | 100次 |
| 并发请求 | 1次/秒 |
| 数据更新频率 | 实时 |
| 返回数量 | 最多50条 |

**建议**：
- 设置缓存，避免频繁调用
- 每1-2小时刷新一次即可
- 如需更高额度，可升级付费版（￥9.9/月起）

---

## 🔐 安全建议

1. **不要将API Key提交到Git**
   - 使用 `.env` 文件存储
   - 确保 `.env` 在 `.gitignore` 中

2. **设置请求频率限制**
   - 避免超出API配额
   - 使用缓存减少请求

3. **错误处理**
   - API调用失败时降级到模拟数据
   - 记录错误日志便于排查

---

## 🎁 其他免费API推荐

如果天聚数行不满足需求，还可以尝试：

1. **聚合数据** - https://www.juhe.cn/
   - 微博热搜API
   - 免费100次/天

2. **APISpace** - https://www.apispace.com/
   - 多平台热搜API
   - 免费额度

3. **免费API大全** - https://www.free-api.com/
   - 收录各种免费API
   - 包含热搜、天气、新闻等

---

## ❓ 常见问题

### Q1: API调用失败怎么办？
A: 检查以下几点：
- API Key是否正确
- 是否超出每日限额
- 网络连接是否正常
- 查看错误信息进行排查

### Q2: 如何提高调用额度？
A: 
- 升级付费版（天聚数行￥9.9/月）
- 使用多个API服务轮换
- 设置合理的缓存策略

### Q3: 小红书为什么没有免费API？
A: 小红书官方API主要面向企业，个人开发者可以：
- 使用付费数据服务（如千瓜数据）
- 自己开发爬虫（仅限学习使用）
- 暂时使用模拟数据

### Q4: 商业项目可以用这些API吗？
A: 
- 天聚数行、ALAPI等第三方服务：可以，但建议升级付费版
- 爬虫方案：不建议，可能违反平台规则
- 官方API：最佳选择，需要企业认证

---

## 📞 技术支持

- **天聚数行客服**: https://www.tianapi.com/console/chat
- **API文档**: https://www.tianapi.com/apiview/100
- **问题反馈**: 在控制台提交工单

---

## 下一步

准备好API Key后，告诉我，我会帮你：
1. ✅ 更新配置文件
2. ✅ 创建API客户端
3. ✅ 修改热点抓取服务
4. ✅ 添加错误处理和缓存
5. ✅ 测试真实API调用

---

**Sources:**
- [微博热搜榜API - 天聚数行](https://www.tianapi.com/apiview/100)
- [抖音热搜榜API - 天聚数行](https://www.tianapi.com/apiview/155)
- [微博热搜榜 - 免费API接口大全](https://www.free-api.com/doc/366)
- [小红书开放平台API文档](https://open.xiaohongshu.com/document/api)
- [抖音开放平台 - 获取实时热点词](https://developer.open-douyin.com/docs/resource/zh-CN/dop/develop/openapi/data-open-service/hot-video-data/get-current-hot-words)
