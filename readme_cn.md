# Publisher 启动模板

此模板是 `Blender Toolchain Hub` 的第一个可运行的 `Publisher Starter`。

## 默认流程

1. 将您的脚本放入 `packages/`。
2. 更新 `publisher.config.json`。
3. 触发 GitHub `Publish` 工作流。

该工作流会为您处理构建、验证、发布资源上传、资源 URL 检查以及 `manifest.json` 的发布。

## 仓库布局

```text
repo-template/
  publisher.config.json
  packages/
  scripts/
    build_repo.py
    validate_manifest.py
    publisher_common.py
  .github/workflows/
    publish.yml
  ci-examples/
    shell-runner/
```

## 配置

`publisher.config.json` 是发布器元数据的唯一真实来源。

- `source` 声明仓库级别的元数据。
- `packages` 声明每个应该发布的包。
- `source_path` 始终是显式的。
  - 对于 `py`，它指向单个 `.py` 文件。
  - 对于 `zip`，它指向将被压缩的目录。

## 本地构建

使用与 CI 工作流相同的命令：

```bash
python scripts/build_repo.py --config publisher.config.json --output-dir dist --artifact-base-url "https://example.com/releases/v1.0.0"
python scripts/validate_manifest.py --manifest dist/manifest.json --artifacts-dir dist/artifacts
```

`build_repo.py` 生成：

- `dist/artifacts/`
- `dist/manifest.json`

`validate_manifest.py` 在您发布任何内容之前，根据本地资源文件重新检查生成的清单。

## GitHub 发布

默认工作流位于 `.github/workflows/publish.yml`。

- 主要路径：`workflow_dispatch`
- 高级路径：匹配 `v*` 的 `push tag`

手动发布需要 `release_tag` 输入。工作流随后：

1. 构建资源和 `manifest.json`
2. 验证生成的输出
3. 将资源上传到 GitHub Releases
4. 验证公共资源 URL
5. 将 `manifest.json` 发布到 GitHub Pages
6. 将最终的 `manifest_url` 写入工作流摘要

最终的 `manifest_url` 格式为：

```text
https://<owner>.github.io/<repo>/manifest.json
```

示例：对于当前仓库 `https://github.com/xuezihe/blender-toolchain-hub-remote`，manifest URL 为：

```text
https://xuezihe.github.io/blender-toolchain-hub-remote/manifest.json
```

## 非 GitHub CI

如果您的团队使用其他 CI 平台，请保持相同的约定：

1. 运行 `build_repo.py`
2. 运行 `validate_manifest.py`
3. 发布资源
4. 验证资源 URL
5. 最后发布 `manifest.json`

请参阅 `ci-examples/shell-runner/` 获取与提供商无关的起点。
