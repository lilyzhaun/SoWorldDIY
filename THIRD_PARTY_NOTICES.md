# 第三方许可证

项目自身使用 MIT；第三方代码保留各自许可证，不因本项目的 MIT 声明而改变。

## 项目图标

`frontend/public/static/images/icon-192.png` 和 `icon-512.png` 由项目作者原创绘制。

## Ant Design Icons

`frontend/src/assets/svgSprite.ts` 的 `icon-history` 包含 Ant Design Icons
`clock-circle` 路径。来源：https://github.com/ant-design/ant-design-icons

MIT LICENSE

Copyright (c) 2018-present Ant UED, https://xtech.antfin.com/

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## npm 与 Python 依赖

可选监控镜像重建 Prometheus 3.15.0（Apache-2.0），保留上游 LICENSE、NOTICE 和 UI
许可证，位于 `/usr/share/licenses/prometheus/` 及其内嵌资源中。来源：
https://github.com/prometheus/prometheus/tree/v3.15.0 。本项目更新其 Go 编译器和
`golang.org/x/net` 依赖；该镜像不是 Prometheus 官方发布的原始二进制。

前端构建使用 `comments.legal` 保留捆绑依赖的版权和许可证注释。
DOMPurify 以 `MPL-2.0 OR Apache-2.0` 双重许可提供，本项目选择 Apache-2.0。
React、React DOM、scheduler 使用 MIT。构建插件复制其完整 LICENSE 文件至
`dist/licenses/`，并分发本文件及项目 LICENSE。

Python 依赖安装包的许可证保留在各自 `.dist-info/licenses` 或包文件中，
镜像同时包含 `/app/LICENSE`、`/app/THIRD_PARTY_NOTICES.md` 和前端许可目录。
