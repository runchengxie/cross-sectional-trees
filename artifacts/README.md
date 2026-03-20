# Artifacts 目录结构

此目录存放由 CSML 研究流水线产生的数据资产、缓存、运行结果与快照副本。

## Git 跟踪约定

仓库默认只跟踪以下轻量内容：

- 本说明文件
- 六个顶层目录的 `.gitkeep` 骨架
- 少量说明/索引文件，例如 `cache/README.md`、`metadata/dataset_registry.csv`

大体积或高频变化的数据内容默认继续忽略；若确实需要纳入版本控制，应按路径显式放开，而不是整体取消忽略。

## 目录概览

| 目录 | 用途 | 默认管理方式 |
|---|---|---|
| `assets/` | 数据提供商的原始/准原始镜像与派生资产 | 保留目录骨架；实际数据默认忽略，建议单独备份 |
| `cache/` | 运行时缓存 | 保留目录骨架与说明文件；缓存数据默认忽略，可删除重建 |
| `metadata/` | 数据集索引、Universe 元数据、symbol 映射 | 保留目录骨架；轻量索引可跟踪，其余按需处理 |
| `reports/` | 审计/分析导出报表 | 保留目录骨架；报表默认忽略 |
| `runs/` | 实验运行输出 | 保留目录骨架；运行结果默认忽略 |
| `snapshots/` | 打包、备份、副本快照 | 保留目录骨架；快照内容默认忽略 |

## 资产结构

```yaml
assets/
  rqdata/
    hk/
      daily/          # 原始的每日 OHLCV 快照
      pit_financials/ # PIT（Point-in-Time）财务基本面数据
      instruments/    # 交易标的元数据
      financial_details/
  universe/
    hk_connect/       # 按日期划分的港股通成员
```

## 清单与索引

- `assets/rqdata/hk/pit_financials/*/pipeline_fundamentals.manifest.yml`：研究级基本面数据清单
- `cache/README.md`：缓存 schema 与元数据说明
- `metadata/dataset_registry.csv`：仓库内关键数据集索引

## 数据生命周期

1. `assets/`：原始或准原始数据资产
2. `assets/` + 流水线输出：研究级衍生数据
3. `cache/`：按 symbol 组织的运行时缓存
4. `metadata/`：索引与元数据
5. `runs/`：实验结果
6. `snapshots/`：打包或备份副本

## 注意事项

- `artifacts/cache/` 可以安全删除，后续运行会按需重建。
- `artifacts/assets/` 不建议整体放进 Git；更适合外部备份或按需打包上传。
- 查找本地数据资产时，优先参考 `metadata/dataset_registry.csv`。
