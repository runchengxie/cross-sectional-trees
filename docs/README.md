# 文档首页

这套文档按四层组织：

1. 入口：`README.md` 和本页
2. 参考：命令、配置、输出、provider、指标、排障、开发
3. 配方：把常见研究流程串起来
4. 内部资料：规划、范围和预算

如果你是第一次进入仓库，先看根目录 `README.md`。

---

## 我想快速跑一次看看效果

1. 看 `README.md` 的「快速开始」部分
2. 执行 `csml run --config default`
3. 跑完后看这 three 个文件：
   - `summary.json`
   - `config.used.yml`
   - `positions_current.csv`

---

## 我想做正式的港股研究

去 `docs/playbooks/hk-selected.md`，那里有完整的研究流程路线。

---

## 我想了解这个项目能做什么

看 `docs/capabilities.md`。

---

## 我想把某个配置参数改一改

1. 先看 `docs/config.md` 的「常用模板」速查表
2. 找到对应的模板，了解关键配置键
3. 深入理解某个概念（模型选择、PIT 覆盖率等），去看 `docs/concepts/`

---

## 我想把某个命令的参数查清楚

直接去 `docs/cli.md` 找对应的命令段落。

---

## 我的运行出错了

去 `docs/troubleshooting.md` 搜一下错误信息或问题现象。

---

## 我想做一个完整的 HK selected 研究

按这个顺序：

1. `docs/playbooks/README.md` - 选研究路线
2. `docs/playbooks/hk-selected.md` - 按路线走
3. 过程中需要查命令，去 `docs/cli.md`
4. 需要查配置，去 `docs/config.md`

---

## 文档分工

| 文档 | 定位 |
|------|------|
| `README.md` | 项目总览和最短路径 |
| `docs/capabilities.md` | 能力边界、主要入口和产物概览 |
| `docs/cli.md` | CLI 参数速查 |
| `docs/config.md` | 配置键速查 + 常用模板 |
| `docs/outputs.md` | 输出文件和字段约定 |
| `docs/cookbook.md` | 常见任务流程（命令串起来） |
| `docs/playbooks/` | 场景化研究配方 |
| `docs/concepts/` | 概念解释和选择指南 |
| `docs/troubleshooting.md` | 常见问题和排错 |
| `docs/dev.md` | 开发和测试 |
| `docs/internal/` | 内部规划资料（不面向用户） |
