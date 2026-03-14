# 股票池模式指南

本页解决什么：三种股票池模式的差异与适用场景。
本页不解决什么：不展开配置键的权威定义。
适合谁：需要选择股票池模式的人。
读完你会得到什么：模式对比与选型建议。
相关页面：`docs/config.md`、`docs/cli.md`、`docs/playbooks/hk-data-assets.md`

这个文档帮你理解 `auto`、`pit`、`static` 三种股票池模式的区别。

## 三种模式一览

| 模式 | 含义 | 适合场景 |
|------|------|---------|
| `auto` | 自动从 provider 获取当期成分 | 快速研究，不需要严格历史 |
| `pit` | 使用按日期的股票池文件 | 长历史回测，需要严谨的时点信息 |
| `static` | 使用固定股票池文件 | 当期研究，不关心历史变化 |

---

## 什么时候用什么模式

### 用 `static` 的情况

- 第一次跑通，想快速验证流程
- 当期研究，不关心历史成分变化
- `default` 模板默认用这个模式

```yaml
universe:
  mode: static
  symbols:
    - 00700.HK
    - 09988.HK
    # ...
```

### 用 `auto` 的情况

- 需要从 provider 动态获取最新成分
- 不想自己维护股票池文件

```yaml
universe:
  mode: auto
  index_code: 000300.SH  # 如需沪深300成分
```

### 用 `pit` 的情况

- 长历史回测，需要知道"某一天哪个股票在成分内"
- 做严谨的学术研究或回测
- 港股通 PIT 研究

```yaml
universe:
  mode: pit
  by_date_file: artifacts/assets/universe/hk_connect_by_date.csv
```

---

## PIT 股票池文件格式

`by_date_file` 应该是 CSV，格式如下：

```csv
trade_date,ts_code,stock_ticker
2024-01-02,00700.HK,00700
2024-01-02,09988.HK,09988
2024-01-03,00700.HK,00700
2024-01-03,09988.HK,09988
```

---

## 生成 PIT 股票池

### 港股通

```bash
csml universe hk-connect \
  --config configs/presets/universe/hk_connect.yml \
  --mode daily
```

### 指数成分

```bash
csml universe index-components \
  --index-code 000300.SH \
  --month 202501
```

更多用法见 `docs/cli.md` 的「universe」命令部分。

---

## 相关文档

- 配置参数：`docs/config.md`
- 港股通 PIT 资产准备：`docs/playbooks/hk-data-assets.md`
- CLI 命令：`docs/cli.md`
