# cross-sectional-machine-learning

使用 TuShare / RQData / EODHD 日线数据做截面因子研究、评估和持仓快照。默认文档与模板以港股研究为主，A 股与美股口径主要用于兼容和对照。

## 这项目是干嘛的

低频研究与复现实验的工作流，覆盖研究、评估、回测与持仓快照输出。

## 我能不能跑起来

Python 3.12+，推荐 `uv`。如果你需要 RQData 能力，安装时加 `--extra rqdata`。

```bash
uv venv --seed
uv sync --extra dev --extra rqdata
cp .env.example .env
```

鉴权与 provider 选择见 `docs/providers.md`。

## 最短命令是什么

`csml run --config default`

## 跑完先看哪三个文件

* `summary.json`
* `config.used.yml`
* `positions_current.csv`

## 后续按什么路径读文档

从 [docs/README.md](docs/README.md) 进入。新手直接看 `docs/get-started.md`，常见任务路线看 `docs/cookbook.md`，按对象查细节看 `docs/cli.md` / `docs/config.md` / `docs/outputs.md`。
